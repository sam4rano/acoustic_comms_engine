from __future__ import annotations

from uuid import UUID

from app.graph.types import ConversationGraph
from app.reasoning.agents.base import BaseAgent
from app.reasoning.llm_client import LLMClient
from app.reasoning.schemas import (
    AnalysisPlan,
    AnalysisReport,
    Claim,
    CoachingAction,
    CommunicationScores,
    DimensionScore,
    EvidenceRef,
    VerifiedAssessment,
)

DIMENSION_WEIGHTS: dict[str, float] = {
    "clarity": 0.20,
    "pacing": 0.15,
    "empathy": 0.20,
    "assertiveness": 0.15,
    "fluency": 0.15,
    "engagement": 0.15,
}

COACHING_TEMPLATES: dict[str, list[dict]] = {
    "clarity": [
        {
            "title": "Reduce filler words",
            "description": "Practice pausing instead of using filler words like 'um', 'uh', 'like'.",
            "priority": "high",
            "practice_tip": "Record yourself speaking for 2 minutes on any topic, then count your filler words. Aim to reduce by half.",
        },
        {
            "title": "Complete your thoughts",
            "description": "Focus on finishing sentences before moving to the next thought.",
            "priority": "medium",
            "practice_tip": "When you catch yourself trailing off, take a breath and complete the original thought.",
        },
    ],
    "pacing": [
        {
            "title": "Regulate speaking pace",
            "description": "Adjust speaking rate for better listener comprehension.",
            "priority": "high",
            "practice_tip": "Practice speaking at 150 WPM by reading a passage aloud with a timer.",
        },
    ],
    "empathy": [
        {
            "title": "Ask more questions",
            "description": "Show engagement by asking follow-up questions.",
            "priority": "high",
            "practice_tip": "After someone shares something, ask at least one question before sharing your own experience.",
        },
    ],
    "assertiveness": [
        {
            "title": "Use direct language",
            "description": "State your position clearly and directly.",
            "priority": "medium",
            "practice_tip": "Practice 'I think...' and 'I believe...' statements instead of qualifiers.",
        },
    ],
    "fluency": [
        {
            "title": "Practice smooth transitions",
            "description": "Work on transitioning between ideas without hesitation.",
            "priority": "medium",
            "practice_tip": "Practice explaining a concept from start to finish without backtracking.",
        },
    ],
    "engagement": [
        {
            "title": "Balance participation",
            "description": "Ensure balanced speaking time among participants.",
            "priority": "medium",
            "practice_tip": "After speaking for 30 seconds, pause and invite another person to share.",
        },
    ],
}


