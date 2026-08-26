"""
Regression tests for the /-with-query-string routing bug: '/', '/?utm_source=x',
and '/?foo=bar' must all resolve to the same BillWatch UI, and /health and
/investigate must keep working. These spin up the real app.Handler on an
ephemeral local port and issue real HTTP requests -- no mocking of routing.
GEMINI_API_KEY is unset for the duration so /investigate exercises the
deterministic MockLLMProvider path, consistent with the rest of the suite.
"""
import os
import threading
import unittest
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

    def _get(self, path):
        url = f"http://127.0.0.1:{self.port}{path}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")

    def test_root_returns_ui(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("Run Live Investigation", body)
        self.assertNotIn('"error": "not found"', body)

    def test_root_with_utm_query_returns_ui(self):
        status, body = self._get("/?utm_source=chatgpt.com")
        self.assertEqual(status, 200)
        self.assertIn("Run Live Investigation", body)
        self.assertNotIn('"error": "not found"', body)

    def test_root_with_arbitrary_query_returns_ui(self):
        status, body = self._get("/?foo=bar")
        self.assertEqual(status, 200)
        self.assertIn("Run Live Investigation", body)
        self.assertNotIn('"error": "not found"', body)

    def test_health_still_works(self):
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertIn('"status": "ok"', body)

    def test_investigate_still_works(self):
        status, body = self._get("/investigate")
        self.assertEqual(status, 200)
        self.assertIn('"success"', body)

    def test_route_path_helper_strips_query_and_fragment(self):
        self.assertEqual(app_module.route_path("/"), "/")
        self.assertEqual(app_module.route_path("/?utm_source=chatgpt.com"), "/")
        self.assertEqual(app_module.route_path("/?foo=bar&baz=qux"), "/")
        self.assertEqual(app_module.route_path("/health?x=1"), "/health")
        self.assertEqual(app_module.route_path("/investigate?x=1#frag"), "/investigate")
        self.assertEqual(app_module.route_path("/nope"), "/nope")


if __name__ == "__main__":
    unittest.main()
