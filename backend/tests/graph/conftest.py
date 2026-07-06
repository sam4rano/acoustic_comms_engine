from uuid import UUID, uuid4

import pytest

from app.graph.builder import GraphBuilder
from app.graph.types import ConversationGraph


@pytest.fixture
def builder() -> GraphBuilder:
    return GraphBuilder()


_SPEAKER_A_ID = UUID("11111111-1111-1111-1111-111111111111")
_SPEAKER_B_ID = UUID("22222222-2222-2222-2222-222222222222")
_SPEAKER_C_ID = UUID("33333333-3333-3333-3333-333333333333")
_SESSION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def sample_graph(builder: GraphBuilder) -> ConversationGraph:
    """2 speakers, 5 turns, 2 embeddings, 2 events, some overlap."""
    session_id = _SESSION_ID
    speakers = [
        {"id": _SPEAKER_A_ID, "label": "Alice"},
        {"id": _SPEAKER_B_ID, "label": "Bob"},
    ]
    turns = [
        {"id": uuid4(), "speaker_id": _SPEAKER_A_ID, "text": "Hello Bob, how are you?",
         "start_ms": 0, "end_ms": 1500, "confidence": 0.95},
        {"id": uuid4(), "speaker_id": _SPEAKER_B_ID, "text": "I am doing great thanks!",
         "start_ms": 1600, "end_ms": 3000, "confidence": 0.90},
        {"id": uuid4(), "speaker_id": _SPEAKER_A_ID, "text": "What do you think about the project?",
         "start_ms": 3100, "end_ms": 4500, "confidence": 0.92},
        {"id": uuid4(), "speaker_id": _SPEAKER_B_ID, "text": "Yeah it is coming along nicely.",
         "start_ms": 4300, "end_ms": 5500, "confidence": 0.88},
        {"id": uuid4(), "speaker_id": _SPEAKER_A_ID, "text": "Great! Let me know if you need help.",
         "start_ms": 5600, "end_ms": 7000, "confidence": 0.94},
    ]
    embeddings = [
        {"id": uuid4(), "turn_id": turns[0]["id"], "vector": [0.1, 0.2, 0.3],
         "dims": 3, "head": "emotion"},
        {"id": uuid4(), "turn_id": turns[2]["id"], "vector": [0.4, 0.5, 0.6],
         "dims": 3, "head": "prosody"},
    ]
    events = [
        {"id": uuid4(), "event_type": "laughter", "start_ms": 300, "end_ms": 800,
         "speaker_id": _SPEAKER_A_ID, "confidence": 0.95},
        {"id": uuid4(), "event_type": "filler", "start_ms": 4400, "end_ms": 4500,
         "speaker_id": _SPEAKER_B_ID, "confidence": 0.80},
    ]
    return builder.build_from_entities(session_id, turns, speakers, embeddings, events)


@pytest.fixture
def single_speaker_graph(builder: GraphBuilder) -> ConversationGraph:
    """1 speaker, 3 turns (monologue scenario)."""
    speakers = [
        {"id": _SPEAKER_A_ID, "label": "Alice"},
    ]
    turns = [
        {"id": uuid4(), "speaker_id": _SPEAKER_A_ID,
         "text": "First point I want to make is about the timeline.",
         "start_ms": 0, "end_ms": 3000, "confidence": 0.95},
        {"id": uuid4(), "speaker_id": _SPEAKER_A_ID,
         "text": "Second, we need to consider the budget constraints.",
         "start_ms": 3500, "end_ms": 6000, "confidence": 0.92},
        {"id": uuid4(), "speaker_id": _SPEAKER_A_ID,
         "text": "And finally, the team should focus on delivery quality.",
         "start_ms": 6500, "end_ms": 9000, "confidence": 0.90},
    ]
    return builder.build_from_entities(_SESSION_ID, turns, speakers)


@pytest.fixture
def empty_graph() -> ConversationGraph:
    """session_id only, no entities."""
    return ConversationGraph(
        session_id=_SESSION_ID,
        speakers=[],
        turns=[],
        embeddings=[],
        events=[],
        edges=[],
    )


@pytest.fixture
def complex_graph(builder: GraphBuilder) -> ConversationGraph:
    """3 speakers, 12 turns, interruptions, questions, filler words."""
    sid = _SESSION_ID
    speakers = [
        {"id": _SPEAKER_A_ID, "label": "Alice"},
        {"id": _SPEAKER_B_ID, "label": "Bob"},
        {"id": _SPEAKER_C_ID, "label": "Charlie"},
    ]
    turns = [
        {"id": uuid4(), "speaker_id": _SPEAKER_A_ID,
         "text": "Good morning everyone, let us start the meeting.",
         "start_ms": 0, "end_ms": 2000, "confidence": 0.95},
        {"id": uuid4(), "speaker_id": _SPEAKER_B_ID,
         "text": "Morning Alice! Do we have the Q3 numbers?",
         "start_ms": 2100, "end_ms": 3500, "confidence": 0.92},
        {"id": uuid4(), "speaker_id": _SPEAKER_C_ID,
         "text": "Yeah I have them here, actually I printed them yesterday.",
         "start_ms": 3400, "end_ms": 5000, "confidence": 0.88},
        {"id": uuid4(), "speaker_id": _SPEAKER_A_ID,
         "text": "Great, um what do they look like?",
         "start_ms": 5100, "end_ms": 6200, "confidence": 0.94},
        {"id": uuid4(), "speaker_id": _SPEAKER_C_ID,
         "text": "Well revenue is up like 15 percent sort of across all segments.",
         "start_ms": 6300, "end_ms": 8000, "confidence": 0.90},
        {"id": uuid4(), "speaker_id": _SPEAKER_B_ID,
         "text": "Wait that seems low, I expected closer to ... actually 20 percent.",
         "start_ms": 7900, "end_ms": 9500, "confidence": 0.85},
        {"id": uuid4(), "speaker_id": _SPEAKER_A_ID,
         "text": "Bob, can you share your reasoning?",
         "start_ms": 9600, "end_ms": 10800, "confidence": 0.93},
        {"id": uuid4(), "speaker_id": _SPEAKER_B_ID,
         "text": "Sure, um based on the pipeline we discussed last quarter, you know.",
         "start_ms": 10900, "end_ms": 12500, "confidence": 0.91},
        {"id": uuid4(), "speaker_id": _SPEAKER_A_ID,
         "text": "Okay I see. What do you think Charlie?",
         "start_ms": 12600, "end_ms": 13800, "confidence": 0.95},
        {"id": uuid4(), "speaker_id": _SPEAKER_C_ID,
         "text": "I agree with Bob honestly, we should have hit 20 percent.",
         "start_ms": 13900, "end_ms": 15500, "confidence": 0.89},
        {"id": uuid4(), "speaker_id": _SPEAKER_A_ID,
         "text": "Alright let us dig into the details then. Where is the gap?",
         "start_ms": 15600, "end_ms": 17200, "confidence": 0.94},
        {"id": uuid4(), "speaker_id": _SPEAKER_B_ID,
         "text": "I think uh the issue is in the EMEA region, like their adoption rate.",
         "start_ms": 17100, "end_ms": 18800, "confidence": 0.90},
    ]
    return builder.build_from_entities(sid, turns, speakers)
