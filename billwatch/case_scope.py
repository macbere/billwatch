"""
CaseScope (Build 1, Section 3 / Phase 3.3A Correction 2).

case_scope must NEVER be silently guessed. It is only ever established two
ways:
  (1) an explicit, structured user selection, or
  (2) a source field that passes a DETERMINISTIC format/vocabulary check.

An LLM's own semantic interpretation, however confident-sounding, can never
by itself produce a controlling (validation_result == PASS) CaseScope. This
module has no dependency on any LLM/model call at all -- it is pure,
deterministic Python, directly testable with plain fixture strings.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .enums import CaseScopeValue, ScopeProvenance, ValidationResult


def _now() -> datetime:
    return datetime.now(timezone.utc)


# A simplified Medicare-Beneficiary-Identifier-shaped pattern, used only to
# demonstrate deterministic format validation -- NOT a claim of full MBI
# specification compliance. Real production validation would use the
# official CMS MBI format rules.
_MEDICARE_ID_PATTERN = re.compile(r"^[1-9][A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{4}$")

_KNOWN_PLAN_TYPE_VOCAB = {
    "medicare": CaseScopeValue.MEDICARE,
    "medicaid": CaseScopeValue.MEDICAID,
    "private": CaseScopeValue.PRIVATE_COMMERCIAL,
    "private_commercial": CaseScopeValue.PRIVATE_COMMERCIAL,
    "commercial": CaseScopeValue.PRIVATE_COMMERCIAL,
    "ppo": CaseScopeValue.PRIVATE_COMMERCIAL,
    "hmo": CaseScopeValue.PRIVATE_COMMERCIAL,
}


@dataclass(frozen=True)
class CaseScope:
    value: CaseScopeValue
    provenance: ScopeProvenance
    source_identifier: str
    validation_result: ValidationResult
    timestamp: datetime = field(default_factory=_now)


def _unknown(source_identifier: str, provenance: ScopeProvenance = ScopeProvenance.NONE) -> CaseScope:
    return CaseScope(
        value=CaseScopeValue.UNKNOWN,
        provenance=provenance,
        source_identifier=source_identifier,
        validation_result=ValidationResult.FAIL,
    )


def establish_from_user_selection(selection: str, source_identifier: str = "intake_form") -> CaseScope:
    """Option A -- explicit structured user selection."""
    key = (selection or "").strip().lower()
    if key not in _KNOWN_PLAN_TYPE_VOCAB:
        return _unknown(source_identifier)
    return CaseScope(
        value=_KNOWN_PLAN_TYPE_VOCAB[key],
        provenance=ScopeProvenance.USER_SELECTED,
        source_identifier=source_identifier,
        validation_result=ValidationResult.PASS,
    )


def establish_from_validated_field(candidate_text: str, source_identifier: str) -> CaseScope:
    """
    Option B -- an authoritative plan/EOB field that passes DETERMINISTIC
    validation (regex/vocabulary match). The LLM may have located this
    candidate text during extraction, but this function -- not the model --
    decides whether it actually qualifies.
    """
    text = (candidate_text or "").strip()
    if _MEDICARE_ID_PATTERN.match(text):
        return CaseScope(
            value=CaseScopeValue.MEDICARE,
            provenance=ScopeProvenance.VALIDATED_EOB_FIELD,
            source_identifier=source_identifier,
            validation_result=ValidationResult.PASS,
        )
    lowered = text.lower()
    if lowered in _KNOWN_PLAN_TYPE_VOCAB:
        return CaseScope(
            value=_KNOWN_PLAN_TYPE_VOCAB[lowered],
            provenance=ScopeProvenance.VALIDATED_EOB_FIELD,
            source_identifier=source_identifier,
            validation_result=ValidationResult.PASS,
        )
    return _unknown(source_identifier)


def reject_llm_inference_as_scope(source_identifier: str = "llm_inference_rejected") -> CaseScope:
    """
    Explicitly demonstrates that LLM-only inference is ALWAYS rejected as a
    basis for controlling case_scope, regardless of the guess's content or
    confidence. Any code path that tries to use a bare LLM guess for scope
    must route through here and will always receive FAIL/UNKNOWN back.
    """
    return _unknown(source_identifier, provenance=ScopeProvenance.LLM_INFERENCE)


def resolve_case_scope(
    user_selection: str = None,
    validated_candidate: str = None,
    llm_inferred_guess: str = None,
    source_identifier: str = "unknown",
) -> CaseScope:
    """
    Deterministic resolution order:
      1. Explicit user selection -- if valid, and it's the only signal
         (or it agrees with a validated field), it establishes scope.
      2. A deterministically validated field -- if valid, and it's the
         only signal, it establishes scope.
      3. If BOTH (1) and (2) are present and PASS but disagree, this is a
         genuine scope conflict -- scope is NOT established (routes to
         INSUFFICIENT_EVIDENCE upstream, per Phase 3.3A Test B Case 5).
      4. LLM-only inference NEVER establishes scope (Case 4) -- included
         explicitly so the rejection is visible and tested, not merely
         assumed.
      5. Nothing usable supplied -- UNKNOWN/FAIL (Case 6).
    """
    user_result = (
        establish_from_user_selection(user_selection, source_identifier)
        if user_selection is not None else None
    )
    field_result = (
        establish_from_validated_field(validated_candidate, source_identifier)
        if validated_candidate is not None else None
    )

    user_pass = user_result is not None and user_result.validation_result == ValidationResult.PASS
    field_pass = field_result is not None and field_result.validation_result == ValidationResult.PASS

    if user_pass and field_pass:
        if user_result.value == field_result.value:
            return user_result
        # Conflicting scope indicators -- do NOT silently prefer either one.
        return _unknown(source_identifier)

    if user_pass:
        return user_result
    if field_pass:
        return field_result

    if llm_inferred_guess is not None:
        return reject_llm_inference_as_scope(source_identifier)

    return _unknown(source_identifier)
