# Agent Pipeline

> Multi-agent reasoning over the conversation graph. Explainable, testable, and extensible.

## Overview

The reasoning layer replaces a single "transcript → LLM → answer" prompt with a **sequential pipeline** of specialized agents. Each agent has typed inputs and outputs (Pydantic models), a defined role, optional tools, and a persisted trace for the frontend `AgentTrace` component.

```
Conversation Graph + Memory Context
              │
              ▼
         ┌─────────┐
         │Retriever│  Gather relevant turns, embeddings, docs
         └────┬────┘
              ▼
         ┌─────────┐
         │ Planner │  Decompose analysis into sub-questions
         └────┬────┘
              ▼
         ┌─────────┐
         │Reasoner │  Draft communication assessment
         └────┬────┘
              ▼
         ┌─────────┐
         │Verifier │  Check claims against graph evidence
         └────┬────┘
              ▼
         ┌─────────┐
         │ Scorer  │  Quantify dimensions + coaching actions
         └────┬────┘
              ▼
        AnalysisReport
```

## Design Principles

1. **Graph-grounded** — Every claim must reference turn IDs, embedding IDs, or retrieved documents.
2. **Structured I/O** — JSON schemas enforced; no free-form blobs between agents.
3. **Traceable** — Each step logged to `analysis_reports.agent_trace` (JSONB column).
4. **Swappable LLM** — Agents call `LLMClient` (Ollama for local research; vLLM / SGLang for production, OpenAI-compatible API); prompts live in `prompts/`.
5. **Fail gracefully** — Verifier can flag issues; Scorer still produces partial report with confidence penalties.

## Status

This pipeline currently runs locally against a single Ollama instance for
research and testing. The idempotency lock, kill-recovery, and fallback-model
paths are implemented against their documented interfaces but are not
exercised under real concurrent load yet — they're here so swapping to
vLLM/SGLang + Redis-backed locking later is a config change, not a rewrite.

| Feature | Status | Notes |
|---------|--------|-------|
| Ollama (`localhost:11434`) | **Active** | Local single-user default |
| vLLM / SGLang | **Dormant** | Swap `LLM_BASE_URL` to activate; tested path |
| Redis idempotency lock | **Dormant** | In-process `asyncio.Lock` for now; Redis SETNX ready |
| Orchestrator kill-recovery | **Phase 2** | Unattended deploy only; re-run analysis locally |
| Fallback model | **Phase 2** | Not needed for single-backend research runs |
| `degraded` reporting | **Active** | Core to explainability goal; cheap to maintain |

## Shared Types

