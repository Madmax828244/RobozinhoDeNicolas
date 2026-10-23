"""Documentação automática dos comandos registrados."""
from __future__ import annotations

from .registry import CATEGORIES, ROLE_NAMES, Registry


def generate_markdown(reg: Registry, prefix: str = ".") -> str:
    c = reg.counts()
    out = [
        "# Comandos do Robô Nicolas 🤖",
        "",
        "> Arquivo gerado automaticamente por `python -m nicolas docs`. Não edite à mão.",
        "",
        f"- **{c['comandos']}** comandos registrados",
        f"- **{c['aliases']}** aliases simples",
        f"- **{c['atalhos']}** atalhos de conversão de unidades (ex.: `{prefix}km-mi 10`)",
        f"- **{c['total_nomes']}** nomes invocáveis no total",
        "",
    ]
    for key, cmds in reg.by_category().items():
        out += [f"## {CATEGORIES[key]} ({len(cmds)})", "", "| Comando | Uso | Descrição | Permissão | Módulo |", "|---|---|---|---|---|"]
        for cmd in cmds:
            usage = f"`{prefix}{cmd.name} {cmd.usage}`".replace(" `", "`") if cmd.usage else f"`{prefix}{cmd.name}`"
            aliases = f" (aliases: {', '.join(cmd.aliases)})" if cmd.aliases else ""
            out.append(f"| {prefix}{cmd.name} | {usage} | {cmd.description}{aliases} | {ROLE_NAMES[cmd.min_role]} | {cmd.module} |")
        out.append("")
    return "\n".join(out)
