"""Configuração via variáveis de ambiente (nunca grave segredos no código)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .utils import num

# Raiz do projeto (pasta que contém "nicolas/", ".env", "data/"). Independe do diretório atual.
ROOT = Path(__file__).resolve().parent.parent


def resolve_path(value: str) -> str:
    """Caminhos relativos são sempre relativos à raiz do projeto (importante no Termux)."""
    if value == ":memory:":
        return value
    p = Path(value).expanduser()
    return str(p if p.is_absolute() else ROOT / p)


def parse_env_text(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def load_dotenv(path=None) -> None:
    """Carrega o .env da raiz do projeto. Variáveis já definidas no ambiente têm prioridade."""
    p = Path(path) if path else ROOT / ".env"
    if not p.is_file():
        return
    for key, value in parse_env_text(p.read_text(encoding="utf-8")).items():
        os.environ.setdefault(key, value)


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass
class Config:
    bot_name: str = "Robô Nicolas 🤖"
    prefix: str = "."
    db_path: str = "data/nicolas.db"
    owner_ids: tuple = ()
    owner_name: str = ""
    owner_contact: str = ""
    tz_offset: float = -3
    # IA
    ai_provider: str = ""
    ai_model: str = ""
    ai_base_url: str = ""
    ai_api_key: str = field(default="", repr=False)
    # Autoriza explicitamente HTTP sem TLS apenas para IP privado de uma API de IA na rede local.
    ai_allow_http_lan: bool = False
    # IA reserva (usada quando a principal dá limite de uso/erro de servidor)
    ai_fallback_provider: str = ""
    ai_fallback_model: str = ""
    ai_fallback_base_url: str = ""
    ai_fallback_api_key: str = field(default="", repr=False)
    # Tradução (LibreTranslate)
    translate_url: str = ""
    translate_api_key: str = field(default="", repr=False)
    weather_enabled: bool = True
    web_enabled: bool = True
    ai_image_model: str = "gemini-2.5-flash-image"
    ai_tts_model: str = "gemini-2.5-flash-preview-tts"
    ai_voice: str = "Kore"
    ai_tts_engine: str = "auto"
    ai_tts_api_key: str = field(default="", repr=False)
    ai_tts_base_url: str = ""
    ai_tts_compat_model: str = "tts-1"
    ai_tts_compat_voice: str = "alloy"
    ai_tts_local_voice: str = "pt-br"
    ai_tts_voice_id: str = ""
    ai_tts_eleven_model: str = "eleven_multilingual_v2"
    ai_stt_model: str = ""
    # Modo esperto (IA responde no grupo)
    esperto_audio_reply: bool = True
    esperto_dm_pause_minutes: int = 10
    extra_prefixes: tuple = ("/",)
    esperto_per_minute: int = 6
    esperto_idle_minutes: int = 180
    # Limites
    rate_limit_count: int = 8
    rate_limit_window: int = 10
    flood_messages: int = 6
    flood_seconds: int = 8
    max_warns: int = 3
    antifake_prefixes: tuple = ("55",)
    # Gateway
    host: str = "127.0.0.1"
    port: int = 8787
    bridge_token: str = field(default="", repr=False)
    log_level: str = "INFO"
    backup_hours: float = 6.0
    startup_notice: bool = True
    backup_keep: int = 7

    @classmethod
    def from_env(cls) -> "Config":
        env = os.environ.get
        owners = tuple(n for n in (num(x) for x in env("OWNER_IDS", "").split(",")) if n)
        prefixes = tuple(p.strip() for p in env("ANTIFAKE_PREFIXES", "55").split(",") if p.strip())
        return cls(
            bot_name=env("BOT_NAME", "Robô Nicolas 🤖"),
            prefix=env("BOT_PREFIX", ".")[:3] or ".",
            db_path=resolve_path(env("DB_PATH", "data/nicolas.db")),
            owner_ids=owners,
            owner_name=env("OWNER_NAME", ""),
            owner_contact=env("OWNER_CONTACT", ""),
            tz_offset=float(env("TZ_OFFSET_HOURS", "-3")),
            ai_provider=env("AI_PROVIDER", "").strip().lower(),
            ai_model=env("AI_MODEL", ""),
            ai_base_url=env("AI_BASE_URL", ""),
            ai_api_key=env("AI_API_KEY", ""),
            ai_allow_http_lan=env("AI_ALLOW_HTTP_LAN", "0") == "1",
            ai_fallback_provider=env("AI_FALLBACK_PROVIDER", "").strip().lower(),
            ai_fallback_model=env("AI_FALLBACK_MODEL", ""),
            ai_fallback_base_url=env("AI_FALLBACK_BASE_URL", ""),
            ai_fallback_api_key=env("AI_FALLBACK_API_KEY", ""),
            translate_url=env("TRANSLATE_URL", "").rstrip("/"),
            translate_api_key=env("TRANSLATE_API_KEY", ""),
            weather_enabled=env("WEATHER_ENABLED", "1") != "0",
            web_enabled=env("WEB_SEARCH_ENABLED", "1") != "0",
            ai_image_model=env("AI_IMAGE_MODEL", "gemini-2.5-flash-image"),
            ai_tts_model=env("AI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
            ai_voice=env("AI_VOICE", "Kore"),
            ai_tts_engine=env("AI_TTS_ENGINE", "auto").strip().lower() or "auto",
            ai_tts_api_key=env("AI_TTS_API_KEY", ""),
            ai_tts_base_url=env("AI_TTS_BASE_URL", ""),
            ai_tts_compat_model=env("AI_TTS_COMPAT_MODEL", "tts-1"),
            ai_tts_compat_voice=env("AI_TTS_COMPAT_VOICE", "alloy"),
            ai_tts_local_voice=env("AI_TTS_LOCAL_VOICE", "pt-br"),
            ai_tts_voice_id=env("AI_TTS_VOICE_ID", ""),
            ai_tts_eleven_model=env("AI_TTS_ELEVEN_MODEL", "eleven_multilingual_v2"),
            ai_stt_model=env("AI_STT_MODEL", ""),
            esperto_audio_reply=env("ESPERTO_RESPONDE_AUDIO", "1") != "0",
            esperto_dm_pause_minutes=_int("ESPERTO_DM_PAUSA_MIN", 10),
            extra_prefixes=tuple(p.strip() for p in env("EXTRA_PREFIXES", "/").split(",") if p.strip()),
            esperto_per_minute=_int("ESPERTO_POR_MINUTO", 6),
            esperto_idle_minutes=_int("ESPERTO_OCIOSO_MINUTOS", 180),
            rate_limit_count=_int("RATE_LIMIT_COUNT", 8),
            rate_limit_window=_int("RATE_LIMIT_WINDOW", 10),
            flood_messages=_int("FLOOD_MESSAGES", 6),
            flood_seconds=_int("FLOOD_SECONDS", 8),
            max_warns=_int("MAX_WARNS", 3),
            antifake_prefixes=prefixes or ("55",),
            host=env("HOST", "127.0.0.1"),
            port=_int("PORT", 8787),
            bridge_token=env("BRIDGE_TOKEN", ""),
            log_level=env("LOG_LEVEL", "INFO").upper(),
            startup_notice=env("AVISO_INICIO", "1") != "0",
            backup_hours=float(env("BACKUP_HORAS", "6") or 6),
            backup_keep=_int("BACKUP_MANTER", 7),
        )

    @property
    def ai_configured(self) -> bool:
        if not (self.ai_provider and self.effective_model):
            return False
        if self.ai_api_key:
            return True
        # Serviços auto-hospedados podem não exigir chave. O endpoint customizado continua obrigatório.
        from .providers import default_base
        if self.ai_provider in {"ollama", "docker-model-runner"}:
            return bool(self.ai_base_url or default_base(self.ai_provider))
        if self.ai_provider == "openai-compatible":
            return bool(self.ai_base_url)
        return False

    @property
    def effective_model(self) -> str:
        """Modelo configurado ou, se vazio, o padrão do provedor."""
        from .providers import default_model
        return self.ai_model or default_model(self.ai_provider)

    def fallback(self):
        """Config equivalente usando a IA reserva, ou None se não houver."""
        import dataclasses
        from .providers import default_model
        fallback_keyless = self.ai_fallback_provider in {"ollama", "docker-model-runner"} or (
            self.ai_fallback_provider == "openai-compatible" and bool(self.ai_fallback_base_url))
        if not (self.ai_fallback_provider and (self.ai_fallback_api_key or fallback_keyless)):
            return None
        model = self.ai_fallback_model or default_model(self.ai_fallback_provider)
        if not model:
            return None
        return dataclasses.replace(
            self, ai_provider=self.ai_fallback_provider, ai_model=model, ai_base_url=self.ai_fallback_base_url,
            ai_api_key=self.ai_fallback_api_key, ai_fallback_provider="", ai_fallback_api_key="")

    @property
    def translate_configured(self) -> bool:
        return bool(self.translate_url)
