"""Fixtures for reasoning pipeline tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel

from app.graph.analyzer import GraphAnalysis, GraphAnalyzer, SpeakerStats
from app.graph.traverser import GraphTraverser
from app.graph.types import (
    ConversationGraph,
    EmbeddingNode,
    EventNode,
    GraphEdge,
    SpeakerNode,
    TurnNode,
)
from app.memory.service import MemoryService
from app.memory.types import (
    EmbeddingMatch,
    MemoryDocument,
    RetrievalBundle,
    SessionSummary,
    TurnSummary,
)
from app.reasoning.agents.planner import Planner
from app.reasoning.agents.reasoner import Reasoner
from app.reasoning.agents.retriever import Retriever
from app.reasoning.agents.scorer import Scorer
from app.reasoning.agents.verifier import Verifier
from app.reasoning.llm_client import LLMClient
from app.reasoning.orchestrator import ReasoningOrchestrator
from app.reasoning.schemas import (
    AnalysisConfig,
    AnalysisPlan,
    Claim,
    DraftAssessment,
    EvidenceRef,
    MemoryContext,
    PlanStep,
    VerifiedAssessment,
    VerifiedClaim,
)

# ------------------------------------------------------------------
# Sample IDs
# ------------------------------------------------------------------

SPEAKER_A_ID = UUID("00000000-0000-0000-0000-000000000001")
SPEAKER_B_ID = UUID("00000000-0000-0000-0000-000000000002")
SESSION_ID = UUID("00000000-0000-0000-0000-000000000010")
USER_ID = UUID("00000000-0000-0000-0000-000000000020")
TURN_IDS = [UUID(f"00000000-0000-0000-0000-00000000010{i}") for i in range(5)]


# ------------------------------------------------------------------
# Sample Pydantic model for structured-output tests
# ------------------------------------------------------------------

class SampleOutput(BaseModel):
    result: str
    score: float


# ------------------------------------------------------------------
# Mock response builder
# ------------------------------------------------------------------

@pytest.fixture
def build_mock_response() -> Any:
    def _build(
        content: str = '{"result": "4", "score": 1.0}',
        model: str = "qwen3-8b-instruct",
        prompt_tokens: int = 10,
        completion_tokens: int = 20,
        total_tokens: int = 30,
    ) -> ChatCompletion:
        message = ChatCompletionMessage(role="assistant", content=content)
        choice = Choice(index=0, message=message, finish_reason="stop")
        return ChatCompletion(
            id="test-completion-id",
            choices=[choice],
            created=1234567890,
            model=model,
            object="chat.completion",
            usage=CompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
        )

    return _build


# ------------------------------------------------------------------
# LLM Client fixtures (mocked)
# ------------------------------------------------------------------

@pytest.fixture
def sample_pydantic_model() -> type[SampleOutput]:
    return SampleOutput


@pytest.fixture
def mock_ollama_client(build_mock_response: Any) -> tuple[LLMClient, AsyncMock]:
    with patch("app.reasoning.llm_client.AsyncOpenAI") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_create = AsyncMock()
        mock_instance.chat.completions.create = mock_create

        client = LLMClient(base_url="http://localhost:11434/v1")
        yield client, mock_create


@pytest.fixture
def mock_vllm_client(build_mock_response: Any) -> tuple[LLMClient, AsyncMock]:
    with patch("app.reasoning.llm_client.AsyncOpenAI") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_create = AsyncMock()
        mock_instance.chat.completions.create = mock_create

        client = LLMClient(base_url="http://localhost:8000/v1")
        yield client, mock_create


@pytest.fixture
def mock_llm_client(build_mock_response: Any) -> tuple[LLMClient, AsyncMock]:
    with patch("app.reasoning.llm_client.AsyncOpenAI") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_create = AsyncMock()
        mock_instance.chat.completions.create = mock_create
        client = LLMClient(base_url="http://localhost:11434/v1")
        yield client, mock_create


@pytest.fixture
def mock_llm_client_vllm(build_mock_response: Any) -> tuple[LLMClient, AsyncMock]:
    with patch("app.reasoning.llm_client.AsyncOpenAI") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_create = AsyncMock()
        mock_instance.chat.completions.create = mock_create
        client = LLMClient(base_url="http://localhost:8000/v1")
        yield client, mock_create


@pytest.fixture
def mock_openrouter_client(build_mock_response: Any) -> tuple[LLMClient, AsyncMock]:
    with patch("app.reasoning.llm_client.AsyncOpenAI") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_create = AsyncMock()
        mock_instance.chat.completions.create = mock_create
        client = LLMClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-or-v1-test-key",
        )
        yield client, mock_create


# ------------------------------------------------------------------
# Sample graph fixtures
# ------------------------------------------------------------------

@pytest.fixture
def sample_speakers() -> list[SpeakerNode]:
    return [
        SpeakerNode(id=SPEAKER_A_ID, label="Speaker A"),
        SpeakerNode(id=SPEAKER_B_ID, label="Speaker B"),
    ]


@pytest.fixture
def sample_turns() -> list[TurnNode]:
    return [
        TurnNode(
            id=TURN_IDS[0], speaker_id=SPEAKER_A_ID,
            text="Hello, how are you today?",
            start_ms=0, end_ms=8000, confidence=0.95,
            acoustic_labels={"emotion": "neutral", "prosody": "normal"},
        ),
        TurnNode(
            id=TURN_IDS[1], speaker_id=SPEAKER_B_ID,
            text="I'm doing great, thanks for asking!",
            start_ms=9000, end_ms=16000, confidence=0.92,
            acoustic_labels={"emotion": "happy", "prosody": "animated"},
        ),
        TurnNode(
            id=TURN_IDS[2], speaker_id=SPEAKER_A_ID,
            text="That's wonderful to hear. What brings you here?",
            start_ms=18000, end_ms=26000, confidence=0.88,
            acoustic_labels={"emotion": "warm", "prosody": "normal"},
        ),
        TurnNode(
            id=TURN_IDS[3], speaker_id=SPEAKER_B_ID,
            text="I wanted to discuss the project timeline.",
            start_ms=28000, end_ms=36000, confidence=0.90,
            acoustic_labels={"emotion": "neutral", "prosody": "normal"},
        ),
        TurnNode(
            id=TURN_IDS[4], speaker_id=SPEAKER_A_ID,
            text="Sure, let me pull up the schedule.",
            start_ms=38000, end_ms=45000, confidence=0.93,
            acoustic_labels={"emotion": "neutral", "prosody": "normal"},
        ),
    ]


@pytest.fixture
def sample_edges(sample_turns: list[TurnNode]) -> list[GraphEdge]:
    edges = []
    for i in range(len(sample_turns) - 1):
        edges.append(GraphEdge(
            source_id=sample_turns[i].id,
            target_id=sample_turns[i + 1].id,
            relation="followed_by",
        ))
    for t in sample_turns:
        edges.append(GraphEdge(
            source_id=t.id,
            target_id=t.speaker_id,
            relation="spoken_by",
        ))
    return edges


@pytest.fixture
def sample_graph(
    sample_speakers: list[SpeakerNode],
    sample_turns: list[TurnNode],
    sample_edges: list[GraphEdge],
) -> ConversationGraph:
    return ConversationGraph(
        session_id=SESSION_ID,
        speakers=sample_speakers,
        turns=sample_turns,
        embeddings=[],
        events=[],
        edges=sample_edges,
    )


@pytest.fixture
def single_speaker_graph(
    sample_turns: list[TurnNode],
) -> ConversationGraph:
    return ConversationGraph(
        session_id=SESSION_ID,
        speakers=[SpeakerNode(id=SPEAKER_A_ID, label="Speaker A")],
        turns=sample_turns,
        embeddings=[],
        events=[],
        edges=[],
    )


@pytest.fixture
def long_session_graph() -> ConversationGraph:
    turns = [
        TurnNode(
            id=UUID(f"00000000-0000-0000-0000-00000000{i:04x}"),
            speaker_id=SPEAKER_A_ID if i % 2 == 0 else SPEAKER_B_ID,
            text=f"Turn {i} content here.",
            start_ms=i * 2000,
            end_ms=i * 2000 + 1500,
            confidence=0.9,
        )
        for i in range(25)
    ]
    return ConversationGraph(
        session_id=SESSION_ID,
        speakers=[
            SpeakerNode(id=SPEAKER_A_ID, label="Speaker A"),
            SpeakerNode(id=SPEAKER_B_ID, label="Speaker B"),
        ],
        turns=turns,
        embeddings=[],
        events=[],
        edges=[],
    )


# ------------------------------------------------------------------
# Sample RetrievalBundle
# ------------------------------------------------------------------

@pytest.fixture
def sample_turn_summaries() -> list[TurnSummary]:
    return [
        TurnSummary(
            turn_id=TURN_IDS[0], speaker_label="Speaker A",
            text="Hello, how are you today?",
            start_ms=0, end_ms=2000, confidence=0.95,
        ),
        TurnSummary(
            turn_id=TURN_IDS[1], speaker_label="Speaker B",
            text="I'm doing great, thanks for asking!",
            start_ms=2500, end_ms=4500, confidence=0.92,
        ),
    ]


@pytest.fixture
def sample_retrieval_bundle(
    sample_turn_summaries: list[TurnSummary],
) -> RetrievalBundle:
    return RetrievalBundle(
        core_turns=sample_turn_summaries,
        relevant_turns=sample_turn_summaries,
        acoustic_neighbors=[
            EmbeddingMatch(
                embedding_id=UUID("00000000-0000-0000-0000-000000000030"),
                turn_id=TURN_IDS[0], score=0.85, head="emotion",
            ),
        ],
        documents=[
            MemoryDocument(
                id=UUID("00000000-0000-0000-0000-000000000040"),
                title="Doc 1",
                content="Sample document content",
                user_id=USER_ID,
                created_at=datetime.now(timezone.utc),
            ),
        ],
        prior_sessions=[
            SessionSummary(
                session_id=UUID("00000000-0000-0000-0000-000000000050"),
                user_id=USER_ID,
                started_at=datetime.now(timezone.utc),
                duration_s=120,
                turn_count=10,
                language="en",
            ),
        ],
        metadata={"retrieval_mode": "hybrid"},
    )


# ------------------------------------------------------------------
# Sample AnalysisPlan
# ------------------------------------------------------------------

@pytest.fixture
def sample_analysis_plan() -> AnalysisPlan:
    return AnalysisPlan(
        objective="Evaluate overall communication quality",
        steps=[
            PlanStep(
                id="clarity",
                question="How clear is the speech?",
                required_evidence=["transcript"],
                priority="high",
            ),
            PlanStep(
                id="empathy",
                question="How empathetic is the interaction?",
                required_evidence=["transcript", "emotion"],
                priority="high",
            ),
        ],
        dimensions=["clarity", "empathy", "pacing"],
        constraints=[],
    )


@pytest.fixture
def sample_single_speaker_plan() -> AnalysisPlan:
    return AnalysisPlan(
        objective="Evaluate monologue communication quality",
        steps=[
            PlanStep(
                id="clarity",
                question="How clear is the speech?",
                required_evidence=["transcript"],
                priority="high",
            ),
            PlanStep(
                id="fluency",
                question="How fluent is the speech?",
                required_evidence=["transcript"],
                priority="medium",
            ),
        ],
        dimensions=["clarity", "fluency"],
        constraints=["single_speaker"],
    )


# ------------------------------------------------------------------
# Sample DraftAssessment
# ------------------------------------------------------------------

@pytest.fixture
def sample_draft() -> DraftAssessment:
    return DraftAssessment(
        summary="Good overall communication with some areas for improvement.",
        claims=[
            Claim(
                statement="Speaker A asks clarifying questions.",
                evidence=[
                    EvidenceRef(
                        type="turn", id=str(TURN_IDS[2]),
                        quote="What brings you here?",
                    ),
                ],
                dimension="empathy",
                polarity="strength",
            ),
            Claim(
                statement="Speaking pace is appropriate.",
                evidence=[
                    EvidenceRef(
                        type="turn", id=str(TURN_IDS[0]),
                    ),
                ],
                dimension="pacing",
                polarity="strength",
            ),
        ],
        speaker_notes={"Speaker A": "Engaged and responsive."},
        open_questions=["Could the speaker improve turn-taking?"],
    )


@pytest.fixture
def sample_draft_with_hallucination() -> DraftAssessment:
    fake_id = UUID("00000000-0000-0000-0000-00000000ffff")
    return DraftAssessment(
        summary="Draft with some unsupported claims.",
        claims=[
            Claim(
                statement="Speaker A interrupts frequently.",
                evidence=[
                    EvidenceRef(
                        type="turn", id=str(fake_id),
                        quote="This turn does not exist.",
                    ),
                ],
                dimension="assertiveness",
                polarity="weakness",
            ),
            Claim(
                statement="Speaker B uses many filler words.",
                evidence=[
                    EvidenceRef(
                        type="turn", id=str(TURN_IDS[1]),
                        quote="I'm doing great",
                    ),
                ],
                dimension="clarity",
                polarity="weakness",
            ),
        ],
        speaker_notes={},
        open_questions=[],
    )


# ------------------------------------------------------------------
# Sample VerifiedAssessment
# ------------------------------------------------------------------

@pytest.fixture
def sample_verified() -> VerifiedAssessment:
    return VerifiedAssessment(
        summary="Good overall communication with some areas for improvement.",
        claims=[
            VerifiedClaim(
                statement="Speaker A asks clarifying questions.",
                evidence=[
                    EvidenceRef(
                        type="turn", id=str(TURN_IDS[2]),
                        quote="What brings you here?",
                    ),
                ],
                dimension="empathy",
                polarity="strength",
                status="verified",
                verification_note="All evidence verified",
            ),
            VerifiedClaim(
                statement="Speaking pace is appropriate.",
                evidence=[
                    EvidenceRef(type="turn", id=str(TURN_IDS[0])),
                ],
                dimension="pacing",
                polarity="strength",
                status="verified",
                verification_note="All evidence verified",
            ),
        ],
        speaker_notes={"Speaker A": "Engaged and responsive."},
        verification_score=1.0,
    )


@pytest.fixture
def sample_degraded_verified() -> VerifiedAssessment:
    return VerifiedAssessment(
        summary="Degraded analysis.",
        claims=[
            VerifiedClaim(
                statement="Claim 1.",
                evidence=[EvidenceRef(type="turn", id=str(TURN_IDS[0]))],
                dimension="clarity",
                polarity="strength",
                status="verified",
                verification_note="OK",
            ),
        ],
        speaker_notes={},
        issues=["Low verification score"],
        verification_score=0.2,
    )


# ------------------------------------------------------------------
# AnalysisConfig fixtures
# ------------------------------------------------------------------

@pytest.fixture
def default_config() -> AnalysisConfig:
    return AnalysisConfig()


@pytest.fixture
def focused_config() -> AnalysisConfig:
    return AnalysisConfig(focus="empathy", dimensions=["empathy", "clarity"])


# ------------------------------------------------------------------
# MemoryContext fixtures
# ------------------------------------------------------------------

@pytest.fixture
def sample_memory_context() -> MemoryContext:
    return MemoryContext(
        user_id=USER_ID,
        prior_sessions=[],
        documents=[],
        preferences={},
    )


# ------------------------------------------------------------------
# Mock services
# ------------------------------------------------------------------

@pytest.fixture
def mock_memory_service(
    sample_retrieval_bundle: RetrievalBundle,
) -> MemoryService:
    svc = MagicMock(spec=MemoryService)
    svc.build_context = AsyncMock(return_value=sample_retrieval_bundle)
    return svc


@pytest.fixture
def mock_graph_traverser(sample_graph: ConversationGraph) -> GraphTraverser:
    traverser = MagicMock(spec=GraphTraverser)
    traverser.build_nx_graph = MagicMock()
    traverser.get_turn_sequence = MagicMock(
        return_value=[t for t in sample_graph.turns if t.speaker_id == SPEAKER_A_ID]
    )
    return traverser


@pytest.fixture
def mock_graph_analyzer(
    sample_graph: ConversationGraph,
) -> GraphAnalyzer:
    analyzer = MagicMock(spec=GraphAnalyzer)
    analysis = GraphAnalysis(
        session_id=SESSION_ID,
        speaker_stats=[
            SpeakerStats(
                speaker_id=SPEAKER_A_ID, label="Speaker A",
                turn_count=3, total_duration_ms=21000,
                avg_turn_duration_ms=7000.0, word_count=30,
                interruption_count=0, question_count=2,
                filler_count=1,
            ),
            SpeakerStats(
                speaker_id=SPEAKER_B_ID, label="Speaker B",
                turn_count=2, total_duration_ms=16000,
                avg_turn_duration_ms=8000.0, word_count=20,
                interruption_count=0, question_count=0,
                filler_count=0,
            ),
        ],
        total_turns=5,
        total_duration_ms=45000,
        turn_balance=0.95,
        overlap_ratio=0.0,
        interruption_count=0,
        pause_stats={"total_pause_ms": 500, "avg_pause_ms": 125.0, "pause_count": 4},
        question_count=2,
        filler_word_count=1,
        speaking_speed={"overall_wpm": 150.0, "per_speaker_wpm": {}},
    )
    analyzer.analyze = MagicMock(return_value=analysis)
    return analyzer


# ------------------------------------------------------------------
# Agent fixtures
# ------------------------------------------------------------------

@pytest.fixture
def retriever_agent(
    mock_llm_client: tuple[LLMClient, AsyncMock],
    mock_memory_service: MemoryService,
    mock_graph_traverser: GraphTraverser,
) -> Retriever:
    client, _ = mock_llm_client
    return Retriever(client, mock_memory_service, mock_graph_traverser)


@pytest.fixture
def planner_agent(
    mock_llm_client: tuple[LLMClient, AsyncMock],
) -> Planner:
    client, _ = mock_llm_client
    return Planner(client)


@pytest.fixture
def reasoner_agent(
    mock_llm_client: tuple[LLMClient, AsyncMock],
    mock_graph_traverser: GraphTraverser,
    mock_graph_analyzer: GraphAnalyzer,
    mock_memory_service: MemoryService,
) -> Reasoner:
    client, _ = mock_llm_client
    return Reasoner(client, mock_graph_traverser, mock_graph_analyzer, mock_memory_service)


@pytest.fixture
def verifier_agent(
    mock_llm_client: tuple[LLMClient, AsyncMock],
    mock_graph_traverser: GraphTraverser,
) -> Verifier:
    client, _ = mock_llm_client
    return Verifier(client, mock_graph_traverser)


@pytest.fixture
def scorer_agent(
    mock_llm_client: tuple[LLMClient, AsyncMock],
) -> Scorer:
    client, _ = mock_llm_client
    return Scorer(client)


# ------------------------------------------------------------------
# Orchestrator fixtures
# ------------------------------------------------------------------

@pytest.fixture
def orchestrator(
    mock_llm_client: tuple[LLMClient, AsyncMock],
    mock_graph_traverser: GraphTraverser,
    mock_graph_analyzer: GraphAnalyzer,
    mock_memory_service: MemoryService,
) -> ReasoningOrchestrator:
    client, _ = mock_llm_client
    return ReasoningOrchestrator(
        llm_client=client,
        graph_traverser=mock_graph_traverser,
        graph_analyzer=mock_graph_analyzer,
        memory_service=mock_memory_service,
    )
