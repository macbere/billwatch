"""
Build 4, Stage 1: provider boundary validation.

Tests billwatch/llm_provider.py ONLY -- the transport/error-handling
boundary. Nothing here tests extraction, hypothesis generation,
verification, adjudication, or any domain logic, because
llm_provider.py contains none of that.

All Gemini-facing tests mock urllib.request.urlopen. No real network
call is ever made; no real API key is ever used.
"""

import json
import os
import unittest
import urllib.error
from unittest import mock

from billwatch.llm_provider import (
    LLMProvider,
    LLMProviderError,
    MockLLMProvider,
    GeminiProvider,
)


class _FakeHTTPResponse:
    """Minimal stand-in for the object urllib.request.urlopen() returns
    when used as a context manager."""

    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


# ---------------------------------------------------------------------
# GROUP A -- Mock provider
# ---------------------------------------------------------------------
class TestMockLLMProvider(unittest.TestCase):

    def test_requires_exactly_one_of_three_args(self):
        with self.assertRaises(ValueError):
            MockLLMProvider()

    def test_two_args_together_rejected(self):
        with self.assertRaises(ValueError):
            MockLLMProvider(fixed_response="a", raise_error=ValueError("x"))

    def test_three_args_together_rejected(self):
        with self.assertRaises(ValueError):
            MockLLMProvider(
                response_fn=lambda s, u: "a",
                fixed_response="a",
                raise_error=ValueError("x"),
            )

    def test_fixed_response_returned(self):
        provider = MockLLMProvider(fixed_response="hello")
        self.assertEqual(provider.complete_json("sys", "user"), "hello")

    def test_fixed_response_reproducible_across_calls(self):
        provider = MockLLMProvider(fixed_response="hello")
        first = provider.complete_json("sys", "user")
        second = provider.complete_json("sys", "user")
        self.assertEqual(first, second)

    def test_response_fn_receives_exact_args(self):
        seen = {}

        def fn(system_prompt, user_content):
            seen["system_prompt"] = system_prompt
            seen["user_content"] = user_content
            return "ok"

        provider = MockLLMProvider(response_fn=fn)
        provider.complete_json("SYS", "USER")
        self.assertEqual(seen, {"system_prompt": "SYS", "user_content": "USER"})

    def test_response_fn_reproducible_when_fn_is_deterministic(self):
        provider = MockLLMProvider(response_fn=lambda s, u: f"{s}:{u}")
        first = provider.complete_json("a", "b")
        second = provider.complete_json("a", "b")
        self.assertEqual(first, second)

    def test_raise_error_is_reraised_verbatim(self):
        err = RuntimeError("boom")
        provider = MockLLMProvider(raise_error=err)
        with self.assertRaises(RuntimeError):
            provider.complete_json("s", "u")

    def test_calls_are_recorded_in_order(self):
        provider = MockLLMProvider(fixed_response="x")
        provider.complete_json("s1", "u1")
        provider.complete_json("s2", "u2")
        self.assertEqual(provider.calls, [("s1", "u1"), ("s2", "u2")])

    @mock.patch("billwatch.llm_provider.urllib.request.urlopen")
    def test_mock_provider_never_touches_network(self, mock_urlopen):
        mock_urlopen.side_effect = AssertionError(
            "MockLLMProvider must never call urlopen"
        )
        provider = MockLLMProvider(fixed_response="x")
        provider.complete_json("s", "u")  # would raise if network were touched
        mock_urlopen.assert_not_called()


# ---------------------------------------------------------------------
# GROUP B -- Gemini provider configuration
# ---------------------------------------------------------------------
class TestGeminiProviderConfiguration(unittest.TestCase):

    def test_default_model_and_timeout(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            provider = GeminiProvider(api_key="k")
        self.assertEqual(provider.model, "gemini-3.5-flash")
        self.assertEqual(provider.timeout_seconds, 30.0)

    def test_api_key_from_constructor_param(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            provider = GeminiProvider(api_key="explicit-key")
        self.assertEqual(provider.api_key, "explicit-key")

    def test_api_key_from_env_var(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "env-key"}, clear=True):
            provider = GeminiProvider()
        self.assertEqual(provider.api_key, "env-key")

    def test_constructor_param_overrides_env_var(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "env-key"}, clear=True):
            provider = GeminiProvider(api_key="explicit-key")
        self.assertEqual(provider.api_key, "explicit-key")

    def test_no_api_key_anywhere_leaves_api_key_none(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            provider = GeminiProvider()
        self.assertIsNone(provider.api_key)

    @mock.patch("billwatch.llm_provider.urllib.request.urlopen")
    def test_missing_api_key_raises_before_any_network_call(self, mock_urlopen):
        with mock.patch.dict(os.environ, {}, clear=True):
            provider = GeminiProvider()
        with self.assertRaises(LLMProviderError):
            provider.complete_json("s", "u")
        mock_urlopen.assert_not_called()


# ---------------------------------------------------------------------
# GROUP C -- HTTP success (fake transport, no real network)
# ---------------------------------------------------------------------
class TestGeminiProviderHTTPSuccess(unittest.TestCase):

    @mock.patch("billwatch.llm_provider.urllib.request.urlopen")
    def test_successful_response_returns_extracted_text(self, mock_urlopen):
        body = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": "extracted text"}]}}]}
        ).encode("utf-8")
        mock_urlopen.return_value = _FakeHTTPResponse(body)
        provider = GeminiProvider(api_key="fake-test-key")
        result = provider.complete_json("sys", "user")
        self.assertEqual(result, "extracted text")

    @mock.patch("billwatch.llm_provider.urllib.request.urlopen")
    def test_request_is_a_post_with_expected_payload_shape(self, mock_urlopen):
        body = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        ).encode("utf-8")
        mock_urlopen.return_value = _FakeHTTPResponse(body)
        provider = GeminiProvider(api_key="fake-test-key")
        provider.complete_json("sys-prompt", "user-content")

        self.assertEqual(mock_urlopen.call_count, 1)
        sent_request = mock_urlopen.call_args[0][0]
        self.assertEqual(sent_request.get_method(), "POST")

        payload = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(
            payload["systemInstruction"]["parts"][0]["text"], "sys-prompt"
        )
        self.assertEqual(payload["contents"][0]["parts"][0]["text"], "user-content")
        self.assertEqual(
            payload["generationConfig"]["responseMimeType"], "application/json"
        )


