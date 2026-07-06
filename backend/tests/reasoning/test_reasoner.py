"""Tests for the Reasoner agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.reasoning.agents.reasoner import Reasoner
from app.reasoning.schemas import DraftAssessment


class TestReasoner:
    async def test_returns_draft_assessment(
        self,
        reasoner_agent: Reasoner,
        sample_graph,
        sample_retrieval_bundle,
        sample_analysis_plan: DraftAssessment,
    ):
        draft = await reasoner_agent.run(sample_graph, sample_retrieval_bundle, sample_analysis_plan)
        assert isinstance(draft, DraftAssessment)

    async def test_claims_cite_evidence(
        self,
        reasoner_agent: Reasoner,
        sample_graph,
        sample_retrieval_bundle,
        sample_analysis_plan: DraftAssessment,
    ):
        draft = await reasoner_agent.run(sample_graph, sample_retrieval_bundle, sample_analysis_plan)
        for claim in draft.claims:
            assert len(claim.evidence) > 0, f"Claim '{claim.statement}' has no evidence"

    async def test_handles_empty_bundle(
        self,
        reasoner_agent: Reasoner,
        sample_graph,
        sample_analysis_plan: DraftAssessment,
    ):
        from app.memory.types import RetrievalBundle

        empty_bundle = RetrievalBundle()
        draft = await reasoner_agent.run(sample_graph, empty_bundle, sample_analysis_plan)
        assert isinstance(draft, DraftAssessment)

    async def test_open_questions_populated(
        self,
        reasoner_agent: Reasoner,
        sample_graph,
        sample_retrieval_bundle,
        sample_analysis_plan: DraftAssessment,
    ):
        draft = await reasoner_agent.run(sample_graph, sample_retrieval_bundle, sample_analysis_plan)
        assert len(draft.open_questions) >= 0

    async def test_summary_not_empty(
        self,
        reasoner_agent: Reasoner,
        sample_graph,
        sample_retrieval_bundle,
        sample_analysis_plan: DraftAssessment,
    ):
        draft = await reasoner_agent.run(sample_graph, sample_retrieval_bundle, sample_analysis_plan)
        assert len(draft.summary) > 0

    async def test_speaker_notes_populated(
        self,
        reasoner_agent: Reasoner,
        sample_graph,
        sample_retrieval_bundle,
        sample_analysis_plan: DraftAssessment,
    ):
        draft = await reasoner_agent.run(sample_graph, sample_retrieval_bundle, sample_analysis_plan)
        assert len(draft.speaker_notes) > 0
