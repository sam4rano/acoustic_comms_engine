from uuid import UUID, uuid4

import pytest

from app.graph.builder import GraphBuilder
from app.graph.errors import SpeakerNotFoundError
from app.graph.types import ConversationGraph


class TestGraphBuilder:
    """Tests for GraphBuilder.build_from_entities."""

    def test_build_from_valid_data(self, builder: GraphBuilder) -> None:
        session_id = uuid4()
        speaker_id = uuid4()
        speakers = [{"id": speaker_id, "label": "Alice"}]
        turns = [
            {"id": uuid4(), "speaker_id": speaker_id, "text": "Hello",
             "start_ms": 0, "end_ms": 1000, "confidence": 0.95},
            {"id": uuid4(), "speaker_id": speaker_id, "text": "World",
             "start_ms": 1500, "end_ms": 2500, "confidence": 0.90},
        ]

        graph = builder.build_from_entities(session_id, turns, speakers)

        assert graph.session_id == session_id
        assert len(graph.speakers) == 1
        assert len(graph.turns) == 2

    def test_sequential_turns_get_followed_by_edges(self, builder: GraphBuilder) -> None:
        session_id = uuid4()
        sid = uuid4()
        speakers = [{"id": sid, "label": "A"}]
        t1_id, t2_id, t3_id = uuid4(), uuid4(), uuid4()
        turns = [
            {"id": t1_id, "speaker_id": sid, "text": "First",
             "start_ms": 0, "end_ms": 1000, "confidence": 1.0},
            {"id": t2_id, "speaker_id": sid, "text": "Second",
             "start_ms": 1500, "end_ms": 2500, "confidence": 1.0},
            {"id": t3_id, "speaker_id": sid, "text": "Third",
             "start_ms": 3000, "end_ms": 4000, "confidence": 1.0},
        ]

        graph = builder.build_from_entities(session_id, turns, speakers)

        followed_edges = [e for e in graph.edges if e.relation == "followed_by"]
        assert len(followed_edges) == 2
        assert followed_edges[0].source_id == t1_id
        assert followed_edges[0].target_id == t2_id
        assert followed_edges[1].source_id == t2_id
        assert followed_edges[1].target_id == t3_id

    def test_overlapping_turns_get_overlaps_edges(self, builder: GraphBuilder) -> None:
        session_id = uuid4()
        sid_a, sid_b = uuid4(), uuid4()
        speakers = [
            {"id": sid_a, "label": "A"},
            {"id": sid_b, "label": "B"},
        ]
        t1_id, t2_id = uuid4(), uuid4()
        turns = [
            {"id": t1_id, "speaker_id": sid_a, "text": "Long turn",
             "start_ms": 0, "end_ms": 3000, "confidence": 1.0},
            {"id": t2_id, "speaker_id": sid_b, "text": "Interrupting",
             "start_ms": 2000, "end_ms": 4000, "confidence": 1.0},
        ]

        graph = builder.build_from_entities(session_id, turns, speakers)

        overlap_edges = [e for e in graph.edges if e.relation == "overlaps_with"]
        assert len(overlap_edges) == 1
        assert overlap_edges[0].source_id == t1_id
        assert overlap_edges[0].target_id == t2_id
        assert overlap_edges[0].weight == 1000.0

    def test_empty_input_returns_graph_with_no_nodes(self, builder: GraphBuilder) -> None:
        session_id = uuid4()
        graph = builder.build_from_entities(session_id, [], [])

        assert isinstance(graph, ConversationGraph)
        assert graph.session_id == session_id
        assert len(graph.speakers) == 0
        assert len(graph.turns) == 0
        assert len(graph.embeddings) == 0
        assert len(graph.events) == 0
        assert len(graph.edges) == 0

    def test_missing_speaker_raises_error(self, builder: GraphBuilder) -> None:
        session_id = uuid4()
        sid_a = uuid4()
        sid_b = uuid4()
        speakers = [{"id": sid_a, "label": "Alice"}]
        turns = [
            {"id": uuid4(), "speaker_id": sid_b, "text": "Who am I?",
             "start_ms": 0, "end_ms": 1000, "confidence": 1.0},
        ]

        with pytest.raises(SpeakerNotFoundError, match=str(sid_b)):
            builder.build_from_entities(session_id, turns, speakers)

    def test_embedding_attachment(self, builder: GraphBuilder) -> None:
        session_id = uuid4()
        sid = uuid4()
        t_id = uuid4()
        emb_id = uuid4()
        speakers = [{"id": sid, "label": "A"}]
        turns = [
            {"id": t_id, "speaker_id": sid, "text": "Hello",
             "start_ms": 0, "end_ms": 1000, "confidence": 1.0},
        ]
        embeddings = [
            {"id": emb_id, "turn_id": t_id, "vector": [0.1, 0.2],
             "dims": 2, "head": "emotion"},
        ]

        graph = builder.build_from_entities(session_id, turns, speakers, embeddings)

        emb_edges = [e for e in graph.edges if e.relation == "has_embedding"]
        assert len(emb_edges) == 1
        assert emb_edges[0].source_id == t_id
        assert emb_edges[0].target_id == emb_id

    def test_spoken_by_edges(self, builder: GraphBuilder) -> None:
        session_id = uuid4()
        sid = uuid4()
        t_id = uuid4()
        speakers = [{"id": sid, "label": "A"}]
        turns = [
            {"id": t_id, "speaker_id": sid, "text": "Hello",
             "start_ms": 0, "end_ms": 1000, "confidence": 1.0},
        ]

        graph = builder.build_from_entities(session_id, turns, speakers)

        spoken_edges = [e for e in graph.edges if e.relation == "spoken_by"]
        assert len(spoken_edges) == 1
        assert spoken_edges[0].source_id == t_id
        assert spoken_edges[0].target_id == sid

    def test_event_attachment(self, builder: GraphBuilder) -> None:
        session_id = uuid4()
        sid = uuid4()
        t_id = uuid4()
        ev_id = uuid4()
        speakers = [{"id": sid, "label": "A"}]
        turns = [
            {"id": t_id, "speaker_id": sid, "text": "Hello there",
             "start_ms": 0, "end_ms": 2000, "confidence": 1.0},
        ]
        events = [
            {"id": ev_id, "event_type": "laughter", "start_ms": 500, "end_ms": 1000,
             "speaker_id": sid},
        ]

        graph = builder.build_from_entities(session_id, turns, speakers, events=events)

        event_edges = [e for e in graph.edges if e.relation == "has_event"]
        assert len(event_edges) == 1
        assert event_edges[0].source_id == t_id
        assert event_edges[0].target_id == ev_id

    def test_responds_to_mention(self, builder: GraphBuilder) -> None:
        session_id = uuid4()
        sid_a, sid_b = uuid4(), uuid4()
        speakers = [
            {"id": sid_a, "label": "Alice"},
            {"id": sid_b, "label": "Bob"},
        ]
        turns = [
            {"id": uuid4(), "speaker_id": sid_a, "text": "What do you think?",
             "start_ms": 0, "end_ms": 1000, "confidence": 1.0},
            {"id": uuid4(), "speaker_id": sid_b, "text": "@Alice I agree!",
             "start_ms": 1500, "end_ms": 2500, "confidence": 1.0},
        ]

        graph = builder.build_from_entities(session_id, turns, speakers)

        respond_edges = [e for e in graph.edges if e.relation == "responds_to"]
        assert len(respond_edges) == 1
        assert respond_edges[0].source_id == turns[1]["id"]
        assert respond_edges[0].target_id == turns[0]["id"]

    def test_uuid_string_inputs(self, builder: GraphBuilder) -> None:
        session_id = uuid4()
        sid = uuid4()
        speakers = [{"id": str(sid), "label": "Alice"}]
        turns = [
            {"id": str(uuid4()), "speaker_id": str(sid), "text": "Test",
             "start_ms": 0, "end_ms": 500, "confidence": 0.9},
        ]

        graph = builder.build_from_entities(session_id, turns, speakers)

        assert len(graph.turns) == 1
        assert len(graph.speakers) == 1
