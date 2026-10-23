"""Recursos multimídia do Gemini: ouvir áudio, ver imagens, gerar imagens e falar em áudio.

Usa a API REST do Gemini (a mesma chave AI_API_KEY). Nada aqui foi validado contra o serviço real por quem montou o
projeto: se o Google mudar nomes de modelos ou formatos, ajuste AI_MODEL, AI_IMAGE_MODEL e AI_TTS_MODEL no .env.
"""
from __future__ import annotations

import base64
import io
import shutil
import subprocess
import wave

from .ai_client import THINKING_HEADROOM, gemini_reason
from .net import NetError, request_json

DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta"
MEDIA_LIMIT = 15_000_000

TOOLS = [{"functionDeclarations": [
    {"name": "gerar_imagem",
     "description": "Cria uma imagem nova. Use quando alguém pedir para criar, gerar, desenhar ou fazer uma imagem, "
                    "foto, ilustração, figurinha, logo, meme ou arte.",
     "parameters": {"type": "OBJECT", "properties": {
         "descricao": {"type": "STRING", "description": "Descrição detalhada da imagem, em português ou inglês"}},
         "required": ["descricao"]}},
    {"name": "falar_em_audio",
     "description": "Envia a resposta como mensagem de voz. Use quando alguém pedir um áudio, que você fale, "
                    "mande voz ou responda falando.",
     "parameters": {"type": "OBJECT", "properties": {
         "texto": {"type": "STRING", "description": "O que deve ser dito em voz alta, em português, de forma natural"}},
         "required": ["texto"]}},
]}]


def _base(cfg) -> str:
    return (cfg.ai_base_url or DEFAULT_BASE).rstrip("/")


def _post(cfg, model: str, body: dict, timeout: int = 60) -> dict:
    return request_json(f"{_base(cfg)}/models/{model}:generateContent", data=body,
                        headers={"x-goog-api-key": cfg.ai_api_key}, timeout=timeout, max_bytes=MEDIA_LIMIT)


def _parts(data: dict) -> list:
    try:
        return data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        raise NetError(f"resposta inesperada da IA ({gemini_reason(data)})") from None


def generate(cfg, prompt: str, system: str, media=(), tools: bool = True, max_tokens: int = 700) -> dict:
    """Texto + (opcional) áudio/imagens de entrada. Retorna {"text": str, "calls": [{"name", "args"}]}."""
    parts = [{"text": prompt[:6000]}]
    for m in media:
        parts.append({"inlineData": {"mimeType": str(m.get("mime", "application/octet-stream")).split(";")[0],
                                     "data": m["data"]}})
    body = {"contents": [{"role": "user", "parts": parts}],
            "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {"maxOutputTokens": max_tokens + THINKING_HEADROOM}}
    if tools:
        body["tools"] = TOOLS
    out_parts = _parts(_post(cfg, cfg.effective_model, body))
    text = "".join(p.get("text", "") for p in out_parts if isinstance(p, dict)).strip()
    calls = [{"name": p["functionCall"].get("name", ""), "args": p["functionCall"].get("args") or {}}
             for p in out_parts if isinstance(p, dict) and isinstance(p.get("functionCall"), dict)]
    if not text and not calls:
        raise NetError("a IA não retornou conteúdo")
    return {"text": text[:3500], "calls": calls}


def make_image(cfg, description: str) -> tuple[str, str]:
    """Gera uma imagem. Retorna (mimetype, base64)."""
    body = {"contents": [{"parts": [{"text": description[:2000]}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}
    for p in _parts(_post(cfg, cfg.ai_image_model, body, timeout=90)):
        inline = p.get("inlineData") or p.get("inline_data") if isinstance(p, dict) else None
        if inline and inline.get("data"):
            return inline.get("mimeType") or inline.get("mime_type") or "image/png", inline["data"]
    raise NetError("o modelo não devolveu imagem")


def _pcm_to_wav(pcm: bytes, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _to_opus(wav_or_pcm: bytes, rate: int) -> bytes | None:
    """Converte PCM em mensagem de voz do WhatsApp (ogg/opus). Exige ffmpeg; sem ele retorna None."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    try:
        proc = subprocess.run([ffmpeg, "-loglevel", "error", "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
                               "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", "pipe:1"],
                              input=wav_or_pcm, capture_output=True, timeout=45)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 and proc.stdout else None


def speak(cfg, text: str) -> dict:
    """Texto em voz. Retorna {"data": bytes, "mimetype": str, "ptt": bool}."""
    body = {"contents": [{"parts": [{"text": text[:1500]}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": cfg.ai_voice}}}}}
    for p in _parts(_post(cfg, cfg.ai_tts_model, body, timeout=90)):
        inline = p.get("inlineData") or p.get("inline_data") if isinstance(p, dict) else None
        if inline and inline.get("data"):
            pcm = base64.b64decode(inline["data"])
            mime = str(inline.get("mimeType") or inline.get("mime_type") or "")
            rate = 24000
            if "rate=" in mime:
                try:
                    rate = int(mime.split("rate=")[1].split(";")[0])
                except ValueError:
                    pass
            opus = _to_opus(pcm, rate)
            if opus:
                return {"data": opus, "mimetype": "audio/ogg; codecs=opus", "ptt": True}
            return {"data": _pcm_to_wav(pcm, rate), "mimetype": "audio/wav", "ptt": False}
    raise NetError("o modelo não devolveu áudio")
