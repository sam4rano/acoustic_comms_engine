import base64
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_user
from app.services.groq_service import GroqService, pcm_to_wav
from app.services.pipeline_service import PipelineService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions/{session_id}/analysis", tags=["analysis"])

_groq = GroqService()
_pipeline = PipelineService()

_analysis_store: dict[str, dict] = {}


class AnalyzeRequest(BaseModel):
    audio_data: str = Field(..., description="Base64-encoded raw PCM audio bytes")
    sample_rate: int = Field(default=16000)
    channels: int = Field(default=1)
    bits_per_sample: int = Field(default=16)


@router.get("")
async def get_analysis_report(
    session_id: UUID,
    user_id: str = Depends(get_current_user),
) -> dict:
    cached = _analysis_store.get(str(session_id))
    if cached:
        return cached

    return {
        "session_id": str(session_id),
        "status": "pending",
        "message": "Analysis not yet available. POST audio to /analyze to generate a report.",
    }


@router.post("/analyze", status_code=status.HTTP_200_OK)
async def analyze_session(
    session_id: UUID,
    body: AnalyzeRequest,
    user_id: str = Depends(get_current_user),
) -> dict:
    try:
        pcm_bytes = base64.b64decode(body.audio_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio data")

    if len(pcm_bytes) == 0:
        raise HTTPException(status_code=400, detail="Audio data is empty")

    wav_bytes = pcm_to_wav(
        pcm_bytes,
        sample_rate=body.sample_rate,
        channels=body.channels,
        bits=body.bits_per_sample,
    )

    logger.info(
        "Processing analysis for session %s: %d PCM bytes (%d WAV bytes)",
        session_id, len(pcm_bytes), len(wav_bytes),
    )

    transcript = ""
    transcription_degraded = False
    try:
        transcript = await _groq.transcribe(wav_bytes)
    except Exception as exc:
        logger.warning("Whisper transcription failed: %s — generating degraded report", exc)
        transcription_degraded = True

    if not transcript.strip():
        duration_s = max(len(pcm_bytes) / (body.sample_rate * body.channels * body.bits_per_sample // 8), 1)
        response = _build_fallback(
            transcript=transcript,
            word_count=0,
            session_id=session_id,
            duration_s=duration_s,
            wpm=0,
        )
        if transcription_degraded:
            response["status"] = "degraded"
            response["degraded"] = True
            response["degradation_reason"] = "Transcription unavailable — showing estimated scores."
        else:
            response["status"] = "no_speech"
            response["message"] = "No speech detected in the recording."
        _analysis_store[str(session_id)] = response
        return response

    words = transcript.split()
    word_count = len(words)
    duration_s = max(len(pcm_bytes) / (body.sample_rate * body.channels * body.bits_per_sample // 8), 1)
    duration_ms = int(duration_s * 1000)
    wpm = round(word_count / (duration_s / 60), 1) if duration_s > 0 else 0

    try:
        report = await _pipeline.analyze_transcript(
            session_id=session_id,
            transcript=transcript,
            duration_ms=duration_ms,
        )
        degraded = word_count < 30 or report.degraded
        degradation_reason = report.degradation_reason or (
            f"Recording too short ({word_count} words < 30 minimum) for stable metrics."
            if word_count < 30 else None
        )
        response = {
            "session_id": str(session_id),
            "status": "complete",
            "overall": report.scores.overall,
            "summary": report.summary,
            "dimensions": [
                {
                    "dimension": d.dimension,
                    "score": d.score,
                    "confidence": d.confidence,
                    "rationale": d.rationale,
                }
                for d in report.scores.dimensions
            ],
            "coaching": [
                {
                    "title": c.title,
                    "description": c.description,
                    "priority": c.priority,
                    "practice_tip": c.practice_tip,
                    "related_turns": c.related_turns,
                    "dimension": c.dimension,
                }
                for c in report.coaching
            ],
            "strengths": [],
            "weaknesses": [],
            "delivery_evidence": {
                "wpm": wpm,
                "hesitations": 0,
                "avg_hesitation_s": 0,
                "confirmed_fillers": 0,
                "word_count": word_count,
                "target_word_count": 60,
                "duration_s": round(duration_s, 1),
            },
            "transcript": [
                {
                    "turn_id": "1",
                    "speaker_label": "Speaker",
                    "text": transcript,
                    "is_final": True,
                    "timestamp": 0,
                }
            ],
            "confidence": report.confidence,
            "degraded": degraded,
            "degradation_reason": degradation_reason,
        }
    except Exception as exc:
        logger.exception("Pipeline analysis failed, using fallback")
        response = _build_fallback(transcript, word_count, session_id, duration_s, wpm)

    _analysis_store[str(session_id)] = response
    return response


def _build_fallback(
    transcript: str,
    word_count: int,
    session_id: UUID,
    duration_s: float,
    wpm: float,
) -> dict:
    from app.services.groq_service import _fallback_analysis
    analysis = _fallback_analysis(transcript)

    return {
        "session_id": str(session_id),
        "status": "complete",
        "overall": analysis.get("overall", 50),
        "summary": analysis.get("summary", ""),
        "dimensions": [
            {
                "dimension": name,
                "score": dim.get("score", 50),
                "confidence": 0.5,
                "rationale": dim.get("rationale", ""),
            }
            for name, dim in analysis.get("dimensions", {}).items()
        ],
        "coaching": [
            {
                "title": c.get("title", ""),
                "description": c.get("description", ""),
                "priority": c.get("priority", "medium"),
                "practice_tip": c.get("practice_tip", ""),
                "related_turns": [],
                "dimension": c.get("dimension", "General"),
            }
            for c in analysis.get("coaching", [])
        ],
        "strengths": analysis.get("strengths", []),
        "weaknesses": analysis.get("weaknesses", []),
        "delivery_evidence": {
            "wpm": wpm,
            "hesitations": 0,
            "avg_hesitation_s": 0,
            "confirmed_fillers": 0,
            "word_count": word_count,
            "target_word_count": 60,
            "duration_s": round(duration_s, 1),
        },
        "transcript": [
            {
                "turn_id": "1",
                "speaker_label": "Speaker",
                "text": transcript,
                "is_final": True,
                "timestamp": 0,
            }
        ],
        "confidence": 0.5,
        "degraded": True,
        "degradation_reason": "Pipeline analysis failed; using algorithmic fallback.",
    }


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    session_id: UUID,
    user_id: str = Depends(get_current_user),
) -> dict:
    return {
        "session_id": str(session_id),
        "status": "accepted",
        "message": "Analysis pipeline triggered",
    }