# ---------------------------------------------------------------------
# GROUP D -- HTTP failure (fake transport, no real network)
# ---------------------------------------------------------------------
class TestGeminiProviderHTTPFailure(unittest.TestCase):

    @mock.patch("billwatch.llm_provider.urllib.request.urlopen")
    def test_url_error_becomes_llm_provider_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("no route to host")
        provider = GeminiProvider(api_key="fake-test-key")
        with self.assertRaises(LLMProviderError):
            provider.complete_json("s", "u")

    @mock.patch("billwatch.llm_provider.urllib.request.urlopen")
    def test_timeout_error_becomes_llm_provider_error(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timed out")
        provider = GeminiProvider(api_key="fake-test-key")
        with self.assertRaises(LLMProviderError):
            provider.complete_json("s", "u")

    @mock.patch("billwatch.llm_provider.urllib.request.urlopen")
    def test_malformed_json_body_raises_llm_provider_error(self, mock_urlopen):
        # Response body that is not valid JSON at all.
        mock_urlopen.return_value = _FakeHTTPResponse(b"not valid json {{{")
        provider = GeminiProvider(api_key="fake-test-key")
        with self.assertRaises(LLMProviderError):
            provider.complete_json("s", "u")

    @mock.patch("billwatch.llm_provider.urllib.request.urlopen")
    def test_missing_candidates_key_raises_llm_provider_error(self, mock_urlopen):
        body = json.dumps({"unexpected": "shape"}).encode("utf-8")
        mock_urlopen.return_value = _FakeHTTPResponse(body)
        provider = GeminiProvider(api_key="fake-test-key")
        with self.assertRaises(LLMProviderError):
            provider.complete_json("s", "u")

    @mock.patch("billwatch.llm_provider.urllib.request.urlopen")
    def test_empty_candidates_list_raises_llm_provider_error(self, mock_urlopen):
        body = json.dumps({"candidates": []}).encode("utf-8")
        mock_urlopen.return_value = _FakeHTTPResponse(body)
        provider = GeminiProvider(api_key="fake-test-key")
        with self.assertRaises(LLMProviderError):
            provider.complete_json("s", "u")

    @mock.patch("billwatch.llm_provider.urllib.request.urlopen")
    def test_missing_content_field_raises_llm_provider_error(self, mock_urlopen):
        body = json.dumps({"candidates": [{"no_content_here": True}]}).encode("utf-8")
        mock_urlopen.return_value = _FakeHTTPResponse(body)
        provider = GeminiProvider(api_key="fake-test-key")
        with self.assertRaises(LLMProviderError):
            provider.complete_json("s", "u")

    @mock.patch("billwatch.llm_provider.urllib.request.urlopen")
    def test_missing_parts_field_raises_llm_provider_error(self, mock_urlopen):
        body = json.dumps({"candidates": [{"content": {}}]}).encode("utf-8")
        mock_urlopen.return_value = _FakeHTTPResponse(body)
        provider = GeminiProvider(api_key="fake-test-key")
        with self.assertRaises(LLMProviderError):
            provider.complete_json("s", "u")


# ---------------------------------------------------------------------
# GROUP E -- Security / contract tests
# ---------------------------------------------------------------------
class TestProviderSecurityContract(unittest.TestCase):

    def test_llm_provider_is_abstract_and_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            LLMProvider()

    def test_no_domain_decision_methods_exist_on_any_provider(self):
        forbidden_method_names = {
            "adjudicate",
            "set_final_status",
            "determine_scope",
            "establish_case_scope",
            "evaluate_authority",
            "evaluate_source_authority",
            "resolve_conflict",
            "authorize_appeal",
            "request_draft_appeal",
        }
        for cls in (LLMProvider, MockLLMProvider, GeminiProvider):
            for name in forbidden_method_names:
                self.assertFalse(
                    hasattr(cls, name),
                    f"{cls.__name__} unexpectedly exposes {name}()",
                )

    def test_mock_provider_failure_raises_rather_than_returning_fake_data(self):
        provider = MockLLMProvider(raise_error=ValueError("simulated failure"))
        with self.assertRaises(ValueError):
            result = provider.complete_json("s", "u")
            self.fail(f"expected an exception, got a return value: {result!r}")

    @mock.patch("billwatch.llm_provider.urllib.request.urlopen")
    def test_gemini_failure_message_does_not_leak_the_api_key_value(
        self, mock_urlopen
    ):
        secret = "totally-fake-secret-value-12345"
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        provider = GeminiProvider(api_key=secret)
        with self.assertRaises(LLMProviderError) as ctx:
            provider.complete_json("s", "u")
        self.assertNotIn(secret, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
