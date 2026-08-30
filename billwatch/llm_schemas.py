"""
LLM Output Schemas (Build 4, Stage 2).

Deterministic parsing + strict validation boundary between untrusted raw
LLM text (billwatch/llm_provider.py) and the existing, already-tested
BillWatch domain model (evidence.py, case_scope.py, authority.py,
enums.py). Nothing in this module ever constructs a CaseScope, an
AuthorityDecision, a FinalStatus, or an appeal -- it only ever produces
*candidate* objects that the caller must still pass through the
existing, unmodified gates.

fact_type AUTHORITATIVE VALUES -- per direct repository inspection of
evidence.py::ExtractedFact (verified this session, not assumed):
    "line_item" | "code" | "date" | "amount" | "clause"          (5 values)
This corrects the Stage 2 design report's "4 known literals" error.

DOMAIN-DECISION FIELD POLICY (locked by ChatGPT, Build 4 Stage 2,
"Mandatory Decision -- Question 4"): if a raw candidate -- at ANY
nesting depth -- contains a key matching a domain-decision field name
(see _DOMAIN_DECISION_FIELDS), the ENTIRE top-level candidate is
rejected. Not just that field, and not just that nested object.

UNKNOWN-FIELD POLICY (this module's implementation choice, as required
to be documented): a harmless unknown field (not in a contract's
whitelist, not a domain-decision field) is silently ignored; the
candidate is still accepted using only its whitelisted fields. Only
domain-decision-shaped fields trigger a full rejection.

PER-FACT REJECTION MECHANISM: within an otherwise-valid extraction
candidate, an individual fact that fails validation (bad fact_type,
empty value, hallucinated source_span, etc.) is excluded and recorded
as a RejectedFact with a reason -- it does not invalidate the rest of
the batch. This mirrors the existing accept/reject-with-reason pattern
already used by reference_data.py::ReferenceStore.load_snapshot() --
the smallest mechanism consistent with the existing architecture, per
Stage 2's instruction not to invent a new persistence subsystem.

HYPOTHESIS LIFECYCLE: the LLM may propose a hypothesis's content, but
never its id. parse_hypothesis_candidate() returns a HypothesisCandidate
with no id at all -- BillWatch itself is responsible for constructing
the real Hypothesis (evidence.py) and assigning its id via the existing
EvidenceLedger. parse_verification_candidate() then only accepts a
hypothesis_id that is already present in a caller-supplied set of KNOWN,
real ledger ids -- the LLM cannot manufacture an id this function will
accept.
"""

import json
from dataclasses import dataclass
from typing import Optional

from .enums import SourceType


class SchemaValidationError(Exception):
    """Raised for structurally invalid or untrusted LLM output. Distinct
    from LLMProviderError (llm_provider.py), which covers transport/
    network failures only -- this covers content/schema failures."""


_VALID_FACT_TYPES = frozenset({"line_item", "code", "date", "amount", "clause"})

_DOMAIN_DECISION_FIELDS = frozenset({
    "final_status",
    "case_scope",
    "casescope",
    "authority",
    "authority_level",
    "authority_result",
    "appeal_eligible",
    "appeal_eligibility",
    "supported_discrepancy",
    "no_supported_discrepancy",
    "insufficient_evidence",
    "conflicting_evidence",
})


