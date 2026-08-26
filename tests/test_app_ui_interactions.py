"""
Regression tests for the UI interaction hardening pass: confirms every
static interactive control (brand/logo, primary CTA, "How BillWatch Works")
is wired via addEventListener rather than inline onclick attributes, has a
real id and type="button", and that the scroll-target section has a
scroll-margin-top offset so the sticky header cannot cover it after a
scroll-to. These are static markup/script-source assertions -- they prove
the wiring exists and is structurally correct, but they cannot execute
JavaScript or simulate real touch/click events in a browser (no headless
browser dependency is available in this environment), so they do not by
themselves prove behavior in a live mobile browser. See README/manual QA
checklist for the browser-verification step this suite cannot perform.
"""
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

    def test_primary_cta_has_stable_id_and_type(self):
        status, body = self._get("/")
        self.assertIn('id="runDemoBtn"', body)
        self.assertIn('type="button"', body)

    def test_how_it_works_button_and_target_exist(self):
        status, body = self._get("/")
        self.assertIn('id="howBtn"', body)
        self.assertIn('id="how"', body)

    def test_brand_is_a_real_focusable_button(self):
        status, body = self._get("/")
        self.assertIn('id="brandBtn"', body)
        self.assertIn('<button type="button" id="brandBtn"', body)

    def test_sticky_header_scroll_offset_present(self):
        status, body = self._get("/")
        self.assertIn("scroll-margin-top", body)

    def test_event_listeners_are_used_not_inline_handlers(self):
        status, body = self._get("/")
        self.assertIn("addEventListener", body)
        self.assertIn("DOMContentLoaded", body)

    def test_result_actions_use_data_action_delegation(self):
        status, body = self._get("/")
        self.assertIn('data-action="copy"', body)
        self.assertIn('data-action="download"', body)
        self.assertIn('data-action="retry"', body)

    def test_root_with_query_string_still_serves_hardened_ui(self):
        status, body = self._get("/?utm_source=chatgpt.com")
        self.assertEqual(status, 200)
        self.assertIn('id="runDemoBtn"', body)
        self.assertNotIn("onclick=", body)

    def test_health_still_works(self):
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertIn('"status": "ok"', body)

    def test_investigate_still_works(self):
        status, body = self._get("/investigate")
        self.assertEqual(status, 200)
        self.assertIn('"success"', body)


if __name__ == "__main__":
    unittest.main()
