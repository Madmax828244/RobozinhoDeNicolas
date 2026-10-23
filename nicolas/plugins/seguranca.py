"""Segurança: senhas fortes, análise local de força e tokens aleatórios."""
from __future__ import annotations

import math
import re
import secrets
import string

from ..core import CommandError

AMBIGUOUS = set("Il1O0o")
COMMON = {"123456", "12345678", "password", "senha", "senha123", "qwerty", "abc123", "111111", "admin", "iloveyou",
          "123456789", "654321", "brasil", "123123", "mudar123"}


def generate_password(length: int = 16, symbols: bool = True, ambiguous: bool = False) -> str:
    pools = [string.ascii_lowercase, string.ascii_uppercase, string.digits] + ([("!@#$%&*?-_+=")] if symbols else [])
    if not ambiguous:
        pools = ["".join(c for c in p if c not in AMBIGUOUS) for p in pools]
    alphabet = "".join(pools)
    pwd = [secrets.choice(p) for p in pools] + [secrets.choice(alphabet) for _ in range(length - len(pools))]
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)


def strength(password: str) -> tuple[int, str, list[str]]:
    """Pontuação 0-100, rótulo e dicas. Análise 100% local."""
    tips = []
    pool = 0
    for pattern, size in ((r"[a-z]", 26), (r"[A-Z]", 26), (r"\d", 10), (r"[^A-Za-z0-9]", 32)):
        if re.search(pattern, password):
            pool += size
    entropy = len(password) * math.log2(pool) if pool else 0
    if len(password) < 12:
        tips.append("use 12+ caracteres")
    if not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password):
        tips.append("misture maiúsculas e minúsculas")
    if not re.search(r"\d", password):
        tips.append("inclua números")
    if not re.search(r"[^A-Za-z0-9]", password):
        tips.append("inclua símbolos")
    if re.search(r"(.)\1{2,}", password):
        tips.append("evite caracteres repetidos")
    if password.lower() in COMMON:
        entropy = min(entropy, 10)
        tips.append("é uma senha muito comum")
    score = max(0, min(100, int(entropy / 80 * 100)))
    label = "fraca 🔴" if score < 40 else "média 🟡" if score < 70 else "forte 🟢"
    return score, label, tips


def setup(reg):
    S = dict(category="seguranca")

    @reg.command("senha", description="Gera uma senha forte aleatória (use no privado!)", usage="[tamanho 8-64] [simples]",
                 example="senha 20", aliases=("gerarsenha", "password"), cooldown=3, **S)
    def senha(ctx):
        length = 16
        for a in ctx.args:
            if a.isdigit():
                length = int(a)
        if not 8 <= length <= 64:
            raise CommandError("O tamanho deve ficar entre 8 e 64.")
        simple = any(a.lower() in {"simples", "semsimbolos"} for a in ctx.args)
        pwd = generate_password(length, symbols=not simple)
        warn = "\n⚠️ Em grupos todos veem a mensagem: use este comando no *privado* do bot." if ctx.msg.is_group else ""
        return f"🔐 `{pwd}`{warn}"

    @reg.command("forcasenha", description="Avalia a força de uma senha localmente (não use senhas reais em grupos)",
                 usage="<senha>", example="forcasenha Abc123!", min_args=1, aliases=("testarsenha",), **S)
    def forcasenha(ctx):
        score, label, tips = strength(ctx.raw)
        extra = f"\nDicas: {', '.join(tips)}." if tips else "\nBoa senha!"
        warn = "\n⚠️ Nunca envie senhas reais em grupos." if ctx.msg.is_group else ""
        return f"🔎 Força: *{label}* ({score}/100){extra}{warn}"

    @reg.command("token", description="Gera um token hexadecimal aleatório", usage="[bytes 4-64]", example="token 16",
                 cooldown=3, **S)
    def token(ctx):
        n = int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else 16
        if not 4 <= n <= 64:
            raise CommandError("Use de 4 a 64 bytes.")
        return f"🔑 `{secrets.token_hex(n)}`"
