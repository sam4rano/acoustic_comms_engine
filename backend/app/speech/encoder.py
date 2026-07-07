import asyncio
import logging
from typing import Optional

import torch

from .types import AcousticEmbedding

logger = logging.getLogger(__name__)


class SpeechEncoder:
    def __init__(self, device: str = "cpu"):
        self.device = device
        self._model: Optional[torch.nn.Module] = None
        self._load_lock = asyncio.Lock()

    async def load_model(self, checkpoint: str, device: Optional[str] = None) -> None:
        if device is not None:
            self.device = device

        async with self._load_lock:
            if self._model is not None:
                logger.info("Encoder model already loaded, skipping")
                return

            logger.info("Loading encoder model from %s onto %s", checkpoint, self.device)
            try:
                self._model = await _async_torch_load(checkpoint, self.device)
                self._model.eval()
                logger.info("Encoder model loaded successfully")
            except RuntimeError as exc:
                if "out of memory" in str(exc).lower() and self.device != "cpu":
                    logger.warning("GPU OOM loading encoder, falling back to CPU: %s", exc)
                    self.device = "cpu"
                    self._model = await _async_torch_load(checkpoint, "cpu")
                    self._model.eval()
                else:
                    raise

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    async def encode(self, waveform: torch.Tensor, sample_rate: int = 16000) -> AcousticEmbedding:
        if self._model is None:
            from app.core.config import settings
            checkpoint = settings.SPEECH_ENCODER_PATH or settings.SPEECH_ENCODER
            logger.info("Encoder model not loaded — loading %s lazily", checkpoint)
            await self.load_model(checkpoint)

        if waveform.dim() not in (1, 2):
            raise ValueError(
                f"Expected 1D or 2D waveform tensor, got {waveform.dim()}D"
            )

        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)

        if waveform.size(0) != 1:
            raise ValueError(
                f"Expected single-channel waveform, got {waveform.size(0)} channels"
            )

        try:
            with torch.no_grad():
                embedding_tensor = self._model(waveform.to(self.device), sample_rate)
        except RuntimeError as exc:
            if "out of memory" in str(exc).lower() and self.device != "cpu":
                logger.warning("GPU OOM during encode, falling back to CPU")
                self.device = "cpu"
                self._model = self._model.to("cpu")
                with torch.no_grad():
                    embedding_tensor = self._model(waveform.cpu())
            else:
                raise

        vector = embedding_tensor.squeeze().cpu().tolist()
        if isinstance(vector, float):
            vector = [vector]
        dims = len(vector)

        return AcousticEmbedding(
            vector=vector,
            dims=dims,
            encoder_version=getattr(self._model, "_encoder_version", "silero-vad@1.0"),
        )


async def _async_torch_load(checkpoint: str, device: str) -> torch.nn.Module:
    """Offload torch.hub.load into a thread to avoid blocking the event loop."""
    loop = asyncio.get_running_loop()

    def _load() -> torch.nn.Module:
        if any(checkpoint.endswith(ext) for ext in (".pt", ".pth", ".jit")):
            model = torch.jit.load(checkpoint, map_location=device)
        else:
            result = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model=checkpoint,
                force_reload=False,
                trust_repo=True,
            )
            # silero_vad returns (model, utils) tuple
            model = result[0] if isinstance(result, tuple) else result
            model._encoder_version = f"{checkpoint}@1.0"
        return model

    return await loop.run_in_executor(None, _load)