```python
# backend/app/reasoning/schemas.py (conceptual)

from uuid import UUID
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


# ── Evidence & tracing ──────────────────────────────────────────────

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
    token_usage: TokenUsage | None
    error: str | None = None          # populated on failure


# ── Pipeline inputs ─────────────────────────────────────────────────

class AnalysisConfig(BaseModel):
    """User-controlled analysis parameters."""
    focus: str | None = None                # e.g. "fluency", "empathy", "clarity"
    dimensions: list[str] | None = None     # override default dimension set
    language: str = "en"                    # ISO 639-1 code
    prompt_version: str = "v1"              # selects prompt set
    enabled_heads: list[Literal["asr", "emotion", "prosody", "stress", "fluency"]] = [
        "asr", "emotion", "prosody", "stress", "fluency"
    ]
    min_turn_confidence: float = 0.6        # filter turns with ASR confidence below this
    include_prior_sessions: bool = True
    max_turns: int = 500                    # hard cap to prevent OOM on very long sessions
    timeout_per_agent_s: float = 120.0


class MemoryContext(BaseModel):
    """Aggregated memory state available to agents."""
    user_id: UUID
    prior_sessions: list["SessionSummary"]
    documents: list["DocumentChunk"]
    preferences: dict = {}


class ConversationGraph(BaseModel):
    """Serializable snapshot of the conversation graph for reasoning."""
    session_id: UUID
    speakers: list["SpeakerNode"]
    turns: list["TurnNode"]
    embeddings: list["EmbeddingNode"]
    events: list["EventNode"]
    edges: list["GraphEdge"]
    metadata: "ConversationMetadata"


# ── Retriever types ─────────────────────────────────────────────────

class TurnSummary(BaseModel):
    """Lightweight turn reference for retrieval results."""
    turn_id: UUID
    speaker_label: str
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    acoustic_labels: dict[str, str] = {}    # head_name → label


class EmbeddingMatch(BaseModel):
    """Acoustic embedding match from Qdrant."""
    embedding_id: UUID
    turn_id: UUID
    score: float
    head: str                               # "emotion" | "prosody" | etc.


class DocumentChunk(BaseModel):
    """Chunk from user knowledge base (RAG)."""
    chunk_id: UUID
    title: str
    content: str
    score: float | None = None


class SessionSummary(BaseModel):
    """Prior session digest for long-term memory."""
    session_id: UUID
    started_at: datetime
    duration_s: int
    turn_count: int
    language: str
    overall_score: float | None = None


class RetrievalMetadata(BaseModel):
    session_language: str
    speaker_count: int
    total_turns: int
    total_duration_ms: int
    enabled_heads: list[str]
    retrieval_mode: str                     # "full" | "compressed" | "empty"
    turn_confidence_pct: float              # % of turns above confidence threshold


# The RetrievalBundle lives in the Retriever section below (QdrantResult).
# Retriever output uses shared types above; schema repeated at §1 for clarity.


# ── Final report ────────────────────────────────────────────────────

class AnalysisReport(BaseModel):
    session_id: UUID
    scores: "CommunicationScores"
    coaching: list["CoachingAction"]
    summary: str
    evidence: list[EvidenceRef]
    agent_trace: list[AgentStepTrace]
    confidence: float
    degraded: bool = False
    degradation_reason: str | None = None
```

## Agent Specifications

---

### 1. Retriever

**Role:** Gather all context needed for analysis — structural graph context, semantically similar turns, acoustic neighbors, and user/domain documents.

| Field | Value |
|-------|-------|
| Input | `ConversationGraph`, `MemoryContext`, `AnalysisConfig` |
| Output | `RetrievalBundle` |
| LLM | Optional reranker; primary work is deterministic + vector search |
| Tools | `graph_traverse`, `vector_search`, `keyword_search`, `memory_lookup` |

**Output schema:**

```python
class RetrievalBundle(BaseModel):
    core_turns: list[TurnSummary]          # Full session timeline (compressed if long)
    relevant_turns: list[TurnSummary]      # Top-K by semantic/acoustic similarity
    acoustic_neighbors: list[EmbeddingMatch]  # Similar prosody/emotion patterns
    documents: list[DocumentChunk]         # RAG from user knowledge base
    prior_sessions: list[SessionSummary]   # Long-term user memory (if enabled)
    metadata: RetrievalMetadata            # Languages, speakers, duration, head coverage
```

**Behavior:**

- Always include all turns if session < 20 turns; otherwise summarize older turns and retrieve top-K relevant to communication analysis.
- Query Qdrant with turn text embeddings AND acoustic embeddings (dual retrieval).
- Respect `AnalysisConfig.focus` (e.g., `"fluency"`, `"empathy"`, `"clarity"`) to bias retrieval.

**Prompt (reranker, optional):**

```
Given the analysis focus "{focus}", rank these retrieved turns by relevance.
Return turn IDs in order with brief justification.
```

---

### 2. Planner

**Role:** Decompose the communication analysis into a structured plan of sub-questions and evidence requirements.

| Field | Value |
|-------|-------|
| Input | `ConversationGraph`, `RetrievalBundle`, `AnalysisConfig` |
| Output | `AnalysisPlan` |
| LLM | Required — lightweight model sufficient (e.g. Qwen3 4-8B, Apache 2.0) |
| Tools | None |

