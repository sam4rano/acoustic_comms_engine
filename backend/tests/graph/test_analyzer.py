import pytest

from app.graph.analyzer import GraphAnalyzer
from app.graph.types import ConversationGraph


class TestGraphAnalyzer:
    """Tests for GraphAnalyzer."""

    def test_speaker_stats_computed_correctly(self, sample_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(sample_graph)

        assert len(analysis.speaker_stats) == 2

        alice_stats = next(s for s in analysis.speaker_stats if s.label == "Alice")
        bob_stats = next(s for s in analysis.speaker_stats if s.label == "Bob")

        assert alice_stats.turn_count == 3
        assert bob_stats.turn_count == 2

        assert alice_stats.word_count > 0
        assert bob_stats.word_count > 0

        assert alice_stats.total_duration_ms > 0
        assert bob_stats.total_duration_ms > 0

        assert alice_stats.avg_turn_duration_ms > 0
        assert bob_stats.avg_turn_duration_ms > 0

    def test_speaker_stats_question_count(self, sample_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(sample_graph)

        alice_stats = next(s for s in analysis.speaker_stats if s.label == "Alice")
        bob_stats = next(s for s in analysis.speaker_stats if s.label == "Bob")

        assert alice_stats.question_count >= 2
        assert bob_stats.question_count == 0

    def test_turn_balance_multi_speaker(self, sample_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(sample_graph)

        assert 0 < analysis.turn_balance <= 1.0

    def test_turn_balance_single_speaker_zero(self, single_speaker_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(single_speaker_graph)

        assert analysis.turn_balance == 0.0

    def test_turn_balance_perfect_balance(self) -> None:
        from uuid import uuid4
        from app.graph.types import ConversationGraph, SpeakerNode, TurnNode

        sid = uuid4()
        sid_a = uuid4()
        sid_b = uuid4()
        graph = ConversationGraph(
            session_id=sid,
            speakers=[
                SpeakerNode(id=sid_a, label="A"),
                SpeakerNode(id=sid_b, label="B"),
            ],
            turns=[
                TurnNode(id=uuid4(), speaker_id=sid_a, text="Hi",
                         start_ms=0, end_ms=500, confidence=1.0),
                TurnNode(id=uuid4(), speaker_id=sid_b, text="Hello",
                         start_ms=600, end_ms=1000, confidence=1.0),
            ],
            embeddings=[],
            events=[],
            edges=[],
        )
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(graph)

        assert analysis.turn_balance == pytest.approx(1.0)

    def test_overlap_detection(self, sample_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(sample_graph)

        assert analysis.overlap_ratio > 0

    def test_interruption_detection(self, complex_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(complex_graph)

        assert analysis.interruption_count >= 1

    def test_question_detection(self, complex_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(complex_graph)

        assert analysis.question_count >= 2

    def test_filler_word_counting(self, complex_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(complex_graph)

        assert analysis.filler_word_count >= 5

    def test_filler_word_counting_single_speaker(self, single_speaker_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(single_speaker_graph)

        assert analysis.filler_word_count == 0

    def test_speaking_speed_wpm(self, sample_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(sample_graph)

        assert analysis.speaking_speed["overall_wpm"] > 0
        assert len(analysis.speaking_speed["per_speaker_wpm"]) == 2

    def test_single_speaker_analysis(self, single_speaker_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(single_speaker_graph)

        assert analysis.total_turns == 3
        assert len(analysis.speaker_stats) == 1
        assert analysis.overlap_ratio == 0.0
        assert analysis.interruption_count == 0
        assert analysis.speaking_speed["overall_wpm"] > 0

    def test_total_turns_and_duration(self, sample_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(sample_graph)

        assert analysis.total_turns == 5
        assert analysis.total_duration_ms > 0
        assert analysis.session_id == sample_graph.session_id

    def test_empty_graph_returns_defaults(self, empty_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(empty_graph)

        assert analysis.total_turns == 0
        assert analysis.total_duration_ms == 0
        assert analysis.turn_balance == 0.0
        assert analysis.overlap_ratio == 0.0
        assert analysis.interruption_count == 0
        assert analysis.question_count == 0
        assert analysis.filler_word_count == 0
        assert analysis.speaker_stats == []
        assert analysis.speaking_speed["overall_wpm"] == 0.0

    def test_pause_stats(self, sample_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(sample_graph)

        assert analysis.pause_stats["total_pause_ms"] > 0
        assert analysis.pause_stats["pause_count"] >= 1
        assert analysis.pause_stats["avg_pause_ms"] > 0

    def test_no_pauses_in_empty_graph(self, empty_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(empty_graph)

        assert analysis.pause_stats["total_pause_ms"] == 0
        assert analysis.pause_stats["pause_count"] == 0
        assert analysis.pause_stats["avg_pause_ms"] == 0.0

    def test_complex_graph_full_analysis(self, complex_graph: ConversationGraph) -> None:
        analyzer = GraphAnalyzer()
        analysis = analyzer.analyze(complex_graph)

        assert analysis.total_turns == 12
        assert len(analysis.speaker_stats) == 3
        assert analysis.turn_balance > 0
        assert analysis.interruption_count >= 1
        assert analysis.question_count >= 2
        assert analysis.filler_word_count >= 8
        assert analysis.speaking_speed["overall_wpm"] > 0

        for stat in analysis.speaker_stats:
            assert stat.turn_count > 0
            assert stat.word_count > 0
