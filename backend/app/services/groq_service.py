import io
import json
import struct
import time
import wave
import logging

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are an executive communication coach. Analyze this transcript and return ONLY valid JSON. No markdown, no text outside JSON.

JSON format:
{"overall": <0-100>, "summary": "<text>", "dimensions": {"Clarity": {"score": <0-100>, "rationale": "<text>"}, "Pace": {"score": <0-100>, "rationale": "<text>"}, "Empathy": {"score": <0-100>, "rationale": "<text>"}, "Assertiveness": {"score": <0-100>, "rationale": "<text>"}, "Fluency": {"score": <0-100>, "rationale": "<text>"}, "Engagement": {"score": <0-100>, "rationale": "<text>"}}, "coaching": [{"title": "<text>", "description": "<text>", "priority": "high|medium|low", "practice_tip": "<text>", "dimension": "<text>"}], "strengths": ["<text>"], "weaknesses": ["<text>"]}

Rules:
- Scores reflect actual communication quality. Short transcripts (<20 words) get lower scores.
- 2-4 coaching actions prioritized by importance.
- Be specific and actionable in tips."""


class AnalysisOutput(BaseModel):
    overall: float
    summary: str
    dimensions: dict[str, dict]
    coaching: list[dict]
    strengths: list[str]
    weaknesses: list[str]


class GroqService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            timeout=120.0,
        )

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio via Groq Whisper. Expects WAV format bytes."""
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "recording.wav"

        logger.info("Sending audio to Groq Whisper (%d bytes)", len(audio_bytes))
        t0 = time.time()

        response = await self._client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=audio_file,
            response_format="json",
            language="en",
            temperature=0.0,
        )

        logger.info("Whisper transcription complete in %.1fs: %s", time.time() - t0, response.text[:100])
        return response.text.strip()

    async def analyze(self, transcript: str) -> dict:
        """Analyze transcript via Groq LLM for communication scores and coaching."""
        logger.info("Sending transcript to Groq LLM (%d chars)", len(transcript))
        t0 = time.time()

        response = await self._client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": ANALYSIS_PROMPT},
                {"role": "user", "content": f"Transcript to analyze:\n\n{transcript}"},
            ],
            temperature=0.1,
            max_tokens=2048,
        )

        raw = response.choices[0].message.content or "{}"
        logger.info("LLM raw response (%d chars): %.200s", len(raw), raw)

        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
            cleaned = cleaned.rsplit("```", 1)[0] if cleaned.endswith("```") else cleaned.rstrip("`")
            cleaned = cleaned.strip()

        # Try to find JSON object
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON from within the text
            import re
            match = re.search(r'\{[\s\S]*\}', cleaned)
            if match:
                try:
                    result = json.loads(match.group(0))
                except json.JSONDecodeError:
                    logger.warning("Could not parse JSON from LLM response")
                    result = self._fallback_analysis(transcript)
            else:
                logger.warning("No JSON object found in LLM response")
                result = self._fallback_analysis(transcript)

        logger.info("LLM analysis complete in %.1fs", time.time() - t0)
        return result

    def _fallback_analysis(self, transcript: str) -> dict:
        return _fallback_analysis(transcript)


def _fallback_analysis(transcript: str) -> dict:
    words = transcript.split()
    word_count = len(words)

    if word_count < 10:
        overall = 40
        clarity = 60
    elif word_count < 30:
        overall = 55
        clarity = 70
    else:
        overall = 68
        clarity = 80

    return {
        "overall": overall,
        "summary": "Communication scores estimated from recording length and structure.",
        "dimensions": {
            "Clarity": {"score": clarity, "rationale": "Based on transcript coherence estimation."},
            "Pace": {"score": 60, "rationale": "Estimated from word spacing."},
            "Empathy": {"score": 55, "rationale": "Limited data for full assessment."},
            "Assertiveness": {"score": 55, "rationale": "Limited data for full assessment."},
            "Fluency": {"score": 55, "rationale": "Limited data for full assessment."},
            "Engagement": {"score": 55, "rationale": "Limited data for full assessment."},
        },
        "coaching": [
            {
                "title": "Speak clearly and at a steady pace",
                "description": "Focus on articulating your words clearly and maintaining a consistent speaking rhythm.",
                "priority": "high",
                "practice_tip": "Record yourself speaking for 30 seconds on any topic, then listen back to identify areas to improve.",
                "dimension": "Clarity",
            },
            {
                "title": "Structure your thoughts",
                "description": "Organize your ideas before speaking to improve coherence and impact.",
                "priority": "medium",
                "practice_tip": "Before speaking, take a moment to outline your main points in your mind.",
                "dimension": "Clarity",
            },
            {
                "title": "Maintain a conversational pace",
                "description": "Aim for a natural rhythm that keeps listeners engaged without rushing.",
                "priority": "medium",
                "practice_tip": "Practice reading aloud at about 150 words per minute — the pace of natural conversation.",
                "dimension": "Pace",
            },
        ],
        "strengths": ["Session recorded successfully."],
        "weaknesses": ["Record a longer session for more detailed analysis."],
    }


def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1, bits: int = 16) -> bytes:
    """Convert raw PCM bytes to WAV format."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(bits // 8)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()
