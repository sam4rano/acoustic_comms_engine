"""Tests for the LLMClient abstraction layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from openai import (
    APIError,
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    RateLimitError,
)
from pydantic import BaseModel

from app.reasoning.errors import LLMJSONError, LLMTimeoutError, LLMUnavailableError
from app.reasoning.llm_client import LLMClient, TokenUsage


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _fake_request() -> httpx.Request:
    return httpx.Request("POST", "http://test/v1/chat/completions")


def _fake_response(status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code=status_code, request=_fake_request())


# ======================================================================
# Ollama detection
# ======================================================================


class TestOllamaDetection:
    def test_detects_ollama_via_port(self):
        client = LLMClient(base_url="http://localhost:11434/v1")
        assert client._is_ollama is True

    def test_detects_ollama_via_hostname(self):
        client = LLMClient(base_url="http://ollama.local:8080/v1")
        assert client._is_ollama is True

    def test_detects_non_ollama_for_vllm(self):
        client = LLMClient(base_url="http://localhost:8000/v1")
        assert client._is_ollama is False

    def test_detects_non_ollama_for_sglang(self):
        client = LLMClient(base_url="http://sglang-server:30000/v1")
        assert client._is_ollama is False


# ======================================================================
# OpenRouter detection
# ======================================================================


class TestOpenRouterDetection:
    def test_detects_openrouter_via_hostname(self):
        client = LLMClient(base_url="https://openrouter.ai/api/v1")
        assert client._is_openrouter is True
        assert client._is_ollama is False

    def test_detects_non_openrouter_for_ollama(self):
        client = LLMClient(base_url="http://localhost:11434/v1")
        assert client._is_openrouter is False

    def test_detects_non_openrouter_for_vllm(self):
        client = LLMClient(base_url="http://localhost:8000/v1")
        assert client._is_openrouter is False

    def test_passes_api_key_to_openrouter(self):
        with patch("app.reasoning.llm_client.AsyncOpenAI") as mock_cls:
            LLMClient(
                base_url="https://openrouter.ai/api/v1",
                api_key="sk-or-v1-test-key",
            )
            _, kwargs = mock_cls.call_args
            assert kwargs["api_key"] == "sk-or-v1-test-key"

    def test_passes_headers_to_openrouter(self):
        with patch("app.reasoning.llm_client.AsyncOpenAI") as mock_cls:
            LLMClient(
                base_url="https://openrouter.ai/api/v1",
                api_key="sk-or-v1-test-key",
                site_url="https://example.com",
                site_name="AcousticComms",
            )
            _, kwargs = mock_cls.call_args
            headers = kwargs["default_headers"]
            assert headers["HTTP-Referer"] == "https://example.com"
            assert headers["X-Title"] == "AcousticComms"

    async def test_openrouter_uses_standard_response_format(
        self,
        mock_openrouter_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        client, mock_create = mock_openrouter_client
        mock_create.return_value = build_mock_response()

        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        await client.complete(
            system_prompt="Be a bot.",
            user_prompt="Output JSON.",
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "Foo", "schema": schema},
            },
        )

        call_kwargs = mock_create.await_args[1]
        assert "response_format" in call_kwargs
        assert call_kwargs["response_format"]["type"] == "json_schema"

    async def test_openrouter_supports_structured_output(
        self,
        mock_openrouter_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        """OpenRouter uses `response_format` (same as vLLM), not Ollama's `format`."""
        from tests.reasoning.conftest import SampleOutput

        client, mock_create = mock_openrouter_client
        mock_create.return_value = build_mock_response(
            content='{"result": "openrouter", "score": 0.9}',
        )

        model_instance, usage = await client.complete_structured(
            system_prompt="You are a bot.",
            user_prompt="Test.",
            output_model=SampleOutput,
        )

        assert model_instance.result == "openrouter"
        assert model_instance.score == 0.9

        # Verify response_format was used (standard path, not Ollama manual parse)
        call_kwargs = mock_create.await_args[1]
        assert "response_format" in call_kwargs


# ======================================================================
# complete() — core functionality
# ======================================================================


