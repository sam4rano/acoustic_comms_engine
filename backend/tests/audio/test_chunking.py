import pytest
import torch

from app.audio.chunking import Chunker
from app.audio.types import VADSegment


class TestChunker:
    def test_chunking_produces_correct_number_of_chunks(self, sample_waveform):
        """1 second at 16 kHz, 30 ms chunks with 10 ms overlap → ~49 chunks."""
        wav, sr = sample_waveform
        chunks = Chunker.chunk(wav, chunk_size_ms=30, overlap_ms=10, sample_rate=sr)
        # hop = 20 ms, so 1000/20 ≈ 50 chunks
        assert len(chunks) == 50
        for c in chunks:
            assert c.waveform.size(-1) == int(sr * 30 / 1000)

    def test_chunk_timestamps_are_contiguous(self, sample_waveform):
        """Chunk start_ms/end_ms should advance by hop size."""
        wav, sr = sample_waveform
        chunks = Chunker.chunk(wav, chunk_size_ms=30, overlap_ms=10, sample_rate=sr)
        for i in range(1, len(chunks)):
            expected_start = chunks[i - 1].start_ms + 20  # hop = 20 ms
            assert chunks[i].start_ms == expected_start, f"Chunk {i} start mismatch"

    def test_overlap_produces_correct_overlap_ms(self, sample_waveform):
        """Chunk N should share overlap_ms with Chunk N+1."""
        wav, sr = sample_waveform
        overlap_ms = 10
        chunk_size_ms = 30
        chunks = Chunker.chunk(
            wav, chunk_size_ms=chunk_size_ms, overlap_ms=overlap_ms, sample_rate=sr
        )
        for i in range(len(chunks) - 1):
            overlap = chunks[i].end_ms - chunks[i + 1].start_ms
            assert overlap == overlap_ms, f"Overlap at index {i} should be {overlap_ms}"

    def test_trailing_partial_chunk_padded(self):
        """A waveform that doesn't divide evenly should pad the last chunk."""
        sr = 16000
        # 50 ms at 16kHz = 800 samples
        # chunk_size=30ms (480 samples), hop=30-10=20ms (320 samples)
        # Chunk 0: samples 0→480  (start=0,   end=30)
        # Chunk 1: samples 320→800 (start=20,  end=50) — fits exactly (480 samples)
        # Chunk 2: samples 640→800 (start=40,  end=70) — only 160 samples, padded to 480
        wav = torch.randn(1, 800)
        chunks = Chunker.chunk(wav, chunk_size_ms=30, overlap_ms=10, sample_rate=sr)
        assert len(chunks) == 3
        # Every chunk should be exactly 30 ms
        expected_size = int(sr * 30 / 1000)  # 480
        for c in chunks:
            assert c.waveform.size(-1) == expected_size
        # Middle chunk covers actual audio (20–50 ms)
        assert chunks[1].start_ms == 20
        assert chunks[1].end_ms == 50
        # Last chunk is padded: start=40ms, padded end=70ms
        assert chunks[2].start_ms == 40
        assert chunks[2].end_ms == 70

    def test_empty_input_returns_empty_list(self):
        """Empty waveform should return [].

        This test validates that chunk() handles the edge case of
        an empty tensor gracefully.
        """
        wav = torch.empty(1, 0)
        chunks = Chunker.chunk(wav, sample_rate=16000)
        assert chunks == []

    def test_wrong_shape_raises_value_error(self):
        """Non-[1, T] input should raise ValueError."""
        wav = torch.randn(2, 16000)
        with pytest.raises(ValueError, match="Expected shape"):
            Chunker.chunk(wav, sample_rate=16000)

    def test_chunk_with_vad_segments(self, sample_waveform):
        """VAD segments should be propagated to overlapping chunks."""
        wav, sr = sample_waveform
        vad_segments = [
            VADSegment(start_ms=0, end_ms=500, is_speech=True),
            VADSegment(start_ms=500, end_ms=1000, is_speech=False),
        ]
        chunks = Chunker.chunk(
            wav,
            chunk_size_ms=100,
            overlap_ms=20,
            sample_rate=sr,
            vad_segments=vad_segments,
        )
        # First few chunks (0–100ms, 80–180ms, etc.) should have is_speech=True
        # Later chunks should have is_speech=False
        assert any(c.is_speech for c in chunks)
        assert any(not c.is_speech for c in chunks)

    def test_chunk_without_overlap(self, sample_waveform):
        """When overlap_ms = 0, chunks should be non-overlapping."""
        wav, sr = sample_waveform
        chunks = Chunker.chunk(wav, chunk_size_ms=100, overlap_ms=0, sample_rate=sr)
        assert len(chunks) == 10
        for i in range(1, len(chunks)):
            assert chunks[i].start_ms == chunks[i - 1].end_ms

    def test_invalid_overlap_raises(self, sample_waveform):
        """overlap_ms >= chunk_size_ms should raise ValueError."""
        wav, sr = sample_waveform
        with pytest.raises(ValueError, match="overlap_ms"):
            Chunker.chunk(wav, chunk_size_ms=30, overlap_ms=30, sample_rate=sr)
