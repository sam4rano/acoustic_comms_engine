from __future__ import annotations

import logging
from uuid import UUID

from app.graph.analyzer import GraphAnalyzer
from app.graph.traverser import GraphTraverser
from app.graph.types import ConversationGraph, TurnNode
from app.memory.service import MemoryService
from app.memory.types import RetrievalBundle, TurnSummary
from app.reasoning.agents.base import BaseAgent
from app.reasoning.llm_client import LLMClient
from app.reasoning.schemas import (
    AnalysisPlan,
    Claim,
    DraftAssessment,
    EvidenceRef,
)

logger = logging.getLogger(__name__)


class Reasoner(BaseAgent):
    name = "reasoner"

    def __init__(
        self,
        llm_client: LLMClient,
        graph_traverser: GraphTraverser,
        graph_analyzer: GraphAnalyzer,
        memory_service: MemoryService,
        model: str | None = None,
    ) -> None:
        super().__init__(llm_client, model)
        self._traverser = graph_traverser
        self._analyzer = graph_analyzer
        self._memory = memory_service

    async def run(
        self,
        graph: ConversationGraph,
        bundle: RetrievalBundle,
        plan: AnalysisPlan,
    ) -> DraftAssessment:
        try:
            system_prompt = self._load_prompt()
            user_prompt = self._build_user_prompt(graph, bundle, plan)
            draft, _ = await self._llm.complete_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_model=DraftAssessment,
                model=self._model,
            )
            return draft
        except Exception:
            logger.warning("LLM reasoner failed, using rule-based draft")
            return self._rule_based_draft(graph, bundle, plan)

    def lookup_turn(self, graph: ConversationGraph, turn_id: UUID) -> TurnNode | None:
        for t in graph.turns:
            if t.id == turn_id:
                return t
        return None

    def lookup_turn_summary(self, bundle: RetrievalBundle, turn_id: UUID) -> TurnSummary | None:
        for t in bundle.core_turns + bundle.relevant_turns:
            if t.turn_id == turn_id:
                return t
        return None

    def lookup_acoustic(self, turn: TurnNode, head: str) -> str | None:
        return turn.acoustic_labels.get(head)

    def _rule_based_draft(
        self,
        graph: ConversationGraph,
        bundle: RetrievalBundle,
        plan: AnalysisPlan,
    ) -> DraftAssessment:
        claims: list[Claim] = []
        analysis = self._analyzer.analyze(graph)

        if "clarity" in plan.dimensions:
            clarity_score = "strength" if analysis.filler_word_count < 5 else "weakness"
            claims.append(Claim(
                statement=f"Filler word count: {analysis.filler_word_count}",
                evidence=[EvidenceRef(type="event", id=str(analysis.session_id))],
                dimension="clarity",
                polarity=clarity_score,
            ))

        if "pacing" in plan.dimensions:
            wpm = analysis.speaking_speed.get("overall_wpm", 0)
            pace = "strength" if 120 <= wpm <= 180 else "weakness"
            claims.append(Claim(
                statement=f"Speaking rate: {wpm} WPM",
                evidence=[EvidenceRef(type="event", id=str(analysis.session_id))],
                dimension="pacing",
                polarity=pace,
            ))

        if "empathy" in plan.dimensions:
            if analysis.question_count > 2:
                claims.append(Claim(
                    statement=f"Questions asked: {analysis.question_count}",
                    evidence=[EvidenceRef(type="event", id="analysis")],
                    dimension="empathy",
                    polarity="strength",
                ))

        if "engagement" in plan.dimensions:
            if analysis.turn_balance > 0.7:
                claims.append(Claim(
                    statement=f"Turn balance: {analysis.turn_balance:.2f}",
                    evidence=[EvidenceRef(type="event", id="analysis")],
                    dimension="engagement",
                    polarity="strength",
                ))
            else:
                claims.append(Claim(
                    statement=f"Turn balance: {analysis.turn_balance:.2f}",
                    evidence=[EvidenceRef(type="event", id="analysis")],
                    dimension="engagement",
                    polarity="weakness",
                ))

        speaker_notes = {}
        for stat in analysis.speaker_stats:
            speaker_notes[stat.label] = (
                f"{stat.turn_count} turns, {stat.word_count} words, "
                f"{stat.filler_count} fillers"
            )

        return DraftAssessment(
            summary=f"Analyzed {analysis.total_turns} turns with {analysis.total_duration_ms}ms total duration.",
            claims=claims,
            speaker_notes=speaker_notes,
            open_questions=["What communication goals did the speaker have?"],
        )

    def _load_prompt(self) -> str:
        try:
            from importlib.resources import files
            return (
                files("app.reasoning.prompts")
                .joinpath("reasoner_system.txt")
                .read_text()
            )
        except Exception:
            return "You are a communication coach analyzing a conversation."

    def _build_user_prompt(
        self,
        graph: ConversationGraph,
        bundle: RetrievalBundle,
        plan: AnalysisPlan,
    ) -> str:
        turns_summary = "\n".join(
            f"  [{t.speaker_label}] {t.text[:120]}"
            for t in (bundle.core_turns + bundle.relevant_turns)[:30]
        )
        steps_summary = "\n".join(f"  {s.id}: {s.question}" for s in plan.steps)
        return (
            f"Session: {graph.session_id}\n"
            f"Plan objective: {plan.objective}\n"
            f"Steps:\n{steps_summary}\n"
            f"Core turns:\n{turns_summary}\n"
        )
