from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID

from app.graph.analyzer import GraphAnalyzer
from app.graph.traverser import GraphTraverser
from app.graph.types import ConversationGraph
from app.memory.service import MemoryService
from app.memory.types import RetrievalBundle
from app.reasoning.agents.planner import Planner
from app.reasoning.agents.reasoner import Reasoner
from app.reasoning.agents.retriever import Retriever
from app.reasoning.agents.scorer import Scorer
from app.reasoning.agents.verifier import Verifier
from app.reasoning.errors import (
    AgentTimeoutError,
    InsufficientContextError,
    LLMUnavailableError,
)
from app.reasoning.llm_client import LLMClient
from app.reasoning.schemas import (
    AgentStepTrace,
    AnalysisConfig,
    AnalysisPlan,
    AnalysisReport,
    DraftAssessment,
    MemoryContext,
    TokenUsage,
    VerifiedAssessment,
)

logger = logging.getLogger(__name__)

# ── Validation thresholds ────────────────────────────────────────────

MIN_TURNS = 3
MIN_SPEAKERS = 2
MIN_DURATION_MS = 30_000
MIN_CONFIDENCE_COVERAGE = 0.4


class ReasoningOrchestrator:
    def __init__(
        self,
        llm_client: LLMClient,
        graph_traverser: GraphTraverser,
        graph_analyzer: GraphAnalyzer,
        memory_service: MemoryService,
    ) -> None:
        self._retriever = Retriever(llm_client, memory_service, graph_traverser)
        self._planner = Planner(llm_client)
        self._reasoner = Reasoner(
            llm_client, graph_traverser, graph_analyzer, memory_service,
        )
        self._verifier = Verifier(llm_client, graph_traverser)
        self._scorer = Scorer(llm_client)

    async def run(
        self,
        session_id: UUID,
        user_id: UUID,
        graph: ConversationGraph,
        config: AnalysisConfig | None = None,
    ) -> AnalysisReport:
        cfg = config or AnalysisConfig()

        self._validate_session(graph, cfg)

        memory_context = MemoryContext(
            user_id=user_id,
            preferences={},
        )

        trace: list[AgentStepTrace] = []

        timeout = cfg.timeout_per_agent_s

        bundle = await self._run_agent(
            "retriever", self._retriever.run,
            trace, timeout,
            graph=graph, memory_context=memory_context, config=cfg,
        )

        plan = await self._run_agent(
            "planner", self._planner.run,
            trace, timeout,
            graph=graph, bundle=bundle, config=cfg,
        )

        draft = await self._run_agent(
            "reasoner", self._reasoner.run,
            trace, timeout,
            graph=graph, bundle=bundle, plan=plan,
        )

        verified = await self._run_agent(
            "verifier", self._verifier.run,
            trace, timeout,
            draft=draft, graph=graph, bundle=bundle,
        )

        report = await self._run_agent(
            "scorer", self._scorer.run,
            trace, timeout,
            verified=verified, graph=graph, plan=plan,
        )

        report.agent_trace = trace
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_agent(
        self,
        name: str,
        coro,
        trace: list[AgentStepTrace],
        agent_timeout: float,
        **kwargs,
    ):
        started_at = _now()
        input_summary = f"{name}({', '.join(k for k in kwargs)})"

        try:
            result = await asyncio.wait_for(
                coro(**kwargs),
                timeout=agent_timeout,
            )

            token_usage: TokenUsage | None = None
            if hasattr(result, "_llm_usage") and result._llm_usage:
                token_usage = result._llm_usage

            trace.append(AgentStepTrace(
                agent=name,
                started_at=started_at,
                duration_ms=_elapsed_ms(started_at),
                input_summary=input_summary,
                output=_safe_output(result),
                model=name,
                token_usage=token_usage,
            ))
            return result

        except asyncio.TimeoutError:
            elapsed = _elapsed_ms(started_at)
            trace.append(AgentStepTrace(
                agent=name,
                started_at=started_at,
                duration_ms=elapsed,
                input_summary=input_summary,
                output={"error": f"Timeout after {agent_timeout}s"},
                model=name,
                error=f"Timeout after {agent_timeout}s",
            ))
            raise AgentTimeoutError(
                f"{name} timed out after {agent_timeout}s"
            )

        except Exception as exc:
            elapsed = _elapsed_ms(started_at)
            trace.append(AgentStepTrace(
                agent=name,
                started_at=started_at,
                duration_ms=elapsed,
                input_summary=input_summary,
                output={"error": str(exc)},
                model=name,
                error=str(exc),
            ))

            if name in ("verifier", "scorer"):
                return self._degraded_output(name, exc)

            raise

    def _validate_session(
        self,
        graph: ConversationGraph,
        config: AnalysisConfig,
    ) -> None:
        if graph.turn_count < MIN_TURNS:
            raise InsufficientContextError(
                f"Session has {graph.turn_count} turns, minimum is {MIN_TURNS}"
            )

        if graph.speaker_count < MIN_SPEAKERS:
            logger.info("Single-speaker session — disabling assertiveness and engagement")

        if graph.duration_ms < MIN_DURATION_MS:
            raise InsufficientContextError(
                f"Session duration {graph.duration_ms}ms is below minimum {MIN_DURATION_MS}ms"
            )

        above_threshold = sum(
            1 for t in graph.turns if t.confidence >= config.min_turn_confidence
        )
        coverage = above_threshold / max(graph.turn_count, 1)
        if coverage < MIN_CONFIDENCE_COVERAGE:
            logger.warning(
                "Low ASR confidence coverage: %.0f%% of turns above %.1f threshold",
                coverage * 100,
                config.min_turn_confidence,
            )

    def _degraded_output(self, agent_name: str, exc: Exception):
        if agent_name == "verifier":
            return VerifiedAssessment(
                summary=f"Verifier failed: {exc}",
                claims=[],
                issues=[f"Verifier error: {exc}"],
                verification_score=0.0,
            )
        return None


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _elapsed_ms(started_at) -> int:
    return int((_now() - started_at).total_seconds() * 1000)


def _safe_output(result) -> dict:
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "model_dump_json"):
        return {"raw": result.model_dump_json()}
    return {"type": type(result).__name__}
