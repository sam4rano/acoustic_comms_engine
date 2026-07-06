from uuid import UUID

import networkx as nx

from app.graph.errors import GraphTraversalError, SpeakerNotFoundError
from app.graph.types import ConversationGraph, TurnNode


class GraphTraverser:
    """Traverses a ConversationGraph using NetworkX for graph algorithms."""

    def __init__(self) -> None:
        self._nx: nx.DiGraph | None = None
        self._graph: ConversationGraph | None = None

    def build_nx_graph(self, graph: ConversationGraph) -> nx.DiGraph:
        G: nx.DiGraph = nx.DiGraph()

        for speaker in graph.speakers:
            G.add_node(speaker.id, type="speaker", label=speaker.label)

        for turn in graph.turns:
            G.add_node(turn.id, type="turn", speaker_id=turn.speaker_id, text=turn.text,
                       start_ms=turn.start_ms, end_ms=turn.end_ms)

        for emb in graph.embeddings:
            G.add_node(emb.id, type="embedding", head=emb.head, dims=emb.dims)

        for event in graph.events:
            G.add_node(event.id, type="event", event_type=event.event_type,
                       start_ms=event.start_ms, end_ms=event.end_ms)

        for edge in graph.edges:
            G.add_edge(edge.source_id, edge.target_id,
                       relation=edge.relation, weight=edge.weight,
                       **(edge.metadata or {}))

        self._nx = G
        self._graph = graph
        return G

    def _ensure_nx(self, graph: ConversationGraph) -> nx.DiGraph:
        if self._nx is None or self._graph != graph:
            return self.build_nx_graph(graph)
        return self._nx

    def _get_speaker_id_by_label(self, speakers: list, label: str) -> UUID | None:
        for s in speakers:
            if s.label == label:
                return s.id
        return None

    def get_turn_sequence(self, graph: ConversationGraph, speaker_id: UUID) -> list[TurnNode]:
        turns = [t for t in graph.turns if t.speaker_id == speaker_id]
        turns.sort(key=lambda t: t.start_ms)
        return turns

    def get_response_chain(self, graph: ConversationGraph, turn_id: UUID, depth: int = 3) -> list[TurnNode]:
        G = self._ensure_nx(graph)

        turn_by_id = {t.id: t for t in graph.turns}

        if turn_id not in turn_by_id:
            return []

        visited: set[UUID] = {turn_id}
        queue: list[tuple[UUID, int]] = [(turn_id, 0)]
        results: list[TurnNode] = []

        while queue:
            current, d = queue.pop(0)
            if d > 0 and current in turn_by_id:
                results.append(turn_by_id[current])
            if d >= depth:
                continue

            for _, neighbor, edge_data in G.edges(current, data=True):
                relation = edge_data.get("relation", "")
                if relation in ("responds_to", "followed_by"):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, d + 1))

            for neighbor, _, edge_data in G.in_edges(current, data=True):
                relation = edge_data.get("relation", "")
                if relation in ("responds_to", "followed_by"):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, d + 1))

        return results

    def find_overlapping_turns(self, graph: ConversationGraph, turn_id: UUID) -> list[TurnNode]:
        G = self._ensure_nx(graph)
        turn_by_id = {t.id: t for t in graph.turns}

        if turn_id not in turn_by_id:
            raise GraphTraversalError(f"Turn {turn_id} not found in graph")

        neighbor_ids = set()
        for _, neighbor, data in G.edges(turn_id, data=True):
            if data.get("relation") == "overlaps_with" and neighbor in turn_by_id:
                neighbor_ids.add(neighbor)
        for neighbor, _, data in G.in_edges(turn_id, data=True):
            if data.get("relation") == "overlaps_with" and neighbor in turn_by_id:
                neighbor_ids.add(neighbor)

        return [turn_by_id[nid] for nid in sorted(neighbor_ids, key=lambda n: turn_by_id[n].start_ms)]

    def get_speaker_turns(self, graph: ConversationGraph, speaker_id: UUID) -> list[TurnNode]:
        if not any(s.id == speaker_id for s in graph.speakers):
            raise SpeakerNotFoundError(f"Speaker {speaker_id} not found in graph")
        turns = [t for t in graph.turns if t.speaker_id == speaker_id]
        turns.sort(key=lambda t: t.start_ms)
        return turns

    def find_paths_between(
        self, graph: ConversationGraph, speaker_a: UUID, speaker_b: UUID
    ) -> list[list[TurnNode]]:
        G = self._ensure_nx(graph)
        turn_by_id = {t.id: t for t in graph.turns}

        turns_a = [t.id for t in graph.turns if t.speaker_id == speaker_a]
        turns_b = [t.id for t in graph.turns if t.speaker_id == speaker_b]

        paths: list[list[TurnNode]] = []
        for ta in turns_a:
            for tb in turns_b:
                if ta == tb:
                    continue
                try:
                    raw_paths = list(nx.all_simple_paths(G, source=ta, target=tb, cutoff=5))
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                for raw in raw_paths:
                    node_path = [turn_by_id[nid] for nid in raw if nid in turn_by_id]
                    if node_path:
                        paths.append(node_path)

        paths.sort(key=len)
        return paths
