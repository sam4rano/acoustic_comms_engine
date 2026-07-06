class StreamError(Exception):
    """Base error for streaming failures."""


class SessionNotFoundError(StreamError):
    """Raised when an operation targets a session that does not exist."""


class SessionLimitError(StreamError):
    """Raised when the maximum number of concurrent sessions is reached."""


class InvalidFrameError(StreamError):
    """Raised when an audio frame is malformed or cannot be processed."""


class RateLimitError(StreamError):
    """Raised when a client sends frames faster than the allowed rate."""
