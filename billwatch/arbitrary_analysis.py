"""Input-driven BillWatch analysis.

This module is the public-product path for arbitrary bill text. It keeps the
existing LLM boundary for extraction, then performs deterministic, bounded
code-pair analysis. It deliberately reports potential issues and missing
context instead of claiming that a bill is definitely wrong or definitely
clean.
"""

from dataclasses import dataclass, field
from datetime import date
from itertools import combinations
import json
import re
from typing import Optional

from .enums import CaseScopeValue
from .evidence import Document
from .extraction import extract_from_document
from .llm_provider import LLMProvider
from .reference_data import LookupStatus, ReferenceStore


MAX_BILL_TEXT_CHARS = 100_000
MAX_CODES_FOR_PAIR_ANALYSIS = 40

_BILLING_CODE_SHAPE = r"(?:[0-9]{5}|[A-V][0-9]{4}|[0-9]{4}[A-Z])"
_EXPLICIT_CODE_PATTERNS = (
    re.compile(
        rf"\b(?:CPT|HCPCS|CODE(?:S)?)\s*[:#-]?\s*({_BILLING_CODE_SHAPE})(?![A-Za-z0-9])",
        re.IGNORECASE,
    ),
)
_UNLABELED_CODE_PATTERN = re.compile(
    rf"(?<![A-Za-z0-9])({_BILLING_CODE_SHAPE})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_BILLING_LINE_HINTS = re.compile(
    r"\b(?:cpt|hcpcs|code|procedure|service|office|visit|diagnostic|surgery|item|description)\b",
    re.IGNORECASE,
)
_DATE_PATTERN = re.compile(r"\b(?:20[0-9]{2}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/20[0-9]{2})\b")
_AMOUNT_PATTERN = re.compile(r"\$[0-9][0-9,]*(?:\.[0-9]{2})?")


def _json_string(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _extract_document_payload(user_content: str):
    document_match = re.search(r"document_id:\s*(\S+)", user_content)
    text_match = re.search(
        r"-----BEGIN DOCUMENT TEXT-----\n(.*?)\n-----END DOCUMENT TEXT-----",
        user_content,
        re.DOTALL,
    )
    if not document_match or not text_match:
        raise ValueError("document extraction prompt did not contain the expected payload")
    return document_match.group(1), text_match.group(1)


def _code_candidates(raw_text: str):
    """Return unique (code, exact source span) candidates in document order."""
    candidates = []
    seen_values = set()
    for pattern in _EXPLICIT_CODE_PATTERNS:
        for match in pattern.finditer(raw_text):
            value = match.group(1).upper()
            span = match.group(0)
            if value not in seen_values:
                seen_values.add(value)
                candidates.append((match.start(), value, span))
    for match in _UNLABELED_CODE_PATTERN.finditer(raw_text):
        line_start = raw_text.rfind("\n", 0, match.start()) + 1
        line_end = raw_text.find("\n", match.end())
        if line_end < 0:
            line_end = len(raw_text)
        line = raw_text[line_start:line_end]
        # An unlabeled code-shaped token is accepted only when its line looks
        # like an itemized billing line. This avoids mistaking claim IDs,
        # phone numbers, ZIP codes, or account numbers for procedure codes.
        if not _BILLING_LINE_HINTS.search(line):
            continue
        value = match.group(1)
        if value not in seen_values:
            seen_values.add(value)
            candidates.append((match.start(), value, match.group(0)))
    return [(value, span) for _, value, span in sorted(candidates, key=lambda item: item[0])]


class InputDrivenMockProvider(LLMProvider):
    """Deterministic offline extractor that reads the submitted bill.

    This is intentionally input-driven; it never returns the old fixed demo
    codes. It makes local demos and tests useful without pretending that a
    live Gemini call occurred.
    """

    def __init__(self):
        self.calls = []

    def complete_json(self, system_prompt: str, user_content: str) -> str:
        self.calls.append((system_prompt, user_content))
        document_id, raw_text = _extract_document_payload(user_content)
        facts = []
        for value, span in _code_candidates(raw_text):
            facts.append({"fact_type": "code", "value": value, "source_span": span})
        for match in _DATE_PATTERN.finditer(raw_text):
            facts.append({"fact_type": "date", "value": match.group(0), "source_span": match.group(0)})
        for match in _AMOUNT_PATTERN.finditer(raw_text):
            facts.append({"fact_type": "amount", "value": match.group(0), "source_span": match.group(0)})
        return _json_string({"document_id": document_id, "extracted_facts": facts})


@dataclass(frozen=True)
class AnalysisContext:
    payer_scope: CaseScopeValue = CaseScopeValue.UNKNOWN
    service_date: Optional[date] = None
    same_date_confirmed: Optional[bool] = None
    same_beneficiary_confirmed: Optional[bool] = None
    modifiers: tuple = ()
    claim_status: Optional[str] = None


@dataclass(frozen=True)
class PairFinding:
    code_a: str
    code_b: str
    status: str
    summary: str
    missing_context: tuple = ()
    reference: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "code_a": self.code_a,
            "code_b": self.code_b,
            "status": self.status,
            "summary": self.summary,
            "missing_context": list(self.missing_context),
            "reference": self.reference,
        }


