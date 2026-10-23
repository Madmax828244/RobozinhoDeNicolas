"""Administração de grupos. Todos os comandos exigem permissão adequada."""
from __future__ import annotations

import re

from ..core import CommandError, Reply
from ..registry import ROLE_ADMIN, ROLE_MOD, ROLE_NAMES, ROLE_OWNER
from ..security import is_owner
from ..utils import fmt_duration, norm, num, parse_duration, tag, level_for, local_dt

HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _target(ctx):
    uid = ctx.target()
    if not uid:
        raise CommandError(f"Marque o participante, responda a mensagem dele ou informe o número. Ex.: {ctx.prefix}{ctx.cmd.example}")
    return uid


def _punishable(ctx):
    uid = _target(ctx)
    if ctx.is_protected(uid):
        raise CommandError("Esse participante é administrador/dono (ou o próprio bot) e não pode ser punido por mim.")
    return uid


def _reason(ctx):
    words = [a for a in ctx.args if not a.startswith("@") and not a.lstrip("+").isdigit()]
    return " ".join(words)[:150] or "sem motivo informado"


def _can_manage_roles(ctx) -> bool:
    return is_owner(ctx.cfg, ctx.sender) or ctx.msg.sender_is_admin or num(ctx.sender) in {num(a) for a in ctx.msg.group_admins}


def _onoff(ctx, field: str, label: str):
    if not ctx.args or norm(ctx.args[0]) not in {"on", "off", "ligar", "desligar", "ativar", "desativar", "1", "0"}:
        state = "ativado ✅" if ctx.group[field] else "desativado ⚪"
        return f"{label} está {state}. Use *{ctx.prefix}{ctx.cmd.name} on* ou *off*."
    on = norm(ctx.args[0]) in {"on", "ligar", "ativar", "1"}
    ctx.db.set_group(ctx.chat, **{field: on})
    ctx.db.log(ctx.chat, ctx.sender, ctx.cmd.name, detail="on" if on else "off", now=ctx.now)
    extra = ""
    if on and not ctx.msg.bot_is_admin and field in {"antilink", "antiflood", "antifake"}:
        extra = "\n⚠️ Para remover mensagens/participantes eu preciso ser administrador do grupo."
    return f"{'✅' if on else '⚪'} {label} {'ativado' if on else 'desativado'}.{extra}"


