"""Regression tests proving the public app is no longer a fixed demo."""

import json
import os
import threading
import unittest
import urllib.error
import urllib.request

import app as app_module


class InputDrivenWorkflowTests(unittest.TestCase):
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

    def _post(self, payload):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/investigate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_different_bills_produce_different_extracted_codes(self):
        _, first = self._post({"bill_text": "CPT 99213 and CPT 93000"})
        _, second = self._post({"bill_text": "HCPCS A0425 and CPT 45378"})

        self.assertEqual({f["value"] for f in first["facts"]}, {"99213", "93000"})
        self.assertEqual({f["value"] for f in second["facts"]}, {"A0425", "45378"})
        self.assertNotEqual(first["document_id"], second["document_id"])

    def test_three_codes_are_checked_as_three_unique_pairs(self):
        _, data = self._post({
            "bill_text": "CPT 45378, CPT 45380, CPT 99213",
            "payer_scope": "unknown",
        })
        self.assertEqual(len(data["findings"]), 3)
        self.assertEqual(data["status"], "INSUFFICIENT_CONTEXT")

    def test_unverified_reference_is_not_presented_as_proven_error(self):
        _, data = self._post({
            "bill_text": "CPT 45378 and CPT 45380 billed on 2026-08-01.",
            "payer_scope": "medicare",
            "service_date": "2026-08-01",
            "same_date_confirmed": True,
            "same_beneficiary_confirmed": True,
        })
        self.assertEqual(data["status"], "INSUFFICIENT_CONTEXT")
        self.assertEqual(data["findings"][0]["status"], "REFERENCE_UNVERIFIED")
        self.assertIn("not", data["findings"][0]["summary"].lower())
        self.assertIsNone(data["review_note"])

    def test_no_match_does_not_claim_bill_is_clean(self):
        _, data = self._post({"bill_text": "CPT 99213 and CPT 93000"})
        self.assertEqual(data["status"], "NO_SUPPORTED_DISCREPANCY_FOUND")
        self.assertIn("does not prove", data["findings"][0]["summary"])
        self.assertIsNone(data["review_note"])

    def test_get_endpoint_cannot_trigger_investigation(self):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/investigate", method="GET"
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(caught.exception.code, 405)


if __name__ == "__main__":
    unittest.main()
