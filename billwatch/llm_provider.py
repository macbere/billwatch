"""
LLM Provider abstraction (Build 4).

The smallest clean boundary needed: ONE abstract method returning raw text.
Everything downstream (extraction.py, hypothesis_reasoning.py,
verification_planning.py) treats that text as UNTRUSTED and runs it
through its own strict, deterministic parser/validator -- never trusting
it directly, per "prompts are not security boundaries."

No SDK dependency is added. GeminiProvider is implemented with stdlib
urllib.request only (a plain HTTPS POST to the Gemini REST endpoint) --
this keeps the project dependency-free and Termux-friendly, at the cost
of not getting the official SDK's convenience wrappers. Justification is
documented in BUILD4-REPORT.md, Section 15.

CONFIRMED FACTS, not assumed (checked directly in this build session):
  - No GEMINI_API_KEY (or GOOGLE_API_KEY) is present in this environment.
  - This sandbox's network egress does not reach
    generativelanguage.googleapis.com (HTTP 403, x-deny-reason:
    host_not_allowed).
Both facts mean GeminiProvider cannot be exercised live in this session.
Prior to Build 4 Stage 1, this docstring incorrectly claimed the module
was "implemented and unit-tested against a fake HTTP layer" -- no such
test file existed at that time. That claim was inaccurate and has been
corrected here. As of Stage 1 (tests/test_llm_provider.py), it IS
unit-tested against a fake/mocked urllib.request.urlopen layer; no live
API call has been made or claimed.
"""

import json
import os
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Callable, Optional


class LLMProviderError(Exception):
    """Raised for provider-level failures: timeout, network/API error,
    missing credentials. NEVER raised for 'the model said something we
    don't like' -- that is a validation-layer concern, not a provider
    concern, and must not be conflated with this."""


class LLMProvider(ABC):
    @abstractmethod
    def complete_json(self, system_prompt: str, user_content: str) -> str:
        """
        Returns raw text from the model. The text MAY be malformed JSON,
        MAY be empty, MAY contain extra/dangerous-looking fields -- none
        of that is this method's concern. Callers must never trust this
        return value directly; it is parsed by a strict, deterministic
        validator specific to the calling component.
        """
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    """
    A documented, deterministic stub for unit/adversarial testing. No
    network, no randomness -- returns exactly what it's configured to
    return, so tests are fully reproducible. This is what Build 4's tests
    actually run against; it is explicitly NOT a claim of live Gemini
    behavior.
    """

    def __init__(self, response_fn: Optional[Callable[[str, str], str]] = None,
                 fixed_response: Optional[str] = None,
                 raise_error: Optional[Exception] = None):
        if sum(x is not None for x in (response_fn, fixed_response, raise_error)) != 1:
            raise ValueError(
                "MockLLMProvider requires exactly one of response_fn, "
                "fixed_response, or raise_error."
            )
        self._response_fn = response_fn
        self._fixed_response = fixed_response
        self._raise_error = raise_error
        self.calls = []  # recorded for test assertions

    def complete_json(self, system_prompt: str, user_content: str) -> str:
        self.calls.append((system_prompt, user_content))
        if self._raise_error is not None:
            raise self._raise_error
        if self._response_fn is not None:
            return self._response_fn(system_prompt, user_content)
        return self._fixed_response


class GeminiProvider(LLMProvider):
    """
    Thin, dependency-free REST wrapper around the Gemini API structured-
    output endpoint. Requires GEMINI_API_KEY in the environment. Never
    hard-codes a key. NOT exercised live in this build session (see module
    docstring) -- exists so a future session with real credentials and
    network access can use it unchanged.
    """

    _ENDPOINT_TEMPLATE = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{model}:generateContent?key={api_key}"
    )

    def __init__(self, model: str = "gemini-3.5-flash", api_key: Optional[str] = None,
                 timeout_seconds: float = 30.0):
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.timeout_seconds = timeout_seconds

    def complete_json(self, system_prompt: str, user_content: str) -> str:
        if not self.api_key:
            raise LLMProviderError(
                "GEMINI_API_KEY is not set. GeminiProvider cannot be used "
                "without real credentials -- no key is hard-coded and none "
                "will be silently substituted."
            )
        url = self._ENDPOINT_TEMPLATE.format(model=self.model, api_key=self.api_key)
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_content}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise LLMProviderError(f"Gemini API request failed: {exc}") from exc
        except TimeoutError as exc:
            raise LLMProviderError(f"Gemini API request timed out: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LLMProviderError(f"Gemini API returned invalid JSON: {exc}") from exc
        try:
            return raw["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                f"Unexpected Gemini API response shape: {raw!r}"
            ) from exc
