"""
Build 4E: Conditional Appeal Generation.

Generates a transient, human-review-only appeal draft, but ONLY when
Gate 3 (state_machine.py, unmodified since Build 1) confirms
final_status == SUPPORTED_DISCREPANCY. This is the first bounded
component where LLM output becomes user-facing prose rather than a
structured field for deterministic code to interpret -- the safety
model compensates by keeping the LLM's role limited to drafting text
that cites ONLY facts/claims already proven to exist in the ledger,
with the whole candidate rejected (never repaired) if it cites
anything that isn't real.

APPEAL DRAFTS ARE TRANSIENT: no AppealDraft entity is added to
EvidenceLedger, and evidence.py is not modified by this build, per
explicit instruction. This function returns a plain result object;
persistence (if ever wanted) is a future, separately-authorized
decision.

This module never determines final_status, never modifies
adjudication, never reinterprets evidence, never determines authority
strength, never advances the state machine, and never sends or submits
anything externally -- it only drafts text for a human to review.

DESIGN NOTE: identifying which specific hypothesis is "the supported
one" is done here with a small, self-contained helper that mirrors
(does not import) adjudication_integration.py's classification rule --
that file is outside this build's authorized file scope to modify or
import private helpers from.
"""

from dataclasses import dataclass
from typing import Optional

from .enums import ValidationResult
from .investigation import Investigation
from .llm_provider import LLMProvider, LLMProviderError
from .llm_schemas import SchemaValidationError, parse_appeal_draft_candidate


class AppealIntegrationError(Exception):
    """Raised for integration-layer misuse -- e.g. calling this with
    something other than a real Investigation."""


@dataclass(frozen=True)
class AppealDraftResult:
    success: bool
    investigation_id: str
    hypothesis_id: Optional[str] = None
    draft_text: Optional[str] = None
    cited_fact_ids: tuple = ()
    cited_claim_ids: tuple = ()
    failure_stage: Optional[str] = None   # None | "not_eligible" | "provider" | "validation"
    failure_reason: Optional[str] = None


def _find_supported_hypothesis(investigation: Investigation):
    """Mirrors adjudication_integration.py's SUPPORTED classification
    rule for a single hypothesis (duplicated here deliberately, not
    imported -- see module docstring). Returns the first hypothesis
    meeting the criteria, in ledger order, or None if none qualify."""
    scope = investigation.case_scope
    scope_established = scope is not None and scope.validation_result == ValidationResult.PASS
    if not scope_established:
        return None
    for hyp in investigation.ledger.hypotheses:
        conflicts = [c for c in investigation.ledger.conflicts if c.claim_id == hyp.claim_id]
        if conflicts:
            continue
        verifications = [v for v in investigation.ledger.verifications if v.hypothesis_id == hyp.id]
        if any(v.corroboration_result == "corroborated" for v in verifications):
            return hyp
    return None


_SYSTEM_PROMPT = (
    "You are an appeal-drafting component for a medical bill investigation "
    "that has ALREADY been deterministically adjudicated as containing a "
    "supported billing discrepancy. You will be given one specific claim, "
    "its explanation, and the exact facts that support it. Draft a clear, "
    "professional appeal letter body citing ONLY the facts and claim given "
    "to you.\n"
    "\n"
    "Respond with JSON matching exactly this shape:\n"
    '{"draft_text": "<the appeal letter body text>", '
    '"cited_fact_ids": ["<only real fact_ids given to you>"], '
    '"cited_claim_ids": ["<only the real claim_id given to you>"]}\n'
    "\n"
    "Rules:\n"
    "- Only cite fact_ids and the claim_id actually given to you. Never "
    "invent an identifier.\n"
    "- Never invent, paraphrase, or reproduce any AMA CPT procedure code "
    "descriptor text -- reference codes only by the bare code number as "
    "given, never by an invented description of what a code means.\n"
    "- The adjudication has already been made deterministically. Do NOT "
    "restate, second-guess, or attach your own confidence about the "
    "verdict. Do NOT include any field other than draft_text, "
    "cited_fact_ids, and cited_claim_ids. In particular, never include "
    "final_status, recommended_status, adjudication, authority_decision, "
    "authority, authority_level, authority_result, appeal_eligible, "
    "confidence, verdict, or case_scope -- including any such field will "
    "cause your entire output to be discarded.\n"
    "- This letter is a DRAFT for human review only. Do not claim it has "
    "been or will be sent anywhere.\n"
    "- Return ONLY the JSON object. No prose, no markdown fences."
)


def _build_user_content(investigation: Investigation, hypothesis) -> str:
    claim = next((c for c in investigation.ledger.claims if c.id == hypothesis.claim_id), None)
    claim_text = claim.statement if claim else "(claim not found)"
    lines = [
        f"claim_id: {hypothesis.claim_id}",
        f"claim: {claim_text}",
        f"hypothesis_explanation: {hypothesis.explanation_text}",
        "supporting facts:",
    ]
    facts_by_id = {f.id: f for f in investigation.ledger.facts}
    for fid in hypothesis.referenced_fact_ids:
        fact = facts_by_id.get(fid)
        if fact is not None:
            lines.append(f"- fact_id={fact.id} | type={fact.fact_type} | value={fact.value!r}")
    return "\n".join(lines)


def generate_appeal_draft(investigation: Investigation, provider: LLMProvider) -> AppealDraftResult:
    if not isinstance(investigation, Investigation):
        raise AppealIntegrationError(
            f"Expected Investigation, got {type(investigation).__name__}"
        )

    # Gate 3 first, before any LLM call.
    if not investigation.can_draft_appeal():
        return AppealDraftResult(
            success=False, investigation_id=investigation.investigation_id,
            failure_stage="not_eligible",
            failure_reason=(
                "Gate 3: appeal drafting requires state == ADJUDICATED and "
                "final_status == SUPPORTED_DISCREPANCY."
            ),
        )
    # Prove the gate structurally (defense in depth, consistent with the
    # pattern used throughout this project) -- this call never mutates
    # state, only validates and returns True or raises.
    investigation.request_draft_appeal()

    hypothesis = _find_supported_hypothesis(investigation)
    if hypothesis is None:
        return AppealDraftResult(
            success=False, investigation_id=investigation.investigation_id,
            failure_stage="not_eligible",
            failure_reason=(
                "No hypothesis meets the SUPPORTED classification despite "
                "final_status == SUPPORTED_DISCREPANCY; refusing to draft "
                "without a traceable basis."
            ),
        )

    known_fact_ids = {f.id for f in investigation.ledger.facts}
    known_claim_ids = {c.id for c in investigation.ledger.claims}

    try:
        raw_text = provider.complete_json(_SYSTEM_PROMPT, _build_user_content(investigation, hypothesis))
    except LLMProviderError as exc:
        return AppealDraftResult(
            success=False, investigation_id=investigation.investigation_id,
            hypothesis_id=hypothesis.id, failure_stage="provider", failure_reason=str(exc),
        )

    try:
        candidate = parse_appeal_draft_candidate(
            raw_text, known_fact_ids=known_fact_ids, known_claim_ids=known_claim_ids
        )
    except SchemaValidationError as exc:
        return AppealDraftResult(
            success=False, investigation_id=investigation.investigation_id,
            hypothesis_id=hypothesis.id, failure_stage="validation", failure_reason=str(exc),
        )

    return AppealDraftResult(
        success=True,
        investigation_id=investigation.investigation_id,
        hypothesis_id=hypothesis.id,
        draft_text=candidate.draft_text,
        cited_fact_ids=candidate.cited_fact_ids,
        cited_claim_ids=candidate.cited_claim_ids,
    )
