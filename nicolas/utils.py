"""Funções utilitárias puras, sem dependências externas."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone


def num(uid) -> str:
    """Normaliza qualquer id de usuário (JID) para apenas os dígitos."""
    if uid is None:
        return ""
    return re.sub(r"\D", "", str(uid).split("@")[0].split(":")[0])


def tag(uid) -> str:
    return "@" + num(uid)


def jid_from_number(number: str) -> str:
    return f"{num(number)}@s.whatsapp.net"


def norm(s: str) -> str:
    """Minúsculas e sem acentos (para comparar nomes de comandos)."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


_DUR = re.compile(r"(\d+)\s*([smhd]?)")
_MULT = {"": 60, "s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(text: str) -> int | None:
    """'30s', '10m', '2h', '1d' -> segundos. Número puro = minutos."""
    m = _DUR.fullmatch(text.strip().lower())
    if not m:
        return None
    value = int(m.group(1)) * _MULT[m.group(2)]
    return value if value > 0 else None


def fmt_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    parts = []
    for label, size in (("d", 86400), ("h", 3600), ("min", 60), ("s", 1)):
        if seconds >= size:
            parts.append(f"{seconds // size}{label}")
            seconds %= size
    return " ".join(parts) or "0s"


def local_dt(ts: float, offset_hours: float = -3) -> datetime:
    return datetime.fromtimestamp(ts, timezone(timedelta(hours=offset_hours)))


def today_str(ts: float, offset_hours: float = -3) -> str:
    return local_dt(ts, offset_hours).strftime("%Y-%m-%d")


def truncate(text: str, size: int) -> str:
    return text if len(text) <= size else text[: size - 1] + "…"


def parse_number(text: str) -> float:
    """Aceita '1.5', '1,5'. Levanta ValueError se inválido."""
    value = float(text.strip().replace(",", "."))
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("número inválido")
    return value


def fmt_number(value: float, digits: int = 6) -> str:
    if isinstance(value, int) or float(value).is_integer():
        n = int(value)
        s = str(n)
        if len(s) > 30:
            return f"{value:.6e}"
        return s
    s = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return s or "0"


def level_for(xp: int) -> int:
    return int((max(xp, 0) / 100) ** 0.5) + 1


def xp_for_level(level: int) -> int:
    return int(((level - 1) ** 2) * 100)
