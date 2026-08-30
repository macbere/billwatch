from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from billwatch.ncci_importer import (
    NCCIImportError,
    NCCISourceSpec,
    build_ncci_database,
)
from billwatch.ncci_repository import NCCIRepositoryError, SQLiteNCCIRepository


CMS_URL = (
    "https://www.cms.gov/medicare/coding-billing/"
    "national-correct-coding-initiative-ncci-edits/"
    "medicare-ncci-procedure-procedure-ptp-edits"
)


def _source_spec(path: Path, expected=2) -> NCCISourceSpec:
    return NCCISourceSpec(
        path=path,
        source_url=CMS_URL,
        version="v322r0-synthetic-test",
        claim_setting="practitioner",
        expected_record_count=expected,
        retrieval_date=date(2026, 8, 29),
    )


def _write_text_zip(path: Path, rows=None, member_name="fixture.txt") -> None:
    if rows is None:
        rows = [
            "Column 1\tColumn 2\tEffective Date\tDeletion Date\tModifier Indicator",
            "45380\t45378\t20260101\t\t0",
            "G0471\t0591T\t20260101\t20260630\t1",
        ]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member_name, "\n".join(rows) + "\n")


def _write_xlsx_zip(path: Path) -> None:
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rows = [
        ["Column 1", "Column 2", "Effective Date", "Deletion Date", "Modifier Indicator"],
        ["0001A", "G0471", "20260701", "", "0"],
    ]
    xml_rows = []
    for row_number, values in enumerate(rows, start=1):
        cells = []
        for column_number, value in enumerate(values):
            column = chr(ord("A") + column_number)
            cells.append(
                f'<c r="{column}{row_number}" t="inlineStr"><is><t>{value}</t></is></c>'
            )
        xml_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<worksheet xmlns="{namespace}"><sheetData>'
        + "".join(xml_rows)
        + "</sheetData></worksheet>"
    )
    inner_path = path.with_suffix(".xlsx")
    with zipfile.ZipFile(inner_path, "w", compression=zipfile.ZIP_DEFLATED) as book:
        book.writestr("xl/worksheets/sheet1.xml", worksheet)
    try:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as outer:
            outer.write(inner_path, arcname="fixture.xlsx")
    finally:
        inner_path.unlink()


class NCCIImporterTests(unittest.TestCase):
    def test_license_acceptance_is_never_assumed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.zip"
            _write_text_zip(source)
            with self.assertRaises(NCCIImportError):
                build_ncci_database(
                    [_source_spec(source)],
                    root / "ncci.sqlite",
                    license_terms_accepted_by_user=False,
                )

    def test_text_zip_import_is_checksum_verified_and_queryable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.zip"
            database = root / "ncci.sqlite"
            _write_text_zip(source)

            report = build_ncci_database(
                [_source_spec(source)],
                database,
                license_terms_accepted_by_user=True,
            )

            self.assertEqual(report.total_records, 2)
            manifest = json.loads(report.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["total_records"], 2)
            self.assertEqual(len(manifest["database_sha256"]), 64)
            with SQLiteNCCIRepository(database) as repository:
                active = repository.lookup_pair(
                    "45378",
                    "45380",
                    program="medicare",
                    claim_setting="practitioner",
                    service_date=date(2026, 8, 1),
                )
                self.assertEqual(active.status, "found")
                self.assertEqual(active.column_one, "45380")
                self.assertEqual(active.column_two, "45378")
                self.assertEqual(active.modifier_indicator, "0")

                deleted = repository.lookup_pair(
                    "0591T",
                    "G0471",
                    program="medicare",
                    claim_setting="practitioner",
                    service_date=date(2026, 8, 1),
                )
                self.assertEqual(deleted.status, "outside_effective_period")

    def test_xlsx_inside_zip_is_supported_without_third_party_packages(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.zip"
            database = root / "ncci.sqlite"
            _write_xlsx_zip(source)

            report = build_ncci_database(
                [_source_spec(source, expected=1)],
                database,
                license_terms_accepted_by_user=True,
            )
            self.assertEqual(report.total_records, 1)
            with SQLiteNCCIRepository(database) as repository:
                result = repository.lookup_pair(
                    "G0471",
                    "0001A",
                    program="medicare",
                    claim_setting="practitioner",
                    service_date=date(2026, 8, 1),
                )
                self.assertEqual(result.status, "found")
                self.assertEqual(result.column_one, "0001A")

    def test_malformed_row_does_not_publish_partial_database(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "bad.zip"
            database = root / "ncci.sqlite"
            _write_text_zip(
                source,
                rows=[
                    "Column 1\tColumn 2\tEffective Date\tDeletion Date\tModifier Indicator",
                    "45380\tBAD!!\t20260101\t\t0",
                ],
            )
            with self.assertRaises(NCCIImportError):
                build_ncci_database(
                    [_source_spec(source, expected=1)],
                    database,
                    license_terms_accepted_by_user=True,
                )
            self.assertFalse(database.exists())
            self.assertFalse(
                database.with_suffix(".sqlite.manifest.json").exists()
            )

    def test_record_count_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.zip"
            database = root / "ncci.sqlite"
            _write_text_zip(source)
            with self.assertRaisesRegex(NCCIImportError, "expected 999"):
                build_ncci_database(
                    [_source_spec(source, expected=999)],
                    database,
                    license_terms_accepted_by_user=True,
                )
            self.assertFalse(database.exists())

    def test_unsafe_archive_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "unsafe.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("../escape.txt", "not allowed")
            with self.assertRaisesRegex(NCCIImportError, "unsafe archive member"):
                build_ncci_database(
                    [_source_spec(source, expected=1)],
                    root / "ncci.sqlite",
                    license_terms_accepted_by_user=True,
                )

    def test_tampered_database_is_rejected_by_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.zip"
            database = root / "ncci.sqlite"
            _write_text_zip(source)
            build_ncci_database(
                [_source_spec(source)],
                database,
                license_terms_accepted_by_user=True,
            )
            with database.open("ab") as handle:
                handle.write(b"tampered")
            with self.assertRaisesRegex(NCCIRepositoryError, "checksum"):
                SQLiteNCCIRepository(database)


if __name__ == "__main__":
    unittest.main()
