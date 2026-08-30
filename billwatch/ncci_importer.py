"""Fail-closed CMS NCCI PTP importer.

This module never downloads data and never accepts license terms. It converts
files that the user has already obtained under the applicable CMS/AMA terms
into a compact, indexed SQLite database. Runtime analysis uses the generated
database offline.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import tempfile
from typing import Iterable, Iterator, Optional
import xml.etree.ElementTree as ET
import zipfile

from .reference_data import is_ncci_billing_code


PARSER_VERSION = "billwatch-ncci-importer-v1"
CMS_PTP_SOURCE_PAGE = (
    "https://www.cms.gov/medicare/coding-billing/"
    "national-correct-coding-initiative-ncci-edits/"
    "medicare-ncci-procedure-procedure-ptp-edits"
)
_ALLOWED_SETTINGS = frozenset({"practitioner", "hospital_outpatient"})
_ALLOWED_PROGRAMS = frozenset({"medicare", "medicaid"})
_ALLOWED_DATA_SUFFIXES = frozenset({".txt", ".tsv", ".csv", ".xlsx"})
_MAX_ARCHIVE_MEMBERS = 50
_MAX_MEMBER_BYTES = 750_000_000
_MAX_TOTAL_BYTES = 1_500_000_000
_XML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


class NCCIImportError(Exception):
    """The source or one of its rows failed closed validation."""


@dataclass(frozen=True)
class NCCISourceSpec:
    path: Path
    source_url: str
    version: str
    claim_setting: str
    expected_record_count: int
    program: str = "medicare"
    retrieval_date: date = field(default_factory=date.today)


@dataclass(frozen=True)
class NCCIImportReport:
    database_path: Path
    manifest_path: Path
    total_records: int
    sources: tuple


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_source_spec(spec: NCCISourceSpec) -> None:
    if not Path(spec.path).is_file():
        raise NCCIImportError(f"source file does not exist: {spec.path}")
    if spec.claim_setting not in _ALLOWED_SETTINGS:
        raise NCCIImportError(f"unsupported claim setting: {spec.claim_setting!r}")
    if spec.program not in _ALLOWED_PROGRAMS:
        raise NCCIImportError(f"unsupported program: {spec.program!r}")
    if not spec.source_url.startswith("https://www.cms.gov/"):
        raise NCCIImportError("source_url must be an official https://www.cms.gov/ URL")
    if not spec.version.strip() or "illustrative" in spec.version.lower():
        raise NCCIImportError("a non-illustrative source version is required")
    if (
        isinstance(spec.expected_record_count, bool)
        or not isinstance(spec.expected_record_count, int)
        or spec.expected_record_count <= 0
    ):
        raise NCCIImportError("expected_record_count must be a positive integer")
    if not isinstance(spec.retrieval_date, date):
        raise NCCIImportError("retrieval_date must be a date")


def _safe_archive_members(archive: zipfile.ZipFile) -> list:
    members = archive.infolist()
    if not members or len(members) > _MAX_ARCHIVE_MEMBERS:
        raise NCCIImportError("archive has an invalid number of members")
    total_size = 0
    candidates = []
    for info in members:
        path = PurePosixPath(info.filename.replace("\\", "/"))
        if (
            path.is_absolute()
            or ".." in path.parts
            or ":" in path.parts[0]
            or info.is_dir()
        ):
            if info.is_dir():
                continue
            raise NCCIImportError(f"unsafe archive member: {info.filename!r}")
        total_size += info.file_size
        if info.file_size > _MAX_MEMBER_BYTES or total_size > _MAX_TOTAL_BYTES:
            raise NCCIImportError("archive exceeds the uncompressed safety limit")
        if path.suffix.lower() in _ALLOWED_DATA_SUFFIXES:
            candidates.append(info)
    if not candidates:
        raise NCCIImportError("archive contains no supported NCCI data file")
    # CMS Medicaid archives can contain equivalent TXT and XLSX copies.
    # Import exactly one representation to avoid duplicate records.
    priority = {".txt": 0, ".tsv": 1, ".csv": 2, ".xlsx": 3}
    candidates.sort(
        key=lambda item: (
            priority[PurePosixPath(item.filename).suffix.lower()],
            item.filename.lower(),
        )
    )
    selected_suffix = PurePosixPath(candidates[0].filename).suffix.lower()
    same_kind = [
        item
        for item in candidates
        if PurePosixPath(item.filename).suffix.lower() == selected_suffix
    ]
    if len(same_kind) != 1:
        raise NCCIImportError(
            "archive contains multiple same-format data files; import each CMS part separately"
        )
    return same_kind


def _normalize_header(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


_HEADER_ALIASES = {
    "column_one": {"column1", "columnone", "col1"},
    "column_two": {"column2", "columntwo", "col2"},
    "effective_date": {"effectivedate", "effdate", "effdt"},
    "deletion_date": {"deletiondate", "deldate", "deldt", "terminationdate"},
    "modifier_indicator": {
        "modifierindicator",
        "modindicator",
        "modind",
        "correctcodingmodifierindicator",
        "ccmi",
    },
}


def _header_map(row: list) -> Optional[dict]:
    normalized = [_normalize_header(value) for value in row]
    mapping = {}
    for field_name, aliases in _HEADER_ALIASES.items():
        for index, value in enumerate(normalized):
            if value in aliases or any(value.startswith(alias) for alias in aliases):
                mapping[field_name] = index
                break
    return mapping if set(mapping) == set(_HEADER_ALIASES) else None


def _parse_date(value, *, required: bool) -> Optional[date]:
    text = str(value or "").strip()
    if not text or text == "*":
        if required:
            raise NCCIImportError("required date is blank")
        return None
    if text.endswith(".0"):
        text = text[:-2]
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    if text.isdigit() and 20_000 <= int(text) <= 80_000:
        return date(1899, 12, 30) + timedelta(days=int(text))
    raise NCCIImportError(f"invalid date value: {value!r}")


def _row_value(row: list, mapping: dict, field_name: str):
    index = mapping[field_name]
    return row[index] if index < len(row) else ""


def _validated_record(row: list, mapping: dict, source_name: str, row_number: int) -> tuple:
    column_one = str(_row_value(row, mapping, "column_one") or "").strip().upper()
    column_two = str(_row_value(row, mapping, "column_two") or "").strip().upper()
    if not column_one and not column_two:
        raise NCCIImportError(f"{source_name} row {row_number}: blank record")
    if not is_ncci_billing_code(column_one):
        raise NCCIImportError(
            f"{source_name} row {row_number}: invalid Column 1 code {column_one!r}"
        )
    if not is_ncci_billing_code(column_two):
        raise NCCIImportError(
            f"{source_name} row {row_number}: invalid Column 2 code {column_two!r}"
        )
    if column_one == column_two:
        raise NCCIImportError(f"{source_name} row {row_number}: identical code pair")
    try:
        effective_date = _parse_date(
            _row_value(row, mapping, "effective_date"), required=True
        )
        deletion_date = _parse_date(
            _row_value(row, mapping, "deletion_date"), required=False
        )
    except NCCIImportError as exc:
        raise NCCIImportError(f"{source_name} row {row_number}: {exc}") from exc
    if deletion_date is not None and deletion_date < effective_date:
        raise NCCIImportError(
            f"{source_name} row {row_number}: deletion date precedes effective date"
        )
    modifier = str(_row_value(row, mapping, "modifier_indicator") or "").strip()
    if modifier.endswith(".0"):
        modifier = modifier[:-2]
    if modifier not in {"0", "1", "9"}:
        raise NCCIImportError(
            f"{source_name} row {row_number}: invalid modifier indicator {modifier!r}"
        )
    return column_one, column_two, effective_date, deletion_date, modifier


def _iter_tabular_rows(rows: Iterable[list], source_name: str) -> Iterator[tuple]:
    mapping = None
    for row_number, row in enumerate(rows, start=1):
        if mapping is None:
            mapping = _header_map(row)
            continue
        if not any(str(value or "").strip() for value in row):
            continue
        yield _validated_record(row, mapping, source_name, row_number)
    if mapping is None:
        raise NCCIImportError(f"{source_name}: required NCCI header row was not found")


def _text_rows(data: bytes) -> Iterator[list]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    sample = "\n".join(text.splitlines()[:20])
    delimiter = "\t" if sample.count("\t") >= sample.count(",") else ","
    yield from csv.reader(io.StringIO(text), delimiter=delimiter)


def _column_index(cell_reference: str) -> int:
    letters = re.match(r"([A-Z]+)", cell_reference or "")
    if not letters:
        raise NCCIImportError(f"invalid XLSX cell reference: {cell_reference!r}")
    value = 0
    for char in letters.group(1):
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value - 1


def _shared_strings(workbook: zipfile.ZipFile) -> list:
    try:
        handle = workbook.open("xl/sharedStrings.xml")
    except KeyError:
        return []
    values = []
    with handle:
        for event, element in ET.iterparse(handle, events=("end",)):
            if element.tag == _XML_NS + "si":
                values.append(
                    "".join(node.text or "" for node in element.iter(_XML_NS + "t"))
                )
                element.clear()
    return values


def _xlsx_rows(data: bytes) -> Iterator[list]:
    try:
        workbook = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise NCCIImportError("invalid XLSX container") from exc
    with workbook:
        shared = _shared_strings(workbook)
        worksheets = sorted(
            name
            for name in workbook.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        if not worksheets:
            raise NCCIImportError("XLSX has no worksheet")
        with workbook.open(worksheets[0]) as sheet:
            for event, row_element in ET.iterparse(sheet, events=("end",)):
                if row_element.tag != _XML_NS + "row":
                    continue
                values = {}
                for cell in row_element.findall(_XML_NS + "c"):
                    index = _column_index(cell.attrib.get("r", ""))
                    cell_type = cell.attrib.get("t")
                    if cell_type == "inlineStr":
                        value = "".join(
                            node.text or "" for node in cell.iter(_XML_NS + "t")
                        )
                    else:
                        value_node = cell.find(_XML_NS + "v")
                        value = value_node.text if value_node is not None else ""
                        if cell_type == "s" and value:
                            try:
                                value = shared[int(value)]
                            except (IndexError, ValueError) as exc:
                                raise NCCIImportError(
                                    "XLSX contains an invalid shared-string reference"
                                ) from exc
                    values[index] = value
                if values:
                    last = max(values)
                    yield [values.get(index, "") for index in range(last + 1)]
                else:
                    yield []
                row_element.clear()


def _source_rows(path: Path) -> Iterator[tuple]:
    suffix = path.suffix.lower()
    if suffix == ".zip":
        try:
            archive = zipfile.ZipFile(path)
        except zipfile.BadZipFile as exc:
            raise NCCIImportError(f"invalid ZIP archive: {path.name}") from exc
        with archive:
            selected = _safe_archive_members(archive)
            info = selected[0]
            data = archive.read(info)
            member_suffix = PurePosixPath(info.filename).suffix.lower()
            rows = _xlsx_rows(data) if member_suffix == ".xlsx" else _text_rows(data)
            yield from _iter_tabular_rows(rows, info.filename)
        return
    if suffix not in _ALLOWED_DATA_SUFFIXES:
        raise NCCIImportError(f"unsupported source file type: {suffix}")
    data = path.read_bytes()
    rows = _xlsx_rows(data) if suffix == ".xlsx" else _text_rows(data)
    yield from _iter_tabular_rows(rows, path.name)


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=DELETE;
        PRAGMA synchronous=FULL;
        CREATE TABLE ncci_ptp_edits (
            program TEXT NOT NULL,
            claim_setting TEXT NOT NULL,
            column_one TEXT NOT NULL,
            column_two TEXT NOT NULL,
            effective_date TEXT NOT NULL,
            deletion_date TEXT,
            modifier_indicator TEXT NOT NULL,
            source_version TEXT NOT NULL,
            source_file TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            source_url TEXT NOT NULL,
            retrieval_date TEXT NOT NULL,
            relationship_verified INTEGER NOT NULL CHECK (relationship_verified = 1),
            UNIQUE (
                program, claim_setting, column_one, column_two,
                effective_date, deletion_date
            )
        );
        CREATE INDEX idx_ncci_pair_forward
            ON ncci_ptp_edits(program, claim_setting, column_one, column_two);
        CREATE INDEX idx_ncci_pair_reverse
            ON ncci_ptp_edits(program, claim_setting, column_two, column_one);
        CREATE INDEX idx_ncci_active_dates
            ON ncci_ptp_edits(effective_date, deletion_date);
        """
    )


