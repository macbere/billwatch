"""
Source Authority Engine (Build 2).

SOURCE + SCOPE + CLAIM CONTEXT -> DETERMINISTIC AUTHORITY DECISION

This module contains NO LLM calls, NO external API calls, and NO network
dependency of any kind. Every function here is a pure function of its
inputs -- same inputs always produce the same AuthorityDecision, which is
the "reproducible" requirement from Phase 3.3A/Phase 4 Section 4.

Authority is deliberately CONTEXTUAL, not a single global ranking: the same
SourceType can resolve to different AuthorityResult values depending on
case_scope and claim_type. This is the direct implementation of the
"CMS/NCCI must not be globally authoritative" correction from Phase 3.2.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid

from .enums import SourceType, CaseScopeValue, ValidationResult
from .case_scope import CaseScope
from .evidence import Source
from .user_context import UserContext


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Reference-data license bases approved by Phase 3.3A Correction 1. No
# actual reference data is imported in Build 2 (Section 9) -- this allowlist
# is only the deterministic RULE that Build 3's loader must enforce.
APPROVED_LICENSE_BASES = frozenset({
    "public_domain_cms",       # HCPCS Level II
    "public_domain_nchs",      # ICD-10-CM
    "public_cms_ncci",         # CMS NCCI edit pairs (code numbers only)
})


class ClaimType(Enum):
    """What kind of question is being asked of a source. Authority is
    evaluated per (source_type, case_scope, claim_type) triple, never from
    source_type alone."""
    CODING_BUNDLING = "coding_bundling"
    COVERAGE_TERMS = "coverage_terms"
    COST_SHARING = "cost_sharing"
    PLAN_METHODOLOGY_ADOPTION = "plan_methodology_adoption"
    ADJUDICATION_RECORD = "adjudication_record"
    DEFINITIONAL = "definitional"
    JURISDICTIONAL_REGULATORY = "jurisdictional_regulatory"
    GENERIC = "generic"


class AuthorityResult(Enum):
    AUTHORITATIVE = "authoritative"
    ADMISSIBLE = "admissible"
    CORROBORATING = "corroborating"
    OUT_OF_SCOPE = "out_of_scope"
    INSUFFICIENT_SCOPE = "insufficient_scope"
    INAPPLICABLE = "inapplicable"
    CONFLICTING = "conflicting"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class AuthorityDecision:
    """Full provenance for a single authority evaluation -- reproducible
    from (source, case_scope, claim_type, ncci_adoption_evidence) alone."""
    source_id: str
    source_type: SourceType
    case_scope_value: CaseScopeValue
    case_scope_validation: ValidationResult
    source_scope: Optional[str]
    claim_type: ClaimType
    rule_applied: str
    result: AuthorityResult
    rationale: str
    id: str = field(default_factory=_new_id)
    evaluated_at: datetime = field(default_factory=_now)


class AuthorityEngineError(TypeError):
    """Raised when the engine is called with an invalid input type --
    in particular, when something other than a real Source/CaseScope is
    handed in where evidence is required."""


def _decision(
    source: Source,
    case_scope: CaseScope,
    claim_type: ClaimType,
    rule: str,
    result: AuthorityResult,
    rationale: str,
) -> AuthorityDecision:
    return AuthorityDecision(
        source_id=source.id,
        source_type=source.source_type,
        case_scope_value=case_scope.value,
        case_scope_validation=case_scope.validation_result,
        source_scope=source.scope,
        claim_type=claim_type,
        rule_applied=rule,
        result=result,
        rationale=rationale,
    )


def evaluate_source_authority(
    source: Source,
    case_scope: CaseScope,
    claim_type: ClaimType,
    ncci_adoption_evidence: Optional[Source] = None,
) -> AuthorityDecision:
    """
    The central deterministic authority decision function.

    ncci_adoption_evidence, if supplied, MUST itself be a real PLAN_POLICY
    Source (never a UserContext, never a bare boolean/string) -- this keeps
    "the plan adopted NCCI methodology" an evidence-backed claim with its
    own provenance, not a flag someone could set from an unverified guess.
    """
    # -- Gate 2, re-enforced at this layer (defense in depth) -----------
    if isinstance(source, UserContext):
        raise AuthorityEngineError(
            "UserContext cannot be evaluated as an evidence source. "
            "A user's stated belief (e.g. \"I know they overcharged me\") "
            "is not evidence and must never enter the authority pipeline."
        )
    if not isinstance(source, Source):
        raise AuthorityEngineError(f"Expected Source, got {type(source).__name__}")
    if not isinstance(case_scope, CaseScope):
        raise AuthorityEngineError(f"Expected CaseScope, got {type(case_scope).__name__}")
    if not isinstance(claim_type, ClaimType):
        raise AuthorityEngineError(f"Expected ClaimType, got {type(claim_type).__name__}")
    if ncci_adoption_evidence is not None:
        if isinstance(ncci_adoption_evidence, UserContext):
            raise AuthorityEngineError(
                "UserContext cannot serve as NCCI-adoption evidence -- a "
                "user's assertion that their plan adopted NCCI methodology "
                "is not itself proof of adoption."
            )
        if not isinstance(ncci_adoption_evidence, Source) or (
            ncci_adoption_evidence.source_type != SourceType.PLAN_POLICY
        ):
            raise AuthorityEngineError(
                "ncci_adoption_evidence must be a Source of type PLAN_POLICY."
            )

    scope_established = case_scope.validation_result == ValidationResult.PASS

    # -- PLAN_POLICY -------------------------------------------------------
    if source.source_type == SourceType.PLAN_POLICY:
        return _decision(
            source, case_scope, claim_type, "plan_policy.self_scoped",
            AuthorityResult.AUTHORITATIVE,
            "A plan's own policy document is authoritative for claims about "
            "that specific plan's own terms, independent of whether "
            "Medicare/Medicaid/private case-scope has been established "
            "elsewhere.",
        )

    # -- EOB -----------------------------------------------------------
    if source.source_type == SourceType.EOB:
        if claim_type == ClaimType.ADJUDICATION_RECORD:
            return _decision(
                source, case_scope, claim_type, "eob.adjudication_record",
                AuthorityResult.AUTHORITATIVE,
                "An EOB is authoritative as a record of what the insurer "
                "actually decided on this claim.",
            )
        return _decision(
            source, case_scope, claim_type, "eob.not_proof_of_correctness",
            AuthorityResult.ADMISSIBLE,
            "An EOB is admissible evidence of the insurer's stated position "
            "but is not, by itself, proof that the position is correct.",
        )

    # -- CMS_MEDICARE ----------------------------------------------------
    if source.source_type == SourceType.CMS_MEDICARE:
        if not scope_established:
            return _decision(
                source, case_scope, claim_type, "cms_medicare.scope_unresolved",
                AuthorityResult.INSUFFICIENT_SCOPE,
                "Case scope is not established; CMS Medicare policy "
                "applicability cannot be determined without guessing.",
            )
        if case_scope.value in (CaseScopeValue.MEDICARE, CaseScopeValue.MEDICAID):
            return _decision(
                source, case_scope, claim_type, "cms_medicare.in_scope",
                AuthorityResult.AUTHORITATIVE,
                "CMS Medicare/Medicaid coverage policy is authoritative "
                "within confirmed Medicare/Medicaid scope.",
            )
        return _decision(
            source, case_scope, claim_type, "cms_medicare.private_out_of_scope",
            AuthorityResult.OUT_OF_SCOPE,
            "CMS Medicare coverage determinations do not apply to a "
            "confirmed private-commercial case.",
        )

    # -- CMS_NCCI (the scope-conditional rule this build exists to prove) --
    if source.source_type == SourceType.CMS_NCCI:
        if not scope_established:
            # Scenario D -- unknown scope. Do not guess.
            return _decision(
                source, case_scope, claim_type, "cms_ncci.scope_unresolved",
                AuthorityResult.INSUFFICIENT_SCOPE,
                "Case scope is not established; NCCI applicability cannot "
                "be determined without guessing (Scenario D).",
            )
        if case_scope.value in (CaseScopeValue.MEDICARE, CaseScopeValue.MEDICAID):
            # Scenario A.
            return _decision(
                source, case_scope, claim_type, "cms_ncci.medicare_scope",
                AuthorityResult.AUTHORITATIVE,
                "NCCI methodology is authoritative within confirmed "
                "Medicare/Medicaid scope (Scenario A).",
            )
        # Private-commercial, scope established.
        if ncci_adoption_evidence is not None:
            # Scenario C.
            return _decision(
                source, case_scope, claim_type,
                "cms_ncci.private_with_adoption_evidence",
                AuthorityResult.AUTHORITATIVE,
                "Explicit plan-policy evidence confirms NCCI methodology "
                "adoption for this private plan; NCCI is authoritative "
                "within that demonstrated scope (Scenario C).",
            )
        # Scenario B -- the exact overreach Phase 3.2 corrected.
        return _decision(
            source, case_scope, claim_type,
            "cms_ncci.private_no_adoption_evidence",
            AuthorityResult.CORROBORATING,
            "Private-plan scope with no evidence of NCCI adoption: NCCI "
            "must not silently control the conclusion; it is corroborating "
            "only (Scenario B).",
        )

    # -- CODE_DEFINITION (HCPCS/ICD-10-CM/NCCI code numbers only) ---------
    if source.source_type == SourceType.CODE_DEFINITION:
        if source.license_usage_basis not in APPROVED_LICENSE_BASES:
            return _decision(
                source, case_scope, claim_type,
                "code_definition.unlicensed_rejected",
                AuthorityResult.UNAVAILABLE,
                "Reference content without an approved public/appropriate "
                "license basis is not usable (Phase 3.3A Correction 1). No "
                "unlicensed AMA CPT descriptor content is ever admitted "
                "here.",
            )
        return _decision(
            source, case_scope, claim_type, "code_definition.public_universal",
            AuthorityResult.AUTHORITATIVE,
            "Approved public code-definition/reference data is payer-"
            "agnostic and universally applicable regardless of case scope.",
        )

    # -- PUBLIC_REGULATORY -------------------------------------------------
    if source.source_type == SourceType.PUBLIC_REGULATORY:
        if source.scope is None:
            return _decision(
                source, case_scope, claim_type, "public_regulatory.scope_unknown",
                AuthorityResult.INSUFFICIENT_SCOPE,
                "Jurisdictional scope of this regulatory source is not "
                "established.",
            )
        # Full jurisdiction-matching logic against the patient's actual
        # jurisdiction is deferred to a later build (needs real reference
        # data, per Section 9); until then this source is admissible
        # context but never treated as automatically authoritative.
        return _decision(
            source, case_scope, claim_type,
            "public_regulatory.jurisdiction_check_deferred",
            AuthorityResult.ADMISSIBLE,
            "Jurisdiction-matching against the patient's confirmed "
            "jurisdiction is not yet implemented (deferred to a build with "
            "real reference data); treated as admissible, not automatically "
            "authoritative, in the meantime.",
        )

    # -- PROVIDER_BILL_LABEL ----------------------------------------------
    if source.source_type == SourceType.PROVIDER_BILL_LABEL:
        return _decision(
            source, case_scope, claim_type, "provider_bill_label.never_authoritative",
            AuthorityResult.ADMISSIBLE,
            "A provider's plain-English bill label is contextual only and "
            "is never authoritative on its own.",
        )

    # -- LLM_INTERPRETATION -------------------------------------------------
    if source.source_type == SourceType.LLM_INTERPRETATION:
        return _decision(
            source, case_scope, claim_type,
            "llm_interpretation.not_an_evidence_source",
            AuthorityResult.UNAVAILABLE,
            "An LLM's own interpretation is a reasoning layer, not an "
            "evidence source, and can never be cited as authority for a "
            "claim.",
        )

    return _decision(
        source, case_scope, claim_type, "unrecognized_source_type",
        AuthorityResult.UNAVAILABLE,
        "Unrecognized source type; no authority rule applies.",
    )


# ---------------------------------------------------------------------
# Section 8 -- conflict preparation (detection only, no resolution).
# ---------------------------------------------------------------------

_USABLE_FOR_CONFLICT = frozenset({AuthorityResult.AUTHORITATIVE, AuthorityResult.CORROBORATING})


@dataclass(frozen=True)
class PotentialConflict:
    """
    Represents "two sources are both usable for the same claim and neither
    automatically overrides the other." Build 2 deliberately does NOT
    decide which one is right -- that is the future Conflict Engine's job.
    This type exists purely so that fact can be represented and passed
    forward without being silently collapsed into a single answer.
    """
    claim_type: ClaimType
    decision_a: AuthorityDecision
    decision_b: AuthorityDecision
    id: str = field(default_factory=_new_id)
    detected_at: datetime = field(default_factory=_now)


def flag_potential_conflict(
    decision_a: AuthorityDecision, decision_b: AuthorityDecision
) -> Optional[PotentialConflict]:
    """
    Returns a PotentialConflict when two decisions are both usable
    (AUTHORITATIVE or CORROBORATING) for the same claim_type and come from
    different sources. Returns None otherwise. This function NEVER picks a
    winner and NEVER returns a resolved AuthorityResult -- resolving actual
    semantic disagreement between two sources' content is out of scope for
    Build 2 (Section 8) and belongs to the future Conflict Engine.
    """
    if decision_a.claim_type != decision_b.claim_type:
        return None
    if decision_a.source_id == decision_b.source_id:
        return None
    if decision_a.result in _USABLE_FOR_CONFLICT and decision_b.result in _USABLE_FOR_CONFLICT:
        return PotentialConflict(
            claim_type=decision_a.claim_type,
            decision_a=decision_a,
            decision_b=decision_b,
        )
    return None
