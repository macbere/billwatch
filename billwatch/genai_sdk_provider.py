"""
Google GenAI SDK Provider (Build 4, Stage 4B).

An ADDITIVE LLMProvider implementation using the official, GA google-genai
SDK (installed as 2.17.0) rather than hand-rolled HTTP. This satisfies the
hackathon's mandatory "Google Agent Framework" requirement (GenAI SDK is
explicitly listed as an accepted framework) while changing nothing about
the existing provider boundary contract: complete_json() still returns
raw, untrusted text for the existing llm_schemas.py validation layer to
judge -- this module makes no domain decisions of any kind.

This module does NOT modify billwatch/llm_provider.py, billwatch/
llm_schemas.py, or billwatch/extraction.py. It reuses LLMProviderError
from llm_provider.py so every existing caller's error handling (e.g.
extraction.py's `except LLMProviderError`) works unchanged for this
provider too.

CREDENTIALS: identical policy to GeminiProvider -- api_key comes only
from the constructor parameter or the GEMINI_API_KEY environment
variable, is never hardcoded, and is never included in any exception
message.

ERROR HANDLING (all verified against the actual installed SDK this
session, not assumed): google.genai.errors.APIError (covers both
ClientError -- 4xx, e.g. bad/missing auth -- and ServerError -- 5xx),
google.genai.errors.UnknownApiResponseError (malformed API response,
a ValueError subclass), and httpx.HTTPError (network/timeout failures
at the transport level, since the SDK uses httpx internally) are all
wrapped as LLMProviderError. An empty/candidate-less response
(response.text is None -- confirmed this is the SDK's real behavior,
not an exception) is also treated as an explicit LLMProviderError,
never silently passed through as if it were valid text. Any other
exception type is a genuine bug and is allowed to propagate.

BOUNDED 503 RETRY (added this pass, forensically justified by repeated
production/local evidence of transient Gemini "503 UNAVAILABLE -- high
demand" responses): when the underlying call raises a genai_errors.
ServerError whose .code is 503 and/or .status is "UNAVAILABLE" -- both
real attributes exposed by APIError.__init__, confirmed by direct
inspection of the installed SDK, not string-matched -- complete_json()
retries the SAME generate_content() call up to _MAX_ATTEMPTS times total
(1 initial + 2 retries), with a short bounded delay between attempts.
No other exception type or status code is ever retried: 4xx client
errors, malformed/unknown responses, transport errors, and any other
ServerError (e.g. a plain 500) all still fail on the first attempt,
preserving the existing fail-closed behavior exactly. The client is
still constructed/closed exactly once per complete_json() call
regardless of how many retry attempts occur -- retries reuse the same
client and config, they do not reconnect.
"""

import os
import time
from typing import Optional

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .llm_provider import LLMProvider, LLMProviderError


class GenAISDKProvider(LLMProvider):

    _MAX_ATTEMPTS = 3
    _RETRY_BACKOFF_SECONDS = 0.5

    def __init__(
        self,
        model: str = "gemini-3.5-flash",
        api_key: Optional[str] = None,
        timeout_seconds: float = 30.0,
        _client=None,
    ):
        """_client is an internal/test-only hook: when supplied, it is used
        directly instead of constructing a real google.genai.Client, and
        the API key requirement below is bypassed entirely -- this lets
        tests inject a fake client with no real credential involved.
        Production callers should never pass _client."""
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.timeout_seconds = timeout_seconds
        self._client = _client

    @staticmethod
    def _is_retryable_503(exc) -> bool:
        """True only for a genai_errors.ServerError whose real .code/.status
        attributes (set by the SDK's own APIError.__init__, not guessed)
        identify a transient 503 UNAVAILABLE. Never true for ClientError
        (4xx) or any other ServerError status."""
        return isinstance(exc, genai_errors.ServerError) and (
            getattr(exc, "code", None) == 503
            or getattr(exc, "status", None) == "UNAVAILABLE"
        )

    def _generate_with_retry(self, client, config, user_content):
        last_error = None
        for attempt in range(self._MAX_ATTEMPTS):
            try:
                return client.models.generate_content(
                    model=self.model,
                    contents=user_content,
                    config=config,
                )
            except genai_errors.UnknownApiResponseError as exc:
                raise LLMProviderError(
                    f"GenAI SDK returned an unrecognized API response: {exc}"
                ) from exc
            except genai_errors.APIError as exc:
                if self._is_retryable_503(exc) and attempt < self._MAX_ATTEMPTS - 1:
                    last_error = exc
                    time.sleep(self._RETRY_BACKOFF_SECONDS)
                    continue
                raise LLMProviderError(f"GenAI SDK API error: {exc}") from exc
            except httpx.HTTPError as exc:
                raise LLMProviderError(f"GenAI SDK transport error: {exc}") from exc
        # Unreachable in practice (the loop always returns or raises), but
        # kept as a safe fallback rather than an unhandled fall-through.
        raise LLMProviderError(f"GenAI SDK API error: {last_error}")

    def complete_json(self, system_prompt: str, user_content: str) -> str:
        if self._client is not None:
            client = self._client
        else:
            if not self.api_key:
                raise LLMProviderError(
                    "GEMINI_API_KEY is not set. GenAISDKProvider cannot be "
                    "used without real credentials -- no key is hard-coded "
                    "and none will be silently substituted."
                )
            client = genai.Client(api_key=self.api_key)

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
        )

        try:
            response = self._generate_with_retry(client, config, user_content)
        finally:
            if self._client is None:
                client.close()

        try:
            text = response.text
        except (ValueError, AttributeError) as exc:
            raise LLMProviderError(f"GenAI SDK response could not be read: {exc}") from exc

        if text is None:
            raise LLMProviderError(
                "GenAI SDK returned an empty response (no candidates); "
                "treating as a provider failure, not a valid empty result."
            )
        return text
