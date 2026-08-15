"""
Build 4D: Deterministic Adjudication.

Computes the correct FinalStatus for an Investigation from its already-
validated EvidenceLedger state. ZERO LLM calls, ZERO network calls --
this is the only bounded component in the 4A-4E chain with no untrusted-
text input at all, since everything it reads was already validated by
the upstream schema/lookup layers (Builds 4A-4C).

DECISION RULE (per the approved Build 4D Closure Audit, Sections D-G):

Per-hypothesis classification:
  SUPPORTED     -- >=1 "corroborated" Verification AND zero unresolved
                   Conflict records on that hypothesis's claim, AND
                   case_scope.validation_result == PASS.
  CONFLICTED    -- >=1 unresolved Conflict record on that hypothesis's
                   claim (overrides SUPPORTED even if a corroborated
                   verification also exists).
  CHECKED_CLEAN -- >=1 real Verification record (any result) but the
                   SUPPORTED conditions above are not met, and zero
                   unresolved Conflict.
  UNCHECKED     -- zero Verification records at all (only
                   MissingEvidence, or nothing processed).

Combination across all hypotheses (worst case wins):
  1. Any hypothesis CONFLICTED                            -> CONFLICTING_EVIDENCE
  2. No CONFLICTED, any hypothesis SUPPORTED               -> SUPPORTED_DISCREPANCY
  3. No CONFLICTED/SUPPORTED, all CHECKED_CLEAN             -> NO_SUPPORTED_DISCREPANCY
  4. Any hypothesis UNCHECKED (none CONFLICTED/SUPPORTED)  -> INSUFFICIENT_EVIDENCE
  5. Zero hypotheses, >=1 fact extracted                    -> NO_SUPPORTED_DISCREPANCY
  6. Zero hypotheses AND zero facts                         -> AdjudicationPreconditionError

This module never calls transition_to() -- per the locked rule, bounded
components do not advance Investigation state; that remains the future
orchestration layer's responsibility. It never touches UserContext,
CaseScope resolution, authority evaluation, or Conflict detection --
it only reads what Builds 4A-4C already produced.
"""

from enum import Enum
from typing import Optional

from .enums import FinalStatus, ValidationResult
from .investigation import Investigation


class AdjudicationPreconditionError(Exception):
    """Raised when an Investigation has nothing to adjudicate at all --
    zero hypotheses AND zero facts. This is 'not ready', not a valid
    basis for any of the four FinalStatus values."""


class _HypothesisClass(Enum):
    SUPPORTED = "supported"
    CONFLICTED = "conflicted"
    CHECKED_CLEAN = "checked_clean"
    UNCHECKED = "unchecked"


def _classify_hypothesis(investigation: Investigation, hypothesis) -> _HypothesisClass:
    verifications = [
        v for v in investigation.ledger.verifications if v.hypothesis_id == hypothesis.id
    ]
    conflicts = [
        c for c in investigation.ledger.conflicts if c.claim_id == hypothesis.claim_id
    ]

    if conflicts:
        return _HypothesisClass.CONFLICTED

    has_corroborated = any(v.corroboration_result == "corroborated" for v in verifications)
    if has_corroborated:
        scope = investigation.case_scope
        scope_established = scope is not None and scope.validation_result == ValidationResult.PASS
        if scope_established:
            return _HypothesisClass.SUPPORTED
        # Corroborated but scope unresolved -- does not qualify as SUPPORTED.
        # A real check genuinely happened, so this is CHECKED_CLEAN, not
        # UNCHECKED.
        return _HypothesisClass.CHECKED_CLEAN

    if verifications:
        return _HypothesisClass.CHECKED_CLEAN

    return _HypothesisClass.UNCHECKED


def compute_final_status(investigation: Investigation) -> FinalStatus:
    if not isinstance(investigation, Investigation):
        raise TypeError(f"Expected Investigation, got {type(investigation).__name__}")

    hypotheses = investigation.ledger.hypotheses

    if not hypotheses:
        if investigation.ledger.facts:
            return FinalStatus.NO_SUPPORTED_DISCREPANCY
        raise AdjudicationPreconditionError(
            "Investigation has zero hypotheses and zero facts -- nothing "
            "has been investigated yet. Adjudication requires at least "
            "some extracted evidence to reach any of the four final "
            "statuses."
        )

    classifications = [_classify_hypothesis(investigation, h) for h in hypotheses]

    if _HypothesisClass.CONFLICTED in classifications:
        return FinalStatus.CONFLICTING_EVIDENCE
    if _HypothesisClass.SUPPORTED in classifications:
        return FinalStatus.SUPPORTED_DISCREPANCY
    if all(c == _HypothesisClass.CHECKED_CLEAN for c in classifications):
        return FinalStatus.NO_SUPPORTED_DISCREPANCY
    return FinalStatus.INSUFFICIENT_EVIDENCE


def adjudicate_investigation(
    investigation: Investigation,
    reason_for_reassessment: Optional[str] = None,
):
    """
    Computes the FinalStatus via compute_final_status(), then hands it to
    the existing, unmodified Investigation.adjudicate(), which itself
    requires state == ADJUDICATED -- a precondition this function does
    not create. Placing the state machine into ADJUDICATED remains the
    future orchestration layer's job, not this bounded component's.
    """
    final_status = compute_final_status(investigation)
    return investigation.adjudicate(final_status, reason_for_reassessment=reason_for_reassessment)
