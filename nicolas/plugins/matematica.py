"""Matemática e contas do dia a dia (tudo calculado localmente, sem rede)."""
from __future__ import annotations

import math
import random

from ..core import CommandError
from ..utils import fmt_number, parse_number

ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
         (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def _int(ctx, i=0, lo=0, hi=10**12, what="número"):
    try:
        v = int(ctx.args[i])
    except (IndexError, ValueError):
        raise CommandError(f"Informe um {what} inteiro.")
    if not lo <= v <= hi:
        raise CommandError(f"O {what} deve estar entre {lo} e {hi}.")
    return v


def _num(ctx, i, what):
    try:
        return parse_number(ctx.args[i])
    except (IndexError, ValueError):
        raise CommandError(f"Informe {what} (número).")


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    return all(n % d for d in range(3, math.isqrt(n) + 1, 2))


def setup(reg):
    M = dict(category="utilidades")

    @reg.command("tabuada", description="Mostra a tabuada de um número", usage="<número>", example="tabuada 7", min_args=1, **M)
    def tabuada(ctx):
        n = _int(ctx, hi=10**6)
        return f"✖️ *Tabuada do {n}*\n" + "\n".join(f"{n} x {i} = {n * i}" for i in range(1, 11))

    @reg.command("primo", description="Diz se um número é primo (e o fatora)", usage="<número>", example="primo 97", min_args=1, **M)
    def primo(ctx):
        n = _int(ctx, hi=10**12)
        if _is_prime(n):
            return f"✅ *{n}* é primo."
        if n < 2:
            return f"❌ *{n}* não é primo."
        f, m, d = [], n, 2
        while d * d <= m:
            while m % d == 0:
                f.append(d)
                m //= d
            d += 1
        if m > 1:
            f.append(m)
        return f"❌ *{n}* não é primo. Fatoração: {' × '.join(map(str, f))}"

    @reg.command("fibonacci", description="Primeiros termos da sequência de Fibonacci", usage="<quantidade até 60>",
                 example="fibonacci 10", min_args=1, aliases=("fib",), **M)
    def fibonacci(ctx):
        n = _int(ctx, lo=1, hi=60, what="quantidade")
        a, b, out = 0, 1, []
        for _ in range(n):
            out.append(a)
            a, b = b, a + b
        return "🔢 " + ", ".join(map(str, out))

    @reg.command("mdc", description="Máximo divisor comum de números", usage="<n1> <n2> [...]", example="mdc 12 18",
                 min_args=2, **M)
    def mdc(ctx):
        vals = [_int(ctx, i, lo=1, hi=10**15) for i in range(min(len(ctx.args), 10))]
        return f"MDC({', '.join(map(str, vals))}) = *{math.gcd(*vals)}*"

    @reg.command("mmc", description="Mínimo múltiplo comum de números", usage="<n1> <n2> [...]", example="mmc 4 6",
                 min_args=2, **M)
    def mmc(ctx):
        vals = [_int(ctx, i, lo=1, hi=10**9) for i in range(min(len(ctx.args), 10))]
        return f"MMC({', '.join(map(str, vals))}) = *{math.lcm(*vals)}*"

    @reg.command("romano", description="Converte número (1-3999) em romano ou romano em número", usage="<valor>",
                 example="romano 2026", min_args=1, **M)
    def romano(ctx):
        v = ctx.args[0].upper()
        if v.isdigit():
            n = int(v)
            if not 1 <= n <= 3999:
                raise CommandError("Use um número de 1 a 3999.")
            out = ""
            for val, sym in ROMAN:
                while n >= val:
                    out, n = out + sym, n - val
            return f"🏛️ {v} = *{out}*"
        total, i = 0, 0
        for val, sym in ROMAN:
            while v[i:i + len(sym)] == sym:
                total, i = total + val, i + len(sym)
        if i != len(v) or total == 0:
            raise CommandError("Numeral romano inválido.")
        return f"🏛️ {v} = *{total}*"

    @reg.command("imc", description="Calcula o índice de massa corporal", usage="<peso kg> <altura m>",
                 example="imc 70 1.75", min_args=2, **M)
    def imc(ctx):
        kg, h = _num(ctx, 0, "o peso em kg"), _num(ctx, 1, "a altura em metros (ex.: 1.75)")
        if h > 3:
            h /= 100  # aceita 175 como centímetros
        if not (2 <= kg <= 500 and 0.5 <= h <= 2.8):
            raise CommandError("Valores fora do esperado.")
        v = kg / (h * h)
        faixa = ("abaixo do peso" if v < 18.5 else "peso normal" if v < 25 else "sobrepeso" if v < 30
                 else "obesidade")
        return f"⚖️ IMC: *{v:.1f}* ({faixa}).\nÉ só uma referência geral; não substitui avaliação profissional."

    @reg.command("gorjeta", description="Calcula a gorjeta e divide a conta", usage="<valor> [%] [pessoas]",
                 example="gorjeta 120 10 4", min_args=1, **M)
    def gorjeta(ctx):
        v = _num(ctx, 0, "o valor")
        pct = _num(ctx, 1, "a porcentagem") if len(ctx.args) > 1 else 10
        people = _int(ctx, 2, lo=1, hi=100, what="número de pessoas") if len(ctx.args) > 2 else 1
        if v < 0 or not 0 <= pct <= 100:
            raise CommandError("Valores inválidos.")
        tip = v * pct / 100
        total = v + tip
        return (f"🧾 Conta: R$ {v:.2f} • gorjeta ({fmt_number(pct)}%): R$ {tip:.2f}\n"
                f"Total: *R$ {total:.2f}*" + (f" • por pessoa: *R$ {total / people:.2f}*" if people > 1 else ""))

    @reg.command("desconto", description="Calcula o preço com desconto", usage="<preço> <% de desconto>",
                 example="desconto 200 15", min_args=2, **M)
    def desconto(ctx):
        v, pct = _num(ctx, 0, "o preço"), _num(ctx, 1, "a porcentagem")
        if v < 0 or not 0 <= pct <= 100:
            raise CommandError("Valores inválidos.")
        return f"🏷️ R$ {v:.2f} com {fmt_number(pct)}% de desconto = *R$ {v * (1 - pct / 100):.2f}* (economia de R$ {v * pct / 100:.2f})"

    @reg.command("equipes", description="Sorteia nomes em equipes", usage="<nº de equipes> <nome1> <nome2> ...",
                 example="equipes 2 ana bia caio davi", min_args=3, **M)
    def equipes(ctx):
        k = _int(ctx, lo=2, hi=10, what="número de equipes")
        names = ctx.args[1:41]
        if len(names) < k:
            raise CommandError("Tem menos nomes do que equipes.")
        names = list(names)
        random.shuffle(names)
        teams = [names[i::k] for i in range(k)]
        return "👥 *Equipes sorteadas*\n" + "\n".join(f"*Equipe {i + 1}:* {', '.join(t)}" for i, t in enumerate(teams))

    @reg.command("inverter", description="Inverte um texto", usage="<texto>", example="inverter bom dia", min_args=1, **M)
    def inverter(ctx):
        return ctx.raw[::-1][:1000]

    @reg.command("palindromo", description="Diz se uma frase é palíndromo", usage="<texto>", example="palindromo ovo",
                 min_args=1, **M)
    def palindromo(ctx):
        import unicodedata
        s = "".join(c for c in unicodedata.normalize("NFD", ctx.raw.lower()) if c.isalnum())
        return "✅ É um palíndromo!" if s and s == s[::-1] else "❌ Não é um palíndromo."