@dataclass(frozen=True)
class ArbitraryAnalysisResult:
    success: bool
    status: str
    document_id: str
    facts: tuple = ()
    findings: tuple = ()
    missing_context: tuple = ()
    review_note: Optional[str] = None
    failure_reason: Optional[str] = None
    gemini_mode: str = "offline_mock"
    analysis_mode: str = "standard"
    completed_stages: tuple = ()
    missing_context_fields: tuple = ()
    blocking_context: tuple = ()
    can_resume: bool = False

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "status": self.status,
            "document_id": self.document_id,
            "facts": list(self.facts),
            "findings": [finding.to_dict() for finding in self.findings],
            "missing_context": list(self.missing_context),
            "review_note": self.review_note,
            "failure_reason": self.failure_reason,
            "gemini_mode": self.gemini_mode,
            "analysis_mode": self.analysis_mode,
            "completed_stages": list(self.completed_stages),
            "missing_context_fields": list(self.missing_context_fields),
            "blocking_context": list(self.blocking_context),
            "can_resume": self.can_resume,
        }


def parse_analysis_context(payload: dict) -> AnalysisContext:
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")

    raw_scope = str(payload.get("payer_scope", "unknown")).strip().lower()
    aliases = {
        "private": CaseScopeValue.PRIVATE_COMMERCIAL,
        "commercial": CaseScopeValue.PRIVATE_COMMERCIAL,
        "private_commercial": CaseScopeValue.PRIVATE_COMMERCIAL,
        "medicare": CaseScopeValue.MEDICARE,
        "medicaid": CaseScopeValue.MEDICAID,
        "unknown": CaseScopeValue.UNKNOWN,
        "": CaseScopeValue.UNKNOWN,
    }
    if raw_scope not in aliases:
        raise ValueError("payer_scope must be medicare, medicaid, private_commercial, or unknown")

    parsed_date = None
    raw_date = payload.get("service_date")
    if raw_date:
        try:
            parsed_date = date.fromisoformat(str(raw_date))
        except ValueError as exc:
            raise ValueError("service_date must use YYYY-MM-DD format") from exc

    def optional_bool(name):
        value = payload.get(name)
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        raise ValueError(f"{name} must be true, false, or omitted")

    raw_modifiers = payload.get("modifiers", [])
    if isinstance(raw_modifiers, str):
        modifiers = tuple(x.strip().upper() for x in raw_modifiers.split(",") if x.strip())
    elif isinstance(raw_modifiers, list) and all(isinstance(x, str) for x in raw_modifiers):
        modifiers = tuple(x.strip().upper() for x in raw_modifiers if x.strip())
    else:
        raise ValueError("modifiers must be a comma-separated string or list of strings")

    claim_status = payload.get("claim_status")
    if claim_status is not None and not isinstance(claim_status, str):
        raise ValueError("claim_status must be text when supplied")

    return AnalysisContext(
        payer_scope=aliases[raw_scope],
        service_date=parsed_date,
        same_date_confirmed=optional_bool("same_date_confirmed"),
        same_beneficiary_confirmed=optional_bool("same_beneficiary_confirmed"),
        modifiers=modifiers,
        claim_status=claim_status.strip() if claim_status else None,
    )