**Output schema:**

```python
class PlanStep(BaseModel):
    id: str
    question: str
    required_evidence: list[Literal["transcript", "emotion", "prosody", "timing", "events"]]
    priority: Literal["high", "medium", "low"]

class AnalysisPlan(BaseModel):
    objective: str
    steps: list[PlanStep]
    dimensions: list[str]  # e.g., clarity, pacing, empathy, assertiveness, fluency
    constraints: list[str]   # e.g., "low-resource language: yo", "2 speakers"
```

**Behavior:**

- Adapt plan to session length and available acoustic heads (skip prosody step if head disabled).
- For low-resource languages, plan includes confidence caveats and cross-lingual reasoning steps.
- Default dimensions: **Clarity**, **Pacing**, **Empathy**, **Assertiveness**, **Fluency**, **Engagement**.

**System prompt (summary):**

```
You are a communication analysis planner. Given a conversation graph summary
and retrieved context, produce a structured plan to evaluate interpersonal
communication. Ground every step in observable evidence types. Do not
invent facts. Output valid JSON matching AnalysisPlan schema.
```

---

### 3. Reasoner

**Role:** Execute the plan and draft a narrative assessment with evidence-linked claims.

| Field | Value |
|-------|-------|
| Input | `ConversationGraph`, `RetrievalBundle`, `AnalysisPlan` |
| Output | `DraftAssessment` |
| LLM | Required — primary reasoning model (7B–14B class; e.g. Qwen3-14B for depth) |
| Tools | `lookup_turn`, `lookup_acoustic`, `compare_speakers` |

**Output schema:**

```python
class Claim(BaseModel):
    statement: str
    evidence: list[EvidenceRef]
    dimension: str
    polarity: Literal["strength", "weakness", "neutral"]

class DraftAssessment(BaseModel):
    summary: str
    claims: list[Claim]
    speaker_notes: dict[str, str]   # per-speaker observations
    open_questions: list[str]       # uncertainties for Verifier
```

**Behavior:**

- Each claim MUST cite at least one `EvidenceRef`.
- Use acoustic labels (emotion, prosody, stress) as supporting evidence, not sole basis.
- Explicitly note code-switching, long pauses, overlaps, and low-confidence ASR segments.

**System prompt (summary):**

```
You are a communication coach analyzing a conversation. Follow the AnalysisPlan
step by step. Every claim must cite turn IDs or events from the provided
context. Distinguish observation from inference. Flag low ASR confidence.
Output valid JSON matching DraftAssessment schema.
```

---

### 4. Verifier

**Role:** Validate draft claims against the conversation graph; remove or downgrade unsupported statements.

| Field | Value |
|-------|-------|
| Input | `DraftAssessment`, `ConversationGraph`, `RetrievalBundle` |
| Output | `VerifiedAssessment` |
| LLM | Required — same or smaller model; temperature 0 |
| Tools | `verify_turn_exists`, `verify_quote`, `check_acoustic_label` |

**Output schema:**

```python
class VerifiedClaim(Claim):
    status: Literal["verified", "downgraded", "removed"]
    verification_note: str

class VerifiedAssessment(BaseModel):
    summary: str
    claims: list[VerifiedClaim]
    speaker_notes: dict[str, str]
    issues: list[str]              # hallucinations caught, missing evidence
    verification_score: float      # 0–1
```

**Behavior:**

- Check every cited turn ID exists and quotes match (fuzzy match threshold for ASR).
- Downgrade claims based on acoustic evidence alone without transcript support.
- Remove claims that cannot be grounded; record in `issues`.
- If `verification_score` < 0.5, orchestrator flags report for human review (future).

**System prompt (summary):**

```
You are a fact-checker for communication analysis. For each claim, verify
cited evidence exists in the conversation graph. Mark claims as verified,
downgraded, or removed. Be strict about hallucinated quotes or invented
events. Output valid JSON matching VerifiedAssessment schema.
```

