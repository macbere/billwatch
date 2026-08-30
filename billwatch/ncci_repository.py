"""Read-only, checksum-verified access to imported NCCI PTP data."""

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import sqlite3
from typing import Optional

from .ncci_importer import sha256_file
from .reference_data import is_ncci_billing_code


class NCCIRepositoryError(Exception):
    """The local database cannot be trusted or queried safely."""


@dataclass(frozen=True)
class NCCIRepositoryResult:
    status: str
    column_one: Optional[str] = None
    column_two: Optional[str] = None
    effective_date: Optional[date] = None
    deletion_date: Optional[date] = None
    modifier_indicator: Optional[str] = None
    source_version: Optional[str] = None
    source_file: Optional[str] = None
    source_sha256: Optional[str] = None
    source_url: Optional[str] = None
    retrieval_date: Optional[date] = None
    claim_setting: Optional[str] = None
    program: Optional[str] = None


class SQLiteNCCIRepository:
    """A small read-only wrapper around the generated indexed database."""

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path).resolve()
        self.manifest_path = self.database_path.with_suffix(
            self.database_path.suffix + ".manifest.json"
        )
        if not self.database_path.is_file() or not self.manifest_path.is_file():
            raise NCCIRepositoryError("database and manifest must both exist")
        try:
            self.manifest = json.loads(
                self.manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise NCCIRepositoryError("manifest is unreadable or invalid") from exc
        if self.manifest.get("schema") != "billwatch.ncci.manifest.v1":
            raise NCCIRepositoryError("manifest schema is unsupported")
        expected_hash = str(self.manifest.get("database_sha256", "")).lower()
        actual_hash = sha256_file(self.database_path).lower()
        if len(expected_hash) != 64 or actual_hash != expected_hash:
            raise NCCIRepositoryError("database checksum does not match manifest")
        uri = self.database_path.as_uri() + "?mode=ro"
        try:
            self._connection = sqlite3.connect(uri, uri=True)
            self._connection.execute("PRAGMA query_only=ON")
            self._connection.execute(
                "SELECT column_one, column_two FROM ncci_ptp_edits LIMIT 0"
            )
        except sqlite3.Error as exc:
            raise NCCIRepositoryError("database schema is missing or invalid") from exc

    def close(self) -> None:
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def lookup_pair(
        self,
        code_a: str,
        code_b: str,
        *,
        program: str,
        claim_setting: str,
        service_date: date,
    ) -> NCCIRepositoryResult:
        first = str(code_a or "").strip().upper()
        second = str(code_b or "").strip().upper()
        if not is_ncci_billing_code(first) or not is_ncci_billing_code(second):
            raise ValueError("both codes must use a supported NCCI billing-code shape")
        if first == second:
            raise ValueError("the two codes must differ")
        if program not in {"medicare", "medicaid"}:
            raise ValueError("program must be medicare or medicaid")
        if claim_setting not in {"practitioner", "hospital_outpatient"}:
            raise ValueError(
                "claim_setting must be practitioner or hospital_outpatient"
            )
        if not isinstance(service_date, date):
            raise ValueError("service_date is required for verified NCCI lookup")

        rows = self._connection.execute(
            """
            SELECT
                program, claim_setting, column_one, column_two,
                effective_date, deletion_date, modifier_indicator,
                source_version, source_file, source_sha256, source_url,
                retrieval_date
            FROM ncci_ptp_edits
            WHERE program = ?
              AND claim_setting = ?
              AND (
                    (column_one = ? AND column_two = ?)
                 OR (column_one = ? AND column_two = ?)
              )
            ORDER BY effective_date DESC
            """,
            (program, claim_setting, first, second, second, first),
        ).fetchall()
        if not rows:
            return NCCIRepositoryResult(
                status="not_found", program=program, claim_setting=claim_setting
            )

        for row in rows:
            effective = date.fromisoformat(row[4])
            deletion = date.fromisoformat(row[5]) if row[5] else None
            if effective <= service_date and (
                deletion is None or service_date <= deletion
            ):
                return NCCIRepositoryResult(
                    status="found",
                    program=row[0],
                    claim_setting=row[1],
                    column_one=row[2],
                    column_two=row[3],
                    effective_date=effective,
                    deletion_date=deletion,
                    modifier_indicator=row[6],
                    source_version=row[7],
                    source_file=row[8],
                    source_sha256=row[9],
                    source_url=row[10],
                    retrieval_date=date.fromisoformat(row[11]),
                )
        newest = rows[0]
        return NCCIRepositoryResult(
            status="outside_effective_period",
            program=newest[0],
            claim_setting=newest[1],
            column_one=newest[2],
            column_two=newest[3],
            effective_date=date.fromisoformat(newest[4]),
            deletion_date=date.fromisoformat(newest[5]) if newest[5] else None,
            modifier_indicator=newest[6],
            source_version=newest[7],
            source_file=newest[8],
            source_sha256=newest[9],
            source_url=newest[10],
            retrieval_date=date.fromisoformat(newest[11]),
        )