class TestComplete:
    async def test_returns_parsed_response_and_token_usage(
        self,
        mock_ollama_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        client, mock_create = mock_ollama_client
        mock_create.return_value = build_mock_response(
            content='{"answer": 42}',
        )

        parsed, usage = await client.complete(
            system_prompt="You are a bot.",
            user_prompt="What is the meaning of life?",
        )

        assert parsed == {"answer": 42}
        assert isinstance(usage, TokenUsage)
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20
        assert usage.total_tokens == 30

    async def test_sends_correct_messages(
        self,
        mock_vllm_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        client, mock_create = mock_vllm_client
        mock_create.return_value = build_mock_response()

        await client.complete(
            system_prompt="You are a bot.",
            user_prompt="Say hi.",
        )

        mock_create.assert_awaited_once()
        call_kwargs = mock_create.await_args[1]  # type: ignore[index]
        messages = call_kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "You are a bot."}
        assert messages[1] == {"role": "user", "content": "Say hi."}

    async def test_uses_default_model_when_model_is_none(
        self,
        mock_vllm_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        client, mock_create = mock_vllm_client
        client.default_model = "custom-model-7b"
        mock_create.return_value = build_mock_response(model="custom-model-7b")

        await client.complete(
            system_prompt="You are a bot.",
            user_prompt="Hello",
            model=None,
        )

        call_kwargs = mock_create.await_args[1]  # type: ignore[index]
        assert call_kwargs["model"] == "custom-model-7b"

    async def test_includes_response_format_in_non_ollama(
        self,
        mock_vllm_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        client, mock_create = mock_vllm_client
        mock_create.return_value = build_mock_response()

        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        await client.complete(
            system_prompt="You are a bot.",
            user_prompt="Output JSON.",
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "Foo", "schema": schema},
            },
        )

        call_kwargs = mock_create.await_args[1]  # type: ignore[index]
        assert "response_format" in call_kwargs
        assert call_kwargs["response_format"]["type"] == "json_schema"

    async def test_passes_format_to_extra_body_in_ollama(
        self,
        mock_ollama_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        client, mock_create = mock_ollama_client
        mock_create.return_value = build_mock_response()

        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        await client.complete(
            system_prompt="You are a bot.",
            user_prompt="Output JSON.",
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "Foo", "schema": schema},
            },
        )

        call_kwargs = mock_create.await_args[1]  # type: ignore[index]
        assert "extra_body" in call_kwargs
        assert call_kwargs["extra_body"]["format"] == schema

    async def test_handles_non_json_content(
        self,
        mock_ollama_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        client, mock_create = mock_ollama_client
        mock_create.return_value = build_mock_response(
            content="Hello, this is plain text.",
        )

        parsed, _ = await client.complete(
            system_prompt="You are a bot.",
            user_prompt="Say hi.",
        )

        assert parsed == {"content": "Hello, this is plain text."}

    async def test_handles_null_content(
        self,
        mock_ollama_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        client, mock_create = mock_ollama_client
        mock_create.return_value = build_mock_response(content=None)  # type: ignore[arg-type]

        parsed, _ = await client.complete(
            system_prompt="You are a bot.",
            user_prompt="Say nothing.",
        )

        assert parsed == {}

    # ------------------------------------------------------------------
    # Retry & error handling
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "error_instance",
        [
            APIError("transient", _fake_request(), body=None),
            APIConnectionError(request=_fake_request()),
            APITimeoutError(request=_fake_request()),
            RateLimitError("transient", response=_fake_response(429), body=None),
            InternalServerError(
                "transient", response=_fake_response(500), body=None
            ),
        ],
    )
    async def test_retries_on_transient_errors(
        self,
        mock_ollama_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
        error_instance,
    ):
        client, mock_create = mock_ollama_client
        client.max_retries = 3

        mock_create.side_effect = [
            error_instance,
            error_instance,
            build_mock_response(content='{"ok": true}'),
        ]

        parsed, _ = await client.complete(
            system_prompt="You are a bot.",
            user_prompt="Retry me.",
        )

        assert parsed == {"ok": True}
        assert mock_create.await_count == 3

    async def test_raises_after_max_retries(
        self,
        mock_ollama_client: tuple[LLMClient, AsyncMock],
    ):
        client, mock_create = mock_ollama_client
        client.max_retries = 2
        err = APIError("always fails", _fake_request(), body=None)
        mock_create.side_effect = err

        with pytest.raises(LLMUnavailableError, match="after 2 retries"):
            await client.complete(
                system_prompt="You are a bot.",
                user_prompt="Fail.",
            )

        assert mock_create.await_count == 2

    async def test_raises_on_auth_error_without_retry(
        self,
        mock_ollama_client: tuple[LLMClient, AsyncMock],
    ):
        client, mock_create = mock_ollama_client
        client.max_retries = 3
        err = AuthenticationError(
            "invalid API key",
            response=_fake_response(401),
            body=None,
        )
        mock_create.side_effect = err

        with pytest.raises(LLMUnavailableError, match="Invalid API key"):
            await client.complete(
                system_prompt="You are a bot.",
                user_prompt="Auth test.",
            )

        # Should not have retried
        assert mock_create.await_count == 1

    async def test_raises_on_timeout(
        self,
        mock_ollama_client: tuple[LLMClient, AsyncMock],
    ):
        client, mock_create = mock_ollama_client
        client.timeout_s = 0.05  # Very short timeout for test

        async def _never_return(**kwargs):
            import asyncio
            await asyncio.sleep(3600)

        mock_create.side_effect = _never_return

        with pytest.raises(LLMTimeoutError, match="timed out"):
            await client.complete(
                system_prompt="You are a bot.",
                user_prompt="Timeout.",
            )

    async def test_passes_timeout_to_openai_client(self):
        """Verify timeout_s is forwarded to the AsyncOpenAI constructor."""
        from app.reasoning import llm_client as llm_mod

        original_init = llm_mod.AsyncOpenAI.__init__
        captured_timeout = None

        def _capturing_init(self, **kwargs):
            nonlocal captured_timeout
            captured_timeout = kwargs.get("timeout")
            return original_init(self, **kwargs)

        with patch.object(llm_mod.AsyncOpenAI, "__init__", _capturing_init):
            LLMClient(
                base_url="http://test:8000/v1",
                timeout_s=42.0,
            )

        assert captured_timeout == 42.0


# ======================================================================
# complete_structured() — Pydantic model output
# ======================================================================


class SampleOutput(BaseModel):
    result: str
    score: float


class TestCompleteStructured:
    async def test_returns_pydantic_model_with_vllm(
        self,
        mock_vllm_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        client, mock_create = mock_vllm_client
        mock_create.return_value = build_mock_response(
            content='{"result": "4", "score": 1.0}',
        )

        model_instance, usage = await client.complete_structured(
            system_prompt="You are a bot.",
            user_prompt="What is 2+2?",
            output_model=SampleOutput,
        )

        assert model_instance.result == "4"
        assert model_instance.score == 1.0
        assert isinstance(usage, TokenUsage)

    async def test_uses_response_format_with_vllm(
        self,
        mock_vllm_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        client, mock_create = mock_vllm_client
        mock_create.return_value = build_mock_response()

        await client.complete_structured(
            system_prompt="You are a bot.",
            user_prompt="What is 2+2?",
            output_model=SampleOutput,
        )

        call_kwargs = mock_create.await_args[1]  # type: ignore[index]
        assert "response_format" in call_kwargs
        assert call_kwargs["response_format"]["type"] == "json_schema"
        schema = call_kwargs["response_format"]["json_schema"]
        assert schema["name"] == "SampleOutput"

    async def test_falls_back_to_manual_parse_on_ollama(
        self,
        mock_ollama_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        """Ollama skips ``response_format`` and parses JSON from plain text."""
        client, mock_create = mock_ollama_client
        mock_create.return_value = build_mock_response(
            content='{"result": "42", "score": 0.5}',
        )

        model_instance, usage = await client.complete_structured(
            system_prompt="You are a bot.",
            user_prompt="What is 2+2?",
            output_model=SampleOutput,
        )

        assert model_instance.result == "42"
        assert model_instance.score == 0.5

        # Should NOT have passed response_format
        call_kwargs = mock_create.await_args[1]  # type: ignore[index]
        assert "response_format" not in call_kwargs

    async def test_raises_json_error_on_invalid_response(
        self,
        mock_ollama_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        client, mock_create = mock_ollama_client
        mock_create.return_value = build_mock_response(
            content="This is not JSON at all.",
        )

        with pytest.raises(LLMJSONError, match="SampleOutput"):
            await client.complete_structured(
                system_prompt="You are a bot.",
                user_prompt="Bad output.",
                output_model=SampleOutput,
            )

    async def test_raises_json_error_on_missing_fields(
        self,
        mock_ollama_client: tuple[LLMClient, AsyncMock],
        build_mock_response,
    ):
        client, mock_create = mock_ollama_client
        mock_create.return_value = build_mock_response(
            content='{"result": "only"}',
        )

        with pytest.raises(LLMJSONError, match="SampleOutput"):
            await client.complete_structured(
                system_prompt="You are a bot.",
                user_prompt="Missing field.",
                output_model=SampleOutput,
            )


# ======================================================================
# Configuration / defaults
# ======================================================================


class TestConfiguration:
    def test_default_ollama_url(self):
        client = LLMClient()
        assert "11434" in str(client._client.base_url)

    def test_default_model_is_set(self):
        client = LLMClient(default_model="my-model")
        assert client.default_model == "my-model"

    def test_custom_timeout(self):
        client = LLMClient(timeout_s=30.0)
        assert client.timeout_s == 30.0

    def test_custom_max_retries(self):
        client = LLMClient(max_retries=5)
        assert client.max_retries == 5

    def test_token_usage_dataclass(self):
        usage = TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3)
        assert usage.prompt_tokens == 1
        assert usage.completion_tokens == 2
        assert usage.total_tokens == 3
        with pytest.raises(AttributeError):
            usage.prompt_tokens = 99  # type: ignore[misc]