def _reference_metadata(reference_store: ReferenceStore, lookup) -> Optional[dict]:
    if lookup.record is None:
        return None
    record = lookup.record
    snapshot = reference_store.get_current_snapshot("ncci_ptp")
    return {
        "dataset": "ncci_ptp",
        "version": snapshot.version if snapshot else None,
        "source": getattr(record, "source", None),
        "source_url": getattr(record, "source_url", None),
        "effective_date": getattr(record, "effective_date", None).isoformat()
        if getattr(record, "effective_date", None) else None,
        "retrieval_date": getattr(record, "retrieval_date", None).isoformat()
        if getattr(record, "retrieval_date", None) else None,
        "license_basis": getattr(record, "license_basis", None),
        "relationship_verified": getattr(record, "relationship_verified", None),
        "column_one": getattr(record, "code_a", None),
        "column_two": getattr(record, "code_b", None),
        "claim_setting": getattr(record, "claim_setting", None),
        "deletion_date": getattr(record, "deletion_date", None).isoformat()
        if getattr(record, "deletion_date", None) else None,
        "source_file": getattr(record, "source_file", None),
        "source_sha256": getattr(record, "source_sha256", None),
        "lookup_status": lookup.status.value,
    }


def _fact_dicts(document: Document, accepted_facts, raw_text: str) -> list:
    facts = [
        {
            "fact_type": fact.fact_type,
            "value": fact.value,
            "source_span": fact.source_span,
            "confidence": fact.confidence,
            "origin": "model_extraction",
        }
        for fact in accepted_facts
    ]
    known = {(item["fact_type"], item["value"], item["source_span"]) for item in facts}
    for value, span in _code_candidates(raw_text):
        key = ("code", value, span)
        if key not in known:
            facts.append({
                "fact_type": "code",
                "value": value,
                "source_span": span,
                "confidence": "deterministic candidate scan",
                "origin": "deterministic_code_scan",
            })
            known.add(key)
    return facts


def _required_context(context: AnalysisContext) -> list:
    missing = []
    if context.payer_scope == CaseScopeValue.UNKNOWN:
        missing.append("payer/program")
    if context.service_date is None:
        missing.append("service date")
    if context.same_date_confirmed is not True:
        missing.append("confirmation that the services share the same date of service")
    if context.same_beneficiary_confirmed is not True:
        missing.append("confirmation that the services belong to the same beneficiary/claim context")
    return missing


_CONTEXT_FIELD_DETAILS = {
    "payer_scope": {
        "label": "Payer or program",
        "reason": "The payer or program determines which bounded reference scope can apply.",
    },
    "service_date": {
        "label": "Service date",
        "reason": "A reference must be effective on the service date before it can be applied.",
    },
    "modifiers": {
        "label": "Modifiers",
        "reason": "A modifier shown on the claim may change whether a pair rule applies.",
    },
    "same_date_confirmed": {
        "label": "Same date confirmation",
        "reason": "The pair check requires confirmation that the services share a date.",
    },
    "same_beneficiary_confirmed": {
        "label": "Same beneficiary or claim confirmation",
        "reason": "The pair check requires confirmation that both items belong to the same beneficiary or claim context.",
    },
    "claim_status": {
        "label": "Claim or EOB status",
        "reason": "The current claim or EOB status may be needed to interpret the review boundary.",
    },
}


def _context_field_for_missing_item(item: str) -> Optional[str]:
    normalized = str(item).strip().lower()
    if "payer/program" in normalized:
        return "payer_scope"
    if normalized.startswith("service date"):
        return "service_date"
    if "same date" in normalized or "share the same date" in normalized:
        return "same_date_confirmed"
    if "same beneficiary" in normalized or "beneficiary/claim" in normalized:
        return "same_beneficiary_confirmed"
    if "modifier" in normalized:
        return "modifiers"
    if "claim status" in normalized or "eob status" in normalized:
        return "claim_status"
    return None


