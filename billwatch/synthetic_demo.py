"""Isolated, deterministic evidence for the public BillWatch Hackathon Demo.

Nothing in this module is CPT, HCPCS, CMS, AMA, payer, insurer, or clinical
data.  The identifiers and the single rule are author-written synthetic
content.  Ordinary medical-bill analysis never imports or consults them.
"""

from dataclasses import dataclass
from datetime import date
import hashlib
import hmac
import json
import re

from .arbitrary_analysis import (
    AnalysisContext,
    ArbitraryAnalysisResult,
    MAX_BILL_TEXT_CHARS,
    PairFinding,
    classify_missing_context_items,
)
from .evidence import Document


HACKATHON_DEMO_MODE = "hackathon_synthetic_v1"
SYNTHETIC_SAMPLE_BILL = (
    "BILLWATCH HACKATHON DEMO - AUTHOR-WRITTEN SYNTHETIC CONTENT\n"
    "Demo identifier BW-DEMO-001 - synthetic review item - $40.00\n"
    "Demo identifier BW-DEMO-002 - synthetic review item - $25.00\n"
    "These are demonstration identifiers, not medical billing codes."
)


@dataclass(frozen=True)
class SyntheticPairRule:
    dataset: str
    code_a: str
    code_b: str
    relationship: str
    source: str
    source_url: str
    version: str
    effective_date: date
    end_date: date
    retrieval_date: date
    relationship_verified: bool
    license_basis: str
    scope: str


PUBLIC_SYNTHETIC_RULES = (
    SyntheticPairRule(
        dataset="billwatch_hackathon_demo",
        code_a="BW-DEMO-001",
        code_b="BW-DEMO-002",
        relationship="author_written_synthetic_pair_review_signal",
        source="BillWatch Hackathon Demo - author-written synthetic rule",
        source_url="internal://billwatch/hackathon-demo/author-written-rule",
        version="bw-hackathon-demo-v1",
        effective_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        retrieval_date=date(2026, 8, 29),
        relationship_verified=True,
        license_basis="author_written_synthetic_demo",
        scope="billwatch_hackathon_demo_only",
    ),
)

# This value is deliberately recorded rather than generated at import time.
# If any canonical rule field changes without a deliberate checksum update,
# the demo fails closed as REFERENCE_UNVERIFIED.
PUBLIC_SYNTHETIC_RULE_SOURCE_SHA256 = (
    "b73de295128e2f9e4bb2b8e5e77dd50271b672059ba641ac38936414ca5b2610"
)

_IDENTIFIER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9-])(?:BW-DEMO-001|BW-DEMO-002)(?![A-Za-z0-9-])"
)


def _canonical_rule_payload(rule: SyntheticPairRule) -> dict:
    return {
        "dataset": rule.dataset,
        "code_a": rule.code_a,
        "code_b": rule.code_b,
        "relationship": rule.relationship,
        "source": rule.source,
        "source_url": rule.source_url,
        "version": rule.version,
        "effective_date": rule.effective_date.isoformat(),
        "end_date": rule.end_date.isoformat(),
        "retrieval_date": rule.retrieval_date.isoformat(),
        "relationship_verified": rule.relationship_verified,
        "license_basis": rule.license_basis,
        "scope": rule.scope,
    }


