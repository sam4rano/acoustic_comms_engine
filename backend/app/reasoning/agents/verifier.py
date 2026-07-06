from __future__ import annotations

from uuid import UUID

from app.graph.traverser import GraphTraverser
from app.graph.types import ConversationGraph
from app.memory.types import RetrievalBundle
from app.reasoning.agents.base import BaseAgent
from app.reasoning.llm_client import LLMClient
from app.reasoning.schemas import (
    Claim,
    DraftAssessment,
    EvidenceRef,
    VerifiedAssessment,
    VerifiedClaim,
)


class Verifier(BaseAgent):
    name = "verifier"

    def __init__(
        self,
        llm_client: LLMClient,
        graph_traverser: GraphTraverser,
        model: str | None = None,
    ) -> None:
        super().__init__(llm_client, model)
        self._traverser = graph_traverser

    async def run(
        self,
        draft: DraftAssessment,
        graph: ConversationGraph,
        bundle: RetrievalBundle,
    ) -> VerifiedAssessment:
        verified_claims: list[VerifiedClaim] = []
        issues: list[str] = []

        turn_ids = {t.id for t in graph.turns}
        turn_texts: dict[UUID, str] = {t.id: t.text for t in graph.turns}

        for claim in draft.claims:
            vc = self._verify_claim(claim, turn_ids, turn_texts)
            if vc.status == "removed":
                issues.append(f"Removed claim: {claim.statement[:80]}")
            elif vc.status == "downgraded":
                issues.append(f"Downgraded claim: {claim.statement[:80]} — {vc.verification_note}")
            verified_claims.append(vc)

        total = len(verified_claims)
        if total == 0:
            verification_score = 1.0
        else:
            verified_count = sum(1 for c in verified_claims if c.status == "verified")
            verification_score = verified_count / total

        if not verified_claims:
            issues.append("All claims were removed — no verified claims remain")

        return VerifiedAssessment(
            summary=draft.summary,
            claims=verified_claims,
            speaker_notes=draft.speaker_notes,
            issues=issues,
            verification_score=verification_score,
        )

    def _verify_claim(
        self,
        claim: Claim,
        turn_ids: set[UUID],
        turn_texts: dict[UUID, str],
    ) -> VerifiedClaim:
        if not claim.evidence:
            return VerifiedClaim(
                statement=claim.statement,
                evidence=claim.evidence,
                dimension=claim.dimension,
                polarity=claim.polarity,
                status="downgraded",
                verification_note="No evidence cited",
            )

        all_valid = True
        for ref in claim.evidence:
            if not self._verify_evidence_ref(ref, turn_ids, turn_texts):
                all_valid = False

        if all_valid:
            return VerifiedClaim(
                statement=claim.statement,
                evidence=claim.evidence,
                dimension=claim.dimension,
                polarity=claim.polarity,
                status="verified",
                verification_note="All evidence verified",
            )

        valid_refs = [
            ref for ref in claim.evidence
            if self._verify_evidence_ref(ref, turn_ids, turn_texts)
        ]

        if not valid_refs:
            return VerifiedClaim(
                statement=claim.statement,
                evidence=claim.evidence,
                dimension=claim.dimension,
                polarity=claim.polarity,
                status="removed",
                verification_note="No valid evidence references found",
            )

        return VerifiedClaim(
            statement=claim.statement,
            evidence=valid_refs,
            dimension=claim.dimension,
            polarity=claim.polarity,
            status="downgraded",
            verification_note="Some evidence references could not be verified",
        )

    def _verify_evidence_ref(
        self,
        ref: EvidenceRef,
        turn_ids: set[UUID],
        turn_texts: dict[UUID, str],
    ) -> bool:
        if ref.type == "turn":
            return self._verify_turn_ref(ref, turn_ids, turn_texts)
        if ref.type == "embedding":
            return True
        if ref.type == "document":
            return True
        if ref.type == "event":
            return True
        return False

    def _verify_turn_ref(
        self,
        ref: EvidenceRef,
        turn_ids: set[UUID],
        turn_texts: dict[UUID, str],
    ) -> bool:
        try:
            tid = UUID(ref.id)
        except ValueError:
            return False

        if tid not in turn_ids:
            return False

        if ref.quote:
            turn_text = turn_texts.get(tid, "")
            if not self._fuzzy_match(ref.quote, turn_text):
                return False

        return True

    @staticmethod
    def _fuzzy_match(quote: str, text: str) -> bool:
        return quote.lower() in text.lower()
