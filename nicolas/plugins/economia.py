"""Economia virtual 100% fictícia e recreativa — sem dinheiro real."""
from __future__ import annotations

from ..achievements import DAILY_MISSIONS, SHOP, award
from ..core import CommandError
from ..utils import fmt_duration, num, tag, today_str

AVISO = "💡 Moedas virtuais: só diversão, sem valor real."
MAX_TRANSFER = 100_000
MAX_BET = 500


def _check_rich(ctx, coins: int) -> str:
    return award(ctx.db, ctx.sender, "rico", ctx.now) if coins >= 1000 else ""


def setup(reg):
    E = dict(category="economia")

    @reg.command("carteira", description="Mostra seu saldo de moedas virtuais", usage="[@usuário]",
                 aliases=("saldo", "bal"), **E)
    def carteira(ctx):
        uid = ctx.target() or ctx.sender
        w = ctx.db.wallet(uid)
        extra = f" • sequência diária: {w['streak']} 🔥" if w["streak"] else ""
        return ctx.reply(f"👛 Carteira de {tag(uid)}: *{w['coins']}* moedas virtuais{extra}\n{AVISO}", mentions=[uid])

    @reg.command("diario", description="Resgata a recompensa diária (1x por dia)", aliases=("daily",), **E)
    def diario(ctx):
        today = ctx.today
        yesterday = today_str(ctx.now - 86400, ctx.cfg.tz_offset)
        result = ctx.db.claim_daily(ctx.sender, today, yesterday)
        if result is None:
            return "⏳ Você já resgatou o prêmio de hoje. Volte amanhã!"
        reward, streak = result
        notes = [award(ctx.db, ctx.sender, "pontual", ctx.now)]
        if streak >= 7:
            notes.append(award(ctx.db, ctx.sender, "fiel", ctx.now))
        coins = ctx.db.wallet(ctx.sender)["coins"]
        notes.append(_check_rich(ctx, coins))
        text = f"🎁 {tag(ctx.sender)} recebeu *{reward}* moedas virtuais! Sequência: {streak} dia(s) 🔥 • saldo: {coins}"
        extra = "\n".join(n for n in notes if n)
        return ctx.reply(text + (f"\n{extra}" if extra else ""), mentions=[ctx.sender])

    @reg.command("trabalhar", description="Faz um 'trabalho' virtual e ganha moedas (a cada 1 hora)",
                 aliases=("work",), **E)
    def trabalhar(ctx):
        reward = ctx.bot.rng.randint(30, 80)
        ok, value = ctx.db.claim_work(ctx.sender, ctx.now, 3600, reward)
        if not ok:
            return f"😴 Você está cansado. Volte em {fmt_duration(value)}."
        jobs = ["entregou pizzas 🍕", "programou um bot 🤖", "regou plantas 🌱", "organizou a estante 📚", "cuidou de gatinhos 🐱"]
        return f"💼 Você {ctx.bot.rng.choice(jobs)} e ganhou *{reward}* moedas virtuais! Saldo: {value}"

    @reg.command("loja", description="Mostra os itens da loja virtual", aliases=("shop",), **E)
    def loja(ctx):
        lines = ["🛒 *Loja virtual*"]
        for key, (name, price, desc) in SHOP.items():
            lines.append(f"• *{key}* — {name} — {price} moedas\n   {desc}")
        lines.append(f"\nCompre com *{ctx.prefix}comprar <item>*. {AVISO}")
        return "\n".join(lines)

    @reg.command("comprar", description="Compra um item da loja virtual", usage="<item>", example="comprar pao",
                 min_args=1, cooldown=2, **E)
    def comprar(ctx):
        key = ctx.args[0].lower()
        if key not in SHOP:
            raise CommandError(f"Item inexistente. Veja {ctx.prefix}loja.")
        name, price, _ = SHOP[key]
        coins = ctx.db.buy_item(ctx.sender, key, price, ctx.now)
        note = award(ctx.db, ctx.sender, "comprador", ctx.now)
        return f"🛍️ Você comprou *{name}* por {price} moedas! Saldo: {coins}" + (f"\n{note}" if note else "")

    @reg.command("inventario", description="Mostra seus itens comprados", usage="[@usuário]", aliases=("inv", "mochila"), **E)
    def inventario(ctx):
        uid = ctx.target() or ctx.sender
        items = ctx.db.inventory(uid)
        if not items:
            return ctx.reply(f"🎒 O inventário de {tag(uid)} está vazio. Visite a {ctx.prefix}loja!", mentions=[uid])
        lines = [f"• {SHOP[i['item']][0] if i['item'] in SHOP else i['item']} × {i['qty']}" for i in items]
        return ctx.reply(f"🎒 *Inventário de {tag(uid)}*\n" + "\n".join(lines), mentions=[uid])

    @reg.command("transferir", description="Transfere moedas virtuais para outro participante", usage="@usuário <valor>",
                 example="transferir @5511999999999 50", min_args=2, cooldown=5, aliases=("pix", "dar"), **E)
    def transferir(ctx):
        uid = ctx.target()
        if not uid:
            raise CommandError("Marque quem vai receber.")
        amounts = [a for a in ctx.args if a.isdigit() and len(a) < 8]
        if not amounts:
            raise CommandError("Informe o valor (número inteiro).")
        amount = int(amounts[-1]) if len(amounts) > 1 else int(amounts[0])
        if num(uid) == num(ctx.sender) or num(uid) == num(ctx.msg.bot_id):
            raise CommandError("Destinatário inválido.")
        if not 1 <= amount <= MAX_TRANSFER:
            raise CommandError(f"O valor deve ficar entre 1 e {MAX_TRANSFER}.")
        ctx.db.transfer(ctx.sender, uid, amount, ctx.now)
        return ctx.reply(f"💸 {tag(ctx.sender)} enviou *{amount}* moedas virtuais para {tag(uid)}.", mentions=[ctx.sender, uid])

    @reg.command("topricos", description="Ranking de riqueza virtual do grupo", group_only=True, aliases=("ricos",), **E)
    def topricos(ctx):
        rows = ctx.db.top_members(ctx.chat, "ricos", 10)
        if not rows:
            return "📊 Ainda não há ninguém no ranking."
        medals = ["🥇", "🥈", "🥉"]
        lines = [f"{medals[i] if i < 3 else f'{i + 1}.'} {r['name'] or '+' + r['user_id']} — {r['score']} moedas"
                 for i, r in enumerate(rows)]
        return "💎 *Ranking de riqueza virtual*\n" + "\n".join(lines)

    @reg.command("apostar", description="Aposta moedas VIRTUAIS (45% de chance de dobrar). Só diversão",
                 usage="<valor>", example="apostar 50", min_args=1, cooldown=5, **E)
    def apostar(ctx):
        arg = ctx.args[0].lower()
        coins = ctx.db.wallet(ctx.sender)["coins"]
        bet = min(coins, MAX_BET) if arg in {"tudo", "all"} else int(arg) if arg.isdigit() else 0
        if bet < 1:
            raise CommandError("Informe um valor inteiro maior que zero.")
        if bet > MAX_BET:
            raise CommandError(f"A aposta máxima é {MAX_BET} moedas virtuais.")
        if bet > coins:
            raise CommandError("Você não tem moedas virtuais suficientes.")
        win = ctx.bot.rng.random() < 0.45
        balance = ctx.db.add_coins(ctx.sender, bet if win else -bet, "aposta", ctx.now)
        note = _check_rich(ctx, balance)
        head = f"🎰 Você ganhou *{bet}* moedas virtuais! 🎉" if win else f"🎰 Você perdeu *{bet}* moedas virtuais. 😅"
        return f"{head} Saldo: {balance}\n{AVISO}" + (f"\n{note}" if note else "")

    @reg.command("missoes", description="Mostra suas missões diárias", aliases=("quests",), **E)
    def missoes(ctx):
        prog = ctx.db.get_progress(ctx.sender, ctx.today)
        done = ctx.db.claimed_missions(ctx.sender, ctx.today)
        lines = ["📜 *Missões de hoje*"]
        for mid, desc, key, goal, reward in DAILY_MISSIONS:
            value = min(prog.get(key, 0), goal)
            state = "✅ resgatada" if mid in done else ("🎁 pronta!" if value >= goal else f"{value}/{goal}")
            lines.append(f"• {desc} — {reward} moedas — {state}")
        lines.append(f"\nUse *{ctx.prefix}resgatar* para coletar as missões concluídas.")
        return "\n".join(lines)

    @reg.command("resgatar", description="Resgata as missões diárias concluídas", **E)
    def resgatar(ctx):
        prog = ctx.db.get_progress(ctx.sender, ctx.today)
        total, got = 0, []
        for mid, desc, key, goal, reward in DAILY_MISSIONS:
            if prog.get(key, 0) >= goal and ctx.db.claim_mission(ctx.sender, ctx.today, mid, reward, ctx.now):
                total += reward
                got.append(desc)
        if not got:
            return "ℹ️ Nenhuma missão concluída para resgatar agora."
        note = award(ctx.db, ctx.sender, "missionario", ctx.now)
        return f"🎉 Missões resgatadas: {', '.join(got)}. Total: *{total}* moedas virtuais." + (f"\n{note}" if note else "")