def classify_missing_context_items(items) -> tuple:
    """Split existing plain-language gaps into resumable fields and blockers."""
    fields = []
    blockers = []
    seen_fields = set()
    seen_blockers = set()
    for item in items:
        reason = str(item).strip()
        if not reason:
            continue
        field_name = _context_field_for_missing_item(reason)
        if field_name is not None:
            if field_name in seen_fields:
                continue
            seen_fields.add(field_name)
            details = _CONTEXT_FIELD_DETAILS[field_name]
            fields.append({
                "field": field_name,
                "label": details["label"],
                "reason": details["reason"],
            })
            continue
        if reason not in seen_blockers:
            seen_blockers.add(reason)
            blockers.append({"reason": reason})
    return tuple(fields), tuple(blockers)


def _result_context_metadata(findings, global_missing) -> tuple:
    items = list(global_missing)
    for finding in findings:
        items.extend(finding.missing_context)
    return classify_missing_context_items(items)


def _make_review_note(findings: list, codes: list) -> Optional[str]:
    potential = [f for f in findings if f.status == "POTENTIAL_DISCREPANCY"]
    if not potential:
        return None
    pairs = ", ".join(f"{f.code_a}/{f.code_b}" for f in potential)
    return (
        "Human-review summary: BillWatch identified a potential coding-rule "
        f"issue involving {pairs}. This is not a determination that the bill "
        "is incorrect. Review the original bill, payer rules, modifiers, "
        "claim context, and explanation of benefits before contacting the payer."
    )


