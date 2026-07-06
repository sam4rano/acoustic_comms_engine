import logging

import torch

logger = logging.getLogger(__name__)


class Denoiser:
    """Noise reduction front-end.

    Currently a no-op passthrough that logs a warning on first use.
    Swap the implementation for an RNNoise wrapper when the native
    ``noisereduce`` or ``rnnoise`` package is added to the project.

    The interface is kept stable so callers do not need to change
    when a real denoiser is wired in.
    """

    _warned: bool = False

    @classmethod
    def denoise(
        cls,
        waveform: torch.Tensor,
        sample_rate: int = 16000,
    ) -> torch.Tensor:
        """Apply noise reduction to ``waveform``.

        Args:
            waveform: ``[1, T]`` float32 mono tensor.
            sample_rate: Sample rate in Hz (default 16 000).

        Returns:
            Denoised ``[1, T]`` float32 tensor (same shape).
        """
        if not cls._warned:
            logger.warning(
                "No noise-reduction library available; returning original waveform. "
                "Install noisereduce or rnnoise to enable denoising."
            )
            cls._warned = True
        return waveform
