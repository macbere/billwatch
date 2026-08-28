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
import json
import re

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
    "You are an appeal-drafting component for a medical bill investigation. "
    "The billing discrepancy has ALREADY been deterministically established "
    "outside this component. Your ONLY task is to turn the supplied factual "
    "record into a concise professional appeal letter body for human review.\\n"
    "\\n"
    "IMPORTANT: You are NOT being asked to explain why a code is bundled, "
    "unbundled, included, excluded, medically necessary, or otherwise governed "
    "by a coding rule. Do not provide coding guidance or interpret any coding "
    "standard.\\n"
    "\\n"
    "You may state only observable facts explicitly supplied to you, such as "
    "that particular codes appeared on a bill, that particular amounts were "
    "billed, or that a particular date or claim identifier appears in the "
    "record. You may request human review of those facts.\\n"
    "\\n"
    "Never invent, paraphrase, or reproduce AMA CPT procedure-code descriptor "
    "text. Reference procedure codes only by their bare code numbers exactly "
    "as supplied.\\n"
    "\\n"
    "Do not restate the deterministic adjudication, explain its reasoning, "
    "state what any coding guideline means, or make a new determination.\\n"
    "\\n"
    "Respond with JSON matching exactly this shape:\\n"
    '{"draft_text": "<the appeal letter body text>", '
    '"cited_fact_ids": ["<only real fact_ids given to you>"], '
    '"cited_claim_ids": ["<only the real claim_id given to you>"]}\\n'
    "\\n"
    "Only cite identifiers actually supplied to you. Never invent an "
    "identifier.\\n"
    "\\n"
    "This letter is a DRAFT for human review only. Do not claim that it has "
    "been or will be sent anywhere.\\n"
    "\\n"
    "Return ONLY the JSON object. No prose and no markdown fences."
)


def _build_user_content(investigation: Investigation, hypothesis) -> str:
    """
    Build the narrowest possible LLM input.

    SECURITY CONTRACT:
    hypothesis.explanation_text is deterministic adjudication reasoning
    and MUST NOT cross the LLM boundary.

    Gemini receives only:
      - claim_id
      - the claim statement
      - explicitly referenced factual ledger entries

    Gemini does NOT receive the hypothesis explanation.
    """
    claim = next(
        (c for c in investigation.ledger.claims if c.id == hypothesis.claim_id),
        None,
    )

    claim_text = claim.statement if claim else "(claim not found)"

    lines = [
        f"claim_id: {hypothesis.claim_id}",
        f"claim: {claim_text}",
        "supporting facts:",
    ]

    facts_by_id = {f.id: f for f in investigation.ledger.facts}

    for fid in hypothesis.referenced_fact_ids:
        fact = facts_by_id.get(fid)
        if fact is not None:
            lines.append(
                f"- fact_id={fact.id} | type={fact.fact_type} | value={fact.value!r}"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------
# Deterministic appeal-prose firewall
# ---------------------------------------------------------------------
#
# Gemini output is NEVER repaired.
#
# If the model attempts to introduce coding-rule explanation or
# adjudicative reasoning into the appeal, the complete candidate is
# rejected.
# ---------------------------------------------------------------------

_FORBIDDEN_APPEAL_PATTERNS = (
    re.compile(r"\bstandard\s+(?:coding|billing)\s+guidelines?\b", re.I),
    re.compile(r"\bcoding\s+guidelines?\b", re.I),
    re.compile(r"\bbilling\s+guidelines?\b", re.I),
    re.compile(r"\bnational\s+correct\s+coding\s+initiative\b", re.I),
    re.compile(r"\bNCCI\b", re.I),
    re.compile(r"\bbundled?\s+(?:into|with)\b", re.I),
    re.compile(r"\bbundling\s+rules?\b", re.I),
    re.compile(r"\bunbundl(?:ed|ing)\b", re.I),
    re.compile(r"\bimproper\s+unbundling\b", re.I),
    re.compile(r"\binappropriate\s+unbundling\b", re.I),
    re.compile(r"\bcomponent\s+of\s+(?:the\s+)?more\s+comprehensive\b", re.I),
    re.compile(r"\bincluded\s+within\b", re.I),
    re.compile(r"\bintegral\s+component\b", re.I),
    re.compile(
        r"\b(?:code|procedure)\s+\d{5}\s+is\s+(?:bundled|included|integral)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:code|procedure)\s+\d{5}\s+(?:must|should)\s+be\s+"
        r"(?:bundled|reported|included)\b",
        re.I,
    ),
    re.compile(r"\baccording\s+to\s+(?:standard\s+)?coding\b", re.I),
    re.compile(r"\baccording\s+to\s+(?:standard\s+)?billing\b", re.I),
    re.compile(
        r"\b(?:CPT|HCPCS)\s+(?:guideline|rule|rules|descriptor|definition)\b",
        re.I,
    ),
    re.compile(
        r"\bthe\s+(?:CPT|HCPCS)\s+(?:guideline|rule|rules)\b",
        re.I,
    ),
)


def _validate_appeal_prose_firewall(draft_text: str) -> None:
    """
    Mechanically reject appeal prose that introduces coding-rule
    explanation or adjudicative reasoning.

    This is deterministic. Gemini output is never repaired.
    """
    if not isinstance(draft_text, str):
        raise SchemaValidationError(
            "Appeal draft_text must be a string."
        )

    for pattern in _FORBIDDEN_APPEAL_PATTERNS:
        if pattern.search(draft_text):
            raise SchemaValidationError(
                "Appeal draft rejected by semantic safety firewall: "
                "prohibited coding-rule/adjudication language detected."
            )



# NOTE: the trailing-JSON-artifact cleanup previously implemented here as
# _extract_first_json_object() has been moved to the shared chokepoint
# llm_schemas.py::_parse_json_object(), since the SAME artifact was also
# independently observed at the hypothesis and extraction stages -- this
# module still benefits from that fix automatically via
# parse_appeal_draft_candidate() without needing its own copy.
#
# Bounded, narrowly-scoped retry for appeal DRAFTING/VALIDATION failures
# only (added in direct response to empirically-confirmed intermittent
# production evidence: a real Gemini appeal response rejected with
# "raw output is not valid JSON: Extra data..."). Reuses the identical
# system prompt and user content on every attempt -- never regenerates
# the input, never touches Gate 3 eligibility, never weakens the
# semantic firewall or citation checks, which are re-applied in full on
# every attempt. Provider-layer (LLMProviderError) failures are NOT
# retried at this layer -- GenAISDKProvider already has its own bounded
# 503/UNAVAILABLE retry; adding a second retry layer on top of that
# would only compound worst-case latency without benefit, since a
# provider that already exhausted its own retry budget is not expected
# to succeed on one more immediate call from here.
_MAX_DRAFT_ATTEMPTS = 2


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

    last_validation_error = None
    for attempt in range(_MAX_DRAFT_ATTEMPTS):
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
            # Defense in depth: schema-valid JSON is not sufficient.
            # The prose itself must satisfy the appeal semantic contract.
            _validate_appeal_prose_firewall(candidate.draft_text)
        except SchemaValidationError as exc:
            last_validation_error = exc
            if attempt < _MAX_DRAFT_ATTEMPTS - 1:
                continue  # ask again with the identical input; the check itself never changes
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

    # Unreachable in practice (the loop always returns), kept as a safe
    # fallback rather than an unhandled fall-through.
    return AppealDraftResult(
        success=False, investigation_id=investigation.investigation_id,
        hypothesis_id=hypothesis.id, failure_stage="validation",
        failure_reason=str(last_validation_error),
    )