def setup(reg):
    A = dict(category="admin", group_only=True)

    @reg.command("ban", description="Bane um participante (e remove, se eu for admin)", usage="@usuário [motivo]",
                 example="ban @5511999999999 spam", min_role=ROLE_ADMIN, **A)
    def ban(ctx):
        uid = _punishable(ctx)
        ctx.db.ban(ctx.chat, uid, _reason(ctx), ctx.sender, ctx.now)
        ctx.db.log(ctx.chat, ctx.sender, "ban", uid, _reason(ctx), ctx.now)
        actions = [ctx.kick_action(uid)] if ctx.msg.bot_is_admin else []
        note = "" if ctx.msg.bot_is_admin else "\n⚠️ Não sou admin: registrei o banimento, mas não consigo remover."
        return ctx.reply(f"🔨 {tag(uid)} foi banido.{note}", mentions=[uid], actions=actions)

    @reg.command("desban", description="Remove o banimento de um participante", usage="@usuário",
                 example="desban @5511999999999", min_role=ROLE_ADMIN, aliases=("unban",), **A)
    def desban(ctx):
        uid = _target(ctx)
        if not ctx.db.unban(ctx.chat, uid):
            return f"ℹ️ {tag(uid)} não estava banido."
        ctx.db.log(ctx.chat, ctx.sender, "desban", uid, now=ctx.now)
        return ctx.reply(f"✅ Banimento de {tag(uid)} removido.", mentions=[uid])

    @reg.command("banidos", description="Lista os participantes banidos", min_role=ROLE_ADMIN, **A)
    def banidos(ctx):
        rows = ctx.db.bans(ctx.chat)
        if not rows:
            return "✅ Nenhum banido neste grupo."
        return "🔨 *Banidos*\n" + "\n".join(f"• +{r['user_id']} — {r['reason']}" for r in rows[:30])

    @reg.command("expulsar", description="Remove um participante sem banir", usage="@usuário",
                 example="expulsar @5511999999999", min_role=ROLE_ADMIN, aliases=("kick",), **A)
    def expulsar(ctx):
        uid = _punishable(ctx)
        if not ctx.msg.bot_is_admin:
            raise CommandError("Preciso ser administrador do grupo para remover participantes.")
        ctx.db.log(ctx.chat, ctx.sender, "kick", uid, now=ctx.now)
        return ctx.reply(f"👢 {tag(uid)} foi removido.", mentions=[uid], actions=[ctx.kick_action(uid)])

    @reg.command("adv", description="Adverte um participante (3 advertências = remoção)", usage="@usuário [motivo]",
                 example="adv @5511999999999 linguagem", min_role=ROLE_MOD, aliases=("advertir",), **A)
    def adv(ctx):
        uid = _punishable(ctx)
        reason = _reason(ctx)
        count = ctx.db.add_warning(ctx.chat, uid, reason, ctx.sender, ctx.now)
        ctx.db.log(ctx.chat, ctx.sender, "adv", uid, reason, ctx.now)
        limit = ctx.group["max_warns"] or ctx.cfg.max_warns
        text = f"⚠️ {tag(uid)} recebeu uma advertência ({count}/{limit}). Motivo: {reason}"
        actions = []
        if count >= limit:
            ctx.db.clear_warnings(ctx.chat, uid)
            if ctx.msg.bot_is_admin:
                actions.append(ctx.kick_action(uid))
                text += "\n🚫 Limite atingido: participante removido."
            else:
                text += "\n🚫 Limite atingido, mas não sou admin para remover."
        return ctx.reply(text, mentions=[uid], actions=actions)

    @reg.command("advs", description="Mostra as advertências de um participante", usage="[@usuário]",
                 example="advs @5511999999999", min_role=ROLE_MOD, aliases=("advertencias",), **A)
    def advs(ctx):
        uid = ctx.target() or ctx.sender
        rows = ctx.db.warnings(ctx.chat, uid)
        if not rows:
            return ctx.reply(f"✅ {tag(uid)} não tem advertências.", mentions=[uid])
        lines = [f"{i}. {r['reason']}" for i, r in enumerate(rows, 1)]
        return ctx.reply(f"⚠️ Advertências de {tag(uid)}:\n" + "\n".join(lines), mentions=[uid])

    @reg.command("resetadv", description="Zera as advertências de um participante", usage="@usuário",
                 example="resetadv @5511999999999", min_role=ROLE_ADMIN, aliases=("limparadv",), **A)
    def resetadv(ctx):
        uid = _target(ctx)
        n = ctx.db.clear_warnings(ctx.chat, uid)
        ctx.db.log(ctx.chat, ctx.sender, "resetadv", uid, now=ctx.now)
        return ctx.reply(f"✅ {n} advertência(s) de {tag(uid)} removida(s).", mentions=[uid])

    @reg.command("mute", description="Silencia um participante (apago as mensagens dele)", usage="@usuário [tempo]",
                 example="mute @5511999999999 30m", min_role=ROLE_MOD, aliases=("silenciar",), **A)
    def mute(ctx):
        uid = _punishable(ctx)
        seconds = 1800
        for a in ctx.args:
            d = parse_duration(a) if not a.startswith("@") and not a.isdigit() else None
            if d:
                seconds = d
        seconds = min(seconds, 7 * 86400)
        ctx.db.set_mute(ctx.chat, uid, ctx.now + seconds, ctx.sender)
        ctx.db.log(ctx.chat, ctx.sender, "mute", uid, fmt_duration(seconds), ctx.now)
        note = "" if ctx.msg.bot_is_admin else "\n⚠️ Sem ser admin eu não consigo apagar as mensagens dele."
        return ctx.reply(f"🔇 {tag(uid)} silenciado por {fmt_duration(seconds)}.{note}", mentions=[uid])

    @reg.command("desmute", description="Remove o silenciamento", usage="@usuário", example="desmute @5511999999999",
                 min_role=ROLE_MOD, aliases=("dessilenciar",), **A)
    def desmute(ctx):
        uid = _target(ctx)
        if not ctx.db.clear_mute(ctx.chat, uid):
            return f"ℹ️ {tag(uid)} não estava silenciado."
        ctx.db.log(ctx.chat, ctx.sender, "desmute", uid, now=ctx.now)
        return ctx.reply(f"🔊 {tag(uid)} pode falar de novo.", mentions=[uid])

    @reg.command("regras", category="admin", description="Mostra as regras do grupo", group_only=True)
    def regras(ctx):
        return f"📜 *Regras do grupo*\n\n{ctx.group['rules']}" if ctx.group["rules"] else \
            f"📜 Este grupo ainda não tem regras. Admins: use {ctx.prefix}setregras <texto>."

    @reg.command("setregras", description="Define as regras do grupo", usage="<texto>",
                 example="setregras 1. Respeite todos", min_role=ROLE_ADMIN, min_args=1, **A)
    def setregras(ctx):
        ctx.db.set_group(ctx.chat, rules=ctx.raw[:1500])
        ctx.db.log(ctx.chat, ctx.sender, "setregras", now=ctx.now)
        return "✅ Regras atualizadas."

    @reg.command("setdesc", description="Define a descrição do grupo", usage="<texto>",
                 example="setdesc Grupo da turma", min_role=ROLE_ADMIN, min_args=1, **A)
    def setdesc(ctx):
        text = ctx.raw[:500]
        ctx.db.set_group(ctx.chat, description=text)
        ctx.db.log(ctx.chat, ctx.sender, "setdesc", now=ctx.now)
        actions = [{"type": "set_description", "chat_id": ctx.chat, "text": text}] if ctx.msg.bot_is_admin else []
        note = "" if ctx.msg.bot_is_admin else " (salva no bot; para mudar no WhatsApp preciso ser admin)"
        return ctx.reply(f"✅ Descrição atualizada{note}.", actions=actions)

    @reg.command("fechargrupo", description="Fecha o grupo: só administradores enviam mensagens", example="fechargrupo",
                 aliases=("fechar",), min_role=ROLE_ADMIN, **A)
    def fechargrupo(ctx):
        if not ctx.msg.bot_is_admin:
            return "⚠️ Preciso ser administrador do grupo para fechá-lo."
        ctx.db.log(ctx.chat, ctx.sender, "fechargrupo", now=ctx.now)
        return ctx.reply("🔒 Grupo fechado: só administradores podem enviar mensagens.",
                         actions=[{"type": "set_announce", "chat_id": ctx.chat, "announce": True}])

    @reg.command("abrirgrupo", description="Abre o grupo: todos podem enviar mensagens", example="abrirgrupo",
                 aliases=("abrir",), min_role=ROLE_ADMIN, **A)
    def abrirgrupo(ctx):
        if not ctx.msg.bot_is_admin:
            return "⚠️ Preciso ser administrador do grupo para abri-lo."
        ctx.db.log(ctx.chat, ctx.sender, "abrirgrupo", now=ctx.now)
        return ctx.reply("🔓 Grupo aberto: todos podem enviar mensagens.",
                         actions=[{"type": "set_announce", "chat_id": ctx.chat, "announce": False}])

    @reg.command("renomear", description="Muda o nome do grupo", usage="<novo nome>", example="renomear Turma 2026",
                 min_role=ROLE_ADMIN, min_args=1, **A)
    def renomear(ctx):
        if not ctx.msg.bot_is_admin:
            return "⚠️ Preciso ser administrador do grupo para mudar o nome."
        name = ctx.raw.strip()[:100]
        ctx.db.log(ctx.chat, ctx.sender, "renomear", detail=name, now=ctx.now)
        return ctx.reply(f"✅ Nome do grupo alterado para *{name}*.",
                         actions=[{"type": "set_subject", "chat_id": ctx.chat, "text": name}])

    @reg.command("membro", description="Exibe informações de um participante", usage="[@usuário]",
                 example="membro @5511999999999", min_role=ROLE_MOD, aliases=("infomembro",), **A)
    def membro(ctx):
        uid = ctx.target() or ctx.sender
        st = ctx.db.stats(ctx.chat, uid)
        user = ctx.db.user(uid)
        muted = ctx.db.mute_until(ctx.chat, uid, ctx.now)
        role = "administrador" if num(uid) in {num(a) for a in ctx.msg.group_admins} else \
            {"mod": "moderador", "admin": "autorizado"}.get(ctx.db.role(ctx.chat, uid), "membro")
        lines = [f"👤 *{user['name'] or tag(uid)}* (+{num(uid)})",
                 f"Cargo: {role}", f"Nível {level_for(st['xp'])} • {st['xp']} XP • {st['msgs']} mensagens",
                 f"Advertências: {ctx.db.warning_count(ctx.chat, uid)}",
                 f"Silenciado: {'sim, por mais ' + fmt_duration(muted - ctx.now) if muted else 'não'}",
                 f"Banido: {'sim' if ctx.db.is_banned(ctx.chat, uid) else 'não'}"]
        return ctx.reply("\n".join(lines), mentions=[uid])

    @reg.command("proibir", description="Adiciona uma palavra à lista de palavras proibidas", usage="<palavra>",
                 example="proibir golpe", min_role=ROLE_ADMIN, min_args=1, **A)
    def proibir(ctx):
        word = norm(ctx.raw)[:40].strip()
        if len(word) < 2:
            raise CommandError("Informe uma palavra com pelo menos 2 letras.")
        added = ctx.db.add_badword(ctx.chat, word)
        ctx.db.log(ctx.chat, ctx.sender, "proibir", detail=word, now=ctx.now)
        return f"🚫 '{word}' adicionada." if added else f"ℹ️ '{word}' já estava na lista."

    @reg.command("liberar", description="Remove uma palavra da lista de proibidas", usage="<palavra>",
                 example="liberar golpe", min_role=ROLE_ADMIN, min_args=1, **A)
    def liberar(ctx):
        word = norm(ctx.raw).strip()
        ok = ctx.db.del_badword(ctx.chat, word)
        return f"✅ '{word}' liberada." if ok else "ℹ️ Essa palavra não estava na lista."

    @reg.command("proibidas", description="Lista as palavras proibidas", min_role=ROLE_ADMIN, **A)
    def proibidas(ctx):
        words = ctx.db.badwords(ctx.chat)
        return "🚫 *Palavras proibidas*\n" + ", ".join(words) if words else "✅ Nenhuma palavra proibida cadastrada."

    @reg.command("antilink", description="Liga/desliga o anti-link (apaga links e adverte)", usage="on|off",
                 example="antilink on", min_role=ROLE_ADMIN, **A)
    def antilink(ctx):
        return _onoff(ctx, "antilink", "Anti-link")

    @reg.command("antiflood", description="Liga/desliga o anti-flood (silencia quem floda)", usage="on|off",
                 example="antiflood on", min_role=ROLE_ADMIN, **A)
    def antiflood(ctx):
        return _onoff(ctx, "antiflood", "Anti-flood")

    @reg.command("antifake", description="Liga/desliga o anti-fake (remove números de outros países)", usage="on|off",
                 example="antifake on", min_role=ROLE_ADMIN, **A)
    def antifake(ctx):
        return _onoff(ctx, "antifake", "Anti-fake") + \
            f"\nPrefixos permitidos: {', '.join(ctx.cfg.antifake_prefixes)}"

    @reg.command("bemvindo", description="Liga/desliga as mensagens de boas-vindas e despedida", usage="on|off",
                 example="bemvindo on", min_role=ROLE_ADMIN, **A)
    def bemvindo(ctx):
        return _onoff(ctx, "welcome_on", "Boas-vindas")

    @reg.command("setbemvindo", description="Define a mensagem de boas-vindas ({usuario} {grupo} {regras})",
                 usage="<texto>", example="setbemvindo Olá {usuario}, bem-vindo ao {grupo}!",
                 min_role=ROLE_ADMIN, min_args=1, **A)
    def setbemvindo(ctx):
        ctx.db.set_group(ctx.chat, welcome=ctx.raw[:800])
        return "✅ Mensagem de boas-vindas atualizada."

    @reg.command("setdespedida", description="Define a mensagem de despedida ({usuario} {grupo})", usage="<texto>",
                 example="setdespedida {usuario} saiu. Até logo!", min_role=ROLE_ADMIN, min_args=1, **A)
    def setdespedida(ctx):
        ctx.db.set_group(ctx.chat, goodbye=ctx.raw[:800])
        return "✅ Mensagem de despedida atualizada."

    def _set_role(ctx, role: str):
        if not _can_manage_roles(ctx):
            raise CommandError("Só administradores do grupo (ou o dono) podem alterar cargos.")
        uid = _target(ctx)
        if is_owner(ctx.cfg, uid):
            raise CommandError("O dono do bot já tem todas as permissões.")
        ctx.db.set_role(ctx.chat, uid, role)
        ctx.db.log(ctx.chat, ctx.sender, "cargo", uid, role, ctx.now)
        names = {"mod": "moderador", "admin": "administrador autorizado", "membro": "membro"}
        return ctx.reply(f"🎖️ {tag(uid)} agora é *{names[role]}*.", mentions=[uid])

    @reg.command("cargo", description="Define o cargo no bot: membro, mod ou admin", usage="@usuário <membro|mod|admin>",
                 example="cargo @5511999999999 mod", min_role=ROLE_ADMIN, min_args=2, **A)
    def cargo(ctx):
        word = next((norm(a) for a in ctx.args if norm(a) in {"membro", "mod", "moderador", "admin"}), None)
        if not word:
            raise CommandError("Cargos válidos: membro, mod, admin.")
        return _set_role(ctx, "mod" if word.startswith("mod") else word)

    @reg.command("autorizar", description="Autoriza um participante como administrador do bot", usage="@usuário",
                 example="autorizar @5511999999999", min_role=ROLE_ADMIN, **A)
    def autorizar(ctx):
        return _set_role(ctx, "admin")

    @reg.command("desautorizar", description="Remove a autorização de administrador do bot", usage="@usuário",
                 example="desautorizar @5511999999999", min_role=ROLE_ADMIN, **A)
    def desautorizar(ctx):
        return _set_role(ctx, "membro")

    @reg.command("autorizados", description="Lista moderadores e administradores autorizados", min_role=ROLE_MOD, **A)
    def autorizados(ctx):
        rows = ctx.db.roles_in(ctx.chat)
        if not rows:
            return "ℹ️ Ninguém tem cargo extra neste grupo."
        names = {"mod": "moderador", "admin": "autorizado"}
        return "🎖️ *Cargos*\n" + "\n".join(f"• +{r['user_id']} — {names.get(r['role'], r['role'])}" for r in rows)

    @reg.command("logs", description="Mostra as últimas ações administrativas", usage="[quantidade]",
                 example="logs 10", min_role=ROLE_ADMIN, **A)
    def logs(ctx):
        n = 10
        if ctx.args and ctx.args[0].isdigit():
            n = max(1, min(int(ctx.args[0]), 25))
        rows = ctx.db.logs(ctx.chat, n)
        if not rows:
            return "📋 Nenhuma ação registrada ainda."
        lines = []
        for r in rows:
            when = local_dt(r["ts"], ctx.cfg.tz_offset).strftime("%d/%m %H:%M")
            target = f" → +{r['target']}" if r["target"] else ""
            detail = f" ({r['detail']})" if r["detail"] else ""
            lines.append(f"{when} • {r['actor']} • {r['action']}{target}{detail}")
        return "📋 *Registro administrativo*\n" + "\n".join(lines)

    @reg.command("horario", description="Define o horário de funcionamento dos comandos", usage="<abre> <fecha>|off",
                 example="horario 08:00 22:00", min_role=ROLE_ADMIN, **A)
    def horario(ctx):
        g = ctx.group
        if not ctx.args:
            if not g["hours_on"]:
                return "🕒 Sem restrição de horário. Use horario 08:00 22:00 para definir."
            fmt = lambda m: f"{m // 60:02d}:{m % 60:02d}"
            return f"🕒 Comandos liberados das {fmt(g['open_min'])} às {fmt(g['close_min'])}."
        if norm(ctx.args[0]) in {"off", "desligar"}:
            ctx.db.set_group(ctx.chat, hours_on=False)
            return "✅ Restrição de horário desativada."
        if len(ctx.args) < 2:
            raise CommandError("Informe abertura e fechamento. Ex.: horario 08:00 22:00")
        a, b = HHMM.match(ctx.args[0]), HHMM.match(ctx.args[1])
        if not a or not b:
            raise CommandError("Use o formato HH:MM, por exemplo 08:00 22:00.")
        ctx.db.set_group(ctx.chat, hours_on=True, open_min=int(a[1]) * 60 + int(a[2]), close_min=int(b[1]) * 60 + int(b[2]))
        ctx.db.log(ctx.chat, ctx.sender, "horario", detail=f"{ctx.args[0]}-{ctx.args[1]}", now=ctx.now)
        return f"✅ Comandos liberados das {ctx.args[0]} às {ctx.args[1]} (admins e moderadores sempre podem usar)."

    @reg.command("config", description="Mostra as configurações de segurança do grupo", min_role=ROLE_ADMIN,
                 aliases=("configuracoes",), **A)
    def config(ctx):
        g = ctx.group
        yn = lambda v: "✅" if v else "⚪"
        return "\n".join([
            "⚙️ *Configurações do grupo*",
            f"{yn(g['antilink'])} Anti-link   {yn(g['antiflood'])} Anti-flood   {yn(g['antifake'])} Anti-fake",
            f"{yn(g['welcome_on'])} Boas-vindas   {yn(g['hours_on'])} Horário",
            f"Prefixo: {ctx.prefix} • limite de advertências: {g['max_warns']}",
            f"Palavras proibidas: {len(ctx.db.badwords(ctx.chat))}",
            f"Módulos desativados: {', '.join(g['disabled_modules']) or 'nenhum'}",
            f"Bot é admin do grupo: {'sim' if ctx.msg.bot_is_admin else 'não (algumas ações ficam limitadas)'}",
        ])

    @reg.command("maxadv", description="Define o limite de advertências antes da remoção (2 a 10)", usage="<número>",
                 example="maxadv 3", min_role=ROLE_ADMIN, min_args=1, **A)
    def maxadv(ctx):
        if not ctx.args[0].isdigit() or not 2 <= int(ctx.args[0]) <= 10:
            raise CommandError("Informe um número de 2 a 10.")
        ctx.db.set_group(ctx.chat, max_warns=int(ctx.args[0]))
        return f"✅ Limite de advertências: {ctx.args[0]}."
