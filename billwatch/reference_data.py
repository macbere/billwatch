"""
Reference Data Store (Build 3).

Deterministic, fail-closed, versioned reference-data lookup for HCPCS
Level II, ICD-10-CM, and CMS NCCI PTP code-pair relationships.

NO LLM calls. NO network calls at runtime. NO live CMS API dependency.
Every lookup is a pure function over a validated, immutable, versioned
local snapshot.

CRITICAL BOUNDARY: this module NEVER stores, loads, or invents AMA CPT
descriptor text. Bare CPT code numbers may only ever come from a user's
own uploaded documents (handled elsewhere, not here). lookup_cpt_descriptor()
exists specifically to prove -- structurally, not just by omission -- that
a request for CPT descriptor meaning always returns UNAVAILABLE rather than
approximated content.

A successful lookup here is NEVER, by itself, an authority decision. Every
lookup result must still be converted to a Source and passed through Build
2's evaluate_source_authority() -- see to_source() below and the "does not
bypass authority" tests in tests/test_reference_data.py.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional
import re
import uuid

from .authority import APPROVED_LICENSE_BASES

# Phase C1: PLAN_POLICY reference data is a controlled, author-written demo
# fixture -- explicitly NOT public CMS/NCHS data -- so it must never be
# validated against APPROVED_LICENSE_BASES (which is specifically the
# allowlist for reused public federal reference data). This constant is a
# deliberately narrow, single-purpose allowlist used ONLY by
# validate_plan_policy_record(), and does not modify authority.py's shared
# APPROVED_LICENSE_BASES in any way.
PLAN_POLICY_LICENSE_BASIS = "controlled_demo_fixture_synthetic"
_PLAN_POLICY_APPROVED_LICENSE_BASES = frozenset({PLAN_POLICY_LICENSE_BASIS})
from .enums import SourceType
from .evidence import Source


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# -- code format rules (deterministic, no LLM) --------------------------
_HCPCS_CODE_RE = re.compile(r"^[A-V][0-9]{4}$")      # HCPCS Level II shape
_ICD10_CODE_RE = re.compile(r"^[A-TV-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$")
_NCCI_BILLING_CODE_RE = re.compile(
    r"^(?:[0-9]{5}|[A-V][0-9]{4}|[0-9]{4}[A-Z])$"
)


def is_ncci_billing_code(value: str) -> bool:
    """Return True only for code shapes present in CMS NCCI pair files."""
    return bool(_NCCI_BILLING_CODE_RE.fullmatch(str(value or "").upper()))


class LookupStatus(Enum):
    FOUND = "found"
    UNKNOWN = "unknown"
    OUTSIDE_EFFECTIVE_PERIOD = "outside_effective_period"
    NO_VALID_SOURCE = "no_valid_source"
    UNAVAILABLE = "unavailable"  # used specifically for the CPT boundary


class ReferenceDataError(Exception):
    """Raised for snapshot-level (not per-record) rejection reasons --
    e.g. reusing an existing version number, or missing snapshot-level
    provenance entirely."""


@dataclass(frozen=True)
class ValidationRejection:
    record_ref: str
    reason: str


# -- record types ---------------------------------------------------------

@dataclass(frozen=True)
class HCPCSRecord:
    code: str
    description: Optional[str]          # None if not legitimately available
    description_verified: bool          # False = not yet checked against a
                                         # live official file this session
    source: str
    source_url: str
    effective_date: date
    version: str
    retrieval_date: date
    license_basis: str
    scope: str = "universal"
    id: str = field(default_factory=_new_id)


@dataclass(frozen=True)
class ICD10Record:
    code: str
    description: Optional[str]
    description_verified: bool
    source: str
    source_url: str
    effective_date: date
    version: str
    retrieval_date: date
    license_basis: str
    scope: str = "universal"
    id: str = field(default_factory=_new_id)


@dataclass(frozen=True)
class NCCIPairRecord:
    code_a: str  # Column One
    code_b: str  # Column Two (bundled component, per CMS PTP terminology)
    relationship: str            # e.g. "column2_bundled_into_column1"
    modifier_indicator: str      # CMS's own modifier-indicator code ("0"/"1"/"9")
    relationship_verified: bool  # False = not yet checked against the live file
    source: str
    source_url: str
    effective_date: date
    version: str
    retrieval_date: date
    license_basis: str
    scope: str = "medicare_ncci_edit_set"
    claim_setting: str = "practitioner"
    deletion_date: Optional[date] = None
    source_file: Optional[str] = None
    source_sha256: Optional[str] = None
    id: str = field(default_factory=_new_id)


@dataclass(frozen=True)
class PlanPolicyRecord:
    """
    Phase C1: a single plan-specific policy rule. Deliberately distinct
    from HCPCSRecord/ICD10Record/NCCIPairRecord -- this represents a
    SINGLE PLAN's own stated policy, not a public/universal code
    reference. rule_text MUST carry an explicit "[DEMO FIXTURE" marker
    (enforced by validate_plan_policy_record(), not just documented) so
    it can never be mistaken for real, unmarked insurer policy text.
    """
    plan_id: str
    policy_id: str
    rule_type: str            # "coverage_rule" | "bundling_methodology_adoption" | "exclusion_rule"
    rule_text: str             # short, synthetic, author-written; must contain the demo marker
    applicable_codes: tuple    # code numbers this rule concerns; may be empty
    patient_cost_share_cents: Optional[int]
    source: str
    source_url: str
    effective_date: date
    version: str
    retrieval_date: date
    license_basis: str
    scope: str = "single_plan"
    id: str = field(default_factory=_new_id)


@dataclass(frozen=True)
class ReferenceSnapshot:
    dataset_name: str            # "hcpcs" | "icd10cm" | "ncci_ptp"
    version: str
    records: tuple
    source: str
    source_url: str
    effective_date: date
    retrieval_date: date
    license_basis: str
    created_at: datetime = field(default_factory=_now)
    id: str = field(default_factory=_new_id)


@dataclass(frozen=True)
class LookupResult:
    status: LookupStatus
    record: Optional[object]
    queried: str
    rationale: str
    id: str = field(default_factory=_new_id)
    evaluated_at: datetime = field(default_factory=_now)


# -- validation (fail-closed) --------------------------------------------

def _validate_common_provenance(ref: str, source, source_url, effective_date,
                                 version, retrieval_date, license_basis,
                                 allowed_license_bases=None) -> list:
    """allowed_license_bases defaults to the shared public-data allowlist
    (authority.APPROVED_LICENSE_BASES) for backward compatibility with the
    three original datasets (hcpcs/icd10cm/ncci_ptp). PLAN_POLICY (added in
    Phase C1) is NOT public CMS/NCHS data and passes its own, distinct,
    much narrower allowlist so it can never be validated as if it were
    officially-licensed public reference data."""
    if allowed_license_bases is None:
        allowed_license_bases = APPROVED_LICENSE_BASES
    issues = []
    if not source or not str(source).strip():
        issues.append(f"{ref}: missing source")
    if not source_url or not str(source_url).strip():
        issues.append(f"{ref}: missing source_url")
    if not isinstance(effective_date, date):
        issues.append(f"{ref}: missing/invalid effective_date")
    if not version or not str(version).strip():
        issues.append(f"{ref}: missing version")
    if not isinstance(retrieval_date, date):
        issues.append(f"{ref}: missing/invalid retrieval_date")
    if license_basis not in allowed_license_bases:
        issues.append(
            f"{ref}: unapproved or missing license_basis={license_basis!r} "
            f"(must be one of {sorted(allowed_license_bases)})"
        )
    return issues


def validate_hcpcs_record(rec: HCPCSRecord) -> list:
    ref = f"HCPCS:{rec.code}"
    issues = _validate_common_provenance(
        ref, rec.source, rec.source_url, rec.effective_date, rec.version,
        rec.retrieval_date, rec.license_basis,
    )
    if not _HCPCS_CODE_RE.match(rec.code or ""):
        issues.append(f"{ref}: malformed HCPCS code format")
    if rec.description is not None and not rec.description.strip():
        issues.append(f"{ref}: description present but empty -- use None, not ''")
    return issues


def validate_icd10_record(rec: ICD10Record) -> list:
    ref = f"ICD10:{rec.code}"
    issues = _validate_common_provenance(
        ref, rec.source, rec.source_url, rec.effective_date, rec.version,
        rec.retrieval_date, rec.license_basis,
    )
    if not _ICD10_CODE_RE.match(rec.code or ""):
        issues.append(f"{ref}: malformed ICD-10-CM code format")
    if rec.description is not None and not rec.description.strip():
        issues.append(f"{ref}: description present but empty -- use None, not ''")
    return issues


def validate_ncci_pair_record(rec: NCCIPairRecord) -> list:
    ref = f"NCCI:{rec.code_a}/{rec.code_b}"
    issues = _validate_common_provenance(
        ref, rec.source, rec.source_url, rec.effective_date, rec.version,
        rec.retrieval_date, rec.license_basis,
    )
    if not is_ncci_billing_code(rec.code_a):
        issues.append(f"{ref}: malformed code_a")
    if not is_ncci_billing_code(rec.code_b):
        issues.append(f"{ref}: malformed code_b")
    if rec.code_a == rec.code_b:
        issues.append(f"{ref}: code_a and code_b must differ")
    if rec.relationship not in {"column2_bundled_into_column1", "mutually_exclusive", "no_edit"}:
        issues.append(f"{ref}: unrecognized relationship value {rec.relationship!r}")
    if rec.modifier_indicator not in {"0", "1", "9"}:
        issues.append(f"{ref}: unrecognized modifier_indicator {rec.modifier_indicator!r}")
    if rec.claim_setting not in {"practitioner", "hospital_outpatient"}:
        issues.append(f"{ref}: unrecognized claim_setting {rec.claim_setting!r}")
    if rec.deletion_date is not None:
        if not isinstance(rec.deletion_date, date):
            issues.append(f"{ref}: invalid deletion_date")
        elif isinstance(rec.effective_date, date) and rec.deletion_date < rec.effective_date:
            issues.append(f"{ref}: deletion_date precedes effective_date")
    if rec.relationship_verified:
        if not rec.source_file or not rec.source_file.strip():
            issues.append(f"{ref}: verified relationship requires source_file")
        if not re.fullmatch(r"[0-9A-Fa-f]{64}", rec.source_sha256 or ""):
            issues.append(f"{ref}: verified relationship requires a SHA-256 source hash")
    return issues


_PLAN_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{2,31}$")
_POLICY_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{2,31}$")
_VALID_PLAN_POLICY_RULE_TYPES = frozenset({
    "coverage_rule", "bundling_methodology_adoption", "exclusion_rule",
})
_PLAN_POLICY_DEMO_MARKER = "[DEMO FIXTURE"


def validate_plan_policy_record(rec: "PlanPolicyRecord") -> list:
    ref = f"PLAN_POLICY:{rec.plan_id}:{rec.policy_id}"
    issues = _validate_common_provenance(
        ref, rec.source, rec.source_url, rec.effective_date, rec.version,
        rec.retrieval_date, rec.license_basis,
        allowed_license_bases=_PLAN_POLICY_APPROVED_LICENSE_BASES,
    )
    if not _PLAN_ID_RE.match(rec.plan_id or ""):
        issues.append(f"{ref}: malformed plan_id")
    if not _POLICY_ID_RE.match(rec.policy_id or ""):
        issues.append(f"{ref}: malformed policy_id")
    if rec.rule_type not in _VALID_PLAN_POLICY_RULE_TYPES:
        issues.append(
            f"{ref}: unrecognized rule_type {rec.rule_type!r}; must be one "
            f"of {sorted(_VALID_PLAN_POLICY_RULE_TYPES)}"
        )
    if not rec.rule_text or not rec.rule_text.strip():
        issues.append(f"{ref}: rule_text must be a non-empty string")
    elif _PLAN_POLICY_DEMO_MARKER not in rec.rule_text:
        issues.append(
            f"{ref}: rule_text must carry the explicit demo-fixture marker "
            f"{_PLAN_POLICY_DEMO_MARKER!r} -- synthetic policy fixtures "
            "must never be presented as unmarked, potentially-real "
            "insurer policy text"
        )
    if not isinstance(rec.applicable_codes, tuple) or not all(
        isinstance(c, str) for c in rec.applicable_codes
    ):
        issues.append(f"{ref}: applicable_codes must be a tuple of strings")
    if rec.patient_cost_share_cents is not None:
        if (
            isinstance(rec.patient_cost_share_cents, bool)
            or not isinstance(rec.patient_cost_share_cents, int)
            or rec.patient_cost_share_cents < 0
        ):
            issues.append(
                f"{ref}: patient_cost_share_cents must be None or a "
                "non-negative integer number of cents"
            )
    return issues


_VALIDATORS = {
    "hcpcs": validate_hcpcs_record,
    "icd10cm": validate_icd10_record,
    "ncci_ptp": validate_ncci_pair_record,
    "plan_policy": validate_plan_policy_record,
}

# Snapshot-level provenance is dataset-specific. The original public
# reference datasets continue to use exactly APPROVED_LICENSE_BASES.
# PLAN_POLICY demo fixtures are deliberately isolated from that federal
# public-data allowlist.
_DATASET_APPROVED_LICENSE_BASES = {
    "hcpcs": APPROVED_LICENSE_BASES,
    "icd10cm": APPROVED_LICENSE_BASES,
    "ncci_ptp": APPROVED_LICENSE_BASES,
    "plan_policy": _PLAN_POLICY_APPROVED_LICENSE_BASES,
}


# -- the store --------------------------------------------------------------

class ReferenceStore:
    """
    Append-only, versioned, immutable reference-data store. A dataset name
    (e.g. "hcpcs") maps to an ordered list of ReferenceSnapshot objects --
    exactly parallel to Investigation's append-only Adjudication history
    (Build 1). Loading a new version never edits or removes a prior one.
    """

    def __init__(self):
        self._snapshots: dict = {}          # dataset_name -> [ReferenceSnapshot, ...]
        self._current_version: dict = {}    # dataset_name -> version string

    def load_snapshot(
        self,
        dataset_name: str,
        records: list,
        source: str,
        source_url: str,
        effective_date: date,
        retrieval_date: date,
        version: str,
        license_basis: str,
    ):
        """
        Fail-closed loader. Returns (snapshot_or_None, rejections).
        A record that fails validation is EXCLUDED and reported -- never
        silently repaired or guessed into a valid shape. If snapshot-level
        provenance itself is invalid (missing source/license/version), the
        entire load is rejected and raises ReferenceDataError.
        """
        if dataset_name not in _VALIDATORS:
            raise ReferenceDataError(f"Unknown dataset_name: {dataset_name!r}")

        snapshot_level_issues = _validate_common_provenance(
            f"snapshot:{dataset_name}:{version}", source, source_url,
            effective_date, version, retrieval_date, license_basis,
            allowed_license_bases=_DATASET_APPROVED_LICENSE_BASES[dataset_name],
        )
        if snapshot_level_issues:
            raise ReferenceDataError(
                f"Snapshot rejected -- missing/invalid provenance: {snapshot_level_issues}"
            )

        existing_versions = {s.version for s in self._snapshots.get(dataset_name, [])}
        if version in existing_versions:
            raise ReferenceDataError(
                f"Version {version!r} already exists for dataset {dataset_name!r}. "
                "Reference snapshots are immutable -- load a new version instead "
                "of overwriting an existing one."
            )

        validator = _VALIDATORS[dataset_name]
        accepted = []
        rejections = []
        seen_keys = set()
        for rec in records:
            issues = validator(rec)

            # Duplicate identity is dataset-specific and fail-closed.
            # Preserve the original keys for all pre-C1 datasets.
            if dataset_name in {"hcpcs", "icd10cm"}:
                key = rec.code
            elif dataset_name == "ncci_ptp":
                key = (rec.code_a, rec.code_b)
            elif dataset_name == "plan_policy":
                key = (rec.plan_id, rec.policy_id)
            else:
                # Defensive branch: dataset_name has already been validated
                # above, so reaching this point indicates an internal bug.
                raise ReferenceDataError(
                    f"No duplicate-key policy exists for dataset {dataset_name!r}"
                )
            if key in seen_keys:
                issues = issues + [f"duplicate record for key={key!r} within this snapshot"]
            if issues:
                rejections.append(ValidationRejection(record_ref=str(key), reason="; ".join(issues)))
                continue
            seen_keys.add(key)
            accepted.append(rec)

        if not accepted:
            # A snapshot with zero valid records is not a usable snapshot.
            raise ReferenceDataError(
                f"Snapshot for {dataset_name!r} version {version!r} rejected: "
                f"no valid records survived validation. Rejections: {rejections}"
            )

        snapshot = ReferenceSnapshot(
            dataset_name=dataset_name,
            version=version,
            records=tuple(accepted),
            source=source,
            source_url=source_url,
            effective_date=effective_date,
            retrieval_date=retrieval_date,
            license_basis=license_basis,
        )
        self._snapshots.setdefault(dataset_name, []).append(snapshot)
        self._current_version[dataset_name] = version
        return snapshot, rejections

    def get_current_snapshot(self, dataset_name: str) -> Optional[ReferenceSnapshot]:
        version = self._current_version.get(dataset_name)
        if version is None:
            return None
        for s in self._snapshots.get(dataset_name, []):
            if s.version == version:
                return s
        return None

    def get_snapshot_version(self, dataset_name: str, version: str) -> Optional[ReferenceSnapshot]:
        for s in self._snapshots.get(dataset_name, []):
            if s.version == version:
                return s
        return None

    def all_versions(self, dataset_name: str) -> tuple:
        return tuple(s.version for s in self._snapshots.get(dataset_name, []))

    # -- lookups (deterministic, no LLM, no network) ------------------------

    def _lookup(self, dataset_name: str, matcher, queried_label: str, as_of: Optional[date]) -> LookupResult:
        snapshot = self.get_current_snapshot(dataset_name)
        if snapshot is None:
            return LookupResult(
                status=LookupStatus.NO_VALID_SOURCE, record=None, queried=queried_label,
                rationale=f"No validated reference snapshot has been loaded for {dataset_name!r}.",
            )
        for rec in snapshot.records:
            if matcher(rec):
                if as_of is not None and rec.effective_date > as_of:
                    return LookupResult(
                        status=LookupStatus.OUTSIDE_EFFECTIVE_PERIOD, record=rec, queried=queried_label,
                        rationale=(
                            f"Record found but its effective_date ({rec.effective_date}) is "
                            f"after the queried as_of date ({as_of}); not automatically applicable."
                        ),
                    )
                deletion_date = getattr(rec, "deletion_date", None)
                if as_of is not None and deletion_date is not None and as_of > deletion_date:
                    return LookupResult(
                        status=LookupStatus.OUTSIDE_EFFECTIVE_PERIOD,
                        record=rec,
                        queried=queried_label,
                        rationale=(
                            f"Record found but its deletion_date ({deletion_date}) is "
                            f"before the queried as_of date ({as_of}); the edit is not active."
                        ),
                    )
                return LookupResult(
                    status=LookupStatus.FOUND, record=rec, queried=queried_label,
                    rationale="Matched a validated record in the current reference snapshot.",
                )
        return LookupResult(
            status=LookupStatus.UNKNOWN, record=None, queried=queried_label,
            rationale=f"{queried_label!r} was not found in the current {dataset_name!r} snapshot. "
                      "No description is guessed for unknown codes.",
        )

    def lookup_hcpcs(self, code: str, as_of: Optional[date] = None) -> LookupResult:
        return self._lookup("hcpcs", lambda r: r.code == code, code, as_of)

    def lookup_icd10(self, code: str, as_of: Optional[date] = None) -> LookupResult:
        return self._lookup("icd10cm", lambda r: r.code == code, code, as_of)

    def lookup_ncci_pair(self, code_a: str, code_b: str, as_of: Optional[date] = None) -> LookupResult:
        label = f"{code_a}/{code_b}"

        def matcher(r):
            return {r.code_a, r.code_b} == {code_a, code_b}

        return self._lookup("ncci_ptp", matcher, label, as_of)

    def lookup_plan_policy(self, plan_id: str, as_of: Optional[date] = None) -> LookupResult:
        return self._lookup("plan_policy", lambda r: r.plan_id == plan_id, plan_id, as_of)

    # -- the CPT boundary, enforced structurally -----------------------------
    def lookup_cpt_descriptor(self, code: str) -> LookupResult:
        """
        ALWAYS returns UNAVAILABLE, regardless of the store's contents or
        the code queried. This function deliberately never consults any
        snapshot at all -- there is no code path by which a CPT descriptor
        could be returned here, because BillWatch never stores one
        (Correction 1 / the Critical Boundary of this build).
        """
        return LookupResult(
            status=LookupStatus.UNAVAILABLE,
            record=None,
            queried=code,
            rationale=(
                "BillWatch does not possess a licensed source for CPT "
                "descriptor text and will not approximate or invent one. "
                "Bare CPT code numbers are only ever used as they appear "
                "in the user's own uploaded documents; this system routes "
                "to insufficient evidence rather than guessing descriptor "
                "meaning."
            ),
        )

    # -- conversion to Build 2's evidence model (never decides authority) ---
    def to_source(self, lookup_result: LookupResult) -> Optional[Source]:
        """
        Converts a FOUND lookup into a Source suitable for
        authority.evaluate_source_authority(). Returns None for any other
        status -- callers must handle UNKNOWN/OUTSIDE_EFFECTIVE_PERIOD/
        NO_VALID_SOURCE/UNAVAILABLE themselves (typically by routing to
        INSUFFICIENT_EVIDENCE upstream). This function NEVER assigns an
        authority level itself -- that decision still belongs entirely to
        Build 2's evaluate_source_authority().
        """
        if lookup_result.status != LookupStatus.FOUND:
            return None
        rec = lookup_result.record
        if isinstance(rec, PlanPolicyRecord):
            return Source(
                source_type=SourceType.PLAN_POLICY,
                reference=f"{rec.policy_id} ({rec.rule_type}): {rec.rule_text}",
                scope=rec.scope,
                license_usage_basis=rec.license_basis,
                retrieved_at=datetime.combine(rec.retrieval_date, datetime.min.time(), tzinfo=timezone.utc),
            )
        if isinstance(rec, NCCIPairRecord):
            return Source(
                source_type=SourceType.CMS_NCCI,
                reference=f"NCCI PTP edit {rec.code_a}/{rec.code_b}: {rec.relationship} "
                          f"(modifier indicator {rec.modifier_indicator})",
                scope=rec.scope,
                license_usage_basis=rec.license_basis,
                retrieved_at=datetime.combine(rec.retrieval_date, datetime.min.time(), tzinfo=timezone.utc),
            )
        # HCPCS / ICD10 -> CODE_DEFINITION
        code = getattr(rec, "code", None)
        desc = rec.description if rec.description_verified else None
        return Source(
            source_type=SourceType.CODE_DEFINITION,
            reference=f"{code}: {desc}" if desc else f"{code} (description not verified this session)",
            scope=rec.scope,
            license_usage_basis=rec.license_basis,
            retrieved_at=datetime.combine(rec.retrieval_date, datetime.min.time(), tzinfo=timezone.utc),
        )
