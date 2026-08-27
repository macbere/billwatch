"""
BillWatch end-to-end demo.

Runs one investigation through the full pipeline: a document containing
an NCCI-bundled code pair, under Medicare scope, produces a
SUPPORTED_DISCREPANCY result with a drafted appeal.

If GEMINI_API_KEY is set in the environment, this uses the real
GenAISDKProvider (a real Gemini call). Otherwise it falls back to a
MockLLMProvider so the demo always works offline, with no key required.
Never prints the API key itself either way.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from billwatch import Document, Investigation
from billwatch.case_scope import establish_from_user_selection
from billwatch.llm_provider import MockLLMProvider
from billwatch.reference_bootstrap import load_bootstrap_data
from billwatch.reference_data import ReferenceStore
from billwatch.pipeline import run_investigation


def _mock_dispatch_provider(doc):
    def dispatch(system_prompt, user_content):
        if "document-extraction component" in system_prompt:
            facts = [
                {"fact_type": "code", "value": "45378", "source_span": "45378"},
                {"fact_type": "code", "value": "45380", "source_span": "45380"},
            ]
            return json.dumps({"document_id": doc.id, "extracted_facts": facts})

        if "hypothesis-proposal component" in system_prompt:
            fact_ids = re.findall(r"fact_id=([0-9a-fA-F-]+)", user_content)
            return json.dumps({
                "claim_statement": "Possible improper unbundling of related procedures",
                "explanation_text": "Codes 45378 and 45380 were billed together; NCCI treats these as bundled.",
                "referenced_fact_ids": fact_ids,
            })

        if "verification-planning component" in system_prompt:
            hyp_match = re.search(r"hypothesis_id:\s*(\S+)", user_content)
            hyp_id = hyp_match.group(1) if hyp_match else ""
            return json.dumps({
                "hypothesis_id": hyp_id,
                "proposed_source_types": ["CMS_NCCI"],
                "verification_rationale": "Check CMS NCCI PTP bundling status for this code pair.",
            })

        if "appeal-drafting component" in system_prompt:
            claim_match = re.search(r"claim_id:\s*(\S+)", user_content)
            claim_id = claim_match.group(1) if claim_match else ""
            fact_ids = re.findall(r"fact_id=([0-9a-fA-F-]+)", user_content)
            return json.dumps({
                "draft_text": (
                    "This is a request for human review of the billing for claim "
                    + (claim_id or "") + ". Codes 45378 and 45380 were billed "
                    "together on the same date of service, totaling $500.00. "
                    "Please review this claim to ensure billing accuracy."
                ),
                "cited_fact_ids": fact_ids,
                "cited_claim_ids": [claim_id] if claim_id else [],
            })

        return "{}"

    return MockLLMProvider(response_fn=dispatch)


def main():
    print("=" * 60)
    print("BillWatch -- End-to-End Demo")
    print("=" * 60)

    doc = Document(
        doc_type="bill",
        raw_text="Itemized bill: CPT/HCPCS codes 45378 and 45380 billed together on the same date of service, $500.00 total.",
    )

    if os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY detected -- using real GenAISDKProvider (live Gemini call).")
        from billwatch.genai_sdk_provider import GenAISDKProvider
        provider = GenAISDKProvider()
    else:
        print("No GEMINI_API_KEY set -- using MockLLMProvider (fully offline demo).")
        provider = _mock_dispatch_provider(doc)

    investigation = Investigation()
    case_scope = establish_from_user_selection("medicare")
    store = ReferenceStore()
    load_bootstrap_data(store)

    print()
    print("Running investigation...")
    result = run_investigation(investigation, [doc], case_scope, provider, store)

    print()
    print("-" * 60)
    print(f"Pipeline success: {result.success}")
    if not result.success:
        print(f"Failed at stage: {result.failed_stage}")
        print(f"Reason: {result.failure_reason}")
        return

    print(f"Final status: {result.final_status.value}")
    print(f"Hypothesis ID: {result.hypothesis_id}")

    if result.appeal is not None and result.appeal.success:
        print()
        print("Appeal draft generated:")
        print("-" * 60)
        print(result.appeal.draft_text)
        print("-" * 60)
        print(f"Cites facts: {result.appeal.cited_fact_ids}")
        print(f"Cites claims: {result.appeal.cited_claim_ids}")
    elif result.appeal is not None:
        print(f"Appeal generation was attempted but failed: {result.appeal.failure_reason}")
    else:
        print("Appeal not eligible for this outcome (only SUPPORTED_DISCREPANCY permits one).")

    print()
    print("Done. This draft is for human review only -- it was never sent anywhere.")


if __name__ == "__main__":
    main()
