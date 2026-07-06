import logging
from typing import Optional

from .heads.base import BaseHead
from .heads.asr import ASRHead
from .heads.emotion import EmotionHead
from .heads.prosody import ProsodyHead
from .heads.stress import StressHead
from .heads.fluency import FluencyHead
from .heads.event import EventHead

logger = logging.getLogger(__name__)

_DEFAULT_HEADS: dict[str, type[BaseHead]] = {
    "asr": ASRHead,
    "emotion": EmotionHead,
    "prosody": ProsodyHead,
    "stress": StressHead,
    "fluency": FluencyHead,
    "event": EventHead,
}


class HeadRegistry:
    def __init__(self, heads: Optional[dict[str, type[BaseHead]]] = None):
        self._heads: dict[str, type[BaseHead]] = {}
        for name, cls in (heads or _DEFAULT_HEADS).items():
            self.register(name, cls)

    def register(self, name: str, head_class: type[BaseHead]) -> None:
        if not issubclass(head_class, BaseHead):
            raise TypeError(f"{head_class.__name__} is not a subclass of BaseHead")
        self._heads[name] = head_class
        logger.debug("Registered head: %s -> %s", name, head_class.__name__)

    def get_head(self, name: str) -> BaseHead:
        cls = self._heads.get(name)
        if cls is None:
            raise KeyError(f"Unknown head: {name}. Available: {list(self._heads)}")
        return cls()

    def list_available_heads(self) -> list[str]:
        return list(self._heads)
