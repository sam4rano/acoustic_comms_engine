from __future__ import annotations

import logging

from app.graph.types import ConversationGraph
from app.memory.types import RetrievalBundle
from app.reasoning.agents.base import BaseAgent
from app.reasoning.llm_client import LLMClient
from app.reasoning.schemas import AnalysisConfig, AnalysisPlan, PlanStep

logger = logging.getLogger(__name__)

DEFAULT_DIMENSIONS = [
    "clarity", "pacing", "empathy", "assertiveness", "fluency", "engagement",
]


class Planner(BaseAgent):
    name = "planner"

    async def run(
        self,
        graph: ConversationGraph,
        bundle: RetrievalBundle,
        config: AnalysisConfig,
    ) -> AnalysisPlan:
        dimensions = self._select_dimensions(graph, config)

        steps = self._build_steps(dimensions, graph, config)

        constraints = self._build_constraints(graph, config)

        plan = AnalysisPlan(
            objective=self._build_objective(config),
            steps=steps,
            dimensions=dimensions,
            constraints=constraints,
        )

        if config.prompt_version != "none":
            try:
                system_prompt = self._load_prompt()
                user_prompt = self._build_user_prompt(graph, bundle, config)
                plan, _ = await self._llm.complete_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    output_model=AnalysisPlan,
                    model=self._model,
                )
            except Exception:
                logger.warning("LLM planner failed, using rule-based plan")

        return plan

    def _select_dimensions(
        self,
        graph: ConversationGraph,
        config: AnalysisConfig,
    ) -> list[str]:
        if config.dimensions:
            return list(config.dimensions)

        dims = list(DEFAULT_DIMENSIONS)

        if graph.speaker_count < 2:
            dims = [d for d in dims if d not in ("assertiveness", "engagement")]

        if "emotion" not in config.enabled_heads:
            dims = [d for d in dims if d != "empathy"]

        if "prosody" not in config.enabled_heads and "fluency" not in config.enabled_heads:
            dims = [d for d in dims if d != "fluency"]

        return dims

    def _build_steps(
        self,
        dimensions: list[str],
        graph: ConversationGraph,
        config: AnalysisConfig,
    ) -> list[PlanStep]:
        steps: list[PlanStep] = []

        if "clarity" in dimensions:
            steps.append(PlanStep(
                id="clarity",
                question="How clear and coherent is each speaker's speech?",
                required_evidence=["transcript"],
                priority="high",
            ))

        if "pacing" in dimensions:
            steps.append(PlanStep(
                id="pacing",
                question="Is the speaking pace appropriate and well-regulated?",
                required_evidence=["transcript", "timing"],
                priority="medium",
            ))

        if "empathy" in dimensions:
            evidence = ["transcript", "emotion"]
            steps.append(PlanStep(
                id="empathy",
                question="Does the speaker demonstrate empathetic listening and responding?",
                required_evidence=evidence,
                priority="high",
            ))

        if "assertiveness" in dimensions:
            steps.append(PlanStep(
                id="assertiveness",
                question="How effectively does each speaker express their position?",
                required_evidence=["transcript", "timing", "events"],
                priority="medium",
            ))

        if "fluency" in dimensions:
            evidence = ["transcript"]
            if "prosody" in config.enabled_heads:
                evidence.append("prosody")
            steps.append(PlanStep(
                id="fluency",
                question="How fluent is the speech with minimal disfluencies?",
                required_evidence=evidence,
                priority="medium",
            ))

        if "engagement" in dimensions:
            steps.append(PlanStep(
                id="engagement",
                question="How engaged are the participants in the conversation?",
                required_evidence=["transcript", "timing", "events"],
                priority="low",
            ))

        return steps

    def _build_constraints(
        self,
        graph: ConversationGraph,
        config: AnalysisConfig,
    ) -> list[str]:
        constraints = []
        if graph.speaker_count < 2:
            constraints.append("single_speaker")
        if config.language not in ("en",):
            constraints.append(f"low_resource_language:{config.language}")
        if len(graph.turns) < 5:
            constraints.append("short_session")
        return constraints

    def _build_objective(self, config: AnalysisConfig) -> str:
        if config.focus:
            return f"Evaluate communication quality focusing on: {config.focus}"
        return "Evaluate overall communication quality across all dimensions"

    def _load_prompt(self) -> str:
        try:
            from importlib.resources import files
            return (
                files("app.reasoning.prompts")
                .joinpath("planner_system.txt")
                .read_text()
            )
        except Exception:
            return "You are a communication analysis planner."

    def _build_user_prompt(
        self,
        graph: ConversationGraph,
        bundle: RetrievalBundle,
        config: AnalysisConfig,
    ) -> str:
        return (
            f"Session: {graph.session_id}\n"
            f"Speakers: {graph.speaker_count}\n"
            f"Turns: {len(graph.turns)}\n"
            f"Duration: {graph.duration_ms}ms\n"
            f"Language: {config.language}\n"
            f"Focus: {config.focus or 'none'}\n"
            f"Enabled heads: {config.enabled_heads}\n"
        )
