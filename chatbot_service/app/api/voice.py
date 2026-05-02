from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import settings
from app.deps import get_current_user

router = APIRouter(prefix="/voice", tags=["voice"])
logger = logging.getLogger("custom_dashboard.voice")


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str = "fr"
    voice: str | None = None


def _gateway_base() -> str:
    if not settings.voice_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voice features are disabled",
        )
    base = (settings.voice_gateway_url or "").rstrip("/")
    if not base:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VOICE_GATEWAY_URL not configured",
        )
    return base


@router.post("/tts")
async def tts(
    req: TTSRequest,
    user: dict = Depends(get_current_user),
) -> Response:
    base = _gateway_base()
    payload = {"text": req.text, "lang": req.language[:2] if req.language else None}
    if req.voice:
        payload["voice"] = req.voice

    try:
        async with httpx.AsyncClient(timeout=settings.voice_gateway_timeout) as client:
            r = await client.post(f"{base}/tts", json=payload)
    except httpx.HTTPError as exc:
        logger.exception("tts_gateway_unreachable", extra={"user": user.get("user")})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Voice gateway unreachable: {exc}",
        ) from exc

    if r.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Voice gateway TTS failed ({r.status_code}): {r.text[:200]}",
        )

    data = r.json()
    audio_hex = data.get("audio_hex") or ""
    if not audio_hex:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Voice gateway returned empty audio",
        )

    try:
        audio_bytes = bytes.fromhex(audio_hex)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Voice gateway returned invalid audio_hex: {exc}",
        ) from exc

    return Response(
        content=audio_bytes,
        media_type=data.get("mime_type") or "audio/wav",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
            "X-Voice-Backend": "piper",
            "X-Voice-Voice": data.get("voice") or "",
            "X-Voice-Lang": data.get("lang") or "",
        },
    )


@router.post("/stt")
async def stt(
    audio: UploadFile = File(...),
    language: str = Form("fr"),
    prompt: str | None = Form(None),
    user: dict = Depends(get_current_user),
) -> dict:
    base = _gateway_base()
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio payload")
    if len(data) > settings.stt_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Audio too large (max {settings.stt_max_bytes} bytes)",
        )

    files = {
        "audio": (
            audio.filename or "voice.webm",
            data,
            audio.content_type or "audio/webm",
        )
    }
    form = {"language": language[:2] if language else ""}

    try:
        async with httpx.AsyncClient(timeout=settings.voice_gateway_timeout) as client:
            r = await client.post(f"{base}/stt", files=files, data=form)
    except httpx.HTTPError as exc:
        logger.exception("stt_gateway_unreachable", extra={"user": user.get("user")})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Voice gateway unreachable: {exc}",
        ) from exc

    if r.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Voice gateway STT failed ({r.status_code}): {r.text[:200]}",
        )

    payload = r.json()
    return {
        "text": (payload.get("text") or "").strip(),
        "language": payload.get("language") or language,
        "model": payload.get("model") or "whisper-faster",
        "bytes": len(data),
    }
