"""
BillWatch Cloud Run entrypoint. Stdlib-only HTTP wrapper -- no new
dependency, no reasoning of its own. Calls the existing, unmodified
pipeline.run_investigation() and serializes its result. Uses
GenAISDKProvider if GEMINI_API_KEY is set, otherwise MockLLMProvider,
exactly like demo.py.
"""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

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
                "claim_statement": "Possible improper unbundling",
                "explanation_text": "Codes 45378/45380 billed together; NCCI treats these as bundled.",
                "referenced_fact_ids": fact_ids,
            })
        if "verification-planning component" in system_prompt:
            m = re.search(r"hypothesis_id:\s*(\S+)", user_content)
            return json.dumps({
                "hypothesis_id": m.group(1) if m else "",
                "proposed_source_types": ["CMS_NCCI"],
                "verification_rationale": "Check CMS NCCI PTP bundling status.",
            })
        if "appeal-drafting component" in system_prompt:
            m = re.search(r"claim_id:\s*(\S+)", user_content)
            fact_ids = re.findall(r"fact_id=([0-9a-fA-F-]+)", user_content)
            return json.dumps({
                "draft_text": "I am appealing the billing of codes 45378 and 45380 together, which CMS NCCI treats as bundled.",
                "cited_fact_ids": fact_ids,
                "cited_claim_ids": [m.group(1)] if m else [],
            })
        return "{}"
    return MockLLMProvider(response_fn=dispatch)


def _run_demo_investigation():
    doc = Document(
        doc_type="bill",
        raw_text="Itemized bill: CPT/HCPCS codes 45378 and 45380 billed together, same date of service, $500.00 total.",
    )
    if os.environ.get("GEMINI_API_KEY"):
        from billwatch.genai_sdk_provider import GenAISDKProvider
        provider = GenAISDKProvider()
    else:
        provider = _mock_dispatch_provider(doc)

    investigation = Investigation()
    case_scope = establish_from_user_selection("medicare")
    store = ReferenceStore()
    load_bootstrap_data(store)

    result = run_investigation(investigation, [doc], case_scope, provider, store)
    payload = {
        "success": result.success,
        "final_status": result.final_status.value if result.final_status else None,
        "failed_stage": result.failed_stage,
        "appeal_generated": result.appeal.success if result.appeal else False,
        "appeal_draft": result.appeal.draft_text if result.appeal and result.appeal.success else None,
        "gemini_mode": "live" if os.environ.get("GEMINI_API_KEY") else "offline_mock",
    }
    return payload


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code, obj):
        body = json.dumps(obj, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "billwatch"})
        elif self.path == "/investigate":
            try:
                self._send_json(200, _run_demo_investigation())
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, format, *args):
        # Never log request bodies/headers that could contain secrets.
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"BillWatch serving on port {port}")
    server.serve_forever()
