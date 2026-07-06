from __future__ import annotations

import logging
from uuid import UUID

from app.graph.traverser import GraphTraverser
from app.graph.types import ConversationGraph
from app.memory.service import (
    AnalysisConfig as MemoryAnalysisConfig,
    MemoryService,
)
from app.memory.types import RetrievalBundle, TurnSummary
from app.reasoning.agents.base import BaseAgent
from app.reasoning.llm_client import LLMClient
from app.reasoning.schemas import AnalysisConfig, MemoryContext

logger = logging.getLogger(__name__)


class Retriever(BaseAgent):
    name = "retriever"

    def __init__(
        self,
        llm_client: LLMClient,
        memory_service: MemoryService,
        graph_traverser: GraphTraverser,
        model: str | None = None,
    ) -> None:
        super().__init__(llm_client, model)
        self._memory = memory_service
        self._traverser = graph_traverser

    async def run(
        self,
        graph: ConversationGraph,
        memory_context: MemoryContext,
        config: AnalysisConfig,
    ) -> RetrievalBundle:
        # Convert reasoning AnalysisConfig to memory service AnalysisConfig
        mem_config = MemoryAnalysisConfig(
            focus=config.focus,
            dimensions=config.dimensions,
            language=config.language,
            enabled_heads=list(config.enabled_heads),
            min_turn_confidence=config.min_turn_confidence,
            include_prior_sessions=config.include_prior_sessions,
            max_turns=config.max_turns,
        )

        bundle = await self._memory.build_context(
            session_id=graph.session_id,
            user_id=memory_context.user_id,
            config=mem_config,
        )

        # Add core turns from the graph
        bundle.core_turns = self._extract_core_turns(graph, config)

        # Enrich metadata
        bundle.metadata["session_id"] = str(graph.session_id)
        bundle.metadata["speaker_count"] = len(graph.speakers)
        bundle.metadata["total_turns"] = len(graph.turns)
        bundle.metadata["total_duration_ms"] = graph.duration_ms
        bundle.metadata["enabled_heads"] = list(config.enabled_heads)

        return bundle

    def _extract_core_turns(
        self,
        graph: ConversationGraph,
        config: AnalysisConfig,
    ) -> list[TurnSummary]:
        turns: list[TurnSummary] = []
        for t in graph.turns:
            if t.confidence < config.min_turn_confidence:
                continue
            turns.append(
                TurnSummary(
                    turn_id=t.id,
                    speaker_label=self._speaker_label(graph, t.speaker_id),
                    text=t.text,
                    start_ms=t.start_ms,
                    end_ms=t.end_ms,
                    confidence=t.confidence,
                    acoustic_labels=dict(t.acoustic_labels),
                )
            )

        turns.sort(key=lambda t: t.start_ms)

        if len(turns) <= 20:
            return turns

        head = turns[:10]
        tail = turns[-10:]
        compressed = head + tail
        for t in compressed:
            t.acoustic_labels["_compressed"] = "true"
        return compressed

    def _speaker_label(self, graph: ConversationGraph, speaker_id: UUID) -> str:
        for s in graph.speakers:
            if s.id == speaker_id:
                return s.label
        return str(speaker_id)
