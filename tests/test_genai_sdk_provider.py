"""
Build 4, Stage 4B: GenAISDKProvider tests.

Tests billwatch/genai_sdk_provider.py ONLY. ZERO real network calls and
ZERO real credentials are used anywhere in this file -- every test uses
either the provider's _client injection hook (a fake client, no
genai.Client constructed at all) or mock.patch on genai.Client itself
(for testing the real construction path without a real key or network).
"""

import unittest
from unittest import mock

import httpx
from google.genai import errors as genai_errors

from billwatch.llm_provider import LLMProvider, LLMProviderError
from billwatch.genai_sdk_provider import GenAISDKProvider


class _FakeResponseWithText:
    def __init__(self, text):
        self.text = text


class _FakeResponseTextRaises:
    """Simulates a malformed/unreadable response where accessing .text
    itself fails, rather than returning None."""
    @property
    def text(self):
        raise ValueError("simulated malformed response body")


class _FakeModels:
    def __init__(self, response=None, exception=None, capture=None):
        self._response = response
        self._exception = exception
        self._capture = capture

    def generate_content(self, *, model, contents, config):
        if self._capture is not None:
            self._capture["model"] = model
            self._capture["contents"] = contents
            self._capture["config"] = config
        if self._exception is not None:
            raise self._exception
        return self._response


class _FakeClient:
    def __init__(self, response=None, exception=None, capture=None):
        self.models = _FakeModels(response=response, exception=exception, capture=capture)
        self.closed = False

    def close(self):
        self.closed = True


# ---------------------------------------------------------------------
# GROUP A -- Interface satisfaction
# ---------------------------------------------------------------------
class TestInterfaceSatisfaction(unittest.TestCase):

    def test_is_an_llmprovider_subclass(self):
        self.assertTrue(issubclass(GenAISDKProvider, LLMProvider))

    def test_implements_complete_json(self):
        fake = _FakeClient(response=_FakeResponseWithText("hello"))
        provider = GenAISDKProvider(_client=fake)
        result = provider.complete_json("sys", "user")
        self.assertEqual(result, "hello")


# ---------------------------------------------------------------------
# GROUP B -- Successful mocked response
# ---------------------------------------------------------------------
class TestSuccessfulResponse(unittest.TestCase):

    def test_successful_response_returns_text_verbatim(self):
        fake = _FakeClient(response=_FakeResponseWithText('{"key": "value"}'))
        provider = GenAISDKProvider(_client=fake)
        result = provider.complete_json("sys", "user")
        self.assertEqual(result, '{"key": "value"}')
        self.assertIsInstance(result, str)

    def test_default_model_is_gemini_3_5_flash(self):
        provider = GenAISDKProvider(_client=_FakeClient(response=_FakeResponseWithText("x")))
        self.assertEqual(provider.model, "gemini-3.5-flash")

    def test_custom_model_is_passed_through_to_generate_content(self):
        capture = {}
        fake = _FakeClient(response=_FakeResponseWithText("x"), capture=capture)
        provider = GenAISDKProvider(model="gemini-3.6-flash", _client=fake)
        provider.complete_json("sys", "user")
        self.assertEqual(capture["model"], "gemini-3.6-flash")

    def test_config_includes_system_instruction_and_json_mime_type(self):
        capture = {}
        fake = _FakeClient(response=_FakeResponseWithText("x"), capture=capture)
        provider = GenAISDKProvider(_client=fake)
        provider.complete_json("my system prompt", "my user content")
        config = capture["config"]
        self.assertEqual(config.system_instruction, "my system prompt")
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertEqual(capture["contents"], "my user content")

    def test_returned_text_is_never_parsed_or_interpreted(self):
        # Confirms this provider does no JSON parsing / validation of its
        # own -- that remains llm_schemas.py's job entirely.
        raw = 'not even valid json {{{'
        fake = _FakeClient(response=_FakeResponseWithText(raw))
        provider = GenAISDKProvider(_client=fake)
        result = provider.complete_json("sys", "user")
        self.assertEqual(result, raw)


# ---------------------------------------------------------------------
# GROUP C -- Empty response
# ---------------------------------------------------------------------
class TestEmptyResponse(unittest.TestCase):

    def test_none_text_raises_llm_provider_error(self):
        # Confirmed this session: response.text is None (not an exception)
        # when there are no candidates -- real SDK behavior, not assumed.
        fake = _FakeClient(response=_FakeResponseWithText(None))
        provider = GenAISDKProvider(_client=fake)
        with self.assertRaises(LLMProviderError):
            provider.complete_json("sys", "user")

    def test_empty_response_never_silently_becomes_empty_success(self):
        fake = _FakeClient(response=_FakeResponseWithText(None))
        provider = GenAISDKProvider(_client=fake)
        try:
            provider.complete_json("sys", "user")
            self.fail("expected LLMProviderError, got a return value instead")
        except LLMProviderError:
            pass


# ---------------------------------------------------------------------
# GROUP D -- Malformed response
# ---------------------------------------------------------------------
class TestMalformedResponse(unittest.TestCase):

    def test_text_property_raising_value_error_is_wrapped(self):
        fake = _FakeClient(response=_FakeResponseTextRaises())
        provider = GenAISDKProvider(_client=fake)
        with self.assertRaises(LLMProviderError):
            provider.complete_json("sys", "user")

    def test_unknown_api_response_error_is_wrapped(self):
        exc = genai_errors.UnknownApiResponseError("bizarre response shape")
        fake = _FakeClient(exception=exc)
        provider = GenAISDKProvider(_client=fake)
        with self.assertRaises(LLMProviderError):
            provider.complete_json("sys", "user")


