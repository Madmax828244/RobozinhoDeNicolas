"""Manipulação segura do arquivo .env (usada pelo install.sh)."""
from __future__ import annotations

import os
import re
import secrets
import tempfile
from pathlib import Path

from .config import ROOT, parse_env_text

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def set_env(path, key: str, value: str) -> None:
    """Define KEY=value preservando comentários e demais linhas. Escrita atômica, permissão 600."""
    if not KEY_RE.match(key):
        raise ValueError(f"nome de variável inválido: {key}")
    if "\n" in value or "\r" in value:
        raise ValueError("o valor não pode ter quebra de linha")
    p = Path(path)
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    done = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.split("=", 1)[0].strip().removeprefix("export ").strip() == key:
            lines[i] = f"{key}={value}"
            done = True
            break
    if not done:
        lines.append(f"{key}={value}")
    fd, tmp = tempfile.mkstemp(dir=str(p.parent or "."), prefix=".env.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def init_env(root=None) -> dict:
    """Cria .env a partir do exemplo, gera BRIDGE_TOKEN se faltar e cria as pastas de trabalho."""
    root = Path(root) if root else ROOT
    env_path, example = root / ".env", root / ".env.example"
    created = False
    if not env_path.exists():
        if not example.exists():
            raise FileNotFoundError(".env.example não encontrado")
        env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        created = True
    os.chmod(env_path, 0o600)
    values = parse_env_text(env_path.read_text(encoding="utf-8"))
    token_generated = False
    if len(values.get("BRIDGE_TOKEN", "")) < 16:
        set_env(env_path, "BRIDGE_TOKEN", secrets.token_urlsafe(32))
        token_generated = True
    for folder in ("data", "logs", "auth"):
        (root / folder).mkdir(exist_ok=True)
    os.chmod(root / "auth", 0o700)
    return {"created": created, "token_generated": token_generated}
