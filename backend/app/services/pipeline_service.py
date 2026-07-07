import logging
from uuid import UUID, uuid4

from app.core.config import settings
from app.graph.analyzer import GraphAnalyzer
from app.graph.traverser import GraphTraverser
from app.graph.types import (
    ConversationGraph,
    EmbeddingNode,
    EventNode,
    GraphEdge,
    SpeakerNode,
    TurnNode,
)
from app.memory.types import RetrievalBundle, TurnSummary
from app.reasoning.agents.planner import Planner
from app.reasoning.agents.reasoner import Reasoner
from app.reasoning.agents.verifier import Verifier
from app.reasoning.agents.scorer import Scorer
from app.reasoning.llm_client import LLMClient
from app.reasoning.schemas import (
    AnalysisConfig,
    AnalysisPlan,
    AnalysisReport,
    CoachingAction,
    CommunicationScores,
    DimensionScore,
    DraftAssessment,
    EvidenceRef,
    MemoryContext,
    VerifiedAssessment,
)

logger = logging.getLogger(__name__)


class PipelineService:

    def __init__(self) -> None:
        self._llm = LLMClient(
            base_url=settings.LLM_BASE_URL,
            default_model=settings.LLM_MODEL,
            api_key=settings.LLM_API_KEY,
        )
        self._traverser = GraphTraverser()
        self._analyzer = GraphAnalyzer()
        self._planner = Planner(self._llm)
        self._verifier = Verifier(self._llm, self._traverser)
        self._scorer = Scorer(self._llm)

    async def analyze_transcript(
        self,
        session_id: UUID,
        transcript: str,
        duration_ms: int,
    ) -> AnalysisReport:
        graph = self._build_graph(session_id, transcript, duration_ms)
        bundle = self._build_bundle(graph)

        cfg = AnalysisConfig(
            language="en",
            prompt_version="v1",
        )

        memory_context = MemoryContext(
            user_id=uuid4(),
        )

        plan = await self._planner.run(
            graph=graph,
            bundle=bundle,
            config=cfg,
        )

        reasoner = Reasoner(
            self._llm, self._traverser, self._analyzer, None,
        )
        draft = await reasoner.run(
            graph=graph,
            bundle=bundle,
            plan=plan,
        )

        verified = await self._verifier.run(
            draft=draft,
            graph=graph,
            bundle=bundle,
        )

        report = await self._scorer.run(
            verified=verified,
            graph=graph,
            plan=plan,
        )

        if not report.coaching:
            report.coaching = [
                CoachingAction(
                    title="Practice active speaking",
                    description="Record yourself speaking on any topic to receive personalized coaching recommendations.",
                    priority="medium",
                    practice_tip="Speak for at least 30 seconds clearly on a topic you know well.",
                    related_turns=[],
                    dimension="general",
                )
            ]
            if not report.scores.dimensions:
                report.scores = CommunicationScores(
                    overall=50,
                    dimensions=[
                        DimensionScore(
                            dimension=dim,
                            score=50,
                            confidence=0.5,
                            rationale="No claims were verified for this dimension.",
                        )
                        for dim in (plan.dimensions or ["clarity", "pacing", "empathy", "assertiveness", "fluency", "engagement"])
                    ],
                )

        return report

    def _build_bundle(self, graph: ConversationGraph) -> RetrievalBundle:
        core_turns = [
            TurnSummary(
                turn_id=t.id,
                speaker_label=self._speaker_label(graph, t.speaker_id),
                text=t.text,
                start_ms=t.start_ms,
                end_ms=t.end_ms,
                confidence=t.confidence,
            )
            for t in graph.turns
        ]
        return RetrievalBundle(
            core_turns=core_turns,
            metadata={
                "session_id": str(graph.session_id),
                "speaker_count": len(graph.speakers),
                "total_turns": len(graph.turns),
                "total_duration_ms": graph.duration_ms,
                "retrieval_mode": "empty",
            },
        )

    def _speaker_label(self, graph: ConversationGraph, speaker_id: UUID) -> str:
        for s in graph.speakers:
            if s.id == speaker_id:
                return s.label
        return str(speaker_id)

    def _build_graph(
        self,
        session_id: UUID,
        transcript: str,
        duration_ms: int,
    ) -> ConversationGraph:
        speaker = SpeakerNode(
            id=uuid4(),
            label="Speaker",
        )

        turn = TurnNode(
            id=uuid4(),
            speaker_id=speaker.id,
            text=transcript,
            start_ms=0,
            end_ms=duration_ms,
            confidence=0.9,
        )

        return ConversationGraph(
            session_id=session_id,
            speakers=[speaker],
            turns=[turn],
            embeddings=[],
            events=[],
            edges=[],
            metadata={},
        )
