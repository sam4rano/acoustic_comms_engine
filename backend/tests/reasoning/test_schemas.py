"""Tests for reasoning pipeline Pydantic schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.reasoning.schemas import (
    AgentStepTrace,
    AnalysisConfig,
    AnalysisPlan,
    AnalysisReport,
    Claim,
    CoachingAction,
    CommunicationScores,
    DimensionScore,
    DraftAssessment,
    EvidenceRef,
    MemoryContext,
    PlanStep,
    TokenUsage,
    VerifiedAssessment,
    VerifiedClaim,
)


class TestEvidenceRef:
    def test_construct_turn_ref(self):
        ref = EvidenceRef(type="turn", id="abc-123", quote="hello")
        assert ref.type == "turn"
        assert ref.id == "abc-123"
        assert ref.quote == "hello"

    def test_construct_embedding_ref(self):
        ref = EvidenceRef(type="embedding", id="emb-1")
        assert ref.type == "embedding"

    def test_construct_document_ref(self):
        ref = EvidenceRef(type="document", id="doc-1", start_ms=0, end_ms=1000)
        assert ref.start_ms == 0
        assert ref.end_ms == 1000

    def test_construct_event_ref(self):
        ref = EvidenceRef(type="event", id="evt-1")
        assert ref.type == "event"

    def test_default_optional_fields(self):
        ref = EvidenceRef(type="turn", id="t1")
        assert ref.quote is None
        assert ref.start_ms is None
        assert ref.end_ms is None


class TestTokenUsage:
    def test_construct(self):
        usage = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20
        assert usage.total_tokens == 30


class TestAgentStepTrace:
    def test_construct(self):
        now = datetime.now(timezone.utc)
        trace = AgentStepTrace(
            agent="planner",
            started_at=now,
            duration_ms=100,
            input_summary="planner(graph, bundle, config)",
            output={"steps": []},
            model="qwen3-8b",
            token_usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        assert trace.agent == "planner"
        assert trace.token_usage is not None
        assert trace.token_usage.total_tokens == 15
        assert trace.error is None

    def test_error_field(self):
        now = datetime.now(timezone.utc)
        trace = AgentStepTrace(
            agent="reasoner",
            started_at=now,
            duration_ms=50,
            input_summary="reasoner(...)",
            output={"error": "timeout"},
            model="qwen3-14b",
            error="Timeout",
        )
        assert trace.error == "Timeout"


class TestAnalysisConfig:
    def test_defaults(self):
        cfg = AnalysisConfig()
        assert cfg.language == "en"
        assert cfg.min_turn_confidence == 0.6
        assert cfg.include_prior_sessions is True
        assert cfg.max_turns == 500
        assert cfg.timeout_per_agent_s == 120.0
        assert "asr" in cfg.enabled_heads
        assert len(cfg.enabled_heads) == 5

    def test_custom_values(self):
        cfg = AnalysisConfig(
            focus="fluency",
            dimensions=["fluency", "clarity"],
            language="es",
            enabled_heads=["asr"],
            timeout_per_agent_s=60.0,
        )
        assert cfg.focus == "fluency"
        assert cfg.dimensions == ["fluency", "clarity"]
        assert cfg.language == "es"
        assert cfg.enabled_heads == ["asr"]
        assert cfg.timeout_per_agent_s == 60.0


class TestPlanStep:
    def test_construct(self):
        step = PlanStep(
            id="clarity",
            question="How clear is the speech?",
            required_evidence=["transcript"],
            priority="high",
        )
        assert step.id == "clarity"
        assert step.priority == "high"


class TestAnalysisPlan:
    def test_construct(self):
        plan = AnalysisPlan(
            objective="Evaluate communication",
            steps=[
                PlanStep(id="s1", question="Q1?", required_evidence=["transcript"], priority="high"),
            ],
            dimensions=["clarity", "empathy"],
            constraints=["2 speakers"],
        )
        assert len(plan.steps) == 1
        assert plan.constraints == ["2 speakers"]


class TestClaim:
    def test_construct(self):
        claim = Claim(
            statement="Speaker is clear",
            evidence=[EvidenceRef(type="turn", id="t1")],
            dimension="clarity",
            polarity="strength",
        )
        assert claim.polarity == "strength"
        assert len(claim.evidence) == 1


class TestDraftAssessment:
    def test_construct(self):
        draft = DraftAssessment(
            summary="Draft summary",
            claims=[
                Claim(
                    statement="Good clarity",
                    evidence=[EvidenceRef(type="turn", id="t1")],
                    dimension="clarity",
                    polarity="strength",
                ),
            ],
            speaker_notes={"A": "Good"},
            open_questions=["Improve pacing?"],
        )
        assert draft.summary == "Draft summary"
        assert len(draft.claims) == 1
        assert draft.speaker_notes["A"] == "Good"
        assert len(draft.open_questions) == 1


class TestVerifiedClaim:
    def test_default_status(self):
        vc = VerifiedClaim(
            statement="Test",
            evidence=[EvidenceRef(type="turn", id="t1")],
            dimension="clarity",
            polarity="strength",
        )
        assert vc.status == "verified"
        assert vc.verification_note == ""


class TestVerifiedAssessment:
    def test_construct(self):
        va = VerifiedAssessment(
            summary="Verified summary",
            claims=[
                VerifiedClaim(
                    statement="Good clarity",
                    evidence=[EvidenceRef(type="turn", id="t1")],
                    dimension="clarity",
                    polarity="strength",
                    status="verified",
                    verification_note="OK",
                ),
            ],
            verification_score=0.85,
        )
        assert va.verification_score == 0.85
        assert va.issues == []
        assert len(va.claims) == 1

    def test_low_verification(self):
        va = VerifiedAssessment(
            summary="Low confidence",
            claims=[],
            issues=["No evidence"],
            verification_score=0.2,
        )
        assert va.verification_score == 0.2
        assert "No evidence" in va.issues


class TestDimensionScore:
    def test_construct(self):
        ds = DimensionScore(
            dimension="clarity",
            score=75.0,
            confidence=0.9,
            rationale="Good clarity with few fillers",
            evidence=[EvidenceRef(type="turn", id="t1")],
        )
        assert ds.score == 75.0
        assert ds.confidence == 0.9


class TestCommunicationScores:
    def test_construct(self):
        scores = CommunicationScores(
            overall=72.5,
            dimensions=[
                DimensionScore(
                    dimension="clarity", score=80.0,
                    confidence=0.9, rationale="Clear speech",
                ),
                DimensionScore(
                    dimension="empathy", score=65.0,
                    confidence=0.8, rationale="Some empathy",
                ),
            ],
        )
        assert scores.overall == 72.5
        assert len(scores.dimensions) == 2


class TestCoachingAction:
    def test_construct(self):
        action = CoachingAction(
            title="Reduce filler words",
            description="Practice pausing.",
            priority="high",
            practice_tip="Count fillers in 2-min speech.",
            related_turns=["t1", "t2"],
            dimension="clarity",
        )
        assert action.priority == "high"
        assert action.dimension == "clarity"

    def test_default_related_turns(self):
        action = CoachingAction(
            title="Test",
            description="Desc",
            priority="low",
            practice_tip="Tip",
            dimension="pacing",
        )
        assert action.related_turns == []


class TestAnalysisReport:
    def test_construct(self):
        sid = uuid4()
        report = AnalysisReport(
            session_id=sid,
            scores=CommunicationScores(
                overall=70.0,
                dimensions=[
                    DimensionScore(
                        dimension="clarity", score=70.0,
                        confidence=0.8, rationale="OK",
                    ),
                ],
            ),
            coaching=[
                CoachingAction(
                    title="Improve", description="Work on it",
                    priority="medium", practice_tip="Practice",
                    dimension="clarity",
                ),
            ],
            summary="Overall analysis report.",
            evidence=[EvidenceRef(type="turn", id="t1")],
            agent_trace=[],
            confidence=0.8,
        )
        assert report.session_id == sid
        assert report.scores.overall == 70.0
        assert len(report.coaching) == 1
        assert report.degraded is False
        assert report.degradation_reason is None

    def test_degraded_mode(self):
        report = AnalysisReport(
            session_id=uuid4(),
            scores=CommunicationScores(overall=0.0, dimensions=[]),
            coaching=[],
            summary="Degraded",
            degraded=True,
            degradation_reason="Low verification",
        )
        assert report.degraded is True
        assert report.degradation_reason == "Low verification"

    def test_round_trip_serialization(self):
        sid = uuid4()
        report = AnalysisReport(
            session_id=sid,
            scores=CommunicationScores(
                overall=80.0,
                dimensions=[
                    DimensionScore(
                        dimension="clarity", score=80.0,
                        confidence=0.9, rationale="Clear",
                        evidence=[EvidenceRef(type="turn", id="t1")],
                    ),
                ],
            ),
            coaching=[
                CoachingAction(
                    title="Keep it up", description="Good job",
                    priority="low", practice_tip="Keep practicing",
                    dimension="clarity",
                ),
            ],
            summary="Good report",
            evidence=[EvidenceRef(type="turn", id="t1")],
            confidence=0.9,
        )

        data = report.model_dump()
        restored = AnalysisReport.model_validate(data)

        assert restored.session_id == sid
        assert restored.scores.overall == 80.0
        assert len(restored.coaching) == 1
        assert restored.confidence == 0.9
        assert len(restored.evidence) == 1


class TestMemoryContext:
    def test_construct(self):
        ctx = MemoryContext(
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
        )
        assert ctx.prior_sessions == []
        assert ctx.documents == []
        assert ctx.preferences == {}
