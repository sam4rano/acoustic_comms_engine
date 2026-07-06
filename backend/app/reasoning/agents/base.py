from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.reasoning.llm_client import LLMClient


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self, llm_client: LLMClient, model: str | None = None) -> None:
        self._llm = llm_client
        self._model = model

    @abstractmethod
    async def run(self, **kwargs) -> BaseModel:
        ...
