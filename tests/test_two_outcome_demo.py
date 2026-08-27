"""
Regression tests for the two-outcome demo (Scenario A: supported
discrepancy, Scenario B: clean/no-discrepancy bill). Both scenarios run
through the real, unmodified pipeline.run_investigation() -- no new
FinalStatus, no new adjudication logic, no frontend-manufactured result.
GEMINI_API_KEY is unset for the duration so this exercises the
deterministic MockLLMProvider path, consistent with the rest of the suite.
"""
import json
import os
import threading
import unittest
import urllib.request

import app as app_module


class TwoOutcomeDemoTests(unittest.TestCase):
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

    def _get_json(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_default_investigate_unchanged_existing_behavior(self):
        status, data = self._get_json("/investigate")
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["final_status"], "supported_discrepancy")
        self.assertTrue(data["appeal_generated"])
        self.assertIsNotNone(data["appeal_draft"])

    def test_explicit_discrepancy_scenario_matches_default(self):
        status, data = self._get_json("/investigate?scenario=discrepancy")
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["final_status"], "supported_discrepancy")
        self.assertTrue(data["appeal_generated"])

    def test_clean_scenario_reaches_no_supported_discrepancy(self):
        status, data = self._get_json("/investigate?scenario=clean")
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        self.assertNotEqual(data["final_status"], "supported_discrepancy")
        self.assertFalse(data["appeal_generated"])
        self.assertIsNone(data["appeal_draft"])

    def test_unknown_scenario_falls_back_to_discrepancy_default(self):
        status, data = self._get_json("/investigate?scenario=bogus")
        self.assertEqual(status, 200)
        self.assertEqual(data["final_status"], "supported_discrepancy")

    def test_response_contract_fields_unchanged_for_both_scenarios(self):
        for scenario in ("discrepancy", "clean"):
            _, data = self._get_json(f"/investigate?scenario={scenario}")
            self.assertEqual(
                sorted(data.keys()),
                sorted(["success", "final_status", "failed_stage", "appeal_generated", "appeal_draft", "gemini_mode"]),
            )

    def test_frontend_exposes_clean_bill_button(self):
        url = f"http://127.0.0.1:{self.port}/"
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read().decode("utf-8")
        self.assertIn('id="runCleanBtn"', body)
        self.assertIn('id="runDemoBtn"', body)
        self.assertIn("scenario=", body)

    def test_root_and_health_still_unaffected(self):
        status, _ = 200, None
        url = f"http://127.0.0.1:{self.port}/health"
        with urllib.request.urlopen(url, timeout=10) as resp:
            self.assertEqual(resp.status, 200)


if __name__ == "__main__":
    unittest.main()