def rule_source_sha256(rule: SyntheticPairRule) -> str:
    canonical = json.dumps(
        _canonical_rule_payload(rule),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def rule_integrity_is_valid(rule: SyntheticPairRule) -> bool:
    return hmac.compare_digest(
        rule_source_sha256(rule),
        PUBLIC_SYNTHETIC_RULE_SOURCE_SHA256,
    )


def _identifier_facts(raw_text: str) -> tuple:
    facts = []
    seen = set()
    for match in _IDENTIFIER_PATTERN.finditer(raw_text):
        value = match.group(0)
        if value in seen:
            continue
        seen.add(value)
        facts.append({
            "fact_type": "code",
            "value": value,
            "source_span": value,
            "confidence": "deterministic exact synthetic identifier match",
            "origin": "synthetic_demo_identifier_scan",
        })
    return tuple(facts)


def _reference_metadata(rule: SyntheticPairRule, integrity_verified: bool) -> dict:
    return {
        "dataset": rule.dataset,
        "version": rule.version,
        "relationship": rule.relationship,
        "source": rule.source,
        "source_url": rule.source_url,
        "effective_date": rule.effective_date.isoformat(),
        "end_date": rule.end_date.isoformat(),
        "retrieval_date": rule.retrieval_date.isoformat(),
        "license_basis": rule.license_basis,
        "scope": rule.scope,
        "scope_label": "BillWatch Hackathon Demo only",
        "relationship_verified": rule.relationship_verified,
        "integrity_verified": integrity_verified,
        "source_sha256": PUBLIC_SYNTHETIC_RULE_SOURCE_SHA256,
        "column_one": rule.code_a,
        "column_two": rule.code_b,
        "lookup_status": "found" if integrity_verified else "reference_unverified",
        "synthetic_notice": (
            "Author-written synthetic demo evidence; not CPT, HCPCS, CMS, AMA, "
            "payer, insurer, or clinical data."
        ),
    }


def _missing_context(context: AnalysisContext) -> tuple:
    missing = []
    if context.service_date is None:
        missing.append("service date for the synthetic rule effective-period check")
    if context.same_date_confirmed is not True:
        missing.append("confirmation that the synthetic demo items share the same date")
    if context.same_beneficiary_confirmed is not True:
        missing.append(
            "confirmation that the synthetic demo items share the same beneficiary/claim context"
        )
    return tuple(missing)


def _workflow_metadata(missing_items, completed_stages) -> dict:
    missing_fields, blockers = classify_missing_context_items(missing_items)
    return {
        "analysis_mode": HACKATHON_DEMO_MODE,
        "completed_stages": tuple(completed_stages),
        "missing_context_fields": missing_fields,
        "blocking_context": blockers,
        "can_resume": bool(missing_fields),
    }


def _result_without_pair(document_id: str, facts: tuple) -> ArbitraryAnalysisResult:
    missing = ("both exact synthetic identifiers BW-DEMO-001 and BW-DEMO-002",)
    return ArbitraryAnalysisResult(
        success=True,
        status="INSUFFICIENT_CONTEXT",
        document_id=document_id,
        facts=facts,
        findings=(),
        missing_context=missing,
        gemini_mode="deterministic_synthetic_demo",
        **_workflow_metadata(
            missing,
            ("bill_received", "facts_extracted", "pairs_generated", "context_evaluated"),
        ),
    )


def analyze_synthetic_bill(
    raw_text: str,
    context: AnalysisContext,
    *,
    demo_mode,
) -> ArbitraryAnalysisResult:
    """Analyze only the explicitly selected, author-written demo pair."""
    if not isinstance(demo_mode, str) or demo_mode != HACKATHON_DEMO_MODE:
        raise ValueError(
            f"demo_mode must be exactly {HACKATHON_DEMO_MODE!r} for the Hackathon Demo"
        )
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("bill text must be non-empty")
    if len(raw_text) > MAX_BILL_TEXT_CHARS:
        raise ValueError(
            f"bill text exceeds the {MAX_BILL_TEXT_CHARS:,}-character limit"
        )

    document = Document(doc_type="bill", raw_text=raw_text)
    facts = _identifier_facts(raw_text)
    identifiers = {fact["value"] for fact in facts}
    expected_identifiers = {"BW-DEMO-001", "BW-DEMO-002"}
    if identifiers != expected_identifiers:
        return _result_without_pair(document.id, facts)

    if len(PUBLIC_SYNTHETIC_RULES) != 1:
        finding = PairFinding(
            "BW-DEMO-001",
            "BW-DEMO-002",
            "REFERENCE_UNVERIFIED",
            "The public demo rule set is not exactly one immutable rule, so BillWatch stopped.",
            ("exactly one verified author-written synthetic demo rule",),
            None,
        )
        return ArbitraryAnalysisResult(
            success=True,
            status="INSUFFICIENT_CONTEXT",
            document_id=document.id,
            facts=facts,
            findings=(finding,),
            gemini_mode="deterministic_synthetic_demo",
            **_workflow_metadata(
                finding.missing_context,
                (
                    "bill_received",
                    "facts_extracted",
                    "pairs_generated",
                    "references_checked",
                    "context_evaluated",
                ),
            ),
        )

    rule = PUBLIC_SYNTHETIC_RULES[0]
    integrity_verified = rule_integrity_is_valid(rule)
    reference = _reference_metadata(rule, integrity_verified)
    if (
        {rule.code_a, rule.code_b} != expected_identifiers
        or not rule.relationship_verified
        or not integrity_verified
    ):
        finding = PairFinding(
            "BW-DEMO-001",
            "BW-DEMO-002",
            "REFERENCE_UNVERIFIED",
            (
                "The author-written synthetic rule did not pass its identity, "
                "verification, and checksum gates, so it cannot support a finding."
            ),
            ("verified synthetic-rule identity and integrity",),
            reference,
        )
        return ArbitraryAnalysisResult(
            success=True,
            status="INSUFFICIENT_CONTEXT",
            document_id=document.id,
            facts=facts,
            findings=(finding,),
            gemini_mode="deterministic_synthetic_demo",
            **_workflow_metadata(
                finding.missing_context,
                (
                    "bill_received",
                    "facts_extracted",
                    "pairs_generated",
                    "references_checked",
                    "context_evaluated",
                ),
            ),
        )

    missing = _missing_context(context)
    if context.service_date is not None and not (
        rule.effective_date <= context.service_date <= rule.end_date
    ):
        finding = PairFinding(
            rule.code_a,
            rule.code_b,
            "INSUFFICIENT_CONTEXT",
            (
                "The author-written synthetic rule is outside its stated effective "
                "period for the supplied service date, so it was not applied."
            ),
            ("a service date within the synthetic rule effective period",),
            {**reference, "lookup_status": "outside_effective_period"},
        )
        return ArbitraryAnalysisResult(
            success=True,
            status="INSUFFICIENT_CONTEXT",
            document_id=document.id,
            facts=facts,
            findings=(finding,),
            gemini_mode="deterministic_synthetic_demo",
            **_workflow_metadata(
                finding.missing_context,
                (
                    "bill_received",
                    "facts_extracted",
                    "pairs_generated",
                    "references_checked",
                    "context_evaluated",
                ),
            ),
        )

    if missing:
        finding = PairFinding(
            rule.code_a,
            rule.code_b,
            "INSUFFICIENT_CONTEXT",
            (
                "The author-written synthetic pair matched, but BillWatch paused "
                "because required context has not been confirmed."
            ),
            missing,
            reference,
        )
        return ArbitraryAnalysisResult(
            success=True,
            status="INSUFFICIENT_CONTEXT",
            document_id=document.id,
            facts=facts,
            findings=(finding,),
            gemini_mode="deterministic_synthetic_demo",
            **_workflow_metadata(
                finding.missing_context,
                (
                    "bill_received",
                    "facts_extracted",
                    "pairs_generated",
                    "references_checked",
                    "context_evaluated",
                ),
            ),
        )

    finding = PairFinding(
        rule.code_a,
        rule.code_b,
        "POTENTIAL_DISCREPANCY",
        (
            "Every deterministic gate for the author-written synthetic demo rule passed. "
            "This is a bounded review signal, not proof that any bill is incorrect."
        ),
        (),
        reference,
    )
    return ArbitraryAnalysisResult(
        success=True,
        status="POTENTIAL_DISCREPANCY",
        document_id=document.id,
        facts=facts,
        findings=(finding,),
        review_note=(
            "Human-review summary: the author-written synthetic demo pair passed "
            "its explicit context and integrity gates. This is not a determination "
            "that a real bill is incorrect, and no external action was taken."
        ),
        gemini_mode="deterministic_synthetic_demo",
        **_workflow_metadata(
            (),
            (
                "bill_received",
                "facts_extracted",
                "pairs_generated",
                "references_checked",
                "context_evaluated",
            ),
        ),
    )


__all__ = (
    "HACKATHON_DEMO_MODE",
    "PUBLIC_SYNTHETIC_RULES",
    "PUBLIC_SYNTHETIC_RULE_SOURCE_SHA256",
    "SYNTHETIC_SAMPLE_BILL",
    "SyntheticPairRule",
    "analyze_synthetic_bill",
    "rule_integrity_is_valid",
    "rule_source_sha256",
)