---

### 5. Scorer

**Role:** Convert verified assessment into quantitative scores and actionable coaching.

| Field | Value |
|-------|-------|
| Input | `VerifiedAssessment`, `ConversationGraph`, `AnalysisPlan` |
| Output | `AnalysisReport` (final) |
| LLM | Required — structured output; temperature 0 |
| Tools | `score_rubric`, `coaching_templates` |

**Output schema:**

```python
class DimensionScore(BaseModel):
    dimension: str
    score: float              # 0–100
    confidence: float           # 0–1
    rationale: str
    evidence: list[EvidenceRef]

class CommunicationScores(BaseModel):
    overall: float
    dimensions: list[DimensionScore]

class CoachingAction(BaseModel):
    title: str
    description: str
    priority: Literal["high", "medium", "low"]
    practice_tip: str
    related_turns: list[str]
    dimension: str

# AnalysisReport — see Shared Types above
```

**Scoring rubric (default weights):**

| Dimension | Weight | Signals |
|-----------|--------|---------|
| Clarity | 20% | ASR coherence, filler ratio, turn completion |
| Pacing | 15% | WPM, pause distribution, overlap rate |
| Empathy | 20% | Emotion alignment, responsive turns |
| Assertiveness | 15% | Turn balance, interruption patterns |
| Fluency | 15% | Disfluency events, stress head output |
| Engagement | 15% | Turn count balance, question frequency |

**Behavior:**

- Apply `verification_score` as multiplier on confidence, not raw scores.
- Generate 2–5 coaching actions prioritized by lowest dimension scores.
- Coaching must reference specific turns and be actionable in one practice session.
- If all acoustic heads are disabled, skip Emotion and Fluency dimensions; redistribute weights proportionally across remaining dimensions.
- If `verified.verification_score < 0.3`, set `AnalysisReport.degraded = True` and flag `degradation_reason`.
- If Verifier removed > 50% of claims, cap `confidence` at 0.5 regardless of computation.

---

## Orchestration

```python
# backend/app/reasoning/orchestrator.py

class ReasoningOrchestrator:
    agents = [Retriever, Planner, Reasoner, Verifier, Scorer]

    async def run(self, session_id: UUID, config: AnalysisConfig) -> AnalysisReport:
        trace: list[AgentStepTrace] = []

        graph = await self.graph_repo.get_snapshot(session_id)
        memory = await self.memory.build_context(session_id, config)

        bundle = await self._run_agent(Retriever, graph, memory, config, trace)
        plan = await self._run_agent(Planner, graph, bundle, config, trace)
        draft = await self._run_agent(Reasoner, graph, bundle, plan, trace)
        verified = await self._run_agent(Verifier, draft, graph, bundle, trace)
        report = await self._run_agent(Scorer, verified, graph, plan, trace)

        report.agent_trace = trace
        await self.report_repo.save(report)
        await self.events.publish(session_id, "analysis.ready", report.id)
        return report
```

**Trigger points:**

- Automatic on session end (Redis Stream job)
- Manual via `POST /sessions/{id}/analysis/run`
- Re-run with different `AnalysisConfig.focus` without re-encoding audio

### Dependency Injection

```python
class ReasoningOrchestrator:
    def __init__(
        self,
        graph_repo: GraphRepository,        # PostgreSQL graph queries
        memory: MemoryService,              # Redis + Qdrant + PG memory
        report_repo: ReportRepository,      # CRUD for analysis_reports
        events: EventBus,                   # Redis Streams publisher
        llm_client: LLMClient,              # vLLM / SGLang OpenAI-compatible
        vector_store: QdrantClient,         # acoustic embedding search
        config: ReasoningConfig,            # env-driven settings
    ): ...
```

### Agent Timeouts & Partial Failure