def analyze_bill(
    raw_text: str,
    context: AnalysisContext,
    provider: LLMProvider,
    reference_store: ReferenceStore,
    gemini_mode: str = "offline_mock",
) -> ArbitraryAnalysisResult:
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("bill text must be non-empty")
    if len(raw_text) > MAX_BILL_TEXT_CHARS:
        raise ValueError(f"bill text exceeds the {MAX_BILL_TEXT_CHARS:,}-character limit")
    candidate_count = len(_code_candidates(raw_text))
    if candidate_count > MAX_CODES_FOR_PAIR_ANALYSIS:
        return ArbitraryAnalysisResult(
            success=False,
            status="INPUT_LIMIT",
            document_id="",
            failure_reason=(
                f"The bill contains {candidate_count} candidate codes; "
                f"pair analysis is limited to {MAX_CODES_FOR_PAIR_ANALYSIS} codes per request."
            ),
            gemini_mode=gemini_mode,
            completed_stages=("bill_received",),
        )

    document = Document(doc_type="bill", raw_text=raw_text)
    extraction = extract_from_document(document, provider)
    if not extraction.success or extraction.candidate is None:
        return ArbitraryAnalysisResult(
            success=False,
            status="EXTRACTION_FAILED",
            document_id=document.id,
            failure_reason=extraction.failure_reason or "bill extraction failed",
            gemini_mode=gemini_mode,
            completed_stages=("bill_received",),
        )

    facts = _fact_dicts(document, extraction.candidate.accepted_facts, raw_text)
    codes = []
    for fact in facts:
        if fact["fact_type"] == "code" and fact["value"] not in codes:
            codes.append(fact["value"])

    pairs = list(combinations(codes, 2))
    findings = []
    global_missing = []
    if len(codes) < 2:
        global_missing.append("at least two candidate billing codes for pair analysis")

    for code_a, code_b in pairs:
        lookup = reference_store.lookup_ncci_pair(
            code_a,
            code_b,
            as_of=context.service_date,
        )
        reference = _reference_metadata(reference_store, lookup)

        if lookup.status == LookupStatus.FOUND:
            record_verified = getattr(lookup.record, "relationship_verified", True) is True
            modifier_indicator = str(getattr(lookup.record, "modifier_indicator", "")).strip()
            if not record_verified:
                status = "REFERENCE_UNVERIFIED"
                summary = (
                    "A matching reference record exists, but this local snapshot "
                    "has not been independently verified against the official file. "
                    "BillWatch will not use it to label the bill incorrect."
                )
                missing = ("an independently verified reference snapshot effective on the service date",)
            elif modifier_indicator == "9":
                status = "NO_MATCHING_RULE"
                summary = (
                    "The reference record is marked not applicable by its modifier indicator; "
                    "it is not treated as an active edit."
                )
                missing = ()
            elif modifier_indicator == "1" and not context.modifiers:
                status = "INSUFFICIENT_CONTEXT"
                summary = (
                    "The reference record allows a possible modifier override, but no modifier "
                    "was supplied to evaluate whether the edit would be bypassed."
                )
                missing = ("modifiers shown on the original claim",)
            elif context.payer_scope == CaseScopeValue.MEDICAID:
                status = "INSUFFICIENT_CONTEXT"
                summary = "A Medicare NCCI snapshot was found, but Medicaid requires Medicaid-specific reference data."
                missing = ("Medicaid-specific NCCI reference source",)
            elif context.payer_scope == CaseScopeValue.PRIVATE_COMMERCIAL:
                status = "INSUFFICIENT_CONTEXT"
                summary = "The pair matches a Medicare NCCI snapshot, but private-plan adoption was not established."
                missing = ("plan policy showing whether this methodology applies",)
            elif context.payer_scope == CaseScopeValue.UNKNOWN:
                status = "INSUFFICIENT_CONTEXT"
                summary = "A matching reference was found, but the payer/program is unknown."
                missing = ("payer/program",)
            else:
                missing = tuple(_required_context(context))
                if missing:
                    status = "INSUFFICIENT_CONTEXT"
                    summary = "A matching Medicare NCCI reference was found, but required claim context is missing."
                else:
                    status = "POTENTIAL_DISCREPANCY"
                    summary = (
                        "The pair matches the loaded Medicare NCCI reference under the supplied context. "
                        "This is a potential issue for human review, not proof of an incorrect bill. "
                        f"The reference modifier indicator is {modifier_indicator or 'not supplied'}."
                    )
            findings.append(PairFinding(code_a, code_b, status, summary, tuple(missing), reference))
        elif lookup.status == LookupStatus.OUTSIDE_EFFECTIVE_PERIOD:
            findings.append(PairFinding(
                code_a,
                code_b,
                "INSUFFICIENT_CONTEXT",
                "A reference record exists, but it is outside the supplied service-date period.",
                ("a reference snapshot effective on the service date",),
                reference,
            ))
        else:
            findings.append(PairFinding(
                code_a,
                code_b,
                "NO_MATCHING_RULE",
                "No matching NCCI pair was found in the loaded reference snapshot; this does not prove the bill is error-free.",
                (),
                reference,
            ))

    statuses = {finding.status for finding in findings}
    if "POTENTIAL_DISCREPANCY" in statuses:
        overall_status = "POTENTIAL_DISCREPANCY"
    elif "INSUFFICIENT_CONTEXT" in statuses or global_missing:
        overall_status = "INSUFFICIENT_CONTEXT"
    elif findings and statuses == {"NO_MATCHING_RULE"}:
        overall_status = "NO_SUPPORTED_DISCREPANCY_FOUND"
    else:
        overall_status = "INSUFFICIENT_CONTEXT"

    completed_stages = [
        "bill_received",
        "facts_extracted",
        "pairs_generated",
    ]
    if pairs:
        completed_stages.append("references_checked")
    completed_stages.append("context_evaluated")
    missing_context_fields, blocking_context = _result_context_metadata(
        findings,
        global_missing,
    )

    return ArbitraryAnalysisResult(
        success=True,
        status=overall_status,
        document_id=document.id,
        facts=tuple(facts),
        findings=tuple(findings),
        missing_context=tuple(global_missing),
        review_note=_make_review_note(findings, codes),
        gemini_mode=gemini_mode,
        completed_stages=tuple(completed_stages),
        missing_context_fields=missing_context_fields,
        blocking_context=blocking_context,
        can_resume=bool(missing_context_fields),
    )
