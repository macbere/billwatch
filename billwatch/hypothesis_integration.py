"""
Build 4B: Hypothesis Engine / Hypothesis Orchestrator.

Bounded component: given already-accepted facts in an Investigation's
EvidenceLedger, asks the LLM to propose ONE structured hypothesis,
treats that output as UNTRUSTED, validates it through the existing,
unmodified llm_schemas.parse_hypothesis_candidate(), and -- only if
valid -- records it as a real Hypothesis via the existing, unmodified
EvidenceLedger.

FINDING FROM INSPECTION (not in the original conceptual flow diagram,
but required by the actual, already-tested Build 1 data model):
evidence.py's Hypothesis dataclass requires claim_id -- a reference to
a real Claim's id, not raw text. HypothesisCandidate only carries
claim_statement (text). This module therefore first constructs a real
Claim via the existing, unmodified EvidenceLedger.add_claim(), then
uses its real id for the Hypothesis. This is correct reuse of an
existing method, not a new gate and not a schema change.

Like extraction_integration.py, this module makes NO domain decision:
it never determines any FinalStatus value, never touches CaseScope or
authority, and never advances the Investigation state machine -- per
ChatGPT's locked Build 4A decision, state-machine transitions belong
to a future orchestration layer, not bounded components like this one.

CONTRACT: llm_schemas.py's HypothesisCandidate contract is single-
hypothesis-per-call; this module does not alter that (locked schema
policy). "Multiple hypotheses" means calling
generate_and_record_hypothesis() more than once, not a new list-based
schema.
"""

from dataclasses import dataclass
from typing import Optional

from .evidence import Claim, Hypothesis
from .investigation import Investigation
from .llm_provider import LLMProvider, LLMProviderError
from .llm_schemas import SchemaValidationError, parse_hypothesis_candidate


class HypothesisIntegrationError(Exception):
    """Raised for integration-layer misuse -- e.g. calling this with
    something other than a real Investigation."""


@dataclass(frozen=True)
class HypothesisIntegrationResult:
    success: bool
    investigation_id: str
    claim_id: Optional[str] = None
    hypothesis_id: Optional[str] = None
    failure_stage: Optional[str] = None   # None | "provider" | "validation"
    failure_reason: Optional[str] = None


_SYSTEM_PROMPT = (
    "You are a hypothesis-proposal component for a medical bill "
    "investigation. You will be given a list of facts already extracted "
    "and accepted into evidence, each with its own real fact_id. Propose "
    "ONE possible hypothesis about a billing discrepancy these facts "
    "might support -- a hypothesis is a candidate explanation, NOT a "
    "conclusion, and NOT a determination that anything is actually wrong.\n"
    "\n"
    "Respond with JSON matching exactly this shape:\n"
    '{"claim_statement": "<short statement of the possible issue>", '
    '"explanation_text": "<why these facts might support that claim>", '
    '"referenced_fact_ids": ["<only real fact_ids from the list given>"]}\n'
    "\n"
    "Rules:\n"
    "- referenced_fact_ids MUST only contain fact_ids that were actually "
    "given to you. Never invent a fact_id.\n"
    "- Do NOT include any other field. In particular, never include "
    "final_status, case_scope, authority, authority_level, "
    "authority_result, or appeal_eligible -- you have no authority to set "
    "any of those, and doing so will cause your entire output to be "
    "discarded.\n"
    "- This is a proposal only. You are not determining whether the bill "
    "is actually wrong.\n"
    "- Return ONLY the JSON object. No prose, no markdown fences."
)


def _build_user_content(investigation: Investigation) -> str:
    lines = ["Facts currently in evidence:"]
    for fact in investigation.ledger.facts:
        lines.append(f"- fact_id={fact.id} | type={fact.fact_type} | value={fact.value!r}")
    if not investigation.ledger.facts:
        lines.append("(no facts currently in evidence)")
    return "\n".join(lines)


def generate_and_record_hypothesis(
    investigation: Investigation,
    provider: LLMProvider,
) -> HypothesisIntegrationResult:
    if not isinstance(investigation, Investigation):
        raise HypothesisIntegrationError(
            f"Expected Investigation, got {type(investigation).__name__}"
        )

    known_fact_ids = {f.id for f in investigation.ledger.facts}

    try:
        raw_text = provider.complete_json(_SYSTEM_PROMPT, _build_user_content(investigation))
    except LLMProviderError as exc:
        return HypothesisIntegrationResult(
            success=False, investigation_id=investigation.investigation_id,
            failure_stage="provider", failure_reason=str(exc),
        )

    try:
        candidate = parse_hypothesis_candidate(raw_text, known_fact_ids=known_fact_ids)
    except SchemaValidationError as exc:
        return HypothesisIntegrationResult(
            success=False, investigation_id=investigation.investigation_id,
            failure_stage="validation", failure_reason=str(exc),
        )

    claim = Claim(
        statement=candidate.claim_statement,
        related_fact_ids=candidate.referenced_fact_ids,
    )
    investigation.ledger.add_claim(claim)

    hypothesis = Hypothesis(
        claim_id=claim.id,
        explanation_text=candidate.explanation_text,
        referenced_fact_ids=candidate.referenced_fact_ids,
    )
    investigation.ledger.add_hypothesis(hypothesis)

    return HypothesisIntegrationResult(
        success=True, investigation_id=investigation.investigation_id,
        claim_id=claim.id, hypothesis_id=hypothesis.id,
    )
