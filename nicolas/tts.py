"""Voz do bot (texto → mensagem de voz), independente do modelo de texto.

Um modelo de TEXTO (como os do OpenRouter) não gera áudio sozinho. Por isso o bot escolhe a resposta com o modelo de
texto e depois converte em voz com um destes motores (AI_TTS_ENGINE):

  gemini  Voz do Gemini. Usa a chave do próprio Gemini (AI_API_KEY se o provedor for gemini, senão AI_TTS_API_KEY).
  openai  API compatível com OpenAI em {base}/audio/speech (OpenAI, ou outro serviço que ofereça esse endereço).
          Variáveis: AI_TTS_API_KEY, AI_TTS_BASE_URL (padrão https://api.openai.com/v1), AI_TTS_COMPAT_MODEL (tts-1),
          AI_TTS_COMPAT_VOICE (alloy).
  elevenlabs  Voz natural da ElevenLabs (AI_TTS_API_KEY + AI_TTS_VOICE_ID; modelo multilíngue, serve para português).
  local   Voz do próprio celular/PC, grátis e sem internet: precisa do pacote espeak (Termux: pkg install espeak ffmpeg).
          A voz é robótica, mas funciona sem conta e sem cota.
  auto    (padrão) gemini se o provedor de texto for gemini; senão local, se espeak estiver instalado.

Se o motor escolhido falhar, o bot tenta a voz local antes de desistir.
"""
from __future__ import annotations

import base64
import dataclasses
import logging
import shutil
import subprocess

from . import gemini_media
from .net import NetError, request_bytes

log = logging.getLogger("nicolas.tts")
LOCAL_BINS = ("espeak-ng", "espeak")


def _local_bin() -> str | None:
    return next((p for p in (shutil.which(b) for b in LOCAL_BINS) if p), None)


def _gemini_cfg(cfg):
    """Config com a chave do Gemini para a voz (a do provedor de texto, ou AI_TTS_API_KEY)."""
    if cfg.ai_provider == "gemini" and cfg.ai_api_key:
        return cfg
    if cfg.ai_tts_api_key:
        return dataclasses.replace(cfg, ai_provider="gemini", ai_api_key=cfg.ai_tts_api_key, ai_base_url="")
    return None


def engine(cfg) -> str | None:
    """Motor de voz que será usado agora (ou None se não houver nenhum configurado/instalado)."""
    want = (cfg.ai_tts_engine or "auto").lower()
    if want == "gemini":
        return "gemini" if _gemini_cfg(cfg) else None
    if want == "openai":
        return "openai" if cfg.ai_tts_api_key else None
    if want == "elevenlabs":
        return "elevenlabs" if cfg.ai_tts_api_key and cfg.ai_tts_voice_id else None
    if want == "local":
        return "local" if _local_bin() else None
    if _gemini_cfg(cfg) and cfg.ai_provider == "gemini":
        return "gemini"
    if want == "auto" and _local_bin():
        return "local"
    return None


def available(cfg) -> bool:
    return engine(cfg) is not None


def _to_opus_from_file(data: bytes, fmt: str | None = None) -> bytes | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    cmd = [ffmpeg, "-loglevel", "error"] + (["-f", fmt] if fmt else []) + ["-i", "pipe:0", "-c:a", "libopus",
                                                                           "-b:a", "32k", "-f", "ogg", "pipe:1"]
    try:
        proc = subprocess.run(cmd, input=data, capture_output=True, timeout=45)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 and proc.stdout else None


def _speak_local(cfg, text: str) -> dict:
    binary = _local_bin()
    if not binary:
        raise NetError("voz local indisponível (instale: pkg install espeak ffmpeg)")
    try:
        proc = subprocess.run([binary, "-v", cfg.ai_tts_local_voice, "-s", "160", "--stdout", text[:1200]],
                              capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        raise NetError("a voz local falhou") from None
    if proc.returncode != 0 or len(proc.stdout) < 100:
        raise NetError("a voz local falhou")
    opus = _to_opus_from_file(proc.stdout)
    if opus:
        return {"data": opus, "mimetype": "audio/ogg; codecs=opus", "ptt": True}
    return {"data": proc.stdout, "mimetype": "audio/wav", "ptt": False}


def _speak_openai(cfg, text: str) -> dict:
    base = (cfg.ai_tts_base_url or "https://api.openai.com/v1").rstrip("/")
    raw = request_bytes(f"{base}/audio/speech",
                        data={"model": cfg.ai_tts_compat_model, "input": text[:1500], "voice": cfg.ai_tts_compat_voice,
                              "response_format": "opus"},
                        headers={"Authorization": f"Bearer {cfg.ai_tts_api_key}"}, timeout=90)
    if raw[:4] == b"OggS":
        return {"data": raw, "mimetype": "audio/ogg; codecs=opus", "ptt": True}
    opus = _to_opus_from_file(raw)  # o serviço devolveu outro formato (mp3/wav...): converte se houver ffmpeg
    if opus:
        return {"data": opus, "mimetype": "audio/ogg; codecs=opus", "ptt": True}
    return {"data": raw, "mimetype": "audio/mpeg", "ptt": False}


ELEVEN_BASE = "https://api.elevenlabs.io/v1"


def _speak_eleven(cfg, text: str) -> dict:
    raw = request_bytes(f"{ELEVEN_BASE}/text-to-speech/{cfg.ai_tts_voice_id}?output_format=mp3_44100_128",
                        data={"text": text[:1500], "model_id": cfg.ai_tts_eleven_model},
                        headers={"xi-api-key": cfg.ai_tts_api_key, "Accept": "audio/mpeg"}, timeout=90)
    opus = _to_opus_from_file(raw)  # mp3 -> mensagem de voz do WhatsApp (precisa do ffmpeg)
    if opus:
        return {"data": opus, "mimetype": "audio/ogg; codecs=opus", "ptt": True}
    return {"data": raw, "mimetype": "audio/mpeg", "ptt": False}


def speak(cfg, text: str) -> dict:
    """Texto → {"data": bytes, "mimetype": str, "ptt": bool}. Levanta NetError se nenhum motor conseguir."""
    text = " ".join((text or "").split())
    if not text:
        raise NetError("sem texto para falar")
    eng = engine(cfg)
    if eng is None:
        raise NetError("nenhum motor de voz configurado")
    try:
        if eng == "gemini":
            return gemini_media.speak(_gemini_cfg(cfg), text)
        if eng == "openai":
            return _speak_openai(cfg, text)
        if eng == "elevenlabs":
            return _speak_eleven(cfg, text)
        return _speak_local(cfg, text)
    except (NetError, OSError, ValueError) as exc:
        if eng != "local" and _local_bin():
            log.warning("voz (%s) falhou (%s); usando a voz local", eng, type(exc).__name__)
            return _speak_local(cfg, text)
        raise


def as_base64(result: dict) -> str:
    return base64.b64encode(result["data"]).decode()