Each agent step is wrapped with a timeout from `AnalysisConfig.timeout_per_agent_s` (default 120 s). For research iteration, prefer shorter timeouts (30–60 s) to fail fast on bad prompts rather than waiting to discover the failure; the production default of 120 s is tuned for deployed latency SLAs.

```python
async def _run_agent(self, agent_cls, *args, trace: list) -> Any:
    try:
        result = await asyncio.wait_for(
            agent_cls(...).run(*args),
            timeout=self.config.timeout_per_agent_s,
        )
    except asyncio.TimeoutError:
        # Partial output from Reasoner: save draft with completed plan steps
        if agent_cls == Reasoner:
            return DraftAssessment(
                summary="(partial — timeout)",
                claims=[],
                speaker_notes={},
                open_questions=[],
                draft_completeness_pct=len(completed_steps) / len(plan.steps),
            )
        raise AgentTimeoutError(agent_cls.__name__)
    except LLMUnavailableError:
        # Retry with smaller model if available
        if agent_cls == Reasoner and self.config.fallback_model:
            result = await self._run_with_fallback(agent_cls, *args)
        else:
            raise
    except Exception as e:
        trace[-1].error = str(e)
        if agent_cls in (Verifier, Scorer):
            return self._degraded_output(agent_cls, e)
        raise
    return result
```

### Idempotency & Concurrent Run Guard

```python
async def run(self, session_id: UUID, config: AnalysisConfig) -> AnalysisReport:
    # Check for existing in-flight analysis (409 Conflict)
    existing = await self.report_repo.get_in_flight(session_id)
    if existing:
        raise ConflictError("Analysis already in progress for this session")

    # Claim with idempotency key (Redis SETNX).
    # For local single-user research, this can be an in-process asyncio.Lock
    # instead — the Redis path is a config-swap for multi-user deploys.
    locked = await self.cache.acquire_lock(f"analysis:{session_id}", ttl=600)
    if not locked:
        raise ConflictError("Analysis already in progress for this session")
    try:
        return await self._execute_pipeline(session_id, config)
    finally:
        await self.cache.release_lock(f"analysis:{session_id}")
```

### Orchestrator Kill Recovery

On startup, scan `analysis_reports` for rows with `status = 'in_progress'` and an incomplete `agent_trace`. Resume from the last completed agent step by checking which agent's output is persisted and re-running the remaining agents. Mark orphaned runs as `status = 'aborted'` after a configurable grace period (e.g., 30 minutes).

> **Phase 2:** This is useful when the service runs unattended or gets restarted mid-analysis in a deployed setting. For local research runs, re-running the analysis is simpler than building resume logic. Keep the interface, defer full implementation until there's an unattended deploy target.

## Tool Registry

| Tool | Used by | Description |
|------|---------|-------------|
| `graph_traverse` | Retriever | BFS/DFS over conversation graph |
| `vector_search` | Retriever | Qdrant similarity (text + acoustic) |
| `keyword_search` | Retriever | PostgreSQL full-text on transcripts |
| `memory_lookup` | Retriever | User long-term memory documents |
| `lookup_turn` | Reasoner | Fetch full turn by ID |
| `lookup_acoustic` | Reasoner | Emotion/prosody labels for turn |
| `compare_speakers` | Reasoner | Turn balance, overlap stats |
| `verify_turn_exists` | Verifier | Graph membership check |
| `verify_quote` | Verifier | Fuzzy quote match against turn text |
| `check_acoustic_label` | Verifier | Confirm emotion/prosody label |
| `score_rubric` | Scorer | Apply dimension weights |
| `coaching_templates` | Scorer | Base templates per dimension |

## Prompt Management

```
backend/app/reasoning/prompts/
├── retriever_rerank.txt
├── planner_system.txt
├── reasoner_system.txt
├── verifier_system.txt
└── scorer_system.txt
```

Prompts versioned in git; `AnalysisConfig.prompt_version` selects active set for reproducibility.

## LLM Client Abstraction

