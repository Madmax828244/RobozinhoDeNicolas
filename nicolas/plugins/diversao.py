"""Diversão: piadas, curiosidades, sorteios, dados e decisões."""
from __future__ import annotations

import hashlib

from ..core import CommandError
from ..data import BOLA8, CURIOSIDADES, DESAFIOS, FRASES, PIADAS
from ..registry import ROLE_ADMIN
from ..utils import tag


def setup(reg):
    D = dict(category="diversao")

    @reg.command("piada", description="Conta uma piada", aliases=("joke",), cooldown=3, **D)
    def piada(ctx):
        return "😂 " + ctx.bot.rng.choice(PIADAS)

    @reg.command("curiosidade", description="Mostra uma curiosidade interessante", aliases=("sabia",), cooldown=3, **D)
    def curiosidade(ctx):
        return "💡 *Você sabia?*\n" + ctx.bot.rng.choice(CURIOSIDADES)

    @reg.command("frase", description="Envia uma frase de incentivo", aliases=("motivacao",), cooldown=3, **D)
    def frase(ctx):
        return "💬 " + ctx.bot.rng.choice(FRASES)

    @reg.command("bola8", description="Bola 8 mágica: responda sim/não", usage="<pergunta>",
                 example="bola8 vai chover hoje?", min_args=1, aliases=("8ball",), **D)
    def bola8(ctx):
        return f"🎱 {ctx.bot.rng.choice(BOLA8)}"

    @reg.command("dado", description="Rola um dado (padrão 6 lados, máx. 1000)", usage="[lados] [quantidade]",
                 example="dado 20 2", aliases=("d",), **D)
    def dado(ctx):
        sides, qty = 6, 1
        args = list(ctx.args)
        if ctx.invoked.startswith("d") and ctx.invoked[1:].isdigit():  # atalhos .d20, .d100...
            args = [ctx.invoked[1:]] + args
        try:
            if args:
                sides = int(args[0])
            if len(args) > 1:
                qty = int(args[1])
        except ValueError:
            raise CommandError("Use números inteiros. Ex.: dado 20 2")
        if not 2 <= sides <= 1000 or not 1 <= qty <= 10:
            raise CommandError("Lados: 2 a 1000 • quantidade: 1 a 10.")
        rolls = [ctx.bot.rng.randint(1, sides) for _ in range(qty)]
        extra = f" (soma {sum(rolls)})" if qty > 1 else ""
        return f"🎲 d{sides}: {', '.join(map(str, rolls))}{extra}"

    # Atalhos para dados comuns: .d4 .d6 .d8 .d10 .d12 .d20 .d100
    for sides in (4, 6, 8, 10, 12, 20, 100):
        reg.add_alias(f"d{sides}", "dado")

    @reg.command("moeda", description="Joga uma moeda (cara ou coroa)", aliases=("caraoucoroa",), **D)
    def moeda(ctx):
        return "🪙 " + ctx.bot.rng.choice(["Cara!", "Coroa!"])

    @reg.command("escolher", description="Escolhe uma opção entre várias separadas por | ou vírgula",
                 usage="a | b | c", example="escolher pizza | hambúrguer | sushi", min_args=2, **D)
    def escolher(ctx):
        sep = "|" if "|" in ctx.raw else ","
        options = [o.strip() for o in ctx.raw.split(sep) if o.strip()]
        if len(options) < 2:
            raise CommandError("Informe pelo menos 2 opções separadas por | ou vírgula.")
        return f"🤔 Eu escolho: *{ctx.bot.rng.choice(options[:30])}*"

    @reg.command("roleta", description="Roleta virtual de entretenimento: gira entre as opções", usage="a | b | c",
                 example="roleta lavar louça | tirar o lixo | descansar", min_args=2, **D)
    def roleta(ctx):
        sep = "|" if "|" in ctx.raw else ","
        options = [o.strip() for o in ctx.raw.split(sep) if o.strip()][:12]
        if len(options) < 2:
            raise CommandError("Informe pelo menos 2 opções separadas por | ou vírgula.")
        return f"🎡 A roleta girou e parou em: *{ctx.bot.rng.choice(options)}*"

    @reg.command("sortenumero", description="Sorteia um número entre dois valores", usage="<mín> <máx>",
                 example="sortenumero 1 100", min_args=2, **D)
    def sortenumero(ctx):
        try:
            a, b = int(ctx.args[0]), int(ctx.args[1])
        except ValueError:
            raise CommandError("Use números inteiros.")
        if a > b:
            a, b = b, a
        if b - a > 10**9:
            raise CommandError("Intervalo muito grande.")
        return f"🔢 Número sorteado entre {a} e {b}: *{ctx.bot.rng.randint(a, b)}*"

    @reg.command("sorteio", description="Sorteio transparente entre os participantes ativos ou uma lista",
                 usage="[quantidade] [nome1, nome2, ...]", example="sorteio 1", category="diversao", cooldown=5)
    def sorteio(ctx):
        qty = 1
        raw = ctx.raw
        if ctx.args and ctx.args[0].isdigit():
            qty = int(ctx.args[0])
            raw = raw[len(ctx.args[0]):].strip()
        if not 1 <= qty <= 10:
            raise CommandError("Sorteie de 1 a 10 vencedores.")
        if raw:
            pool = [x.strip() for x in raw.split(",") if x.strip()]
            labels, mentions = pool, []
            origin = "lista informada"
        else:
            if not ctx.msg.is_group:
                raise CommandError("Sem lista, o sorteio funciona só em grupos (usa os participantes ativos).")
            pool = [f"+{u}" for u in ctx.db.known_members(ctx.chat)]
            labels, mentions = pool, []
            origin = "participantes que já falaram no grupo"
        pool = list(dict.fromkeys(pool))
        if len(pool) < qty:
            raise CommandError(f"Só há {len(pool)} participante(s) disponíveis para sortear.")
        winners = ctx.bot.rng.sample(pool, qty)
        seed = hashlib.sha256((ctx.chat + str(ctx.now) + ",".join(pool)).encode()).hexdigest()[:10]
        lines = ["🎁 *Sorteio*", f"Origem: {origin} • participantes: {len(pool)}", ""]
        for i, w in enumerate(winners, 1):
            if w.startswith("+") and w[1:].isdigit():
                jid = f"{w[1:]}@s.whatsapp.net"
                mentions.append(jid)
                lines.append(f"🏆 {i}º: {tag(jid)}")
            else:
                lines.append(f"🏆 {i}º: {w}")
        lines.append(f"\n🔍 Código de verificação: {seed}")
        return ctx.reply("\n".join(lines), mentions=mentions)

    @reg.command("desafio", description="Mostra o desafio seguro do dia", aliases=("desafiododia",), **D)
    def desafio(ctx):
        idx = int(hashlib.sha256(ctx.today.encode()).hexdigest(), 16) % len(DESAFIOS)
        return (f"🏁 *Desafio do dia ({ctx.today})*\n{DESAFIOS[idx]}\n\n"
                f"Fez? Use *{ctx.prefix}desafiofeito* para ganhar moedas virtuais (1x por dia).")

    @reg.command("desafiofeito", description="Resgata a recompensa do desafio do dia (1x por dia)", **D)
    def desafiofeito(ctx):
        if not ctx.db.claim_mission(ctx.sender, ctx.today, "desafio", 25, ctx.now):
            return "✅ Você já resgatou o desafio de hoje. Volte amanhã!"
        return ctx.reply(f"🎉 {tag(ctx.sender)} completou o desafio do dia e ganhou *25 moedas virtuais*!",
                         mentions=[ctx.sender])

    @reg.command("casal", description="Escolhe aleatoriamente dois participantes ativos (só diversão)", group_only=True,
                 **D)
    def casal(ctx):
        members = ctx.db.known_members(ctx.chat)
        if len(members) < 2:
            raise CommandError("Preciso ver pelo menos 2 participantes falando para formar a dupla.")
        a, b = ctx.bot.rng.sample(members, 2)
        ja, jb = f"{a}@s.whatsapp.net", f"{b}@s.whatsapp.net"
        return ctx.reply(f"🤝 Dupla do dia (só diversão!): {tag(ja)} e {tag(jb)}", mentions=[ja, jb])

    @reg.command("porcentagem", description="Mede aleatoriamente uma 'porcentagem' divertida", usage="<assunto>",
                 example="porcentagem sono", min_args=1, aliases=("medidor",), **D)
    def porcentagem(ctx):
        assunto = ctx.raw[:40]
        return f"📊 {assunto}: *{ctx.bot.rng.randint(0, 100)}%* (resultado aleatório, só para rir 😄)"
