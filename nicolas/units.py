"""Conversão de unidades (tabelas de fatores para a unidade-base de cada grandeza)."""
from __future__ import annotations

TABLES = {
    "comprimento": {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0, "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344},
    "massa": {"mg": 1e-6, "g": 1e-3, "kg": 1.0, "t": 1000.0, "oz": 0.028349523125, "lb": 0.45359237},
    "volume": {"ml": 0.001, "l": 1.0, "m3": 1000.0, "gal": 3.785411784, "xic": 0.24},
    "tempo": {"s": 1.0, "min": 60.0, "h": 3600.0, "d": 86400.0, "sem": 604800.0},
    "dados": {"b": 1.0, "kb": 1000.0, "mb": 1e6, "gb": 1e9, "tb": 1e12, "kib": 1024.0, "mib": 1024.0 ** 2, "gib": 1024.0 ** 3},
    "velocidade": {"ms": 1.0, "kmh": 1 / 3.6, "mph": 0.44704, "nos": 0.514444},
    "area": {"m2": 1.0, "km2": 1e6, "ha": 10000.0, "ft2": 0.09290304, "ac": 4046.8564224},
}
TEMPS = ("c", "f", "k")
ALIASES = {"°c": "c", "celsius": "c", "°f": "f", "fahrenheit": "f", "kelvin": "k", "km/h": "kmh", "m/s": "ms",
           "milha": "mi", "milhas": "mi", "quilometros": "km", "quilômetros": "km", "metros": "m", "libras": "lb",
           "litros": "l", "segundos": "s", "minutos": "min", "horas": "h", "dias": "d", "semanas": "sem"}


class UnitError(ValueError):
    pass


def category_of(unit: str):
    if unit in TEMPS:
        return "temperatura"
    for cat, table in TABLES.items():
        if unit in table:
            return cat
    return None


def canon(unit: str) -> str:
    u = unit.strip().lower()
    return ALIASES.get(u, u)


def convert(value: float, src: str, dst: str) -> float:
    src, dst = canon(src), canon(dst)
    a, b = category_of(src), category_of(dst)
    if a is None:
        raise UnitError(f"Unidade desconhecida: {src}")
    if b is None:
        raise UnitError(f"Unidade desconhecida: {dst}")
    if a != b:
        raise UnitError(f"Não dá para converter {a} em {b}.")
    if a == "temperatura":
        celsius = value if src == "c" else (value - 32) * 5 / 9 if src == "f" else value - 273.15
        if celsius < -273.15 - 1e-9:
            raise UnitError("Temperatura abaixo do zero absoluto.")
        return celsius if dst == "c" else celsius * 9 / 5 + 32 if dst == "f" else celsius + 273.15
    table = TABLES[a]
    return value * table[src] / table[dst]


def all_units() -> dict[str, list[str]]:
    out = {cat: list(table) for cat, table in TABLES.items()}
    out["temperatura"] = list(TEMPS)
    return out