```python
# backend/app/reasoning/llm_client.py (conceptual)

class LLMClient:
    """Thin wrapper over Ollama / vLLM / SGLang OpenAI-compatible API.

    SGLang's RadixAttention gives a throughput edge on this workload:
    the 5-agent pipeline re-sends overlapping context (system prompt,
    retrieved evidence, session state) at every stage, creating the
    shared-prefix pattern that RadixAttention caches aggressively.
    Both runtimes expose the same /v1/chat/completions contract,
    so swapping is a config change (LLM_BASE_URL), not a code change.

    For local single-user research, Ollama at localhost:11434 is the
    default. vLLM / SGLang activate by swapping LLM_BASE_URL.
    """
    def __init__(self, base_url: str, default_model: str, timeout_s: float = 120):
        self.client = AsyncOpenAI(base_url=base_url, api_key="not-needed")
        self._is_ollama = "11434" in base_url or "ollama" in base_url.lower()

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: dict | None = None,  # JSON schema for structured output
    ) -> tuple[dict, TokenUsage]:
        kwargs = dict(
            model=model or self.default_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if response_format is not None:
            if self._is_ollama:
                # Ollama's OpenAI-compatible endpoint does not fully honor
                # response_format: {"type": "json_schema", ...} — it ignores
                # the field on some versions. Ollama expects its own `format`
                # parameter with the raw JSON schema directly.
                kwargs["extra_body"] = {
                    "format": response_format["json_schema"]["schema"]
                }
            else:
                kwargs["response_format"] = response_format

        ...
```

**Ollama compatibility note:** Ollama's `/v1/chat/completions` does not reliably honor the standard `response_format: {"type": "json_schema", "json_schema": {...}}` payload. It expects its own `format` parameter with the raw JSON schema object. This mapping is handled automatically in `LLMClient` based on the detected backend, but should be explicitly tested against whichever backend is configured — a mismatch here fails silently (returns unconstrained text instead of schema-validated JSON), which breaks the structured-output guarantee every downstream agent relies on. Add a test in `test_llm_client.py` that validates the pipeline gets valid Pydantic-parsable output from each agent model.

## Input Validation (Pre-Pipeline)

Before the pipeline starts, validate the session meets minimum requirements:

| Check | Threshold | Action |
|-------|-----------|--------|
| Minimum turns | ≥ 3 turns | Abort with `InsufficientContextError` if fewer |
| Minimum speakers | ≥ 2 speakers | Flag as `single_speaker` mode (monologue analysis limited to Fluency + Clarity) |
| Minimum duration | ≥ 30 s | Abort with `InsufficientContextError` if shorter |
| ASR confidence coverage | ≥ 40% turns above `min_turn_confidence` | Downgrade confidence; filter low-conf turns |
| Enabled heads | At least `["asr"]` | Require ASR; all others optional |
| Idempotency | Check for existing in-flight analysis | Return 409 if analysis already running for session |

## Error Handling