class Scorer(BaseAgent):
    name = "scorer"

    async def run(
        self,
        verified: VerifiedAssessment,
        graph: ConversationGraph,
        plan: AnalysisPlan,
    ) -> AnalysisReport:
        dimensions = plan.dimensions or list(DIMENSION_WEIGHTS.keys())

        weights = self._compute_weights(dimensions)

        dimension_scores = self._score_dimensions(
            verified.claims, dimensions, weights, verified.verification_score,
        )

        overall = sum(d.score * w for d, w in zip(dimension_scores, weights.values()))

        coaching = self._generate_coaching(dimension_scores, verified)

        evidence = self._collect_evidence(verified.claims)

        confidence = self._compute_confidence(verified, dimension_scores)

        degraded, degradation_reason = self._check_degradation(verified, dimension_scores)

        return AnalysisReport(
            session_id=graph.session_id,
            scores=CommunicationScores(
                overall=round(overall, 1),
                dimensions=dimension_scores,
            ),
            coaching=coaching,
            summary=verified.summary,
            evidence=evidence,
            confidence=confidence,
            degraded=degraded,
            degradation_reason=degradation_reason,
        )

    def _compute_weights(self, dimensions: list[str]) -> dict[str, float]:
        weights = {}
        total_weight = 0.0
        for d in dimensions:
            dl = d.lower()
            if dl in DIMENSION_WEIGHTS:
                weights[dl] = DIMENSION_WEIGHTS[dl]
                total_weight += DIMENSION_WEIGHTS[dl]

        if total_weight > 0 and abs(total_weight - 1.0) > 0.001:
            for d in weights:
                weights[d] /= total_weight

        return weights

    def _score_dimensions(
        self,
        claims: list[Claim],
        dimensions: list[str],
        weights: dict[str, float],
        verification_score: float,
    ) -> list[DimensionScore]:
        base_score = 50.0
        claim_adjustments: dict[str, list[float]] = {d: [] for d in dimensions}

        for claim in claims:
            dim = claim.dimension.lower()
            if dim not in claim_adjustments:
                continue
            if claim.polarity == "strength":
                claim_adjustments[dim].append(20.0)
            elif claim.polarity == "weakness":
                claim_adjustments[dim].append(-15.0)
            else:
                claim_adjustments[dim].append(0.0)

        scores: list[DimensionScore] = []
        for dim in dimensions:
            dl = dim.lower()
            adjustments = claim_adjustments.get(dl, [])
            raw_score = base_score + sum(adjustments)
            final_score = max(0.0, min(100.0, raw_score))

            rationale_parts = []
            if adjustments:
                pos = sum(1 for a in adjustments if a > 0)
                neg = sum(1 for a in adjustments if a < 0)
                if pos:
                    rationale_parts.append(f"{pos} strength(s) identified")
                if neg:
                    rationale_parts.append(f"{neg} weakness(es) identified")
            if not rationale_parts:
                rationale_parts.append("No specific claims for this dimension")

            plausible = verification_score
            if verification_score < 0.5:
                plausible = max(0.1, verification_score)

            scores.append(DimensionScore(
                dimension=dl,
                score=round(final_score, 1),
                confidence=round(plausible, 2),
                rationale="; ".join(rationale_parts),
                evidence=self._claim_evidence_for_dimension(claims, dl),
            ))

        return scores

    def _claim_evidence_for_dimension(
        self,
        claims: list[Claim],
        dimension: str,
    ) -> list[EvidenceRef]:
        all_evidence: list[EvidenceRef] = []
        for c in claims:
            if c.dimension.lower() == dimension:
                all_evidence.extend(c.evidence)
        return all_evidence

    def _generate_coaching(
        self,
        dimension_scores: list[DimensionScore],
        verified: VerifiedAssessment,
    ) -> list[CoachingAction]:
        sorted_dims = sorted(dimension_scores, key=lambda d: d.score)
        actions: list[CoachingAction] = []

        for ds in sorted_dims[:3]:
            templates = COACHING_TEMPLATES.get(ds.dimension, [])
            if not templates:
                continue
            tpl = templates[0]
            related_turns = [
                str(e.id) for e in ds.evidence
                if e.type == "turn"
            ][:3]
            actions.append(CoachingAction(
                title=tpl["title"],
                description=tpl["description"],
                priority=tpl["priority"],
                practice_tip=tpl["practice_tip"],
                related_turns=related_turns,
                dimension=ds.dimension,
            ))

        return actions[:5]

    def _collect_evidence(self, claims: list[Claim]) -> list[EvidenceRef]:
        seen: set[str] = set()
        result: list[EvidenceRef] = []
        for c in claims:
            for e in c.evidence:
                key = f"{e.type}:{e.id}"
                if key not in seen:
                    seen.add(key)
                    result.append(e)
        return result

    def _compute_confidence(
        self,
        verified: VerifiedAssessment,
        dimension_scores: list[DimensionScore],
    ) -> float:
        if verified.verification_score < 0.3:
            return 0.0

        removed_count = sum(1 for c in verified.claims if c.status == "removed")
        total = len(verified.claims)
        if total > 0 and removed_count / total > 0.5:
            return 0.5

        avg_dim_confidence = (
            sum(d.confidence for d in dimension_scores) / len(dimension_scores)
            if dimension_scores
            else 0.0
        )

        return round(avg_dim_confidence, 2)

    def _check_degradation(
        self,
        verified: VerifiedAssessment,
        dimension_scores: list[DimensionScore],
    ) -> tuple[bool, str | None]:
        if verified.verification_score < 0.3:
            return True, "Verification score below 0.3 threshold"

        removed_count = sum(1 for c in verified.claims if c.status == "removed")
        total = len(verified.claims)
        if total > 0 and removed_count / total > 0.5:
            return True, "More than 50% of claims were removed"

        if not dimension_scores:
            return True, "No dimensions could be scored"

        return False, None
