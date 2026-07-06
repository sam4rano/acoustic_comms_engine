"""Thin wrapper over Ollama / vLLM / SGLang OpenAI-compatible API.

Auto-detects Ollama backend by checking the base URL for ``"11434"`` or
``"ollama"``.  Handles the ``response_format`` → ``extra_body["format"]``
mapping required by Ollama's custom /v1/chat/completions implementation.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from openai import (
    APIError,
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    InternalServerError,
    RateLimitError,
)
from pydantic import BaseModel

from app.reasoning.errors import LLMJSONError, LLMTimeoutError, LLMUnavailableError


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


_TRANSIENT_ERRORS = (
    APIError,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)


class LLMClient:
    """Thin wrapper over OpenAI-compatible API backends.

    Supports Ollama, vLLM, SGLang, and OpenRouter.

    Parameters
    ----------
    base_url:
        Base URL of the OpenAI-compatible API endpoint.
        Default ``http://localhost:11434/v1`` (Ollama).
    default_model:
        Model name to use when ``model`` is not passed to ``complete()`` /
        ``complete_structured()``.
    api_key:
        API key for authentication.  Required for OpenRouter.
        If ``None``, a placeholder ``"not-needed"`` is used (works for Ollama).
    timeout_s:
        Maximum seconds to wait for a single request.
    max_retries:
        Number of times to retry on transient errors (exponential backoff).
    site_url:
        Site URL sent in the ``HTTP-Referer`` header (OpenRouter only).
    site_name:
        Site name sent in the ``X-Title`` header (OpenRouter only).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        default_model: str = "qwen3-8b-instruct",
        api_key: str | None = None,
        timeout_s: float = 120.0,
        max_retries: int = 3,
        site_url: str | None = None,
        site_name: str | None = None,
    ) -> None:
        self.default_model = default_model
        self.timeout_s = timeout_s
        self.max_retries = max_retries

        self._is_ollama = "11434" in base_url or "ollama" in base_url.lower()
        self._is_openrouter = "openrouter" in base_url.lower()

        resolved_key = api_key if api_key is not None else "not-needed"
        extra_headers: dict[str, str] = {}
        if self._is_openrouter:
            if site_url:
                extra_headers["HTTP-Referer"] = site_url
            if site_name:
                extra_headers["X-Title"] = site_name

        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=resolved_key,
            timeout=timeout_s,
            max_retries=0,  # We handle retry ourselves
            default_headers=extra_headers or None,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], TokenUsage]:
        """Send a completion request.

        Returns *(parsed_response_dict, token_usage)*.

        For Ollama backends ``response_format`` is mapped to
        ``extra_body["format"]`` because Ollama does not honour the
        standard ``response_format`` parameter.  Retries on transient
        failures with exponential backoff.

        Raises
        ------
        LLMUnavailableError
            After exhausting all retries, or on non-retryable errors
            such as an invalid API key (401).
        LLMTimeoutError
            The request exceeded the configured timeout.
        """
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format is not None:
            if self._is_ollama:
                kwargs.setdefault("extra_body", {})["format"] = response_format[
                    "json_schema"
                ]["schema"]
            else:
                kwargs["response_format"] = response_format

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.wait_for(
                    self._client.chat.completions.create(**kwargs),
                    timeout=self.timeout_s,
                )
            except asyncio.TimeoutError as exc:
                raise LLMTimeoutError(
                    f"LLM request timed out after {self.timeout_s}s"
                ) from exc
            except AuthenticationError as exc:
                raise LLMUnavailableError(
                    "Invalid API key — authentication failed"
                ) from exc
            except _TRANSIENT_ERRORS as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)
                continue

            # Success — parse and return
            content = response.choices[0].message.content
            if content:
                try:
                    parsed: dict[str, Any] = json.loads(content)
                except json.JSONDecodeError:
                    parsed = {"content": content}
            else:
                parsed = {}

            usage = response.usage
            return parsed, TokenUsage(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )

        raise LLMUnavailableError(
            f"LLM request failed after {self.max_retries} retries. "
            f"Last error: {last_error}"
        ) from last_error

    async def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_model: type[BaseModel],
        model: str | None = None,
        temperature: float = 0.0,
    ) -> tuple[BaseModel, TokenUsage]:
        """Send a completion and parse the response as *output_model*.

        Uses ``response_format`` (structured output / JSON schema) when
        the backend supports it (vLLM, SGLang).  Falls back to manual
        JSON parsing for backends such as Ollama that do not reliably
        honour the standard ``response_format`` parameter.

        Returns *(model_instance, token_usage)*.

        Raises
        ------
        LLMJSONError
            Response could not be parsed as the target *output_model*.
        """
        # For non-Ollama backends, try structured output first.
        if not self._is_ollama:
            try:
                schema = output_model.model_json_schema()
                result, usage = await self.complete(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    temperature=temperature,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": output_model.__name__,
                            "schema": schema,
                        },
                    },
                )
                return output_model.model_validate(result), usage
            except (LLMUnavailableError, LLMTimeoutError):
                raise
            except Exception:
                pass

        # Fallback: plain completion → manual JSON parse
        result, usage = await self.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            response_format=None,
        )
        try:
            return output_model.model_validate(result), usage
        except Exception as exc:
            raise LLMJSONError(
                f"Failed to parse LLM response as {output_model.__name__}: {exc}"
            ) from exc
