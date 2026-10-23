"""Módulo de inteligência artificial (provedor definido por variáveis de ambiente)."""
from __future__ import annotations

from ..ai_client import AINotConfigured, ask
from ..core import CommandError
from ..net import NetError
from ..registry import ROLE_ADMIN, ROLE_OWNER
from ..utils import num

NOT_CONFIGURED = ("🧠 A IA ainda não foi configurada pelo responsável do bot.\n"
                  "Para API com chave, rode: python3 -m nicolas ia\n"
                  "Para API local/compatível sem chave, rode: python3 -m nicolas ia-local")


def _run(ctx, prompt: str, *, history_key=None):
    cfg = ctx.cfg
    if not cfg.ai_configured:
        return NOT_CONFIGURED
    history = list(ctx.bot.ai_history[history_key]) if history_key else []
    try:
        answer = ask(cfg, prompt, history)
    except AINotConfigured:
        return NOT_CONFIGURED
    except NetError as exc:
        return f"⚠️ Não consegui falar com a IA agora ({exc})."
    if history_key:
        ctx.bot.ai_history[history_key].append(("user", prompt))
        ctx.bot.ai_history[history_key].append(("assistant", answer))
    return f"🤖 {answer}"


def setup(reg):
    I = dict(category="ia", min_args=1, cooldown=8)

    @reg.command("ia", description="Conversa com a IA (lembra das últimas mensagens)", usage="<pergunta>",
                 example="ia explique o que é um buraco negro", aliases=("ai", "nicolas", "gpt"), **I)
    def ia(ctx):
        return _run(ctx, ctx.raw, history_key=(ctx.chat, num(ctx.sender)))

    @reg.command("iareset", category="ia", description="Apaga o contexto da sua conversa com a IA")
    def iareset(ctx):
        ctx.bot.ai_history.pop((ctx.chat, num(ctx.sender)), None)
        return "🧹 Contexto da IA apagado."

    @reg.command("explicar", description="A IA explica um assunto de forma simples", usage="<assunto>",
                 example="explicar blockchain", **I)
    def explicar(ctx):
        return _run(ctx, f"Explique de forma simples e curta, com um exemplo: {ctx.raw}")

    @reg.command("resumir", description="A IA resume um texto", usage="<texto>", example="resumir <texto longo>", **I)
    def resumir(ctx):
        if len(ctx.raw) < 40:
            raise CommandError("Envie um texto um pouco maior para resumir.")
        return _run(ctx, f"Resuma em poucos tópicos curtos o texto a seguir:\n\n{ctx.raw}")

    @reg.command("corrigir", description="A IA corrige ortografia e gramática", usage="<texto>",
                 example="corrigir eu fui na casa dele ontem a noite", **I)
    def corrigir(ctx):
        return _run(ctx, f"Corrija ortografia, acentuação e gramática do texto, devolvendo só o texto corrigido e, "
                         f"em uma linha, o que mudou:\n\n{ctx.raw}")

    @reg.command("ideias", description="A IA sugere ideias sobre um tema", usage="<tema>", example="ideias presente de aniversário",
                 **I)
    def ideias(ctx):
        return _run(ctx, f"Dê 5 ideias criativas e práticas, em lista curta, sobre: {ctx.raw}")

    @reg.command("codigo", description="A IA ajuda com programação", usage="<dúvida>",
                 example="codigo como inverter uma lista em python", aliases=("code", "programar"), **I)
    def codigo(ctx):
        return _run(ctx, f"Ajude com esta dúvida de programação, com um exemplo curto de código: {ctx.raw}")

    @reg.command("historia", description="A IA cria uma história original curta", usage="<tema>",
                 example="historia um robô que aprende a cozinhar", aliases=("conto",), **I)
    def historia(ctx):
        return _run(ctx, f"Escreva uma história original e curta (até 900 caracteres), para todas as idades, sobre: {ctx.raw}")

    # ---------------------------------------------------------------- modo esperto
    E = dict(category="ia", min_role=ROLE_ADMIN)

    @reg.command("ativaesperto", description="[admin] Liga o modo esperto: a IA responde tudo no grupo",
                 example="ativaesperto", cooldown=3, **E)
    def ativaesperto(ctx):
        if not ctx.cfg.ai_configured:
            return NOT_CONFIGURED
        ctx.db.set_group(ctx.chat, esperto=True)
        ctx.db.log(ctx.chat, ctx.sender, "ativaesperto", detail="on", now=ctx.now)
        if not ctx.msg.is_group:
            return ("🧠 *Modo esperto ligado nesta conversa direta.* Vou responder quem escrever aqui, como se fosse você. "
                    f"Se você mesmo escrever, eu fico quieto por {ctx.cfg.esperto_dm_pause_minutes} min.\n"
                    "ℹ️ As mensagens desta conversa são enviadas ao serviço de IA.\n"
                    f"Para desligar: *{ctx.prefix}desligaresperto*")
        proativo = "ligadas" if ctx.group["esperto_proativo"] else "desligadas"
        return ("🧠 *Modo esperto ativado!* Agora eu respondo as mensagens do grupo com inteligência artificial "
                f"e puxo assunto quando o grupo fica parado (mensagens espontâneas {proativo}).\n"
                "ℹ️ Enquanto estiver ligado, as mensagens recentes do grupo são enviadas ao serviço de IA configurado.\n"
                f"Para desligar: *{ctx.prefix}desligaresperto*")

    @reg.command("desligaresperto", description="[admin] Desliga o modo esperto", aliases=("desativaesperto",),
                 example="desligaresperto", cooldown=3, **E)
    def desligaresperto(ctx):
        ctx.db.set_group(ctx.chat, esperto=False)
        ctx.db.log(ctx.chat, ctx.sender, "desligaresperto", detail="off", now=ctx.now)
        ctx.bot.esperto.forget(ctx.chat)
        if not ctx.msg.is_group and ctx.db.group("__dm__")["esperto"]:
            return (f"⚪ Desliguei nesta conversa, mas a IA nas conversas diretas está ligada para todas. "
                    f"Para desligar geral: *{ctx.prefix}espertodm off*")
        return "⚪ *Modo esperto desligado.* Volto a responder só aos comandos."

    @reg.command("esperto", description="[admin] Mostra o estado do modo esperto", example="esperto", **E)
    def esperto(ctx):
        g = ctx.group if ctx.msg.is_group else ctx.db.group(ctx.chat)
        es = ctx.bot.esperto
        c = es.counters
        diag = (f"• Respostas dadas: {c['respostas']} • erros da IA: {c['erros_ia']} • DMs ignoradas (modo off): {c['dm_off']}"
                f" • limite/min: {c['limite_minuto']}" + (f"\n• Último erro: {es.last_error}" if es.last_error else ""))
        return ("🧠 *Modo esperto*\n"
                f"• Estado: {'ligado ✅' if g['esperto'] else 'desligado ⚪'}\n"
                f"• Mensagens espontâneas: {'ligadas' if g['esperto_proativo'] else 'desligadas'}\n"
                f"• IA configurada: {'sim' if ctx.cfg.ai_configured else 'não'}\n"
                f"• Limite: {ctx.cfg.esperto_per_minute} respostas por minuto neste grupo\n{diag}\n"
                f"Comandos: {ctx.prefix}ativaesperto, {ctx.prefix}desligaresperto, {ctx.prefix}espertoproativo on|off")

    @reg.command("espertoproativo", description="[admin] Liga/desliga as mensagens espontâneas do modo esperto",
                 usage="on|off", example="espertoproativo off", **E)
    def espertoproativo(ctx):
        arg = (ctx.args[0].lower() if ctx.args else "")
        if arg not in {"on", "off"}:
            raise CommandError(f"Use {ctx.prefix}espertoproativo on ou off.")
        ctx.db.set_group(ctx.chat, esperto_proativo=(arg == "on"))
        ctx.db.log(ctx.chat, ctx.sender, "espertoproativo", detail=arg, now=ctx.now)
        return f"{'✅' if arg == 'on' else '⚪'} Mensagens espontâneas {'ligadas' if arg == 'on' else 'desligadas'}."

    @reg.command("espertodm", category="ia", min_role=ROLE_OWNER, usage="on|off", example="espertodm on", cooldown=3,
                 description="[dono] Liga/desliga a IA nas conversas diretas (privado) com qualquer pessoa")
    def espertodm(ctx):
        from ..esperto import DM_KEY
        arg = (ctx.args[0].lower() if ctx.args else "")
        if arg not in {"on", "off"}:
            on = ctx.db.group(DM_KEY)["esperto"]
            return (f"💬 IA nas conversas diretas: {'ligada ✅' if on else 'desligada ⚪'}.\n"
                    f"Use *{ctx.prefix}espertodm on* ou *off*.")
        if arg == "on" and not ctx.cfg.ai_configured:
            return NOT_CONFIGURED
        ctx.db.set_group(DM_KEY, esperto=(arg == "on"))
        ctx.db.log(DM_KEY, ctx.sender, "espertodm", detail=arg, now=ctx.now)
        if arg == "on":
            return ("💬 *IA ligada nas conversas diretas.* Vou responder automaticamente quem te chamar no privado, "
                    "como se fosse você. Se você mesmo escrever na conversa, eu fico quieto por "
                    f"{ctx.cfg.esperto_dm_pause_minutes} min.\n⚠️ As mensagens dessas conversas são enviadas ao serviço de IA.\n"
                    f"Para desligar: *{ctx.prefix}espertodm off*")
        return "⚪ IA desligada nas conversas diretas."
