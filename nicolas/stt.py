"""Transcrição de áudio (voz → texto) para provedores compatíveis com OpenAI (Groq Whisper, OpenAI)."""
from __future__ import annotations

import base64

from .net import NetError, post_multipart
from .providers import default_base

STT_MODELS = {"groq": "whisper-large-v3-turbo", "openai": "whisper-1"}
_EXT = {"audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/wav": "wav", "audio/webm": "webm"}


def supported(cfg) -> bool:
    return cfg.ai_configured and cfg.ai_provider in STT_MODELS


def transcribe(cfg, b64: str, mime: str = "audio/ogg") -> str:
    if not supported(cfg):
        raise NetError("transcrição não disponível para este provedor")
    try:
        raw = base64.b64decode(b64, validate=False)
    except ValueError:
        raise NetError("áudio inválido") from None
    base_mime = (mime or "audio/ogg").split(";")[0].strip().lower()
    base = (cfg.ai_base_url or default_base(cfg.ai_provider)).rstrip("/")
    data = post_multipart(
        f"{base}/audio/transcriptions",
        fields={"model": cfg.ai_stt_model or STT_MODELS[cfg.ai_provider], "language": "pt", "response_format": "json"},
        file_field="file", filename=f"audio.{_EXT.get(base_mime, 'ogg')}", content=raw, mime=base_mime,
        headers={"Authorization": f"Bearer {cfg.ai_api_key}"})
    text = (data.get("text") if isinstance(data, dict) else "") or ""
    if not text.strip():
        raise NetError("não consegui entender o áudio")
    return text.strip()[:1500]