def _find_domain_decision_fields(obj, path=""):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_path = f"{path}.{k}" if path else str(k)
            if isinstance(k, str) and k.lower() in _DOMAIN_DECISION_FIELDS:
                found.append(key_path)
            found.extend(_find_domain_decision_fields(v, key_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(_find_domain_decision_fields(item, f"{path}[{i}]"))
    return found


def _reject_if_domain_decision_fields_present(raw, context: str) -> None:
    found = _find_domain_decision_fields(raw)
    if found:
        raise SchemaValidationError(
            f"{context}: candidate rejected in full -- domain-decision "
            f"field(s) found at {found!r}. The LLM may never establish "
            "final_status, case_scope, authority, or appeal eligibility; "
            "the ENTIRE candidate is discarded, not just the offending field."
        )


def _strip_trailing_json_artifact(raw_text: str) -> str:
    """Defensive cleanup for a confirmed, empirically-observed Gemini
    output artifact: the model occasionally emits one well-formed JSON
    value followed by trailing whitespace/newline or other incidental
    trailing content after the closing brace, which strict json.loads()
    rejects as 'Extra data'. This has been directly captured in
    production/live diagnostics at the appeal, hypothesis, and
    extraction stages -- it is a single quirk affecting all four
    LLM-output contracts that flow through this shared function, not a
    per-stage bug.

    This performs NO semantic relaxation whatsoever: it parses exactly
    the FIRST complete JSON value from the start of the (whitespace-
    stripped) string using the stdlib's own decoder, and discards only
    whatever comes after it. If the text doesn't begin with a parseable
    JSON value at all, it is returned completely unchanged, so every
    existing malformed-JSON rejection path (e.g. "not json {{{") still
    fires exactly as before this fix -- confirmed against the full
    existing test_llm_schemas.py suite, which contains no test relying
    on trailing-content-after-valid-JSON being rejected."""
    if not isinstance(raw_text, str):
        return raw_text
    stripped = raw_text.strip()
    if not stripped:
        return raw_text
    try:
        obj, _end = json.JSONDecoder().raw_decode(stripped)
    except (ValueError, TypeError):
        return raw_text
    return json.dumps(obj)


def _parse_json_object(raw_text: str, context: str) -> dict:
    cleaned_text = _strip_trailing_json_artifact(raw_text)
    try:
        parsed = json.loads(cleaned_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise SchemaValidationError(f"{context}: raw output is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SchemaValidationError(
            f"{context}: expected a JSON object at the top level, got {type(parsed).__name__}"
        )
    return parsed


# ---------------------------------------------------------------------
# Evidence extraction candidate
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class ExtractedFactCandidate:
    fact_type: str
    value: str
    source_span: str
    confidence: Optional[str] = None


@dataclass(frozen=True)
class RejectedFact:
    index: int
    reason: str


@dataclass(frozen=True)
class ExtractionResult:
    document_id: str
    accepted_facts: tuple
    rejected_facts: tuple


def parse_extraction_candidate(raw_text: str, document, known_fact_types=_VALID_FACT_TYPES) -> ExtractionResult:
    """
    document must be the actual Document (evidence.py) this extraction
    claims to be about -- its real .id and .raw_text are used to validate
    document_id and every fact's source_span. The caller is responsible
    for looking up the real Document from the ledger; this function never
    trusts a document_id it hasn't been given the real object for.
    """
    raw = _parse_json_object(raw_text, "extraction candidate")
    _reject_if_domain_decision_fields_present(raw, "extraction candidate")

    document_id = raw.get("document_id")
    if not isinstance(document_id, str) or not document_id:
        raise SchemaValidationError("extraction candidate: missing or invalid document_id")
    if document_id != document.id:
        raise SchemaValidationError(
            f"extraction candidate: document_id {document_id!r} does not match "
            f"the provided Document's real id {document.id!r}"
        )

    raw_facts = raw.get("extracted_facts")
    if not isinstance(raw_facts, list):
        raise SchemaValidationError("extraction candidate: extracted_facts must be a list")

    accepted = []
    rejected = []
    for i, item in enumerate(raw_facts):
        if not isinstance(item, dict):
            rejected.append(RejectedFact(index=i, reason="fact is not a JSON object"))
            continue

        fact_type = item.get("fact_type")
        if fact_type not in known_fact_types:
            rejected.append(RejectedFact(
                index=i, reason=f"unknown fact_type {fact_type!r}; must be one of {sorted(known_fact_types)}"
            ))
            continue

        value = item.get("value")
        if not isinstance(value, str) or not value:
            rejected.append(RejectedFact(index=i, reason="value must be a non-empty string"))
            continue

        source_span = item.get("source_span")
        if not isinstance(source_span, str) or not source_span:
            rejected.append(RejectedFact(index=i, reason="source_span must be a non-empty string"))
            continue
        if source_span not in document.raw_text:
            rejected.append(RejectedFact(
                index=i, reason="source_span is not a literal substring of the document's raw_text"
            ))
            continue

        if fact_type == "code" and value not in source_span:
            rejected.append(RejectedFact(
                index=i, reason="code value is not contained in its cited source_span"
            ))
            continue

        confidence = item.get("confidence")
        if confidence is not None and not isinstance(confidence, str):
            rejected.append(RejectedFact(index=i, reason="confidence must be a string or null"))
            continue

        accepted.append(ExtractedFactCandidate(
            fact_type=fact_type, value=value, source_span=source_span, confidence=confidence
        ))

    return ExtractionResult(
        document_id=document_id, accepted_facts=tuple(accepted), rejected_facts=tuple(rejected)
    )


# ---------------------------------------------------------------------
# Hypothesis generation candidate
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class HypothesisCandidate:
    """No id field -- BillWatch, not the LLM, assigns the real id when it
    constructs the actual Hypothesis via EvidenceLedger."""
    claim_statement: str
    explanation_text: str
    referenced_fact_ids: tuple


def parse_hypothesis_candidate(raw_text: str, known_fact_ids) -> HypothesisCandidate:
    """
    known_fact_ids must be the real set of fact ids already present in the
    ledger. Any referenced_fact_ids entry not in this set is rejected --
    this candidate is not itself added to the ledger by this function;
    EvidenceLedger.add_hypothesis() performs its own orphan-fact check
    again when the caller actually constructs the real Hypothesis.
    """
    raw = _parse_json_object(raw_text, "hypothesis candidate")
    _reject_if_domain_decision_fields_present(raw, "hypothesis candidate")

    claim_statement = raw.get("claim_statement")
    if not isinstance(claim_statement, str) or not claim_statement:
        raise SchemaValidationError("hypothesis candidate: claim_statement must be a non-empty string")

    explanation_text = raw.get("explanation_text")
    if not isinstance(explanation_text, str) or not explanation_text:
        raise SchemaValidationError("hypothesis candidate: explanation_text must be a non-empty string")

    referenced_fact_ids = raw.get("referenced_fact_ids", [])
    if not isinstance(referenced_fact_ids, list) or not all(isinstance(x, str) for x in referenced_fact_ids):
        raise SchemaValidationError("hypothesis candidate: referenced_fact_ids must be a list of strings")

    unknown = [fid for fid in referenced_fact_ids if fid not in known_fact_ids]
    if unknown:
        raise SchemaValidationError(
            f"hypothesis candidate: references unknown fact_id(s) {unknown!r}; "
            "orphan hypotheses are rejected"
        )

    return HypothesisCandidate(
        claim_statement=claim_statement,
        explanation_text=explanation_text,
        referenced_fact_ids=tuple(referenced_fact_ids),
    )


# ---------------------------------------------------------------------
# Verification planning candidate
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class VerificationCandidate:
    hypothesis_id: str
    proposed_source_types: tuple
    verification_rationale: str


_VALID_SOURCE_TYPE_NAMES = frozenset(st.name for st in SourceType)


def parse_verification_candidate(raw_text: str, known_hypothesis_ids) -> VerificationCandidate:
    """
    known_hypothesis_ids must be the real set of hypothesis ids already
    present in the ledger (i.e. ids BillWatch itself assigned -- see the
    HYPOTHESIS LIFECYCLE note at the top of this module). The LLM cannot
    manufacture an id this function will accept.
    """
    raw = _parse_json_object(raw_text, "verification candidate")
    _reject_if_domain_decision_fields_present(raw, "verification candidate")

    hypothesis_id = raw.get("hypothesis_id")
    if not isinstance(hypothesis_id, str) or not hypothesis_id:
        raise SchemaValidationError("verification candidate: missing or invalid hypothesis_id")
    if hypothesis_id not in known_hypothesis_ids:
        raise SchemaValidationError(
            f"verification candidate: hypothesis_id {hypothesis_id!r} is not a "
            "known, existing hypothesis id -- the LLM cannot manufacture "
            "an authoritative hypothesis identity"
        )

    raw_types = raw.get("proposed_source_types")
    if not isinstance(raw_types, list) or not raw_types:
        raise SchemaValidationError("verification candidate: proposed_source_types must be a non-empty list")

    proposed = []
    for t in raw_types:
        if not isinstance(t, str) or t not in _VALID_SOURCE_TYPE_NAMES:
            raise SchemaValidationError(
                f"verification candidate: {t!r} is not a valid SourceType name; "
                f"must be one of {sorted(_VALID_SOURCE_TYPE_NAMES)}"
            )
        proposed.append(SourceType[t])

    rationale = raw.get("verification_rationale")
    if not isinstance(rationale, str) or not rationale:
        raise SchemaValidationError("verification candidate: verification_rationale must be a non-empty string")

    return VerificationCandidate(
        hypothesis_id=hypothesis_id,
        proposed_source_types=tuple(proposed),
        verification_rationale=rationale,
    )


# ---------------------------------------------------------------------
# Appeal draft candidate (Build 4E)
#
# ADDITION ONLY -- does not alter any existing contract above. Reuses
# _parse_json_object() and the general domain-decision-rejection
# principle, but with its own, appeal-scoped forbidden-field set rather
# than modifying the shared _DOMAIN_DECISION_FIELDS/_find_domain_decision_
# fields() used by extraction/hypothesis/verification, to guarantee zero
# risk to those three existing, already-tested contracts.
# ---------------------------------------------------------------------

_APPEAL_FORBIDDEN_FIELDS = frozenset({
    "final_status", "case_scope", "casescope", "authority", "authority_level",
    "authority_result", "appeal_eligible", "appeal_eligibility",
    "supported_discrepancy", "no_supported_discrepancy",
    "insufficient_evidence", "conflicting_evidence",
    # Build 4E additions, per this build's explicit authorization:
    "recommended_status", "adjudication", "adjudication_result",
    "authority_decision", "verdict", "confidence",
})


def _find_appeal_forbidden_fields(obj, path=""):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_path = f"{path}.{k}" if path else str(k)
            if isinstance(k, str) and k.lower() in _APPEAL_FORBIDDEN_FIELDS:
                found.append(key_path)
            found.extend(_find_appeal_forbidden_fields(v, key_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(_find_appeal_forbidden_fields(item, f"{path}[{i}]"))
    return found


@dataclass(frozen=True)
class AppealDraftCandidate:
    draft_text: str
    cited_fact_ids: tuple
    cited_claim_ids: tuple


def parse_appeal_draft_candidate(raw_text: str, known_fact_ids, known_claim_ids) -> AppealDraftCandidate:
    """
    known_fact_ids / known_claim_ids must be the real sets of fact/claim
    ids already present in the ledger. Any citation not in those sets
    rejects the ENTIRE candidate -- never silently dropped, repaired, or
    invented, per this build's explicit requirement.
    """
    raw = _parse_json_object(raw_text, "appeal draft candidate")

    forbidden_found = _find_appeal_forbidden_fields(raw)
    if forbidden_found:
        raise SchemaValidationError(
            f"appeal draft candidate: candidate rejected in full -- "
            f"domain-decision field(s) found at {forbidden_found!r}. An "
            "appeal draft may never carry final_status, a recommended "
            "status, an adjudication/authority decision, a verdict, or a "
            "confidence level intended to determine the outcome."
        )

    draft_text = raw.get("draft_text")
    if not isinstance(draft_text, str) or not draft_text.strip():
        raise SchemaValidationError("appeal draft candidate: draft_text must be a non-empty string")

    cited_fact_ids = raw.get("cited_fact_ids", [])
    if not isinstance(cited_fact_ids, list) or not all(isinstance(x, str) for x in cited_fact_ids):
        raise SchemaValidationError("appeal draft candidate: cited_fact_ids must be a list of strings")
    unknown_facts = [fid for fid in cited_fact_ids if fid not in known_fact_ids]
    if unknown_facts:
        raise SchemaValidationError(
            f"appeal draft candidate: cites unknown fact_id(s) {unknown_facts!r}; "
            "candidate rejected in full, not repaired"
        )

    cited_claim_ids = raw.get("cited_claim_ids", [])
    if not isinstance(cited_claim_ids, list) or not all(isinstance(x, str) for x in cited_claim_ids):
        raise SchemaValidationError("appeal draft candidate: cited_claim_ids must be a list of strings")
    unknown_claims = [cid for cid in cited_claim_ids if cid not in known_claim_ids]
    if unknown_claims:
        raise SchemaValidationError(
            f"appeal draft candidate: cites unknown claim_id(s) {unknown_claims!r}; "
            "candidate rejected in full, not repaired"
        )

    return AppealDraftCandidate(
        draft_text=draft_text.strip(),
        cited_fact_ids=tuple(cited_fact_ids),
        cited_claim_ids=tuple(cited_claim_ids),
    )
