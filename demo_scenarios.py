"""
BillWatch judge-facing demo -- all four real deterministic outcomes.

DEMO/OFFLINE MODE by default: uses MockLLMProvider, no network, no
GEMINI_API_KEY required, fully repeatable. If GEMINI_API_KEY is set,
each scenario runs against the real, live GenAISDKProvider instead --
clearly labeled either way. Every outcome below is produced by the
real, unmodified pipeline.run_investigation() and the real
adjudication_integration.py decision engine -- none of these results
are faked or hardcoded for presentation.

Each scenario is built only from data that genuinely exists in the
bootstrap reference dataset (reference_bootstrap.py) -- no invented
lookups, no shortcuts around the real deterministic machinery.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from billwatch import Document, Investigation
from billwatch.case_scope import CaseScope
from billwatch.enums import CaseScopeValue, ScopeProvenance, ValidationResult
from billwatch.llm_provider import MockLLMProvider
from billwatch.reference_bootstrap import load_bootstrap_data
from billwatch.reference_data import ReferenceStore
from billwatch.pipeline import run_investigation


def _mode_label():
    return "LIVE GEMINI" if os.environ.get("GEMINI_API_KEY") else "DEMO/OFFLINE MODE (MockLLMProvider, no network, no key required)"


def _get_provider(doc, hypothesis_json, verification_json, appeal_text=None):
    """Builds a provider. If GEMINI_API_KEY is set, uses the real
    GenAISDKProvider (Gemini genuinely decides its own wording for
    extraction/hypothesis/verification/appeal -- never the final
    status). Otherwise a deterministic MockLLMProvider dispatcher."""
    if os.environ.get("GEMINI_API_KEY"):
        from billwatch.genai_sdk_provider import GenAISDKProvider
        return GenAISDKProvider()

    def dispatch(system_prompt, user_content):
        if "document-extraction component" in system_prompt:
            # Document is frozen by design. Read codes from the actual
            # document text instead of attaching a mutable private field.
            codes = re.findall(r"\b\d{5}\b", doc.raw_text)
            return json.dumps({"document_id": doc.id, "extracted_facts": [
                {"fact_type": "code", "value": v, "source_span": v} for v in codes
            ]})
        if "hypothesis-proposal component" in system_prompt:
            fact_ids = re.findall(r"fact_id=([0-9a-fA-F-]+)", user_content)
            return json.dumps(hypothesis_json(fact_ids))
        if "verification-planning component" in system_prompt:
            m = re.search(r"hypothesis_id:\s*(\S+)", user_content)
            return json.dumps(verification_json(m.group(1) if m else ""))
        if "appeal-drafting component" in system_prompt:
            m = re.search(r"claim_id:\s*(\S+)", user_content)
            fact_ids = re.findall(r"fact_id=([0-9a-fA-F-]+)", user_content)
            return json.dumps({
                "draft_text": appeal_text or "Draft appeal citing the evidence above.",
                "cited_fact_ids": fact_ids,
                "cited_claim_ids": [m.group(1)] if m else [],
            })
        return "{}"
    return MockLLMProvider(response_fn=dispatch)


def _scope(value, established=True):
    if not established:
        return None
    return CaseScope(
        value=value, provenance=ScopeProvenance.USER_SELECTED,
        source_identifier="demo", validation_result=ValidationResult.PASS,
    )


def _make_doc(text, codes):
    # Document is frozen. Keep the codes argument for scenario readability,
    # but extraction comes from the actual raw document text.
    return Document(doc_type="bill", raw_text=text)


def _run_scenario(title, expectation, doc, case_scope, hyp_fn, ver_fn, appeal_text=None):
    print("=" * 70)
    print(title)
    print(f"Expected: {expectation}")
    print(f"Provider mode: {_mode_label()}")
    print("-" * 70)

    provider = _get_provider(doc, hyp_fn, ver_fn, appeal_text)
    store = ReferenceStore()
    load_bootstrap_data(store)
    investigation = Investigation()

    result = run_investigation(investigation, [doc], case_scope, provider, store)

    print(f"success: {result.success}")
    if not result.success:
        print(f"failed_stage: {result.failed_stage}")
        print(f"reason: {result.failure_reason}")
    else:
        print(f"final_status: {result.final_status.value.upper()}")
        if result.appeal and result.appeal.success:
            print("appeal: GENERATED")
            print(f"  draft: {result.appeal.draft_text}")
        else:
            print("appeal: NOT GENERATED (correctly withheld)")
    print()
    return result


def scenario_1_supported_discrepancy():
    doc = _make_doc(
        "Itemized bill: CPT/HCPCS codes 45378 and 45380 billed together, same date of service, $500.00.",
        ["45378", "45380"],
    )
    return _run_scenario(
        "SCENARIO 1 -- Legitimate supported discrepancy (Medicare, real NCCI bundling rule)",
        "SUPPORTED_DISCREPANCY, appeal permitted",
        doc,
        _scope(CaseScopeValue.MEDICARE),
        lambda fact_ids: {
            "claim_statement": "Possible improper unbundling",
            "explanation_text": "Codes 45378/45380 billed together; CMS NCCI treats these as bundled.",
            "referenced_fact_ids": fact_ids,
        },
        lambda hyp_id: {
            "hypothesis_id": hyp_id, "proposed_source_types": ["CMS_NCCI"],
            "verification_rationale": "Check CMS NCCI PTP bundling status.",
        },
        appeal_text="This is a request for human review of the billing for this claim. Codes 45378 and 45380 were billed together on the same date of service, totaling $500.00. Please review this claim to ensure billing accuracy.",
    )


def scenario_2_no_supported_discrepancy():
    doc = _make_doc(
        "Itemized bill: CPT/HCPCS codes 45378 and 45380 billed together. Governing plan/payer type not yet confirmed.",
        ["45378", "45380"],
    )
    return _run_scenario(
        "SCENARIO 2 -- System refuses to manufacture certainty without established scope",
        "NO_SUPPORTED_DISCREPANCY, no appeal (a real NCCI rule matched, but scope was never established -- BillWatch will not claim support on that basis alone)",
        doc,
        _scope(None, established=False),
        lambda fact_ids: {
            "claim_statement": "Possible bundling issue",
            "explanation_text": "Codes 45378/45380 billed together; checking bundling status.",
            "referenced_fact_ids": fact_ids,
        },
        lambda hyp_id: {
            "hypothesis_id": hyp_id, "proposed_source_types": ["CMS_NCCI"],
            "verification_rationale": "Check CMS NCCI PTP bundling status.",
        },
    )


def scenario_3_insufficient_evidence():
    doc = _make_doc(
        "Itemized bill: CPT/HCPCS code 45378 billed. Patient believes this relates to their specific plan's own coverage terms.",
        ["45378"],
    )
    return _run_scenario(
        "SCENARIO 3 -- Insufficient evidence (no automated way to check this source type yet)",
        "INSUFFICIENT_EVIDENCE, no appeal",
        doc,
        _scope(CaseScopeValue.MEDICARE),
        lambda fact_ids: {
            "claim_statement": "Possible plan-policy coverage issue",
            "explanation_text": "This may relate to the patient's specific plan policy terms.",
            "referenced_fact_ids": fact_ids,
        },
        lambda hyp_id: {
            "hypothesis_id": hyp_id, "proposed_source_types": ["PLAN_POLICY"],
            "verification_rationale": "Check the patient's actual plan policy document.",
        },
    )


def scenario_4_conflicting_evidence():
    doc = _make_doc(
        "Itemized bill: CPT/HCPCS codes 45378 and 45380 billed together, same date of service.",
        ["45378", "45380"],
    )
    return _run_scenario(
        "SCENARIO 4 -- Two independently usable sources disagree; BillWatch does not silently pick a winner",
        "CONFLICTING_EVIDENCE, no appeal",
        doc,
        _scope(CaseScopeValue.MEDICARE),
        lambda fact_ids: {
            "claim_statement": "Possible improper unbundling",
            "explanation_text": "Codes 45378/45380 billed together; checking bundling status from multiple angles.",
            "referenced_fact_ids": fact_ids,
        },
        lambda hyp_id: {
            "hypothesis_id": hyp_id, "proposed_source_types": ["CMS_NCCI", "CMS_NCCI"],
            "verification_rationale": "Check CMS NCCI PTP bundling status via two independent lookups.",
        },
    )


def scenario_5_alarming_text_has_no_effect():
    doc = _make_doc(
        "Itemized bill: code 45378 billed. MASSIVE FRAUD!!! Obvious overcharge, definitely wrong, I know they cheated me!!!",
        ["45378"],
    )
    return _run_scenario(
        "SCENARIO 5 -- Alarming wording in the bill/claim cannot force an adverse verdict",
        "NO_SUPPORTED_DISCREPANCY or INSUFFICIENT_EVIDENCE (never SUPPORTED_DISCREPANCY merely from alarming text)",
        doc,
        _scope(None, established=False),
        lambda fact_ids: {
            "claim_statement": "MASSIVE FRAUD, obvious overcharge, definitely wrong!!!",
            "explanation_text": "The wording is alarming, but this is still just a hypothesis to check.",
            "referenced_fact_ids": fact_ids,
        },
        lambda hyp_id: {
            "hypothesis_id": hyp_id, "proposed_source_types": ["CMS_NCCI"],
            "verification_rationale": "Check regardless of how alarming the wording is.",
        },
    )


def main():
    print("#" * 70)
    print("# BillWatch -- Judge-Facing Demo: Four Real Deterministic Outcomes")
    print("#" * 70)
    print()
    r1 = scenario_1_supported_discrepancy()
    r2 = scenario_2_no_supported_discrepancy()
    r3 = scenario_3_insufficient_evidence()
    r4 = scenario_4_conflicting_evidence()
    r5 = scenario_5_alarming_text_has_no_effect()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for label, r in [("1 (Supported)", r1), ("2 (No support)", r2),
                      ("3 (Insufficient)", r3), ("4 (Conflicting)", r4),
                      ("5 (Alarming text -> no forced verdict)", r5)]:
        status = r.final_status.value.upper() if r.success and r.final_status else "N/A"
        appeal = "YES" if (r.appeal and r.appeal.success) else "no"
        print(f"  Scenario {label}: {status}  (appeal generated: {appeal})")
    print()
    print("None of these outcomes were hardcoded -- each came from the real,")
    print("unmodified deterministic adjudication engine.")


if __name__ == "__main__":
    main()
