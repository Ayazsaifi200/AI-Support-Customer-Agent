"""ElevenLabs voice pipeline for the AI Customer Support Agent.

Pipeline:  audio in  ──STT(ElevenLabs)──►  LangGraph agent  ──TTS(ElevenLabs)──►  audio out

Endpoints:
- POST /voice/tts   : text  -> spoken audio (mp3)
- POST /voice/stt   : audio -> transcript text
- POST /voice/talk  : audio -> (STT) -> agent decision -> (TTS) -> spoken audio,
                      with the transcript, reply and decision returned in headers.
"""
import io
from functools import lru_cache
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.graph import run_agent
from app.config import get_settings

router = APIRouter(prefix="/voice", tags=["voice"])


@lru_cache
def _client():
    from elevenlabs.client import ElevenLabs

    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not configured.")
    return ElevenLabs(api_key=settings.elevenlabs_api_key)


def _synthesize(text: str, voice_id: str | None = None) -> bytes:
    settings = get_settings()
    audio = _client().text_to_speech.convert(
        voice_id=voice_id or settings.elevenlabs_voice_id,
        model_id=settings.elevenlabs_tts_model,
        text=text,
        output_format="mp3_44100_128",
    )
    return b"".join(audio)


def _transcribe(data: bytes) -> str:
    settings = get_settings()
    result = _client().speech_to_text.convert(
        file=io.BytesIO(data),
        model_id=settings.elevenlabs_stt_model,
    )
    return getattr(result, "text", "") or ""


class TTSRequest(BaseModel):
    text: str
    voice_id: str | None = None


@router.post("/tts")
def text_to_speech(req: TTSRequest):
    """Convert text into spoken audio using ElevenLabs. Returns an MP3 stream."""
    try:
        audio = _synthesize(req.text, req.voice_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ElevenLabs TTS error: {exc}") from exc
    return StreamingResponse(io.BytesIO(audio), media_type="audio/mpeg")


@router.post("/stt")
async def speech_to_text(file: UploadFile = File(...)):
    """Transcribe an uploaded audio file using ElevenLabs Scribe."""
    data = await file.read()
    try:
        text = _transcribe(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ElevenLabs STT error: {exc}") from exc
    return {"text": text}


@router.post("/talk")
async def talk(
    file: UploadFile = File(...),
    customer_id: str | None = Form(default=None),
):
    """Full voice turn: transcribe audio, run the agent, speak the reply.

    Returns the agent's spoken reply as an MP3 stream. The transcript, text
    reply and refund decision are returned in response headers:
      X-Transcript, X-Reply, X-Decision
    """
    data = await file.read()

    # 1. Speech -> text (ElevenLabs)
    try:
        transcript = _transcribe(data)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ElevenLabs STT error: {exc}") from exc
    if not transcript.strip():
        raise HTTPException(status_code=400, detail="No speech detected in the audio.")

    # 2. Text -> agent decision (LangGraph + Groq)
    try:
        result = run_agent(user_message=transcript, customer_id=customer_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}") from exc
    reply = result.get("reply") or "I'm sorry, I couldn't process that request."

    # 3. Text -> speech (ElevenLabs)
    try:
        audio = _synthesize(reply)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ElevenLabs TTS error: {exc}") from exc

    headers = {
        "X-Transcript": quote(transcript),
        "X-Reply": quote(reply),
        "X-Decision": result.get("decision") or "none",
    }
    return StreamingResponse(io.BytesIO(audio), media_type="audio/mpeg", headers=headers)
