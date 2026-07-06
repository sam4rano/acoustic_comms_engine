"""Tests for the ReasoningOrchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.graph.analyzer import GraphAnalyzer
from app.graph.traverser import GraphTraverser
from app.graph.types import ConversationGraph
from app.memory.service import MemoryService
from app.memory.types import RetrievalBundle, TurnSummary
from app.reasoning.errors import InsufficientContextError
from app.reasoning.llm_client import LLMClient
from app.reasoning.orchestrator import ReasoningOrchestrator
from app.reasoning.schemas import (
    AgentStepTrace,
    AnalysisConfig,
    AnalysisPlan,
    AnalysisReport,
    Claim,
    DraftAssessment,
    EvidenceRef,
    PlanStep,
    VerifiedAssessment,
    VerifiedClaim,
)
from tests.reasoning.conftest import SPEAKER_A_ID, SPEAKER_B_ID, SESSION_ID, USER_ID, TURN_IDS


def _make_orchestrator() -> ReasoningOrchestrator:
    llm = MagicMock(spec=LLMClient)
    traverser = MagicMock(spec=GraphTraverser)
    analyzer = MagicMock(spec=GraphAnalyzer)
    memory = MagicMock(spec=MemoryService)
    memory.build_context = AsyncMock(return_value=RetrievalBundle(
        core_turns=[],
        relevant_turns=[],
        metadata={},
    ))
    return ReasoningOrchestrator(
        llm_client=llm,
        graph_traverser=traverser,
        graph_analyzer=analyzer,
        memory_service=memory,
    )


class TestReasoningOrchestrator:
    async def test_full_pipeline_runs(
        self,
        orchestrator: ReasoningOrchestrator,
        sample_graph: ConversationGraph,
        default_config: AnalysisConfig,
    ):
        report = await orchestrator.run(
            session_id=SESSION_ID,
            user_id=USER_ID,
            graph=sample_graph,
            config=default_config,
        )
        assert isinstance(report, AnalysisReport)
        assert report.scores.overall >= 0

    async def test_agent_trace_populated(
        self,
        orchestrator: ReasoningOrchestrator,
        sample_graph: ConversationGraph,
        default_config: AnalysisConfig,
    ):
        report = await orchestrator.run(
            session_id=SESSION_ID,
            user_id=USER_ID,
            graph=sample_graph,
            config=default_config,
        )
        assert len(report.agent_trace) > 0
        agent_names = {t.agent for t in report.agent_trace}
        assert "retriever" in agent_names
        assert "planner" in agent_names
        assert "reasoner" in agent_names
        assert "verifier" in agent_names
        assert "scorer" in agent_names

    async def test_insufficient_turns_raises_error(
        self,
        default_config: AnalysisConfig,
        sample_speakers,
    ):
        orchestrator = _make_orchestrator()
        empty_graph = ConversationGraph(
            session_id=SESSION_ID,
            speakers=sample_speakers,
            turns=[],
            embeddings=[],
            events=[],
            edges=[],
        )
        with pytest.raises(InsufficientContextError, match="minimum is 3"):
            await orchestrator.run(
                session_id=SESSION_ID,
                user_id=USER_ID,
                graph=empty_graph,
                config=default_config,
            )

    async def test_single_speaker_handled(
        self,
        orchestrator: ReasoningOrchestrator,
        single_speaker_graph: ConversationGraph,
        default_config: AnalysisConfig,
    ):
        report = await orchestrator.run(
            session_id=SESSION_ID,
            user_id=USER_ID,
            graph=single_speaker_graph,
            config=default_config,
        )
        assert isinstance(report, AnalysisReport)

    async def test_timeout_during_pipeline(
        self,
        sample_graph: ConversationGraph,
    ):
        orch = _make_orchestrator()
        fast_config = AnalysisConfig(timeout_per_agent_s=0.001)

        with pytest.raises(Exception):
            await orch.run(
                session_id=SESSION_ID,
                user_id=USER_ID,
                graph=sample_graph,
                config=fast_config,
            )

    async def test_agent_trace_has_error_on_timeout(
        self,
        sample_graph: ConversationGraph,
    ):
        orch = _make_orchestrator()
        fast_config = AnalysisConfig(timeout_per_agent_s=0.001)

        with pytest.raises(Exception):
            await orch.run(
                session_id=SESSION_ID,
                user_id=USER_ID,
                graph=sample_graph,
                config=fast_config,
            )