# ---------------------------------------------------------------------
# GROUP E -- Authentication / server / transport failures
# ---------------------------------------------------------------------
class TestFailureWrapping(unittest.TestCase):

    def test_client_error_authentication_failure_wrapped(self):
        # ClientError covers 4xx responses, including bad/missing auth.
        exc = genai_errors.ClientError(code=401, response_json={"error": "unauthorized"})
        fake = _FakeClient(exception=exc)
        provider = GenAISDKProvider(_client=fake)
        with self.assertRaises(LLMProviderError):
            provider.complete_json("sys", "user")

    def test_server_error_wrapped(self):
        exc = genai_errors.ServerError(code=503, response_json={"error": "unavailable"})
        fake = _FakeClient(exception=exc)
        provider = GenAISDKProvider(_client=fake)
        with self.assertRaises(LLMProviderError):
            provider.complete_json("sys", "user")

    def test_httpx_connect_error_wrapped(self):
        exc = httpx.ConnectError("no route to host")
        fake = _FakeClient(exception=exc)
        provider = GenAISDKProvider(_client=fake)
        with self.assertRaises(LLMProviderError):
            provider.complete_json("sys", "user")

    def test_httpx_timeout_wrapped(self):
        exc = httpx.TimeoutException("request timed out")
        fake = _FakeClient(exception=exc)
        provider = GenAISDKProvider(_client=fake)
        with self.assertRaises(LLMProviderError):
            provider.complete_json("sys", "user")

    def test_unrelated_exception_type_still_propagates(self):
        # A genuine bug (not an SDK/transport failure) must not be
        # silently absorbed into a fake LLMProviderError.
        fake = _FakeClient(exception=RuntimeError("unexpected bug"))
        provider = GenAISDKProvider(_client=fake)
        with self.assertRaises(RuntimeError):
            provider.complete_json("sys", "user")


# ---------------------------------------------------------------------
# GROUP F -- Missing credential / real construction path
# ---------------------------------------------------------------------
class TestCredentialHandling(unittest.TestCase):

    def test_missing_api_key_raises_before_any_client_construction(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with mock.patch("billwatch.genai_sdk_provider.genai.Client") as mock_client_cls:
                provider = GenAISDKProvider()
                with self.assertRaises(LLMProviderError):
                    provider.complete_json("sys", "user")
                mock_client_cls.assert_not_called()

    def test_api_key_from_env_var_used_to_construct_real_client(self):
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "env-test-key"}, clear=True):
            with mock.patch("billwatch.genai_sdk_provider.genai.Client") as mock_client_cls:
                mock_instance = mock_client_cls.return_value
                mock_instance.models.generate_content.return_value = _FakeResponseWithText("ok")
                provider = GenAISDKProvider()
                result = provider.complete_json("sys", "user")
                self.assertEqual(result, "ok")
                mock_client_cls.assert_called_once_with(api_key="env-test-key")

    def test_constructor_api_key_overrides_env_var(self):
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"}, clear=True):
            with mock.patch("billwatch.genai_sdk_provider.genai.Client") as mock_client_cls:
                mock_instance = mock_client_cls.return_value
                mock_instance.models.generate_content.return_value = _FakeResponseWithText("ok")
                provider = GenAISDKProvider(api_key="explicit-key")
                provider.complete_json("sys", "user")
                mock_client_cls.assert_called_once_with(api_key="explicit-key")

    def test_real_client_is_closed_after_use(self):
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"}, clear=True):
            with mock.patch("billwatch.genai_sdk_provider.genai.Client") as mock_client_cls:
                mock_instance = mock_client_cls.return_value
                mock_instance.models.generate_content.return_value = _FakeResponseWithText("ok")
                provider = GenAISDKProvider()
                provider.complete_json("sys", "user")
                mock_instance.close.assert_called_once()

    def test_real_client_is_closed_even_on_failure(self):
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "env-key"}, clear=True):
            with mock.patch("billwatch.genai_sdk_provider.genai.Client") as mock_client_cls:
                mock_instance = mock_client_cls.return_value
                mock_instance.models.generate_content.side_effect = httpx.ConnectError("down")
                provider = GenAISDKProvider()
                with self.assertRaises(LLMProviderError):
                    provider.complete_json("sys", "user")
                mock_instance.close.assert_called_once()

    def test_injected_client_is_never_closed_by_the_provider(self):
        # The _client injection hook is caller-owned (used by every other
        # test in this file) -- the provider must not close a client it
        # did not construct itself.
        fake = _FakeClient(response=_FakeResponseWithText("ok"))
        provider = GenAISDKProvider(_client=fake)
        provider.complete_json("sys", "user")
        self.assertFalse(fake.closed)

    def test_api_key_value_never_appears_in_error_message(self):
        secret = "totally-fake-secret-abc123xyz"
        exc = genai_errors.ClientError(code=401, response_json={"error": "unauthorized"})
        fake = _FakeClient(exception=exc)
        provider = GenAISDKProvider(api_key=secret, _client=fake)
        with self.assertRaises(LLMProviderError) as ctx:
            provider.complete_json("sys", "user")
        self.assertNotIn(secret, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
