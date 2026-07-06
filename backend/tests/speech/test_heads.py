import random

import pytest

from app.speech.heads.asr import ASRHead
from app.speech.heads.base import BaseHead
from app.speech.heads.emotion import EmotionHead
from app.speech.heads.event import EventHead
from app.speech.heads.fluency import FluencyHead
from app.speech.heads.prosody import ProsodyHead
from app.speech.heads.stress import StressHead
from app.speech.registry import HeadRegistry
from app.speech.types import AcousticEmbedding, AcousticLabel, AudioEvent, TranscriptSegment


@pytest.fixture
def embedding() -> AcousticEmbedding:
    random.seed(42)
    vector = [random.uniform(-1.0, 1.0) for _ in range(256)]
    return AcousticEmbedding(vector=vector, dims=256, encoder_version="test@1.0")


@pytest.mark.asyncio
async def test_asr_head_returns_transcript_segments(embedding):
    head = ASRHead()
    results = await head.process(embedding)
    assert len(results) == 1
    seg = results[0]
    assert isinstance(seg, TranscriptSegment)
    assert isinstance(seg.text, str)
    assert seg.start_ms == 0
    assert seg.end_ms > 0
    assert 0 < seg.confidence <= 1.0
    assert not seg.is_partial


@pytest.mark.asyncio
async def test_emotion_head_returns_valid_labels(embedding):
    head = EmotionHead()
    results = await head.process(embedding)
    assert len(results) == 1
    label = results[0]
    assert isinstance(label, AcousticLabel)
    assert label.head == "emotion"
    assert label.label in ("neutral", "happy", "sad", "angry", "surprised")
    assert 0 < label.confidence <= 1.0


@pytest.mark.asyncio
async def test_prosody_head_returns_valid_labels(embedding):
    head = ProsodyHead()
    results = await head.process(embedding)
    assert len(results) == 1
    label = results[0]
    assert isinstance(label, AcousticLabel)
    assert label.head == "prosody"
    assert label.label in ("monotone", "varied", "expressive", "flat")
    assert 0 < label.confidence <= 1.0


@pytest.mark.asyncio
async def test_prosody_head_flat_for_constant_vector():
    emb = AcousticEmbedding(vector=[0.5] * 256, dims=256, encoder_version="test@1.0")
    head = ProsodyHead()
    results = await head.process(emb)
    assert results[0].label == "flat"


@pytest.mark.asyncio
async def test_stress_head_returns_valid_labels(embedding):
    head = StressHead()
    results = await head.process(embedding)
    assert len(results) == 1
    label = results[0]
    assert isinstance(label, AcousticLabel)
    assert label.head == "stress"
    assert label.label in ("low", "moderate", "high")
    assert 0 < label.confidence <= 1.0


@pytest.mark.asyncio
async def test_fluency_head_returns_valid_labels(embedding):
    head = FluencyHead()
    results = await head.process(embedding)
    assert len(results) == 1
    label = results[0]
    assert isinstance(label, AcousticLabel)
    assert label.head == "fluency"
    assert label.label in ("fluent", "some_disfluency", "disfluent")
    assert 0 < label.confidence <= 1.0


@pytest.mark.asyncio
async def test_event_head_returns_audio_events(embedding):
    head = EventHead()
    results = await head.process(embedding)
    for event in results:
        assert isinstance(event, AudioEvent)
        assert event.event_type in (
            "laughter", "overlap", "long_pause", "filler", "cough", "silence"
        )
        assert event.start_ms >= 0
        assert event.end_ms >= event.start_ms
        assert 0 < event.confidence <= 1.0


@pytest.mark.asyncio
async def test_event_head_returns_sorted_events(embedding):
    head = EventHead()
    results = await head.process(embedding)
    starts = [e.start_ms for e in results]
    assert starts == sorted(starts)


def test_all_heads_subclass_base():
    for cls in (ASRHead, EmotionHead, ProsodyHead, StressHead, FluencyHead, EventHead):
        assert issubclass(cls, BaseHead)


def test_head_registry_register_and_get():
    registry = HeadRegistry()
    assert "asr" in registry.list_available_heads()
    head = registry.get_head("asr")
    assert isinstance(head, ASRHead)


def test_head_registry_unknown_raises():
    registry = HeadRegistry()
    with pytest.raises(KeyError, match="foobar"):
        registry.get_head("foobar")


def test_head_registry_list():
    registry = HeadRegistry()
    available = registry.list_available_heads()
    assert "asr" in available
    assert "emotion" in available
    assert "prosody" in available
    assert "stress" in available
    assert "fluency" in available
    assert "event" in available
    assert len(available) == 6


def test_head_registry_custom_heads():
    class _TestHead(BaseHead):
        name = "test"
        async def process(self, embedding):
            return []

    registry = HeadRegistry(heads={"test": _TestHead})
    assert "test" in registry.list_available_heads()
    assert "asr" not in registry.list_available_heads()


def test_head_registry_register_rejects_non_base():
    registry = HeadRegistry()
    with pytest.raises(TypeError, match="not a subclass"):
        registry.register("bad", dict)
