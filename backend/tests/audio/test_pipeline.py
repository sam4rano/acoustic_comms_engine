from unittest.mock import patch

import pytest
import torch

from app.audio.errors import AudioProcessingError
from app.audio.pipeline import AudioPipeline, PipelineConfig
from app.audio.vad import VAD


class TestAudioPipeline:
    def test_full_pipeline_end_to_end(self, sample_waveform):
        """Pipeline should process a waveform into chunks without error."""
        wav, sr = sample_waveform
        # Mock VAD to avoid model download
        with patch("app.audio.vad.VAD._model", object()):
            with patch.object(
                VAD,
                "_get_speech_timestamps",
                return_value=[{"start": 0, "end": 16000}],
            ):
                pipeline = AudioPipeline()
                chunks = pipeline.process(wav, sr)

        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.waveform.dtype == torch.float32
            assert chunk.waveform.size(0) == 1
            assert chunk.sample_rate == 16000
            assert chunk.start_ms >= 0
            assert chunk.end_ms > chunk.start_ms

    def test_pipeline_vad_disabled(self, sample_waveform):
        """Disabling VAD should skip voice activity detection."""
        wav, sr = sample_waveform
        config = PipelineConfig(vad=False)

        pipeline = AudioPipeline(config)
        chunks = pipeline.process(wav, sr)

        assert len(chunks) > 0
        # All chunks should default to is_speech = True
        assert all(c.is_speech for c in chunks)

    def test_pipeline_empty_input_returns_empty_list(self):
        """Empty waveform should produce an empty chunk list."""
        wav = torch.empty(1, 0)
        pipeline = AudioPipeline()
        chunks = pipeline.process(wav, 16000)
        assert chunks == []

    def test_pipeline_denoise_disabled(self, sample_waveform):
        """Disabling denoise should skip denoising."""
        wav, sr = sample_waveform
        config = PipelineConfig(denoise=False)
        with patch("app.audio.vad.VAD._model", object()):
            with patch.object(
                VAD,
                "_get_speech_timestamps",
                return_value=[{"start": 0, "end": 16000}],
            ):
                pipeline = AudioPipeline(config)
                chunks = pipeline.process(wav, sr)

        assert len(chunks) > 0

    def test_pipeline_resample_disabled_preserves_original_sr(self, sample_waveform):
        """With resample disabled, output sample_rate should match input."""
        wav, sr = sample_waveform
        config = PipelineConfig(resample=False, target_sample_rate=16000)
        with patch("app.audio.vad.VAD._model", object()):
            with patch.object(
                VAD,
                "_get_speech_timestamps",
                return_value=[{"start": 0, "end": 16000}],
            ):
                pipeline = AudioPipeline(config)
                chunks = pipeline.process(wav, sr)

        assert len(chunks) > 0
        assert chunks[0].sample_rate == 16000

    def test_pipeline_chunk_disabled(self, sample_waveform):
        """Disabling chunking should produce a single chunk for the whole waveform."""
        wav, sr = sample_waveform
        config = PipelineConfig(chunk=False)
        with patch("app.audio.vad.VAD._model", object()):
            with patch.object(
                VAD,
                "_get_speech_timestamps",
                return_value=[{"start": 0, "end": 16000}],
            ):
                pipeline = AudioPipeline(config)
                chunks = pipeline.process(wav, sr)

        assert len(chunks) == 1
        assert chunks[0].start_ms == 0
        assert chunks[0].end_ms == 1000

    def test_pipeline_48k_input(self):
        """Pipeline should handle 48 kHz input."""
        sr = 48000
        wav = torch.randn(1, 48000)
        with patch("app.audio.vad.VAD._model", object()):
            with patch.object(
                VAD,
                "_get_speech_timestamps",
                return_value=[{"start": 0, "end": 16000}],
            ):
                pipeline = AudioPipeline()
                chunks = pipeline.process(wav, sr)

        assert len(chunks) > 0
        assert chunks[0].sample_rate == 16000

    def test_pipeline_custom_config(self, sample_waveform):
        """Custom chunk size and overlap should be respected."""
        wav, sr = sample_waveform
        config = PipelineConfig(chunk_size_ms=100, chunk_overlap_ms=20)
        with patch("app.audio.vad.VAD._model", object()):
            with patch.object(
                VAD,
                "_get_speech_timestamps",
                return_value=[{"start": 0, "end": 16000}],
            ):
                pipeline = AudioPipeline(config)
                chunks = pipeline.process(wav, sr)

        # With 100ms chunk and 20ms overlap → hop = 80ms → 13 chunks for 1000ms
        assert len(chunks) == 13
        for c in chunks:
            assert c.waveform.size(-1) == int(16000 * 100 / 1000)

    def test_pipeline_vad_failure_propagates(self, sample_waveform):
        """If VAD raises, AudioProcessingError should propagate."""
        wav, sr = sample_waveform
        with patch("app.audio.vad.VAD._model", None):
            with patch(
                "app.audio.vad.VAD._load_silero_vad",
                side_effect=Exception("model crash"),
            ):
                pipeline = AudioPipeline()
                with pytest.raises(AudioProcessingError, match="VAD failed"):
                    pipeline.process(wav, sr)

    def test_process_file_not_found(self):
        """process_file should raise AudioProcessingError for missing files."""
        pipeline = AudioPipeline()
        with pytest.raises(AudioProcessingError, match="Audio file not found"):
            pipeline.process_file("/nonexistent/audio.wav")

    def test_default_config(self):
        """Default PipelineConfig should have all stages enabled."""
        config = PipelineConfig()
        assert config.resample is True
        assert config.vad is True
        assert config.denoise is True
        assert config.chunk is True
        assert config.target_sample_rate == 16000
        assert config.chunk_size_ms == 30
        assert config.chunk_overlap_ms == 10
