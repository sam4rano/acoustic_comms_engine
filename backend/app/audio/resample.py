import logging
from typing import Optional

import torch
import torchaudio

from app.audio.errors import ResamplingError

logger = logging.getLogger(__name__)


class Resampler:
    """Lazy-loaded multi-rate audio resampler.

    Caches ``torchaudio.transforms.Resample`` instances by
    ``(orig_sr, target_sr)`` pair so that repeated resampling
    between the same rates reuses the pre-computed filter.
    """

    _instances: dict[tuple[int, int], torchaudio.transforms.Resample] = {}

    @classmethod
    def _get(cls, orig_sr: int, target_sr: int) -> torchaudio.transforms.Resample:
        key = (orig_sr, target_sr)
        if key not in cls._instances:
            logger.debug("Creating new resampler for %d → %d Hz", orig_sr, target_sr)
            cls._instances[key] = torchaudio.transforms.Resample(
                orig_freq=orig_sr,
                new_freq=target_sr,
                dtype=torch.float32,
            )
        return cls._instances[key]

    @classmethod
    def resample(
        cls,
        waveform: torch.Tensor,
        orig_sr: int,
        target_sr: int = 16000,
    ) -> torch.Tensor:
        """Resample ``waveform`` from ``orig_sr`` to ``target_sr``.

        Args:
            waveform: ``[1, T]`` float32 tensor.
            orig_sr: Source sample rate in Hz.
            target_sr: Target sample rate in Hz (default 16 000).

        Returns:
            Resampled ``[1, T']`` float32 tensor.

        Raises:
            ResamplingError: If the input is empty or has an unexpected shape.
        """
        if waveform.numel() == 0:
            raise ResamplingError("Cannot resample empty waveform")

        if waveform.dim() != 2 or waveform.size(0) != 1:
            raise ResamplingError(
                f"Expected shape [1, T], got {list(waveform.shape)}"
            )

        if orig_sr == target_sr:
            return waveform

        try:
            resampler = cls._get(orig_sr, target_sr)
            return resampler(waveform)
        except Exception as exc:
            raise ResamplingError(
                f"Resampling failed ({orig_sr} → {target_sr}): {exc}"
            ) from exc


def resample(
    waveform: torch.Tensor,
    orig_sr: int,
    target_sr: int = 16000,
) -> torch.Tensor:
    """Convenience wrapper around :meth:`Resampler.resample`."""
    return Resampler.resample(waveform, orig_sr, target_sr)
