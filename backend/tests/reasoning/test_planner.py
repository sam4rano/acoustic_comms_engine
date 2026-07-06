"""Tests for the Planner agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.reasoning.agents.planner import Planner
from app.reasoning.schemas import AnalysisConfig, AnalysisPlan


class TestPlanner:
    async def test_returns_analysis_plan(
        self,
        planner_agent: Planner,
        sample_graph,
        sample_retrieval_bundle,
        default_config: AnalysisConfig,
    ):
        plan = await planner_agent.run(sample_graph, sample_retrieval_bundle, default_config)
        assert isinstance(plan, AnalysisPlan)
        assert len(plan.steps) > 0
        assert len(plan.dimensions) > 0

    async def test_plan_includes_default_dimensions(
        self,
        planner_agent: Planner,
        sample_graph,
        sample_retrieval_bundle,
        default_config: AnalysisConfig,
    ):
        plan = await planner_agent.run(sample_graph, sample_retrieval_bundle, default_config)
        for dim in ("clarity", "pacing", "empathy", "assertiveness", "fluency", "engagement"):
            if dim in plan.dimensions:
                matching_steps = [s for s in plan.steps if s.id == dim]
                assert len(matching_steps) > 0, f"No step for dimension {dim}"

    async def test_adapts_to_single_speaker(
        self,
        planner_agent: Planner,
        single_speaker_graph,
        sample_retrieval_bundle,
        default_config: AnalysisConfig,
    ):
        plan = await planner_agent.run(single_speaker_graph, sample_retrieval_bundle, default_config)
        assert "assertiveness" not in plan.dimensions
        assert "engagement" not in plan.dimensions
        assert "single_speaker" in plan.constraints

    async def test_respects_disabled_heads(
        self,
        planner_agent: Planner,
        sample_graph,
        sample_retrieval_bundle,
    ):
        config = AnalysisConfig(enabled_heads=["asr"])
        plan = await planner_agent.run(sample_graph, sample_retrieval_bundle, config)
        assert "empathy" not in plan.dimensions

    async def test_handles_low_confidence_config(
        self,
        planner_agent: Planner,
        sample_graph,
        sample_retrieval_bundle,
    ):
        config = AnalysisConfig(min_turn_confidence=0.9)
        plan = await planner_agent.run(sample_graph, sample_retrieval_bundle, config)
        assert isinstance(plan, AnalysisPlan)

    async def test_respects_custom_dimensions(
        self,
        planner_agent: Planner,
        sample_graph,
        sample_retrieval_bundle,
    ):
        config = AnalysisConfig(dimensions=["fluency", "clarity"])
        plan = await planner_agent.run(sample_graph, sample_retrieval_bundle, config)
        assert plan.dimensions == ["fluency", "clarity"]
