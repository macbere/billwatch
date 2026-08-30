"""Static UI contract tests for the public arbitrary-bill workflow."""

import os
import threading
import unittest
import urllib.request

import app as app_module


class UIInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_key = os.environ.pop("GEMINI_API_KEY", None)
        cls.server = app_module.HTTPServer(("127.0.0.1", 0), app_module.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        if cls._old_key is not None:
            os.environ["GEMINI_API_KEY"] = cls._old_key

    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")

    def test_no_inline_onclick_handlers_remain(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertNotIn("onclick=", body)

    def test_input_form_has_real_controls(self):
        _, body = self._get("/")
        self.assertIn('<form id="analysisForm">', body)
        self.assertIn('id="billText"', body)
        self.assertIn('id="fileInput" type="file"', body)
        self.assertIn('id="runDemoBtn"', body)
        self.assertIn('type="submit"', body)

    def test_how_it_works_button_and_target_exist(self):
        _, body = self._get("/")
        self.assertIn('id="howBtn"', body)
        self.assertIn('id="how"', body)

    def test_brand_is_a_real_focusable_button(self):
        _, body = self._get("/")
        self.assertIn('id="brandBtn"', body)
        self.assertIn('<button type="button" id="brandBtn"', body)

    def test_event_listeners_are_used_not_inline_handlers(self):
        _, body = self._get("/")
        self.assertIn("addEventListener", body)
        self.assertIn('data-action="example"', body)

    def test_example_text_uses_valid_javascript_newline_escapes(self):
        _, body = self._get("/")
        self.assertIn(r'multi:"Itemized bill\nCPT 45378', body)
        self.assertNotIn('multi:"Itemized bill\nCPT 45378', body)

    def test_result_actions_use_safe_delegation(self):
        _, body = self._get("/")
        self.assertIn('data-action="copy"', body)
        self.assertIn('data-action="download"', body)

    def test_root_with_query_string_still_serves_input_ui(self):
        status, body = self._get("/?utm_source=chatgpt.com")
        self.assertEqual(status, 200)
        self.assertIn('id="analysisForm"', body)
        self.assertNotIn("onclick=", body)

    def test_health_still_works(self):
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertIn('"status": "ok"', body)

    def test_active_tab_only_session_notice_is_prominent(self):
        _, body = self._get("/")
        self.assertIn('id="sessionNotice"', body)
        self.assertIn("Active browser tab only.", body)
        self.assertIn("Closing or refreshing this tab clears the investigation", body)
        self.assertIn("Raw bill text is processed transiently", body)

    def test_hackathon_demo_is_separate_and_unmistakably_synthetic(self):
        _, body = self._get("/")
        self.assertIn('id="hackathonDemoCard"', body)
        self.assertIn('id="loadDemoBtn"', body)
        self.assertIn("BW-DEMO-001", body)
        self.assertIn("BW-DEMO-002", body)
        self.assertIn("author-written and synthetic", body)
        self.assertIn("not CPT or HCPCS", body)

    def test_investigation_state_exists_only_as_page_memory(self):
        _, body = self._get("/")
        self.assertIn("var investigation=null", body)
        self.assertIn("attempts:[]", body)
        self.assertIn("timeline:[]", body)
        self.assertIn("approvalDecision:null", body)
        for forbidden in (
            "localStorage",
            "sessionStorage",
            "indexedDB",
            "document.cookie",
            "sendBeacon",
            "beforeunload",
            "unload",
        ):
            self.assertNotIn(forbidden, body)

    def test_start_new_and_load_demo_share_reset_confirmation(self):
        _, body = self._get("/")
        self.assertIn('id="startNewBtn"', body)
        self.assertIn("function confirmClearInvestigation", body)
        self.assertIn("if(!confirmClearInvestigation())return", body)
        self.assertIn("function resetInvestigation", body)

    def test_ordinary_form_remains_primary_and_does_not_default_to_demo(self):
        _, body = self._get("/")
        self.assertLess(body.index('id="analysisForm"'), body.index('id="hackathonDemoCard"'))
        self.assertIn('var selectedMode="standard"', body)
        self.assertIn('if(investigation.mode===HACKATHON_DEMO_MODE)', body)

    def test_pause_panel_and_resume_control_exist(self):
        _, body = self._get("/")
        self.assertIn('id="pauseCard"', body)
        self.assertIn('id="resumeFields"', body)
        self.assertIn('id="resumeBtn"', body)
        self.assertIn("Resume investigation", body)
        self.assertIn("start a new investigation and correct the original bill text", body)

    def test_resume_uses_shared_fresh_post_helper(self):
        _, body = self._get("/")
        self.assertIn("async function postInvestigation(payload)", body)
        self.assertIn('fetch("/investigate"', body)
        self.assertIn('runAttempt("initial")', body)
        self.assertIn('runAttempt("resume")', body)

    def test_resume_retains_bill_and_appends_attempt(self):
        _, body = self._get("/")
        self.assertIn("bill_text:investigation.billText", body)
        self.assertIn("investigation.attempts.push(attempt)", body)
        self.assertNotIn("investigation.attempts=[attempt]", body)
        self.assertIn("if(!investigation.id)investigation.id=data.request_id", body)
        self.assertIn('id="attemptHistory"', body)
        self.assertIn("investigation.attempts.slice(0,-1)", body)
        self.assertIn("<details", body)
        self.assertIn("function attemptMissingContext(data)", body)
        self.assertIn("(finding.missing_context||[])", body)

    def test_only_server_supported_missing_fields_are_rendered(self):
        _, body = self._get("/")
        self.assertIn("var RESUMABLE_FIELDS=", body)
        self.assertIn("data.missing_context_fields||[]", body)
        self.assertIn("RESUMABLE_FIELDS.indexOf(item.field)", body)

    def test_pause_locks_source_and_records_human_confirmation(self):
        _, body = self._get("/")
        self.assertIn("setSourceLocked(true)", body)
        self.assertIn('appendTimeline("human","context_supplied"', body)
        self.assertIn("investigation.currentContext", body)

    def test_processing_guard_prevents_duplicate_resume(self):
        _, body = self._get("/")
        self.assertIn("var processing=false", body)
        self.assertIn("if(processing)return", body)
        self.assertIn("resumeBtn.disabled", body)

    def test_timeline_uses_only_server_returned_completed_stages(self):
        _, body = self._get("/")
        self.assertIn('id="timelinePanel"', body)
        self.assertIn('id="timelineList"', body)
        self.assertIn("data.completed_stages||[]", body)
        self.assertIn("function appendCompletedStages", body)
        self.assertNotIn('<li class="done">Bill received</li>', body)

    def test_timeline_distinguishes_automatic_and_human_events(self):
        _, body = self._get("/")
        self.assertIn('event.actor==="human"', body)
        self.assertIn('class="timeline-item ', body)
        self.assertIn("renderTimeline()", body)

    def test_retry_is_a_fresh_attempt_and_not_a_cached_result(self):
        _, body = self._get("/")
        self.assertIn('id="retryBtn"', body)
        self.assertIn('runAttempt("retry")', body)
        self.assertIn('appendTimeline("human","retry_requested"', body)
        self.assertNotIn("render(attempt.response)", body)

    def test_failed_attempt_is_retained_without_static_completed_stages(self):
        _, body = self._get("/")
        self.assertIn("attempt.error=", body)
        self.assertIn("investigation.attempts.push(attempt)", body)
        self.assertIn("appendCompletedStages(data,attemptNumber)", body)
        self.assertIn("The investigation did not finish", body)

    def test_invalid_empty_input_creates_no_investigation(self):
        _, body = self._get("/")
        validation = body.index('if(!text.value.trim())')
        creation = body.index("investigation=emptyInvestigation()")
        self.assertGreaterEqual(validation, 0)
        self.assertGreater(creation, validation)

    def test_simulated_approval_card_is_hidden_and_buttons_are_non_submitting(self):
        _, body = self._get("/")
        self.assertIn('class="card approval-card hidden" id="approvalCard"', body)
        self.assertIn('<button type="button" class="primary" id="approveBtn">', body)
        self.assertIn('<button type="button" class="secondary" id="rejectBtn">', body)

    def test_approval_is_eligible_only_for_successful_potential_discrepancy(self):
        _, body = self._get("/")
        self.assertIn(
            'data&&data.success&&data.status==="POTENTIAL_DISCREPANCY"', body
        )
        self.assertIn('data.status!=="POTENTIAL_DISCREPANCY"', body)

    def test_approval_decision_changes_only_page_memory_and_timeline(self):
        _, body = self._get("/")
        start = body.index("function recordApprovalDecision(decision)")
        end = body.index("function attemptMissingContext", start)
        handler = body[start:end]
        self.assertIn("investigation.approvalDecision=decision", handler)
        self.assertIn('appendTimeline("human","approval_decision"', handler)
        self.assertIn("renderApproval(data)", handler)
        for forbidden in (
            "postInvestigation",
            "fetch(",
            "navigator.",
            "window.location",
            "document.createElement",
            "Blob(",
            "URL.createObjectURL",
        ):
            self.assertNotIn(forbidden, handler)

    def test_approval_decision_is_single_use_and_explicitly_sends_nothing(self):
        _, body = self._get("/")
        self.assertIn("investigation.approvalDecision||!data", body)
        self.assertIn("Nothing was sent.", body)
        self.assertIn("Nothing is transmitted, downloaded, copied, published, or sent", body)

    def test_synthetic_result_does_not_offer_copy_or_download_actions(self):
        _, body = self._get("/")
        self.assertIn(
            "data.review_note&&data.analysis_mode!==HACKATHON_DEMO_MODE", body
        )

    def test_file_loader_enforces_supported_extensions_and_size_before_reading(self):
        _, body = self._get("/")
        extension_check = body.index(r"/\.(txt|csv|json)$/i.test(selected.name)")
        size_check = body.index("selected.size>200000")
        read = body.index("reader.readAsText(selected)")
        self.assertLess(extension_check, size_check)
        self.assertLess(size_check, read)
        self.assertIn("Supported file types are TXT, CSV, and JSON.", body)

    def test_client_rejects_limit_exceeding_text_before_creating_investigation(self):
        _, body = self._get("/")
        validation = body.index("text.value.length>MAX_BILL_TEXT_CHARS")
        creation = body.index("investigation=emptyInvestigation()")
        self.assertIn("var MAX_BILL_TEXT_CHARS=100000", body)
        self.assertLess(validation, creation)
        self.assertIn("Please use no more than 100,000 characters.", body)


if __name__ == "__main__":
    unittest.main()