def build_ncci_database(
    sources: Iterable[NCCISourceSpec],
    database_path: Path,
    *,
    license_terms_accepted_by_user: bool,
) -> NCCIImportReport:
    """Build and atomically publish a verified local SQLite snapshot."""
    if license_terms_accepted_by_user is not True:
        raise NCCIImportError(
            "the user must personally accept the applicable CMS/AMA license terms"
        )
    source_specs = tuple(sources)
    if not source_specs:
        raise NCCIImportError("at least one source file is required")
    for spec in source_specs:
        _validate_source_spec(spec)

    destination = Path(database_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = destination.with_suffix(destination.suffix + ".manifest.json")
    temp_db_handle = tempfile.NamedTemporaryFile(
        prefix=destination.name + ".", suffix=".tmp", dir=destination.parent, delete=False
    )
    temp_db_path = Path(temp_db_handle.name)
    temp_db_handle.close()
    source_manifest = []
    total_records = 0
    try:
        connection = sqlite3.connect(temp_db_path)
        try:
            _create_schema(connection)
            insert_sql = """
                INSERT INTO ncci_ptp_edits (
                    program, claim_setting, column_one, column_two,
                    effective_date, deletion_date, modifier_indicator,
                    source_version, source_file, source_sha256, source_url,
                    retrieval_date, relationship_verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """
            for spec in source_specs:
                source_hash = sha256_file(spec.path)
                source_count = 0
                try:
                    for record in _source_rows(Path(spec.path)):
                        column_one, column_two, effective, deletion, modifier = record
                        connection.execute(
                            insert_sql,
                            (
                                spec.program,
                                spec.claim_setting,
                                column_one,
                                column_two,
                                effective.isoformat(),
                                deletion.isoformat() if deletion else None,
                                modifier,
                                spec.version,
                                Path(spec.path).name,
                                source_hash,
                                spec.source_url,
                                spec.retrieval_date.isoformat(),
                            ),
                        )
                        source_count += 1
                except sqlite3.IntegrityError as exc:
                    raise NCCIImportError(
                        f"{Path(spec.path).name}: duplicate or invalid database record"
                    ) from exc
                if source_count != spec.expected_record_count:
                    raise NCCIImportError(
                        f"{Path(spec.path).name}: expected {spec.expected_record_count} "
                        f"records but parsed {source_count}"
                    )
                total_records += source_count
                source_manifest.append(
                    {
                        "program": spec.program,
                        "claim_setting": spec.claim_setting,
                        "source_file": Path(spec.path).name,
                        "source_sha256": source_hash,
                        "source_url": spec.source_url,
                        "version": spec.version,
                        "retrieval_date": spec.retrieval_date.isoformat(),
                        "record_count": source_count,
                    }
                )
            connection.commit()
        finally:
            connection.close()

        database_hash = sha256_file(temp_db_path)
        manifest = {
            "schema": "billwatch.ncci.manifest.v1",
            "parser_version": PARSER_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database_file": destination.name,
            "database_sha256": database_hash,
            "total_records": total_records,
            "license_notice": "CMS/AMA End User Point and Click Agreement applies",
            "redistribution_included": False,
            "sources": source_manifest,
        }
        manifest_fd, manifest_name = tempfile.mkstemp(
            prefix=manifest_path.name + ".",
            suffix=".tmp",
            dir=manifest_path.parent,
        )
        os.close(manifest_fd)
        temp_manifest = Path(manifest_name)
        try:
            temp_manifest.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temp_db_path, destination)
            os.replace(temp_manifest, manifest_path)
        finally:
            if temp_manifest.exists():
                temp_manifest.unlink()
    except Exception:
        if temp_db_path.exists():
            temp_db_path.unlink()
        raise

    return NCCIImportReport(
        database_path=destination,
        manifest_path=manifest_path,
        total_records=total_records,
        sources=tuple(source_manifest),
    )
