import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

from app.graph.types import ConversationGraph, TurnNode


QUESTION_WORDS = {"what", "why", "how", "when", "where", "who", "which", "whose", "whom",
                  "is", "are", "was", "were", "do", "does", "did", "have", "has", "had",
                  "can", "could", "will", "would", "shall", "should", "may", "might"}

FILLER_WORDS = {"um", "uh", "like", "you know", "actually", "sort of", "kind of",
                "i mean", "you see", "well", "so", "basically", "literally",
                "right", "okay", "anyway", "honestly"}

FILLER_PATTERNS = [
    re.compile(r"\bum+\b", re.IGNORECASE),
    re.compile(r"\buh+\b", re.IGNORECASE),
    re.compile(r"\blike\b", re.IGNORECASE),
    re.compile(r"\byou know\b", re.IGNORECASE),
    re.compile(r"\bactually\b", re.IGNORECASE),
    re.compile(r"\bsort of\b", re.IGNORECASE),
    re.compile(r"\bkind of\b", re.IGNORECASE),
    re.compile(r"\bi mean\b", re.IGNORECASE),
    re.compile(r"\byou see\b", re.IGNORECASE),
]


@dataclass
class SpeakerStats:
    speaker_id: UUID
    label: str
    turn_count: int
    total_duration_ms: int
    avg_turn_duration_ms: float
    word_count: int
    interruption_count: int
    question_count: int
    filler_count: int


@dataclass
class GraphAnalysis:
    session_id: UUID
    speaker_stats: list[SpeakerStats]
    total_turns: int
    total_duration_ms: int
    turn_balance: float
    overlap_ratio: float
    interruption_count: int
    pause_stats: dict = field(default_factory=dict)
    question_count: int = 0
    filler_word_count: int = 0
    speaking_speed: dict = field(default_factory=dict)


def _word_count(text: str) -> int:
    return len(text.split())


def _is_question(turn: TurnNode) -> bool:
    text = turn.text.strip()
    if text.endswith("?"):
        return True
    first_word = text.split(maxsplit=1)[0].lower().strip(".,!?;:") if text else ""
    return first_word in QUESTION_WORDS


def _count_fillers(text: str) -> int:
    total = 0
    for pattern in FILLER_PATTERNS:
        matches = pattern.findall(text)
        total += len(matches)
    return total


def _compute_turn_balance(turns: list[TurnNode]) -> float:
    if not turns:
        return 0.0
    counts: dict[UUID, int] = defaultdict(int)
    for t in turns:
        counts[t.speaker_id] += 1

    n_speakers = len(counts)
    if n_speakers <= 1:
        return 0.0

    total = len(turns)
    entropy = 0.0
    for c in counts.values():
        p = c / total
        if p > 0:
            entropy -= p * math.log2(p)

    max_entropy = math.log2(n_speakers)
    return entropy / max_entropy if max_entropy > 0 else 0.0


def _compute_overlap_ratio(turns: list[TurnNode], total_duration_ms: int) -> float:
    if total_duration_ms <= 0 or len(turns) < 2:
        return 0.0

    timeline: dict[int, int] = defaultdict(int)
    for t in turns:
        timeline[t.start_ms] += 1
        timeline[t.end_ms] -= 1

    sorted_times = sorted(timeline)
    active = 0
    total_overlap_ms = 0

    for i in range(len(sorted_times) - 1):
        active += timeline[sorted_times[i]]
        if active > 1:
            total_overlap_ms += sorted_times[i + 1] - sorted_times[i]

    return min(total_overlap_ms / total_duration_ms, 1.0)


def _detect_interruptions(turns: list[TurnNode]) -> list[tuple[TurnNode, TurnNode]]:
    sorted_turns = sorted(turns, key=lambda t: t.start_ms)
    interruptions: list[tuple[TurnNode, TurnNode]] = []

    for i, t1 in enumerate(sorted_turns):
        for t2 in sorted_turns[i + 1:]:
            if t2.start_ms >= t1.end_ms:
                break
            if t1.speaker_id == t2.speaker_id:
                continue
            overlap_duration = t1.end_ms - t2.start_ms
            if 0 < overlap_duration < 500:
                interruptions.append((t1, t2))

    return interruptions


