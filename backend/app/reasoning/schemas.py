from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from app.memory.types import MemoryDocument, SessionSummary


class EvidenceRef(BaseModel):
    type: Literal["turn", "embedding", "document", "event"]
    id: str
    quote: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class AgentStepTrace(BaseModel):
    agent: str
    started_at: datetime
    duration_ms: int
    input_summary: str
    output: dict
    model: str
    token_usage: TokenUsage | None = None
    error: str | None = None


class AnalysisConfig(BaseModel):
    focus: str | None = None
    dimensions: list[str] | None = None
    language: str = "en"
    prompt_version: str = "v1"
    enabled_heads: list[str] = [
        "asr", "emotion", "prosody", "stress", "fluency"
    ]
    min_turn_confidence: float = 0.6
    include_prior_sessions: bool = True
    max_turns: int = 500
    timeout_per_agent_s: float = 120.0


class MemoryContext(BaseModel):
    user_id: UUID
    prior_sessions: list[SessionSummary] = []
    documents: list[MemoryDocument] = []
    preferences: dict[str, Any] = {}


class PlanStep(BaseModel):
    id: str
    question: str
    required_evidence: list[Literal["transcript", "emotion", "prosody", "timing", "events"]]
    priority: Literal["high", "medium", "low"]


class AnalysisPlan(BaseModel):
    objective: str
    steps: list[PlanStep]
    dimensions: list[str]
    constraints: list[str] = []


class Claim(BaseModel):
    statement: str
    evidence: list[EvidenceRef]
    dimension: str
    polarity: Literal["strength", "weakness", "neutral"]


class DraftAssessment(BaseModel):
    summary: str
    claims: list[Claim]
    speaker_notes: dict[str, str] = {}
    open_questions: list[str] = []


class VerifiedClaim(Claim):
    status: Literal["verified", "downgraded", "removed"] = "verified"
    verification_note: str = ""


class VerifiedAssessment(BaseModel):
    summary: str
    claims: list[VerifiedClaim]
    speaker_notes: dict[str, str] = {}
    issues: list[str] = []
    verification_score: float = 1.0


class DimensionScore(BaseModel):
    dimension: str
    score: float
    confidence: float
    rationale: str
    evidence: list[EvidenceRef] = []


class CommunicationScores(BaseModel):
    overall: float
    dimensions: list[DimensionScore]


class CoachingAction(BaseModel):
    title: str
    description: str
    priority: Literal["high", "medium", "low"]
    practice_tip: str
    related_turns: list[str] = []
    dimension: str


class AnalysisReport(BaseModel):
    session_id: UUID
    scores: CommunicationScores
    coaching: list[CoachingAction]
    summary: str
    evidence: list[EvidenceRef] = []
    agent_trace: list[AgentStepTrace] = []
    confidence: float = 1.0
    degraded: bool = False
    degradation_reason: str | None = None
