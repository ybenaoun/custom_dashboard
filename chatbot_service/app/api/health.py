from __future__ import annotations

from fastapi import APIRouter

from app.config import settings


router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "model": settings.cohere_model,
        "voice_enabled": settings.voice_enabled,
        "voice_backend": "piper+whisper (local gateway)",
        "voice_gateway_url": settings.voice_gateway_url,
    }
