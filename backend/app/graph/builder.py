import re
from uuid import UUID
from typing import Any

from app.graph.errors import SpeakerNotFoundError
from app.graph.types import (
    ConversationGraph,
    EmbeddingNode,
    EventNode,
    GraphEdge,
    SpeakerNode,
    TurnNode,
)


def _ensure_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _parse_turn(raw: dict) -> TurnNode:
    return TurnNode(
        id=_ensure_uuid(raw["id"]),
        speaker_id=_ensure_uuid(raw["speaker_id"]),
        text=raw.get("text", ""),
        start_ms=int(raw.get("start_ms", 0)),
        end_ms=int(raw.get("end_ms", 0)),
        confidence=float(raw.get("confidence", 1.0)),
        acoustic_labels=raw.get("acoustic_labels", {}),
        embedding_id=_ensure_uuid(raw["embedding_id"]) if raw.get("embedding_id") else None,
        metadata=raw.get("metadata", {}),
    )


def _parse_speaker(raw: dict) -> SpeakerNode:
    return SpeakerNode(
        id=_ensure_uuid(raw["id"]),
        label=raw.get("label", ""),
        metadata=raw.get("metadata", {}),
    )


def _parse_embedding(raw: dict) -> EmbeddingNode:
    return EmbeddingNode(
        id=_ensure_uuid(raw["id"]),
        turn_id=_ensure_uuid(raw["turn_id"]),
        vector=list(raw.get("vector", [])),
        dims=int(raw.get("dims", 0)),
        head=raw.get("head", ""),
        metadata=raw.get("metadata", {}),
    )


def _parse_event(raw: dict) -> EventNode:
    return EventNode(
        id=_ensure_uuid(raw["id"]),
        event_type=raw.get("event_type", ""),
        start_ms=int(raw.get("start_ms", 0)),
        end_ms=int(raw.get("end_ms", 0)),
        speaker_id=_ensure_uuid(raw["speaker_id"]) if raw.get("speaker_id") else None,
        confidence=float(raw.get("confidence", 1.0)),
        metadata=raw.get("metadata", {}),
    )


def _validate_speakers(
    turns: list[TurnNode],
    speakers: list[SpeakerNode],
) -> None:
    speaker_ids = {s.id for s in speakers}
    for turn in turns:
        if turn.speaker_id not in speaker_ids:
            raise SpeakerNotFoundError(
                f"Turn {turn.id} references speaker {turn.speaker_id} "
                f"which is not present in the speaker list"
            )


def _build_spoken_by(turns: list[TurnNode]) -> list[GraphEdge]:
    return [
        GraphEdge(
            source_id=t.id,
            target_id=t.speaker_id,
            relation="spoken_by",
        )
        for t in turns
    ]


def _build_followed_by(turns: list[TurnNode]) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    for i in range(1, len(turns)):
        edges.append(
            GraphEdge(
                source_id=turns[i - 1].id,
                target_id=turns[i].id,
                relation="followed_by",
                weight=float(turns[i].start_ms - turns[i - 1].end_ms),
            )
        )
    return edges


def _build_overlaps(turns: list[TurnNode]) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    sorted_turns = sorted(turns, key=lambda t: t.start_ms)
    for i, t1 in enumerate(sorted_turns):
        for t2 in sorted_turns[i + 1:]:
            if t2.start_ms >= t1.end_ms:
                break
            overlap_ms = min(t1.end_ms, t2.end_ms) - t2.start_ms
            if overlap_ms > 0:
                edges.append(
                    GraphEdge(
                        source_id=t1.id,
                        target_id=t2.id,
                        relation="overlaps_with",
                        weight=float(overlap_ms),
                    )
                )
    return edges


def _build_has_embedding(
    turns: list[TurnNode],
    embeddings: list[EmbeddingNode],
) -> list[GraphEdge]:
    turn_by_id = {t.id: t for t in turns}
    edges: list[GraphEdge] = []
    for emb in embeddings:
        if emb.turn_id in turn_by_id:
            edges.append(
                GraphEdge(
                    source_id=emb.turn_id,
                    target_id=emb.id,
                    relation="has_embedding",
                )
            )
    return edges


def _build_has_event(
    turns: list[TurnNode],
    events: list[EventNode],
) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    for event in events:
        for turn in turns:
            if event.start_ms >= turn.start_ms and event.end_ms <= turn.end_ms:
                edges.append(
                    GraphEdge(
                        source_id=turn.id,
                        target_id=event.id,
                        relation="has_event",
                    )
                )
                break
    return edges


def _build_responds_to(turns: list[TurnNode], speaker_labels: dict[UUID, str]) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    for i, turn in enumerate(turns):
        text = turn.text.lstrip()
        mention_match = re.match(r"^@(\S+)", text)
        if mention_match:
            mentioned = mention_match.group(1).lower()
            for label_id, label in speaker_labels.items():
                if label.lower() == mentioned:
                    for j in range(i - 1, -1, -1):
                        if turns[j].speaker_id == label_id:
                            edges.append(
                                GraphEdge(
                                    source_id=turn.id,
                                    target_id=turns[j].id,
                                    relation="responds_to",
                                )
                            )
                            break
                    break
        if re.match(r"^re:\s", text, re.IGNORECASE):
            if i > 0:
                edges.append(
                    GraphEdge(
                        source_id=turns[i].id,
                        target_id=turns[i - 1].id,
                        relation="responds_to",
                    )
                )
    return edges


class GraphBuilder:
    """Builds a ConversationGraph from raw entity dictionaries."""

    def build_from_entities(
        self,
        session_id: UUID,
        turns: list[dict],
        speakers: list[dict],
        embeddings: list[dict] | None = None,
        events: list[dict] | None = None,
    ) -> ConversationGraph:
        parsed_turns = [_parse_turn(t) for t in turns]
        parsed_speakers = [_parse_speaker(s) for s in speakers]
        parsed_embeddings = [_parse_embedding(e) for e in (embeddings or [])]
        parsed_events = [_parse_event(e) for e in (events or [])]

        _validate_speakers(parsed_turns, parsed_speakers)

        edges: list[GraphEdge] = []
        edges.extend(_build_spoken_by(parsed_turns))
        edges.extend(_build_followed_by(parsed_turns))
        edges.extend(_build_overlaps(parsed_turns))
        edges.extend(_build_has_embedding(parsed_turns, parsed_embeddings))
        edges.extend(_build_has_event(parsed_turns, parsed_events))

        speaker_labels = {s.id: s.label for s in parsed_speakers}
        edges.extend(_build_responds_to(parsed_turns, speaker_labels))

        return ConversationGraph(
            session_id=session_id,
            speakers=parsed_speakers,
            turns=parsed_turns,
            embeddings=parsed_embeddings,
            events=parsed_events,
            edges=edges,
        )
