"""HTTP contract tests for the input-driven public BillWatch app."""

import json
import os
import threading
import unittest
from unittest import mock
import urllib.error
import urllib.request

import app as app_module


class AppRouteTests(unittest.TestCase):
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

    def setUp(self):
        app_module._request_times.clear()

    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                return resp.status, dict(resp.headers), resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read().decode("utf-8")

    def _post(self, payload, raw=False):
        body = payload if raw else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/investigate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_root_returns_input_form(self):
        status, _, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn('id="analysisForm"', body)
        self.assertIn('id="billText"', body)
        self.assertIn('id="fileInput"', body)
        self.assertIn("Analyze your bill", body)
        self.assertNotIn("scenario=", body)

    def test_root_queries_still_return_same_ui(self):
        for path in ("/?utm_source=chatgpt.com", "/?foo=bar"):
            status, _, body = self._get(path)
            self.assertEqual(status, 200)
            self.assertIn('id="analysisForm"', body)
            self.assertNotIn('"error": "not found"', body)

    def test_health_reports_safe_operating_mode(self):
        status, _, body = self._get("/health")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["mode"], "offline_mock")

    def test_get_investigate_is_rejected(self):
        status, headers, body = self._get("/investigate")
        self.assertEqual(status, 405)
        self.assertEqual(headers.get("Allow"), "POST")
        self.assertEqual(body, "")

    def test_post_investigate_accepts_arbitrary_bill_text(self):
        status, data = self._post({
            "bill_text": "Itemized bill: CPT 99213 and CPT 93000.",
            "payer_scope": "unknown",
        })
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["gemini_mode"], "offline_mock")
        self.assertEqual({f["value"] for f in data["facts"]}, {"99213", "93000"})
        self.assertEqual(len(data["findings"]), 1)
        self.assertEqual(data["findings"][0]["status"], "NO_MATCHING_RULE")
        self.assertTrue(data["request_id"])
        self.assertEqual(data["analysis_mode"], "standard")
        self.assertEqual(
            data["completed_stages"],
            [
                "bill_received",
                "facts_extracted",
                "pairs_generated",
                "references_checked",
                "context_evaluated",
            ],
        )

    def test_exact_demo_flag_reaches_only_the_synthetic_branch(self):
        status, paused = self._post({
            "bill_text": app_module.SYNTHETIC_SAMPLE_BILL,
            "demo_mode": "hackathon_synthetic_v1",
        })
        self.assertEqual(status, 200)
        self.assertTrue(paused["success"])
        self.assertEqual(paused["analysis_mode"], "hackathon_synthetic_v1")
        self.assertEqual(paused["status"], "INSUFFICIENT_CONTEXT")
        self.assertTrue(paused["can_resume"])
        self.assertEqual(
            {item["field"] for item in paused["missing_context_fields"]},
            {"service_date", "same_date_confirmed", "same_beneficiary_confirmed"},
        )
        self.assertEqual(paused["findings"][0]["reference"]["dataset"], "billwatch_hackathon_demo")

        status, complete = self._post({
            "bill_text": app_module.SYNTHETIC_SAMPLE_BILL,
            "demo_mode": "hackathon_synthetic_v1",
            "service_date": "2026-08-01",
            "same_date_confirmed": True,
            "same_beneficiary_confirmed": True,
        })
        self.assertEqual(status, 200)
        self.assertEqual(complete["status"], "POTENTIAL_DISCREPANCY")
        self.assertFalse(complete["can_resume"])
        self.assertNotEqual(paused["request_id"], complete["request_id"])

    def test_synthetic_identifiers_without_demo_flag_stay_on_ordinary_path(self):
        status, data = self._post({
            "bill_text": app_module.SYNTHETIC_SAMPLE_BILL,
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["analysis_mode"], "standard")
        self.assertFalse(
            [fact for fact in data["facts"] if fact["fact_type"] == "code"]
        )
        self.assertEqual(data["findings"], [])
        self.assertNotIn("billwatch_hackathon_demo", json.dumps(data))

    def test_invalid_demo_flag_types_and_values_are_rejected(self):
        for invalid_mode in (
            None,
            "",
            "HACKATHON_SYNTHETIC_V1",
            "hackathon_synthetic_v1 ",
            True,
            1,
        ):
            with self.subTest(invalid_mode=invalid_mode):
                status, data = self._post({
                    "bill_text": app_module.SYNTHETIC_SAMPLE_BILL,
                    "demo_mode": invalid_mode,
                })
                self.assertEqual(status, 400)
                self.assertEqual(data["error"], "invalid_request")

    def test_optional_metadata_does_not_echo_the_raw_bill(self):
        unique_text = "private-marker-that-must-not-enter-response-metadata"
        status, data = self._post({
            "bill_text": f"CPT 99213 and CPT 93000 {unique_text}",
        })
        self.assertEqual(status, 200)
        metadata = {
            key: data[key]
            for key in (
                "analysis_mode",
                "completed_stages",
                "missing_context_fields",
                "blocking_context",
                "can_resume",
                "limits",
                "request_id",
            )
        }
        self.assertNotIn(unique_text, json.dumps(metadata))

    def test_each_standard_post_is_independently_evaluated(self):
        payload = {
            "bill_text": "CPT 99213 and CPT 93000",
            "payer_scope": "unknown",
        }
        first_status, first = self._post(payload)
        second_status, second = self._post({**payload, "payer_scope": "medicare"})
        self.assertEqual((first_status, second_status), (200, 200))
        self.assertNotEqual(first["request_id"], second["request_id"])
        self.assertEqual(first["analysis_mode"], "standard")
        self.assertEqual(second["analysis_mode"], "standard")

    def test_unexpected_analysis_failure_returns_safe_500_without_stages(self):
        with mock.patch.object(app_module, "_run_analysis", side_effect=RuntimeError("secret detail")):
            status, data = self._post({"bill_text": "CPT 99213 and CPT 93000"})
        self.assertEqual(status, 500)
        self.assertEqual(data["error"], "investigation_unavailable")
        self.assertNotIn("secret detail", json.dumps(data))
        self.assertNotIn("completed_stages", data)

    def test_post_investigate_evaluates_every_unique_pair(self):
        status, data = self._post({
            "bill_text": "CPT 45378, CPT 45380, CPT 99213",
            "payer_scope": "medicare",
            "service_date": "2026-08-01",
            "same_date_confirmed": True,
            "same_beneficiary_confirmed": True,
        })
        self.assertEqual(status, 200)
        self.assertEqual(len(data["findings"]), 3)
        self.assertEqual(
            {(f["code_a"], f["code_b"]) for f in data["findings"]},
            {("45378", "45380"), ("45378", "99213"), ("45380", "99213")},
        )

    def test_invalid_json_and_missing_bill_text_are_safe_client_errors(self):
        status, data = self._post(b"not-json", raw=True)
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "invalid_request")

        status, data = self._post({"payer_scope": "unknown"})
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "invalid_request")

    def test_oversized_request_is_rejected_before_analysis(self):
        status, data = self._post({"bill_text": "x" * 200_001})
        self.assertEqual(status, 413)
        self.assertEqual(data["error"], "request_too_large")

    def test_rate_limit_is_enforced(self):
        for _ in range(app_module.MAX_REQUESTS_PER_WINDOW):
            status, _ = self._post({"bill_text": "CPT 99213 and CPT 93000"})
            self.assertEqual(status, 200)
        status, data = self._post({"bill_text": "CPT 99213 and CPT 93000"})
        self.assertEqual(status, 429)
        self.assertEqual(data["error"], "rate_limited")

    def test_route_path_helper_strips_query_and_fragment(self):
        self.assertEqual(app_module.route_path("/"), "/")
        self.assertEqual(app_module.route_path("/?utm_source=chatgpt.com"), "/")
        self.assertEqual(app_module.route_path("/?foo=bar&baz=qux"), "/")
        self.assertEqual(app_module.route_path("/health?x=1"), "/health")
        self.assertEqual(app_module.route_path("/investigate?x=1#frag"), "/investigate")
        self.assertEqual(app_module.route_path("/nope"), "/nope")


if __name__ == "__main__":
    unittest.main()
