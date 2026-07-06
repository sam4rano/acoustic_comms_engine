"""Tests for the Scorer agent."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.reasoning.agents.scorer import Scorer
from app.reasoning.schemas import (
    AnalysisConfig,
    AnalysisPlan,
    AnalysisReport,
    Claim,
    CoachingAction,
    CommunicationScores,
    DimensionScore,
    DraftAssessment,
    EvidenceRef,
    PlanStep,
    VerifiedAssessment,
    VerifiedClaim,
)


class TestScorer:
    async def test_scores_computed_from_claims(
        self,
        scorer_agent: Scorer,
        sample_graph,
        sample_analysis_plan: AnalysisPlan,
    ):
        verified = VerifiedAssessment(
            summary="Test",
            claims=[
                VerifiedClaim(
                    statement="Good clarity",
                    evidence=[EvidenceRef(type="turn", id=str(sample_graph.turns[0].id))],
                    dimension="clarity",
                    polarity="strength",
                    status="verified",
                    verification_note="OK",
                ),
                VerifiedClaim(
                    statement="Empathetic",
                    evidence=[EvidenceRef(type="turn", id=str(sample_graph.turns[0].id))],
                    dimension="empathy",
                    polarity="strength",
                    status="verified",
                    verification_note="OK",
                ),
            ],
        )
        report = await scorer_agent.run(verified, sample_graph, sample_analysis_plan)
        assert isinstance(report, AnalysisReport)
        assert len(report.scores.dimensions) > 0
        assert report.scores.overall > 0

    async def test_coaching_actions_generated(
        self,
        scorer_agent: Scorer,
        sample_graph,
        sample_analysis_plan: AnalysisPlan,
        sample_verified: VerifiedAssessment,
    ):
        report = await scorer_agent.run(sample_verified, sample_graph, sample_analysis_plan)
        assert len(report.coaching) > 0
        assert all(isinstance(a, CoachingAction) for a in report.coaching)

    async def test_confidence_capped_at_05_when_more_than_50_percent_removed(
        self,
        scorer_agent: Scorer,
        sample_graph,
        sample_analysis_plan: AnalysisPlan,
    ):
        verified = VerifiedAssessment(
            summary="Half removed",
            claims=[
                VerifiedClaim(
                    statement="Claim 1",
                    evidence=[EvidenceRef(type="turn", id="t1")],
                    dimension="clarity", polarity="strength",
                    status="verified", verification_note="OK",
                ),
                VerifiedClaim(
                    statement="Claim 2",
                    evidence=[EvidenceRef(type="turn", id="t2")],
                    dimension="clarity", polarity="weakness",
                    status="removed", verification_note="Removed",
                ),
                VerifiedClaim(
                    statement="Claim 3",
                    evidence=[EvidenceRef(type="turn", id="t3")],
                    dimension="clarity", polarity="neutral",
                    status="removed", verification_note="Removed",
                ),
            ],
            verification_score=0.5,
        )
        report = await scorer_agent.run(verified, sample_graph, sample_analysis_plan)
        assert report.confidence <= 0.5

    async def test_degraded_true_when_verification_score_below_03(
        self,
        scorer_agent: Scorer,
        sample_graph,
        sample_analysis_plan: AnalysisPlan,
        sample_degraded_verified: VerifiedAssessment,
    ):
        report = await scorer_agent.run(sample_degraded_verified, sample_graph, sample_analysis_plan)
        assert report.degraded is True
        assert report.degradation_reason is not None

    async def test_dimension_weights_redistributed(
        self,
        scorer_agent: Scorer,
        sample_graph,
    ):
        plan = AnalysisPlan(
            objective="Test",
            steps=[
                PlanStep(id="clarity", question="Q?", required_evidence=["transcript"], priority="high"),
            ],
            dimensions=["clarity"],
            constraints=[],
        )
        verified = VerifiedAssessment(
            summary="Test",
            claims=[
                VerifiedClaim(
                    statement="Good",
                    evidence=[EvidenceRef(type="turn", id="t1")],
                    dimension="clarity", polarity="strength",
                    status="verified", verification_note="OK",
                ),
            ],
        )
        report = await scorer_agent.run(verified, sample_graph, plan)
        assert len(report.scores.dimensions) == 1
        assert report.scores.dimensions[0].dimension == "clarity"

    async def test_coaching_references_specific_turns(
        self,
        scorer_agent: Scorer,
        sample_graph,
        sample_analysis_plan: AnalysisPlan,
        sample_verified: VerifiedAssessment,
    ):
        report = await scorer_agent.run(sample_verified, sample_graph, sample_analysis_plan)
        for action in report.coaching:
            assert isinstance(action.dimension, str)

    async def test_empty_claims_produces_base_scores(
        self,
        scorer_agent: Scorer,
        sample_graph,
        sample_analysis_plan: AnalysisPlan,
    ):
        verified = VerifiedAssessment(
            summary="Empty claims",
            claims=[],
            verification_score=1.0,
        )
        report = await scorer_agent.run(verified, sample_graph, sample_analysis_plan)
        assert len(report.scores.dimensions) > 0
        for ds in report.scores.dimensions:
            assert ds.score == 50.0

    async def test_report_structure(
        self,
        scorer_agent: Scorer,
        sample_graph,
        sample_analysis_plan: AnalysisPlan,
        sample_verified: VerifiedAssessment,
    ):
        report = await scorer_agent.run(sample_verified, sample_graph, sample_analysis_plan)
        assert isinstance(report.session_id, UUID)
        assert isinstance(report.scores, CommunicationScores)
        assert isinstance(report.coaching, list)
        assert isinstance(report.summary, str)
        assert isinstance(report.evidence, list)
        assert isinstance(report.confidence, float)
        assert isinstance(report.degraded, bool)
