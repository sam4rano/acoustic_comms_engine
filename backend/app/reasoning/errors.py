"""Custom error types for the reasoning pipeline."""


class ReasoningError(Exception):
    """Base exception for all reasoning pipeline errors."""


class LLMUnavailableError(ReasoningError):
    """The LLM backend is unreachable or returned a non-retryable error."""


class LLMTimeoutError(ReasoningError):
    """The LLM request exceeded the configured timeout."""


class LLMJSONError(ReasoningError):
    """Failed to parse LLM response as expected JSON / Pydantic model."""


class InsufficientContextError(ReasoningError):
    """The session does not meet the minimum requirements for analysis."""


class AgentTimeoutError(ReasoningError):
    """An agent step exceeded its configured timeout."""
