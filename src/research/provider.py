"""Provider adapters for optional OpenAI-compatible structured generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import json
import os
import time
from typing import Any
from urllib import error, request
import re


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    request_id: str | None
    model: str
    usage: dict[str, int] | None = None
    latency_seconds: float | None = None
    reasoning_content_present: bool = False
    reasoning_content_hash: str | None = None


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_payload: dict[str, Any], temperature: float) -> ProviderResponse:
        pass


class OpenAICompatibleProvider(LLMProvider):
    """Minimal stdlib adapter; secrets are read only from environment variables."""

    def __init__(
        self,
        *,
        max_tokens: int = 1600,
        timeout: int = 120,
        retry: int = 1,
        thinking_mode: bool | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        self.base_url = os.environ.get("LLM_BASE_URL", "").rstrip("/")
        self.api_key = os.environ.get("LLM_API_KEY", "")
        self.model = os.environ.get("LLM_MODEL", "")
        self.max_tokens = int(max_tokens)
        self.timeout = int(timeout)
        self.retry = int(retry)
        self.thinking_mode = thinking_mode
        self.reasoning_effort = reasoning_effort
        if not all((self.base_url, self.api_key, self.model)):
            raise RuntimeError("LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL are required for live LLM use")

    def generate(self, system_prompt: str, user_payload: dict[str, Any], temperature: float) -> ProviderResponse:
        payload_body = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        }
        if self.reasoning_effort:
            payload_body["reasoning_effort"] = self.reasoning_effort
        if self.thinking_mode is not None:
            payload_body["thinking"] = {"type": "enabled" if self.thinking_mode else "disabled"}
        if self.thinking_mode is not True:
            payload_body["response_format"] = {"type": "json_object"}
        body = json.dumps(payload_body).encode("utf-8")
        http_request = request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        last_error = None
        started = time.perf_counter()
        for _ in range(self.retry + 1):
            try:
                with request.urlopen(http_request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    request_id = response.headers.get("x-request-id") or payload.get("id")
                break
            except error.HTTPError as exc:
                response_text = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"HTTP {exc.code}: {redact_sensitive_text(response_text, [self.api_key])[:1000]}")
            except Exception as exc:
                last_error = exc
        else:
            raise RuntimeError("Live LLM request failed after configured retries") from last_error
        message = payload["choices"][0]["message"]
        reasoning = message.get("reasoning_content") or ""
        usage = {key: int(value) for key, value in (payload.get("usage") or {}).items() if isinstance(value, (int, float))}
        return ProviderResponse(
            message.get("content") or "",
            request_id,
            payload.get("model") or self.model,
            usage=usage,
            latency_seconds=time.perf_counter() - started,
            reasoning_content_present=bool(reasoning),
            reasoning_content_hash=hashlib.sha256(reasoning.encode("utf-8")).hexdigest() if reasoning else None,
        )


def redact_sensitive_text(text: str, secrets: list[str] | None = None) -> str:
    """Redact explicit known secrets and common authorization/key assignments."""
    redacted = text
    for secret in secrets or []:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    redacted = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)[^\s\"']+", r"\1[REDACTED]", redacted)
    redacted = re.sub(r"(?i)((?:api[_-]?key|token)\s*[=:]\s*)[^\s,;\"']+", r"\1[REDACTED]", redacted)
    return redacted


class FixtureProvider(LLMProvider):
    """Provider fixture with queued responses, including invalid-output repair tests."""

    def __init__(self, responses: list[str], model: str = "fixture-provider") -> None:
        self.responses = list(responses)
        self.model = model
        self.calls = 0

    def generate(self, system_prompt: str, user_payload: dict[str, Any], temperature: float) -> ProviderResponse:
        if self.calls >= len(self.responses):
            raise IndexError("FixtureProvider exhausted")
        text = self.responses[self.calls]
        self.calls += 1
        return ProviderResponse(text, f"fixture-{self.calls}", self.model)
