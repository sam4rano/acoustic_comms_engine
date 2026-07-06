"""Tests for the Retriever agent."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.memory.types import RetrievalBundle, TurnSummary
from app.reasoning.agents.retriever import Retriever
from app.reasoning.schemas import AnalysisConfig, MemoryContext


class TestRetriever:
    async def test_returns_retrieval_bundle(
        self,
        retriever_agent: Retriever,
        sample_graph,
        sample_memory_context: MemoryContext,
        default_config: AnalysisConfig,
    ):
        bundle = await retriever_agent.run(sample_graph, sample_memory_context, default_config)
        assert isinstance(bundle, RetrievalBundle)
        assert len(bundle.core_turns) > 0

    async def test_includes_metadata(
        self,
        retriever_agent: Retriever,
        sample_graph,
        sample_memory_context: MemoryContext,
        default_config: AnalysisConfig,
    ):
        bundle = await retriever_agent.run(sample_graph, sample_memory_context, default_config)
        assert "session_id" in bundle.metadata
        assert bundle.metadata["session_id"] == str(sample_graph.session_id)
        assert "speaker_count" in bundle.metadata
        assert bundle.metadata["speaker_count"] == 2
        assert "total_turns" in bundle.metadata
        assert bundle.metadata["total_turns"] == 5

    async def test_respects_config_focus(
        self,
        retriever_agent: Retriever,
        sample_graph,
        sample_memory_context: MemoryContext,
    ):
        config = AnalysisConfig(focus="empathy")
        bundle = await retriever_agent.run(sample_graph, sample_memory_context, config)
        assert isinstance(bundle, RetrievalBundle)

    async def test_filters_low_confidence_turns(
        self,
        retriever_agent: Retriever,
        sample_graph,
        sample_memory_context: MemoryContext,
    ):
        config = AnalysisConfig(min_turn_confidence=0.99)
        bundle = await retriever_agent.run(sample_graph, sample_memory_context, config)
        high_conf = [t for t in bundle.core_turns if t.confidence >= 0.99]
        assert len(high_conf) == 0

    async def test_compresses_long_sessions(
        self,
        retriever_agent: Retriever,
        long_session_graph,
        sample_memory_context: MemoryContext,
        default_config: AnalysisConfig,
    ):
        bundle = await retriever_agent.run(long_session_graph, sample_memory_context, default_config)
        assert len(bundle.core_turns) <= 20

    async def test_handles_empty_graph(
        self,
        retriever_agent: Retriever,
        sample_memory_context: MemoryContext,
        default_config: AnalysisConfig,
        sample_speakers,
    ):
        from app.graph.types import ConversationGraph
        from uuid import uuid4

        empty_graph = ConversationGraph(
            session_id=uuid4(),
            speakers=sample_speakers,
            turns=[],
            embeddings=[],
            events=[],
            edges=[],
        )
        bundle = await retriever_agent.run(empty_graph, sample_memory_context, default_config)
        assert bundle.core_turns == []
