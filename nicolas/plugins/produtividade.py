"""Produtividade: lembretes, temporizadores, cronômetro e tarefas."""
from __future__ import annotations

from ..core import CommandError
from ..utils import fmt_duration, local_dt, num, parse_duration, tag

MAX_PENDING = 10
MAX_SECONDS = 30 * 86400


def setup(reg):
    P = dict(category="produtividade")

    def _schedule(ctx, seconds: int, text: str) -> str:
        if len(ctx.db.pending_reminders(ctx.chat, ctx.sender)) >= MAX_PENDING:
            raise CommandError(f"Você já tem {MAX_PENDING} lembretes pendentes. Aguarde algum disparar.")
        due = ctx.now + seconds
        ctx.db.add_reminder(ctx.chat, ctx.sender, due, text)
        when = local_dt(due, ctx.cfg.tz_offset).strftime("%d/%m %H:%M")
        return f"⏰ Combinado! Aviso em {fmt_duration(seconds)} (às {when})."

    @reg.command("lembrete", description="Cria um lembrete (30s, 10m, 2h, 1d)", usage="<tempo> <texto>",
                 example="lembrete 30m tomar água", min_args=2, aliases=("lembrar", "remind"), **P)
    def lembrete(ctx):
        seconds = parse_duration(ctx.args[0])
        if not seconds or seconds > MAX_SECONDS:
            raise CommandError("Tempo inválido. Use 30s, 10m, 2h ou 1d (máx. 30 dias).")
        return _schedule(ctx, seconds, ctx.raw[len(ctx.args[0]):].strip()[:200])

    @reg.command("temporizador", description="Inicia um temporizador (30s, 10m, 1h)", usage="<tempo>",
                 example="temporizador 10m", min_args=1, aliases=("timer",), **P)
    def temporizador(ctx):
        seconds = parse_duration(ctx.args[0])
        if not seconds or seconds > 86400:
            raise CommandError("Tempo inválido. Use 30s, 10m ou 1h (máx. 24h).")
        return _schedule(ctx, seconds, "⏳ Seu temporizador terminou!")

    @reg.command("lembretes", description="Lista seus lembretes pendentes neste chat", **P)
    def lembretes(ctx):
        rows = ctx.db.pending_reminders(ctx.chat, ctx.sender)
        if not rows:
            return "⏰ Você não tem lembretes pendentes."
        lines = [f"{i}. {local_dt(r['due'], ctx.cfg.tz_offset).strftime('%d/%m %H:%M')} — {r['text']}"
                 for i, r in enumerate(rows, 1)]
        return "⏰ *Seus lembretes*\n" + "\n".join(lines)

    @reg.command("cronometro", description="Cronômetro pessoal: iniciar, parcial ou parar", usage="iniciar|parcial|parar",
                 example="cronometro iniciar", **P)
    def cronometro(ctx):
        key = f"cron:{num(ctx.sender)}"
        state = ctx.db.game_get(ctx.chat, key)
        action = (ctx.args[0].lower() if ctx.args else "parcial")
        if action in {"iniciar", "start", "comecar", "começar"}:
            ctx.db.game_set(ctx.chat, key, {"t0": ctx.now}, ctx.now)
            return "⏱️ Cronômetro iniciado!"
        if not state:
            return f"⏱️ Nenhum cronômetro ativo. Use {ctx.prefix}cronometro iniciar."
        elapsed = ctx.now - state["t0"]
        if action in {"parar", "stop", "fim"}:
            ctx.db.game_del(ctx.chat, key)
            return f"⏹️ Cronômetro parado: *{fmt_duration(elapsed)}*."
        return f"⏱️ Parcial: *{fmt_duration(elapsed)}*."

    @reg.command("tarefa", description="Adiciona uma tarefa à sua lista", usage="<texto>", example="tarefa estudar inglês",
                 min_args=1, aliases=("todo",), **P)
    def tarefa(ctx):
        if len(ctx.db.tasks(ctx.chat, ctx.sender)) >= 50:
            raise CommandError("Limite de 50 tarefas. Remova algumas com tarefadel.")
        ctx.db.add_task(ctx.chat, ctx.sender, ctx.raw, ctx.now)
        return "✅ Tarefa adicionada."

    @reg.command("tarefas", description="Mostra sua lista de tarefas", aliases=("lista",), **P)
    def tarefas(ctx):
        rows = ctx.db.tasks(ctx.chat, ctx.sender)
        if not rows:
            return f"📝 Sua lista está vazia. Use {ctx.prefix}tarefa <texto>."
        return "📝 *Suas tarefas*\n" + "\n".join(f"{i}. {'✅' if r['done'] else '⬜'} {r['text']}" for i, r in enumerate(rows, 1))

    def _nth(ctx):
        if not ctx.args[0].isdigit():
            raise CommandError("Informe o número da tarefa.")
        rows = ctx.db.tasks(ctx.chat, ctx.sender)
        n = int(ctx.args[0])
        if not 1 <= n <= len(rows):
            raise CommandError("Tarefa inexistente. Veja " + ctx.prefix + "tarefas.")
        return rows[n - 1]

    @reg.command("feito", description="Marca uma tarefa como concluída", usage="<número>", example="feito 1", min_args=1, **P)
    def feito(ctx):
        t = _nth(ctx)
        ctx.db.set_task_done(t["id"])
        return f"🎉 Tarefa concluída: {t['text']}"

    @reg.command("tarefadel", description="Remove uma tarefa da lista", usage="<número>", example="tarefadel 2", min_args=1, **P)
    def tarefadel(ctx):
        t = _nth(ctx)
        ctx.db.delete_task(t["id"])
        return "🗑️ Tarefa removida."
