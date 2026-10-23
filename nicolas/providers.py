"""Provedores de IA conhecidos: endereço, modelo padrão e reconhecimento pelo formato da chave.

Os modelos padrão são só um ponto de partida: mudam com o tempo. Se der "modelo não encontrado", troque com
`python3 -m nicolas setenv AI_MODEL <nome>` (a lista de modelos fica no painel do provedor).
"""
from __future__ import annotations

PROVIDERS = {
    "gemini": {"label": "Google Gemini", "base": "https://generativelanguage.googleapis.com/v1beta",
               "model": "gemini-flash-latest", "keys": "https://aistudio.google.com/apikey"},
    "groq": {"label": "Groq", "base": "https://api.groq.com/openai/v1",
             "model": "llama-3.3-70b-versatile", "keys": "https://console.groq.com/keys"},
    "openai": {"label": "OpenAI", "base": "https://api.openai.com/v1", "model": "gpt-4o-mini",
               "keys": "https://platform.openai.com/api-keys"},
    "openrouter": {"label": "OpenRouter", "base": "https://openrouter.ai/api/v1", "model": "",
                   "keys": "https://openrouter.ai/keys"},
    "deepseek": {"label": "DeepSeek", "base": "https://api.deepseek.com/v1", "model": "deepseek-chat",
                 "keys": "https://platform.deepseek.com/api_keys"},
    "together": {"label": "Together AI", "base": "https://api.together.xyz/v1", "model": "",
                 "keys": "https://api.together.ai/settings/api-keys"},
    "anthropic": {"label": "Anthropic Claude", "base": "https://api.anthropic.com", "model": "",
                  "keys": "https://console.anthropic.com/settings/keys"},
    "ollama": {"label": "Ollama (local)", "base": "http://127.0.0.1:11434/v1", "model": "", "keys": ""},
    "docker-model-runner": {"label": "Docker Model Runner (local/remoto)",
                            "base": "http://127.0.0.1:12434/engines/v1", "model": "", "keys": ""},
    "openai-compatible": {"label": "Outra API compatível com OpenAI", "base": "", "model": "", "keys": ""},
}


def default_model(provider: str) -> str:
    return PROVIDERS.get(provider, {}).get("model", "")


def default_base(provider: str) -> str:
    return PROVIDERS.get(provider, {}).get("base", "")


def detect_provider(key: str) -> str:
    """Palpite do provedor pelo formato da chave ('' se não der para saber)."""
    k = (key or "").strip()
    if k.startswith("gsk_"):
        return "groq"
    if k.startswith("sk-ant-"):
        return "anthropic"
    if k.startswith("sk-or-"):
        return "openrouter"
    if k.startswith("AIza") or k.startswith("AQ."):
        return "gemini"
    if k.startswith("sk-"):
        return "openai"
    return ""
