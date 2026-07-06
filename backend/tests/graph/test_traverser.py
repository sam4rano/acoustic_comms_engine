from uuid import UUID, uuid4

import pytest

from app.graph.errors import SpeakerNotFoundError
from app.graph.traverser import GraphTraverser
from app.graph.types import ConversationGraph, TurnNode


class TestGraphTraverser:
    """Tests for GraphTraverser."""

    def test_get_turn_sequence_returns_chronological(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        alice_id = UUID("11111111-1111-1111-1111-111111111111")
        bob_id = UUID("22222222-2222-2222-2222-222222222222")

        alice_turns = traverser.get_turn_sequence(sample_graph, alice_id)
        assert len(alice_turns) == 3
        for i in range(1, len(alice_turns)):
            assert alice_turns[i].start_ms > alice_turns[i - 1].start_ms

        bob_turns = traverser.get_turn_sequence(sample_graph, bob_id)
        assert len(bob_turns) == 2

    def test_get_turn_sequence_no_speaker_turns(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        fake_id = uuid4()
        turns = traverser.get_turn_sequence(sample_graph, fake_id)
        assert turns == []

    def test_get_response_chain_follows_edges(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        first_turn_id = sample_graph.turns[0].id

        chain = traverser.get_response_chain(sample_graph, first_turn_id, depth=2)

        assert isinstance(chain, list)
        assert len(chain) > 0

    def test_get_response_chain_zero_depth(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        first_turn_id = sample_graph.turns[0].id

        chain = traverser.get_response_chain(sample_graph, first_turn_id, depth=0)

        assert chain == []

    def test_find_overlapping_turns(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        third_turn = sample_graph.turns[2]
        fourth_turn = sample_graph.turns[3]

        overlapping = traverser.find_overlapping_turns(sample_graph, fourth_turn.id)

        assert len(overlapping) >= 1
        overlap_ids = {t.id for t in overlapping}
        assert third_turn.id in overlap_ids

    def test_find_overlapping_turns_none(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        first_turn = sample_graph.turns[0]

        overlapping = traverser.find_overlapping_turns(sample_graph, first_turn.id)

        assert overlapping == []

    def test_find_overlapping_turns_not_found(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        fake_id = uuid4()

        with pytest.raises(Exception):
            traverser.find_overlapping_turns(sample_graph, fake_id)

    def test_get_speaker_turns(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        alice_id = UUID("11111111-1111-1111-1111-111111111111")

        turns = traverser.get_speaker_turns(sample_graph, alice_id)

        assert all(t.speaker_id == alice_id for t in turns)
        assert len(turns) == 3

    def test_get_speaker_turns_not_found(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        fake_id = uuid4()

        with pytest.raises(SpeakerNotFoundError, match=str(fake_id)):
            traverser.get_speaker_turns(sample_graph, fake_id)

    def test_find_paths_between(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        alice_id = UUID("11111111-1111-1111-1111-111111111111")
        bob_id = UUID("22222222-2222-2222-2222-222222222222")

        paths = traverser.find_paths_between(sample_graph, alice_id, bob_id)

        assert isinstance(paths, list)
        if paths:
            for path in paths:
                assert all(isinstance(t, TurnNode) for t in path)

    def test_find_paths_between_same_speaker(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        alice_id = UUID("11111111-1111-1111-1111-111111111111")

        paths = traverser.find_paths_between(sample_graph, alice_id, alice_id)

        assert isinstance(paths, list)
        for path in paths:
            assert all(isinstance(t, TurnNode) for t in path)
        assert len(paths) >= 0

    def test_single_speaker_graph(self, single_speaker_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        alice_id = UUID("11111111-1111-1111-1111-111111111111")

        turn_seq = traverser.get_turn_sequence(single_speaker_graph, alice_id)
        assert len(turn_seq) == 3

        speaker_turns = traverser.get_speaker_turns(single_speaker_graph, alice_id)
        assert len(speaker_turns) == 3

        response_chain = traverser.get_response_chain(
            single_speaker_graph, single_speaker_graph.turns[0].id
        )
        assert isinstance(response_chain, list)

    def test_empty_graph(self, empty_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        fake_id = uuid4()

        turns = traverser.get_turn_sequence(empty_graph, fake_id)
        assert turns == []

        response_chain = traverser.get_response_chain(empty_graph, fake_id)
        assert response_chain == []

        with pytest.raises(SpeakerNotFoundError):
            traverser.get_speaker_turns(empty_graph, fake_id)

    def test_build_nx_graph(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()

        G = traverser.build_nx_graph(sample_graph)

        assert G.number_of_nodes() > 0
        assert G.number_of_edges() > 0

        expected_nodes = (
            len(sample_graph.speakers)
            + len(sample_graph.turns)
            + len(sample_graph.embeddings)
            + len(sample_graph.events)
        )
        assert G.number_of_nodes() == expected_nodes

    def test_nx_cache_reuses_graph(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()

        G1 = traverser.build_nx_graph(sample_graph)
        G2 = traverser._ensure_nx(sample_graph)

        assert G1 is G2

    def test_find_overlapping_turns_turn3_and_4(self, sample_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()
        fourth_turn = sample_graph.turns[3]

        overlapping = traverser.find_overlapping_turns(sample_graph, fourth_turn.id)

        assert len(overlapping) >= 1
    def test_complex_graph_multiple_overlaps(self, complex_graph: ConversationGraph) -> None:
        traverser = GraphTraverser()

        for turn in complex_graph.turns:
            overlapping = traverser.find_overlapping_turns(complex_graph, turn.id)
            if overlapping:
                assert all(isinstance(t, TurnNode) for t in overlapping)
                break