| Failure | Behavior |
|---------|----------|
| Retriever empty (0 turns) | Abort with `InsufficientContextError`; suggest longer session |
| Retriever empty (Qdrant unreachable) | Fall back to PostgreSQL-only retrieval; flag `retrieval_mode: "degraded"` in metadata |
| Retriever empty (PG full-text down) | Fall back to Qdrant-only; skip keyword search dimension in plan |
| Planner invalid JSON | Retry once with repair prompt; then fail with `AgentJSONError` |
| Planner returns 0 steps | Retry with broader objective prompt; if still 0, abort |
| Reasoner timeout | Partial draft from completed plan steps; flag `draft_completeness_pct` |
| Reasoner LLM unavailable | Retry with fallback model (7B if 14B down); if both fail, abort |
| Verifier removes all claims | Return report with `confidence: 0`, summary explains limitation, `degraded: true` |
| Verifier returns `verification_score < 0.5` | Orchestrator flags report for human review; still deliver to client with warning |
| Scorer failure | Return verified assessment without scores (degraded mode); `degraded: true` |
| Scorer LLM returns malformed scores | Apply rubric heuristics as fallback (rule-based extraction from verified claims) |
| All acoustic heads disabled | Skip acoustic dimensions (Emotion, Fluency); score only from transcript evidence |
| Single speaker session | Disable Assertiveness and Engagement dimensions; adjust rubric weights |
| All ASR confidence < threshold | Abort with `LowConfidenceError`; suggest re-recording with better audio |
| Concurrent analysis on same session | Idempotency key guard; return existing report or 409 Conflict |
| Memory backend unavailable | Skip `prior_sessions` in context; flag in report metadata |
| vLLM base URL unreachable | Retry 3x with exponential backoff; abort with `LLMUnavailableError` after |
| Agent step raises unexpected exception | Catch, log full trace, inject error into `AgentStepTrace`, continue to next step if possible |
| Orchestrator killed mid-pipeline | On restart, detect incomplete trace and resume from last completed step |

## Testing Agents

```python
# Each agent tested in isolation with fixture graphs

@pytest.fixture
def sample_graph(): ...

async def test_verifier_removes_hallucinated_quote(sample_graph):
    draft = DraftAssessment(claims=[Claim(statement="...", evidence=[fake_ref])])
    result = await VerifierAgent().run(draft, sample_graph, bundle)
    assert result.claims[0].status == "removed"
```

Snapshot tests on agent outputs for regression when prompts change.

**CI testing with lightweight models:** For CI pipelines that need a real LLM without GPU access, configure `ci_test_model` to a CPU-capable model like `LiquidAI/LFM2.5-230M` (42 tok/s on Raspberry Pi 5, vLLM/SGLang compatible). The model's 32K context length and agentic/tool-use focus suit Planner, Verifier, and Scorer — but it is explicitly not suitable for the Reasoner (reasoning-heavy workloads). CI test suites should either mock the Reasoner or skip it, running the other four agents against real inference to validate pipeline wiring without a GPU requirement.

## Future Agents (Not MVP)

| Agent | Purpose |
|-------|---------|
| **Summarizer** | Pre-compress sessions > 100 turns before Planner |
| **Comparative** | Compare two sessions for same user |
| **Adaptation** | Suggest fine-tuning data from flagged turns |
| **Language Specialist** | Low-resource language-specific reasoning |

Insert into pipeline via orchestrator config without changing existing agent contracts.

## Configuration

```yaml
# config/reasoning.yaml
llm:
  base_url: http://localhost:11434/v1  # Ollama, OpenAI-compatible — local/research phase
  # base_url: http://localhost:8080/v1 # vLLM or SGLang — swap when moving beyond single-user local
  planner_model: <planner-model>      # e.g. qwen3-8b-instruct; lightweight, fast, Apache 2.0
  reasoner_model: <reasoner-model>    # e.g. qwen3-14b-instruct; larger, high quality, Apache 2.0
  verifier_model: <verifier-model>    # e.g. same as planner; temperature 0
  scorer_model: <scorer-model>        # e.g. same as planner; structured output
  fallback_model: <fallback-model>    # smaller model for degraded mode (e.g. 3B class) — Phase 2
  ci_test_model: <ci-test-model>      # ultra-light model for CI/testing (e.g. LiquidAI/LFM2.5-230M — 42 tok/s on Raspberry Pi 5, CPU-only capable)
  temperature: 0.1
  max_tokens: 4096
  timeout_per_agent_s: 120

retrieval:
  top_k_turns: 15
  acoustic_neighbors: 5
  include_prior_sessions: true

scoring:
  rubric_version: v1
  min_session_turns: 3
```

## Related Documents

- [System Architecture](./docs/architecture/README.md)
- [Backend Architecture](./docs/architecture/backend.md)
- [Frontend Architecture](./docs/architecture/frontend.md)
