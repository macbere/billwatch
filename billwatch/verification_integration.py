"""
Build 4C: Evidence Verification (bounded component).

Given an existing hypothesis, asks the LLM which source-type categories
to check, treats that as UNTRUSTED, validates it through the existing
parse_verification_candidate(), and -- only for source types this
bounded stage can actually resolve deterministically -- performs a real
lookup via reference_data.py and a real authority decision via
authority.py. Source types with no reference-data lookup mechanism are
recorded as MissingEvidence, never fabricated.

DESIGN DECISIONS (documented, not hidden):
- ReferenceStore is passed in as an explicit parameter, exactly like
  LLMProvider already is -- Investigation itself is NOT modified to own
  one. This avoids a data-model change.
- This module NEVER produces a "contradicted" Verification result --
  only "corroborated" (AUTHORITATIVE/CORROBORATING/ADMISSIBLE) or
  "silent" (everything else, including INSUFFICIENT_SCOPE/OUT_OF_SCOPE/
  UNAVAILABLE). Judging actual content-level contradiction is out of
  this bounded stage's authority.
- If two proposed source types both resolve to independently-usable
  decisions for the same claim, the existing, unmodified
  authority.flag_potential_conflict() is reused to detect it, and a
  Conflict is recorded -- never resolved. This is how "conflicting
  evidence" surfaces here without ever touching FinalStatus.
- If investigation.case_scope is None, this module does not guess --
  it calls the existing, unmodified case_scope.resolve_case_scope()
  with no arguments, which deterministically returns UNKNOWN/FAIL,
  exactly as it does everywhere else in the repository.
- This module never determines final_status, appeal_eligible, or any
  other domain decision, and never advances the state machine.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import date
from typing import Optional
import re

from .authority import ClaimType, AuthorityResult, evaluate_source_authority, flag_potential_conflict
from .case_scope import resolve_case_scope
from .enums import SourceType
from .evidence import Verification, MissingEvidence, Conflict
from .investigation import Investigation
from .llm_provider import LLMProvider, LLMProviderError
from .llm_schemas import SchemaValidationError, parse_verification_candidate
from .reference_data import ReferenceStore, LookupStatus


class VerificationIntegrationError(Exception):
    """Raised for integration-layer misuse -- e.g. calling this with
    something other than a real Investigation."""


@dataclass(frozen=True)
class VerificationIntegrationResult:
    success: bool
    investigation_id: str
    hypothesis_id: Optional[str] = None
    verification_ids: tuple = ()
    missing_evidence_ids: tuple = ()
    conflict_ids: tuple = ()
    failure_stage: Optional[str] = None   # None | "registration" | "provider" | "validation"
    failure_reason: Optional[str] = None


# Source types with no deterministic reference-data lookup mechanism in
# this bounded stage. Never fabricated -- always routed to MissingEvidence
# with an honest, specific reason.
_NO_LOOKUP_SOURCE_TYPES = {
    SourceType.EOB: (
        "requires the patient's actual EOB document -- not available via "
        "automated reference-data lookup in this bounded stage"
    ),
    SourceType.CMS_MEDICARE: (
        "no CMS Medicare coverage-policy reference dataset exists in this "
        "bounded stage (only HCPCS/ICD-10/NCCI code data is available)"
    ),
    SourceType.PUBLIC_REGULATORY: (
        "no public-regulatory reference dataset exists in this bounded stage"
    ),
    SourceType.PROVIDER_BILL_LABEL: (
        "a provider's bill label requires the actual uploaded bill "
        "document -- not available via automated reference-data lookup "
        "in this bounded stage"
    ),
    SourceType.LLM_INTERPRETATION: (
        "an LLM's own interpretation is never an evidence source (Gate 1) "
        "-- recorded as missing evidence rather than fabricated"
    ),
}

_USABLE_RESULTS = frozenset({
    AuthorityResult.AUTHORITATIVE, AuthorityResult.CORROBORATING, AuthorityResult.ADMISSIBLE,
})


def _corroboration_result_for(decision) -> str:
    return "corroborated" if decision.result in _USABLE_RESULTS else "silent"


def _code_values_for_hypothesis(investigation: Investigation, hypothesis) -> list:
    facts_by_id = {f.id: f for f in investigation.ledger.facts}
    return [
        facts_by_id[fid].value
        for fid in hypothesis.referenced_fact_ids
        if fid in facts_by_id and facts_by_id[fid].fact_type == "code"
    ]


_PATIENT_RESPONSIBILITY_MARKERS = (
    "patient responsibility",
    "patient owes",
    "patient due",
    "amount due from patient",
)

_CURRENCY_VALUE_RE = re.compile(r"^\$?([0-9]+(?:\.[0-9]{1,2})?)$")


def _amount_value_to_cents(value):
    """Parse one extracted amount value into integer cents.

    No semantic meaning is inferred here. This function only performs a
    strict numeric conversion.
    """
    raw = str(value).strip().replace(",", "")
    match = _CURRENCY_VALUE_RE.fullmatch(raw)
    if not match:
        return None

    try:
        amount = Decimal(match.group(1))
    except InvalidOperation:
        return None

    if amount < 0:
        return None

    cents = amount * 100
    if cents != cents.to_integral_value():
        return None

    return int(cents)


def _patient_responsibility_cents_for_hypothesis(
    investigation: Investigation,
    hypothesis,
) -> list:
    """Return only explicitly-labelled patient-responsibility amounts.

    Fail closed:
    - generic totals are ignored;
    - provider charges are ignored;
    - unlabeled amounts are ignored;
    - malformed values are ignored;
    - only referenced facts are eligible.
    """
    facts_by_id = {f.id: f for f in investigation.ledger.facts}
    values = []

    for fid in hypothesis.referenced_fact_ids:
        fact = facts_by_id.get(fid)

        if fact is None or fact.fact_type != "amount":
            continue

        span = (fact.source_span or "").lower()

        if not any(
            marker in span
            for marker in _PATIENT_RESPONSIBILITY_MARKERS
        ):
            continue

        cents = _amount_value_to_cents(fact.value)

        if cents is not None:
            values.append(cents)

    return values


def _service_dates_for_hypothesis(
    investigation: Investigation,
    hypothesis,
) -> list:
    """Return strictly parsed ISO dates from referenced date facts only.

    PLAN_POLICY temporal applicability must be based on document facts
    already admitted to the evidence ledger. No LLM interpretation,
    current-date substitution, or fuzzy date parsing is permitted here.
    """
    facts_by_id = {f.id: f for f in investigation.ledger.facts}
    values = []

    for fid in hypothesis.referenced_fact_ids:
        fact = facts_by_id.get(fid)

        if fact is None or fact.fact_type != "date":
            continue

        try:
            parsed = date.fromisoformat(str(fact.value).strip())
        except (TypeError, ValueError):
            continue

        values.append(parsed)

    return values


def _plan_id_values_for_hypothesis(investigation: Investigation, hypothesis, reference_store: ReferenceStore) -> list:
    """Phase C1: deterministic plan-identifier matching. A 'clause' fact
    (an existing, unmodified fact_type -- no schema change) is treated as
    a candidate plan_id ONLY if it exactly matches a plan_id already
    present in the loaded plan_policy reference snapshot. This is a pure
    string-equality check against known, real, already-validated data --
    never a fuzzy match, never an LLM judgment of applicability."""
    facts_by_id = {f.id: f for f in investigation.ledger.facts}
    clause_values = [
        facts_by_id[fid].value
        for fid in hypothesis.referenced_fact_ids
        if fid in facts_by_id and facts_by_id[fid].fact_type == "clause"
    ]
    snapshot = reference_store.get_current_snapshot("plan_policy")
    known_plan_ids = {rec.plan_id for rec in snapshot.records} if snapshot else set()
    return [v for v in clause_values if v in known_plan_ids]


def _resolve_case_scope(investigation: Investigation):
    if investigation.case_scope is not None:
        return investigation.case_scope
    return resolve_case_scope(source_identifier="verification-no-scope-set")


def _attempt_lookup(
    source_type,
    code_values,
    plan_id_values,
    patient_responsibility_cents,
    service_dates,
    case_scope,
    reference_store: ReferenceStore,
):
    """Returns (decision, missing_reason, corroboration_override).

    corroboration_override is normally None so all pre-C1 pathways retain
    their original behavior.

    PLAN_POLICY uses the override to distinguish:
      - authoritative policy + proven bill contradiction -> corroborated
      - authoritative policy + checked clean bill -> silent

    Authority is not the same thing as discrepancy proof.
    """
    if source_type in _NO_LOOKUP_SOURCE_TYPES:
        return None, _NO_LOOKUP_SOURCE_TYPES[source_type], None

    if source_type == SourceType.PLAN_POLICY:
        if not plan_id_values:
            return None, (
                "PLAN_POLICY verification requires a plan identifier "
                "extracted as a 'clause' fact matching a known plan_id in "
                "the loaded plan_policy reference snapshot; none was found "
                "among the referenced facts"
            ), None

        unique_plan_ids = tuple(dict.fromkeys(plan_id_values))

        if len(unique_plan_ids) != 1:
            return None, (
                "PLAN_POLICY verification found multiple distinct plan "
                "identifiers among the referenced facts; BillWatch will "
                "not guess which plan governs the claim"
            ), None

        plan_id = unique_plan_ids[0]

        unique_service_dates = tuple(dict.fromkeys(service_dates))

        if len(unique_service_dates) != 1:
            return None, (
                "PLAN_POLICY verification requires exactly one valid ISO "
                "service-date fact among the referenced facts; "
                f"{len(unique_service_dates)} distinct usable dates were found"
            ), None

        service_date = unique_service_dates[0]

        lookup = reference_store.lookup_plan_policy(
            plan_id,
            as_of=service_date,
        )

        if lookup.status == LookupStatus.OUTSIDE_EFFECTIVE_PERIOD:
            return None, (
                f"PLAN_POLICY record for plan_id {plan_id!r} was not yet "
                f"effective on service date {service_date.isoformat()}"
            ), None

        if lookup.status != LookupStatus.FOUND:
            return None, (
                f"No applicable plan-policy record found for plan_id "
                f"{plan_id!r} on service date {service_date.isoformat()}"
            ), None

        rec = lookup.record

        if rec.rule_type != "coverage_rule":
            return None, (
                f"PLAN_POLICY record {rec.policy_id!r} has rule_type "
                f"{rec.rule_type!r}, which this bounded comparator does "
                "not support"
            ), None

        applicable_codes = set(rec.applicable_codes)
        referenced_codes = set(code_values)

        if not applicable_codes.intersection(referenced_codes):
            return None, (
                f"PLAN_POLICY record {rec.policy_id!r} does not apply to "
                f"any referenced code {sorted(referenced_codes)!r}"
            ), None

        if rec.patient_cost_share_cents is None:
            return None, (
                f"PLAN_POLICY record {rec.policy_id!r} has no structured "
                "patient cost-sharing value for deterministic comparison"
            ), None

        if len(patient_responsibility_cents) != 1:
            return None, (
                "PLAN_POLICY cost-sharing verification requires exactly "
                "one explicitly-labelled patient-responsibility amount; "
                f"{len(patient_responsibility_cents)} usable values were found"
            ), None

        actual_cents = patient_responsibility_cents[0]
        allowed_cents = rec.patient_cost_share_cents

        source = reference_store.to_source(lookup)

        decision = evaluate_source_authority(
            source,
            case_scope,
            ClaimType.GENERIC,
        )

        if actual_cents > allowed_cents:
            return decision, None, "corroborated"

        return decision, None, "silent"

    if source_type == SourceType.CMS_NCCI:
        if len(code_values) < 2:
            return None, (
                "CMS_NCCI verification requires two referenced code facts; "
                f"only {len(code_values)} were available"
            ), None

        lookup = reference_store.lookup_ncci_pair(
            code_values[0],
            code_values[1],
        )

        if lookup.status != LookupStatus.FOUND:
            return None, (
                f"No NCCI pair record found for codes "
                f"{code_values[0]!r}/{code_values[1]!r}"
            ), None

        source = reference_store.to_source(lookup)

        return (
            evaluate_source_authority(
                source,
                case_scope,
                ClaimType.CODING_BUNDLING,
            ),
            None,
            None,
        )

    if source_type == SourceType.CODE_DEFINITION:
        for code in code_values:
            lookup = reference_store.lookup_hcpcs(code)

            if lookup.status != LookupStatus.FOUND:
                lookup = reference_store.lookup_icd10(code)

            if lookup.status == LookupStatus.FOUND:
                source = reference_store.to_source(lookup)

                return (
                    evaluate_source_authority(
                        source,
                        case_scope,
                        ClaimType.DEFINITIONAL,
                    ),
                    None,
                    None,
                )

        return None, (
            f"No HCPCS/ICD-10 record found for any referenced code "
            f"{code_values!r}"
        ), None

    return None, (
        f"No deterministic lookup mechanism exists for source type "
        f"{source_type.value!r} in this bounded stage"
    ), None


_SYSTEM_PROMPT = (
    "You are a verification-planning component for a medical bill "
    "investigation. You will be given one hypothesis (a candidate "
    "explanation, NOT a conclusion) and its referenced facts. Propose "
    "which categories of reference source should be checked to verify "
    "or contextualize this hypothesis -- you do NOT decide whether the "
    "hypothesis is correct.\n"
    "\n"
    "Respond with JSON matching exactly this shape:\n"
    '{"hypothesis_id": "<the exact hypothesis_id given to you>", '
    '"proposed_source_types": ["<one or more of: PLAN_POLICY, EOB, '
    "CMS_MEDICARE, CMS_NCCI, CODE_DEFINITION, PUBLIC_REGULATORY, "
    'PROVIDER_BILL_LABEL, LLM_INTERPRETATION>"], '
    '"verification_rationale": "<why these source types are relevant>"}\n'
    "\n"
    "Rules:\n"
    "- hypothesis_id MUST exactly match the one given to you.\n"
    "- proposed_source_types MUST only use the exact category names "
    "listed above.\n"
    "- Do NOT include any other field. In particular, never include "
    "final_status, case_scope, authority, authority_level, "
    "authority_result, or appeal_eligible -- you have no authority to "
    "set any of those, and doing so will cause your entire output to "
    "be discarded.\n"
    "- You are proposing which categories to check, not deciding "
    "whether any source is authoritative.\n"
    "- Return ONLY the JSON object. No prose, no markdown fences."
)


def _build_user_content(investigation: Investigation, hypothesis) -> str:
    claim = next((c for c in investigation.ledger.claims if c.id == hypothesis.claim_id), None)
    claim_text = claim.statement if claim else "(claim not found)"
    lines = [
        f"hypothesis_id: {hypothesis.id}",
        f"claim: {claim_text}",
        f"explanation: {hypothesis.explanation_text}",
        "referenced facts:",
    ]
    facts_by_id = {f.id: f for f in investigation.ledger.facts}
    for fid in hypothesis.referenced_fact_ids:
        fact = facts_by_id.get(fid)
        if fact is not None:
            lines.append(f"- fact_id={fact.id} | type={fact.fact_type} | value={fact.value!r}")
    return "\n".join(lines)


def verify_hypothesis(
    investigation: Investigation,
    hypothesis_id: str,
    provider: LLMProvider,
    reference_store: ReferenceStore,
) -> VerificationIntegrationResult:
    if not isinstance(investigation, Investigation):
        raise VerificationIntegrationError(
            f"Expected Investigation, got {type(investigation).__name__}"
        )

    hypothesis = next((h for h in investigation.ledger.hypotheses if h.id == hypothesis_id), None)
    if hypothesis is None:
        return VerificationIntegrationResult(
            success=False, investigation_id=investigation.investigation_id,
            failure_stage="registration",
            failure_reason=f"No hypothesis with id {hypothesis_id!r} exists in this investigation's ledger.",
        )

    known_hypothesis_ids = {h.id for h in investigation.ledger.hypotheses}

    try:
        raw_text = provider.complete_json(_SYSTEM_PROMPT, _build_user_content(investigation, hypothesis))
    except LLMProviderError as exc:
        return VerificationIntegrationResult(
            success=False, investigation_id=investigation.investigation_id,
            failure_stage="provider", failure_reason=str(exc),
        )

    try:
        candidate = parse_verification_candidate(raw_text, known_hypothesis_ids=known_hypothesis_ids)
    except SchemaValidationError as exc:
        return VerificationIntegrationResult(
            success=False, investigation_id=investigation.investigation_id,
            failure_stage="validation", failure_reason=str(exc),
        )

    if candidate.hypothesis_id != hypothesis_id:
        return VerificationIntegrationResult(
            success=False, investigation_id=investigation.investigation_id,
            failure_stage="validation",
            failure_reason=(
                f"Verification candidate references hypothesis_id "
                f"{candidate.hypothesis_id!r}, expected {hypothesis_id!r}."
            ),
        )

    case_scope = _resolve_case_scope(investigation)
    code_values = _code_values_for_hypothesis(investigation, hypothesis)
    plan_id_values = _plan_id_values_for_hypothesis(
        investigation,
        hypothesis,
        reference_store,
    )
    patient_responsibility_cents = (
        _patient_responsibility_cents_for_hypothesis(
            investigation,
            hypothesis,
        )
    )
    service_dates = _service_dates_for_hypothesis(
        investigation,
        hypothesis,
    )

    decisions = []
    verification_ids = []
    missing_evidence_ids = []

    for source_type in candidate.proposed_source_types:
        (
            decision,
            missing_reason,
            corroboration_override,
        ) = _attempt_lookup(
            source_type,
            code_values,
            plan_id_values,
            patient_responsibility_cents,
            service_dates,
            case_scope,
            reference_store,
        )

        if decision is not None:
            decisions.append(decision)

            verification = Verification(
                hypothesis_id=hypothesis.id,
                corroboration_result=(
                    corroboration_override
                    if corroboration_override is not None
                    else _corroboration_result_for(decision)
                ),
                citation_ref=decision.source_id,
                authority_result=decision.result.value,
            )
            investigation.ledger.add_verification(verification)
            verification_ids.append(verification.id)
        else:
            missing = MissingEvidence(claim_id=hypothesis.claim_id, description=missing_reason)
            investigation.ledger.add_missing_evidence(missing)
            missing_evidence_ids.append(missing.id)

    conflict_ids = []
    for i in range(len(decisions)):
        for j in range(i + 1, len(decisions)):
            potential = flag_potential_conflict(decisions[i], decisions[j])
            if potential is not None:
                recorded = Conflict(
                    claim_id=hypothesis.claim_id,
                    source_a_id=potential.decision_a.source_id,
                    source_b_id=potential.decision_b.source_id,
                    what_each_says=(
                        f"{potential.decision_a.source_type.value}: {potential.decision_a.rationale} | "
                        f"{potential.decision_b.source_type.value}: {potential.decision_b.rationale}"
                    ),
                    why_unresolved=(
                        "Both sources are independently usable (AUTHORITATIVE/CORROBORATING) "
                        "for the same claim; this bounded stage does not resolve "
                        "content-level disagreement between them."
                    ),
                )
                investigation.ledger.add_conflict(recorded)
                conflict_ids.append(recorded.id)

    return VerificationIntegrationResult(
        success=True,
        investigation_id=investigation.investigation_id,
        hypothesis_id=hypothesis.id,
        verification_ids=tuple(verification_ids),
        missing_evidence_ids=tuple(missing_evidence_ids),
        conflict_ids=tuple(conflict_ids),
    )