def _compute_pause_stats(turns: list[TurnNode]) -> dict:
    if len(turns) < 2:
        return {"total_pause_ms": 0, "avg_pause_ms": 0.0, "pause_count": 0}

    total_pause = 0
    pauses: list[int] = []
    sorted_turns = sorted(turns, key=lambda t: t.start_ms)

    for i in range(1, len(sorted_turns)):
        gap = sorted_turns[i].start_ms - sorted_turns[i - 1].end_ms
        if gap > 0:
            total_pause += gap
            pauses.append(gap)

    pause_count = len(pauses)
    avg_pause = total_pause / pause_count if pause_count > 0 else 0.0

    return {
        "total_pause_ms": total_pause,
        "avg_pause_ms": avg_pause,
        "pause_count": pause_count,
    }


def _compute_speaking_speed(
    turns: list[TurnNode],
) -> dict:
    if not turns:
        return {"overall_wpm": 0.0, "per_speaker_wpm": {}}

    total_words = sum(_word_count(t.text) for t in turns)
    total_speech_duration_ms = sum(t.end_ms - t.start_ms for t in turns)
    total_speech_minutes = total_speech_duration_ms / 60_000

    overall_wpm = total_words / total_speech_minutes if total_speech_minutes > 0 else 0.0

    speaker_words: dict[UUID, int] = defaultdict(int)
    speaker_duration_ms: dict[UUID, int] = defaultdict(int)
    for t in turns:
        speaker_words[t.speaker_id] += _word_count(t.text)
        speaker_duration_ms[t.speaker_id] += t.end_ms - t.start_ms

    per_speaker = {}
    for sid, words in speaker_words.items():
        minutes = speaker_duration_ms[sid] / 60_000
        per_speaker[str(sid)] = words / minutes if minutes > 0 else 0.0

    return {
        "overall_wpm": round(overall_wpm, 1),
        "per_speaker_wpm": per_speaker,
    }


class GraphAnalyzer:
    """Analyzes a ConversationGraph and produces quantitative metrics."""

    def analyze(self, graph: ConversationGraph) -> GraphAnalysis:
        speaker_map = {s.id: s for s in graph.speakers}
        interruptions = _detect_interruptions(graph.turns)
        total_questions = sum(1 for t in graph.turns if _is_question(t))
        total_fillers = sum(_count_fillers(t.text) for t in graph.turns)

        stats: list[SpeakerStats] = []
        per_speaker_interruptions: dict[UUID, int] = defaultdict(int)
        for sid, _ in speaker_map.items():
            per_speaker_interruptions[sid] = 0
        for _, t2 in interruptions:
            per_speaker_interruptions[t2.speaker_id] += 1

        for speaker in graph.speakers:
            speaker_turns = [t for t in graph.turns if t.speaker_id == speaker.id]
            if not speaker_turns:
                stats.append(SpeakerStats(
                    speaker_id=speaker.id,
                    label=speaker.label,
                    turn_count=0,
                    total_duration_ms=0,
                    avg_turn_duration_ms=0.0,
                    word_count=0,
                    interruption_count=0,
                    question_count=0,
                    filler_count=0,
                ))
                continue

            total_duration = sum(t.end_ms - t.start_ms for t in speaker_turns)
            avg_duration = total_duration / len(speaker_turns)
            wc = sum(_word_count(t.text) for t in speaker_turns)
            qc = sum(1 for t in speaker_turns if _is_question(t))
            fc = sum(_count_fillers(t.text) for t in speaker_turns)

            stats.append(SpeakerStats(
                speaker_id=speaker.id,
                label=speaker.label,
                turn_count=len(speaker_turns),
                total_duration_ms=total_duration,
                avg_turn_duration_ms=round(avg_duration, 1),
                word_count=wc,
                interruption_count=per_speaker_interruptions.get(speaker.id, 0),
                question_count=qc,
                filler_count=fc,
            ))

        return GraphAnalysis(
            session_id=graph.session_id,
            speaker_stats=stats,
            total_turns=graph.turn_count,
            total_duration_ms=graph.duration_ms,
            turn_balance=_compute_turn_balance(graph.turns),
            overlap_ratio=_compute_overlap_ratio(graph.turns, graph.duration_ms),
            interruption_count=len(interruptions),
            pause_stats=_compute_pause_stats(graph.turns),
            question_count=total_questions,
            filler_word_count=total_fillers,
            speaking_speed=_compute_speaking_speed(graph.turns),
        )
