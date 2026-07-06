class AudioProcessingError(Exception):
    """Base error for audio processing failures."""


class VADError(AudioProcessingError):
    """Raised when voice activity detection fails."""


class ResamplingError(AudioProcessingError):
    """Raised when audio resampling fails."""
