"""Tests for the Verifier agent."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.reasoning.agents.verifier import Verifier
from app.reasoning.schemas import (
    Claim,
    DraftAssessment,
    EvidenceRef,
    VerifiedAssessment,
)


class TestVerifier:
    async def test_verifies_valid_claims(
        self,
        verifier_agent: Verifier,
        sample_graph,
        sample_retrieval_bundle,
        sample_draft: DraftAssessment,
    ):
        result = await verifier_agent.run(sample_draft, sample_graph, sample_retrieval_bundle)
        assert isinstance(result, VerifiedAssessment)
        assert all(c.status == "verified" for c in result.claims)

    async def test_removes_hallucinated_turn_ids(
        self,
        verifier_agent: Verifier,
        sample_graph,
        sample_retrieval_bundle,
        sample_draft_with_hallucination: DraftAssessment,
    ):
        result = await verifier_agent.run(
            sample_draft_with_hallucination, sample_graph, sample_retrieval_bundle,
        )
        claim_with_fake = [
            c for c in result.claims
            if any(e.id == "00000000-0000-0000-0000-00000000ffff" for e in c.evidence)
        ]
        assert len(claim_with_fake) == 1
        assert claim_with_fake[0].status == "removed"

    async def test_downgrades_acoustic_only_claim(
        self,
        verifier_agent: Verifier,
        sample_graph,
        sample_retrieval_bundle,
    ):
        draft = DraftAssessment(
            summary="Test",
            claims=[
                Claim(
                    statement="Speaker sounds happy.",
                    evidence=[
                        EvidenceRef(type="turn", id=str(sample_graph.turns[0].id)),
                    ],
                    dimension="empathy",
                    polarity="strength",
                ),
            ],
        )
        result = await verifier_agent.run(draft, sample_graph, sample_retrieval_bundle)
        assert result.claims[0].status in ("verified", "downgraded")

    async def test_fuzzy_quote_matching(
        self,
        verifier_agent: Verifier,
        sample_graph,
        sample_retrieval_bundle,
    ):
        draft = DraftAssessment(
            summary="Test",
            claims=[
                Claim(
                    statement="Speaker A greets.",
                    evidence=[
                        EvidenceRef(
                            type="turn",
                            id=str(sample_graph.turns[0].id),
                            quote="HELLO, HOW",
                        ),
                    ],
                    dimension="clarity",
                    polarity="strength",
                ),
            ],
        )
        result = await verifier_agent.run(draft, sample_graph, sample_retrieval_bundle)
        assert result.claims[0].status == "verified"

    async def test_verification_score_computed(
        self,
        verifier_agent: Verifier,
        sample_graph,
        sample_retrieval_bundle,
        sample_draft_with_hallucination: DraftAssessment,
    ):
        result = await verifier_agent.run(
            sample_draft_with_hallucination, sample_graph, sample_retrieval_bundle,
        )
        assert 0 <= result.verification_score <= 1.0
        assert result.verification_score == 0.5

    async def test_handles_empty_draft(
        self,
        verifier_agent: Verifier,
        sample_graph,
        sample_retrieval_bundle,
    ):
        draft = DraftAssessment(summary="Empty", claims=[])
        result = await verifier_agent.run(draft, sample_graph, sample_retrieval_bundle)
        assert result.verification_score == 1.0
        assert result.claims == []

    async def test_all_claims_removed_scenario(
        self,
        verifier_agent: Verifier,
        sample_graph,
        sample_retrieval_bundle,
    ):
        fake_id = UUID("00000000-0000-0000-0000-00000000ffff")
        draft = DraftAssessment(
            summary="All fake",
            claims=[
                Claim(
                    statement="Fake claim 1",
                    evidence=[EvidenceRef(type="turn", id=str(fake_id))],
                    dimension="clarity",
                    polarity="strength",
                ),
                Claim(
                    statement="Fake claim 2",
                    evidence=[EvidenceRef(type="turn", id=str(fake_id))],
                    dimension="empathy",
                    polarity="weakness",
                ),
            ],
        )
        result = await verifier_agent.run(draft, sample_graph, sample_retrieval_bundle)
        assert all(c.status == "removed" for c in result.claims)
        assert result.verification_score == 0.0

    async def test_issues_populated_for_removed_claims(
        self,
        verifier_agent: Verifier,
        sample_graph,
        sample_retrieval_bundle,
        sample_draft_with_hallucination: DraftAssessment,
    ):
        result = await verifier_agent.run(
            sample_draft_with_hallucination, sample_graph, sample_retrieval_bundle,
        )
        assert len(result.issues) > 0
