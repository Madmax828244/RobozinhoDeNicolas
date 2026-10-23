"""Menu, ajuda, status e controle de módulos."""
from __future__ import annotations

import platform

from .. import __version__
from ..core import CommandError, Reply
from ..registry import CATEGORIES, PROTECTED_MODULES, ROLE_ADMIN, ROLE_OWNER
from ..utils import fmt_duration, norm

PER_PAGE = 8


def _cmd_lines(ctx, cmds):
    p = ctx.prefix
    lines = []
    for c in cmds:
        usage = f" {c.usage}" if c.usage else ""
        line = f"• *{p}{c.name}*{usage} — {c.description}"
        if c.example:
            line += f"\n   ↳ ex.: {p}{c.example}"
        lines.append(line)
    return lines


def build_pages(ctx) -> list[tuple[str, str]]:
    reg, p = ctx.registry, ctx.prefix
    counts = reg.counts()
    grp = ctx.group if ctx.msg.is_group else {"disabled_modules": []}
    modules = sorted(reg.modules())
    off = [m for m in modules if m in grp["disabled_modules"]]
    on = [m for m in modules if m not in off]
    cats = reg.by_category()
    pages: list[tuple[str, str]] = []
    body: list[tuple[str, str]] = []
    for key, cmds in cats.items():
        chunks = [cmds[i:i + PER_PAGE] for i in range(0, len(cmds), PER_PAGE)]
        for n, chunk in enumerate(chunks, 1):
            suffix = f" ({n}/{len(chunks)})" if len(chunks) > 1 else ""
            title = f"{CATEGORIES[key]}{suffix}"
            body.append((key, f"*{title}*\n\n" + "\n".join(_cmd_lines(ctx, chunk))))
    total = len(body) + 1
    index = [
        f"🤖 *{ctx.cfg.bot_name}* — menu",
        "Sou o assistente do grupo: administração, jogos, IA, ferramentas e economia virtual.",
        "",
        f"📊 *{counts['comandos']}* comandos registrados (+{counts['aliases']} aliases e {counts['atalhos']} atalhos de conversão).",
        f"🧩 Módulos ativos: {', '.join(on) or '—'}",
    ]
    if off:
        index.append(f"🔒 Desativados neste grupo: {', '.join(off)}")
    index += ["", "📚 *Páginas*", "1. Índice"]
    ranges: dict[str, list[int]] = {}
    for i, (key, _) in enumerate(body, 2):
        ranges.setdefault(key, []).append(i)
    for key, nums in ranges.items():
        span = f"{nums[0]}" if len(nums) == 1 else f"{nums[0]}-{nums[-1]}"
        index.append(f"{span}. {CATEGORIES[key]} ({len(cats[key])})")
    index += ["", f"Use *{p}menu 2*, *{p}menu admin* ou *{p}comandos <busca>*.", f"Ajuda geral: *{p}ajuda*"]
    pages.append(("indice", "\n".join(index) + f"\n\n— página 1/{total}"))
    for i, (key, text) in enumerate(body, 2):
        footer = f"\n\n— página {i}/{total} • *{p}menu {i + 1 if i < total else 1}* para continuar"
        pages.append((key, text + footer))
    return pages


def setup(reg):
    @reg.command("menu", category="sistema", description="Mostra o menu de comandos (paginado)",
                 usage="[página|categoria]", example="menu admin", aliases=("m", "start"))
    def menu(ctx):
        pages = build_pages(ctx)
        if not ctx.args:
            return pages[0][1]
        arg = ctx.args[0]
        if arg.isdigit():
            n = int(arg)
            if not 1 <= n <= len(pages):
                raise CommandError(f"Página inválida. Escolha de 1 a {len(pages)}.")
            return pages[n - 1][1]
        q = norm(arg)
        for key, text in pages[1:]:
            if q in norm(key) or q in norm(CATEGORIES[key]):
                return text
        raise CommandError(f"Categoria '{arg}' não encontrada. Use {ctx.prefix}menu para ver o índice.")

    @reg.command("ajuda", category="sistema", description="Explica como usar o bot", aliases=("help",))
    def ajuda(ctx):
        p = ctx.prefix
        return (f"🤖 *Como usar o {ctx.cfg.bot_name}*\n\n"
                f"• Todo comando começa com *{p}* (ex.: {p}ping).\n"
                f"• *{p}menu* mostra as categorias; *{p}menu 3* abre a página 3.\n"
                f"• *{p}comandos <palavra>* pesquisa comandos.\n"
                f"• Para detalhes de um comando: *{p}ajuda <comando>*.\n"
                f"• Comandos de administração exigem ser admin do grupo.\n"
                f"• A economia é só diversão: moedas virtuais, sem valor real.") if not ctx.args else _help_one(ctx)

    def _help_one(ctx):
        found = ctx.registry.resolve(ctx.args[0].lstrip(ctx.prefix))
        if not found:
            raise CommandError(f"Comando '{ctx.args[0]}' não encontrado.")
        cmd, _ = found
        p = ctx.prefix
        lines = [f"📖 *{p}{cmd.name}* — {cmd.description}",
                 f"Uso: {p}{cmd.name} {cmd.usage}".rstrip()]
        if cmd.example:
            lines.append(f"Exemplo: {p}{cmd.example}")
        if cmd.aliases:
            lines.append("Aliases: " + ", ".join(p + a for a in cmd.aliases))
        lines.append(f"Categoria: {CATEGORIES[cmd.category]} • módulo: {cmd.module}")
        return "\n".join(lines)

    @reg.command("comandos", category="sistema", description="Pesquisa comandos pelo nome ou descrição",
                 usage="<busca>", example="comandos senha", min_args=1, aliases=("buscar", "cmds"))
    def comandos(ctx):
        found = ctx.registry.search(ctx.raw)
        if not found:
            return f"🔎 Nada encontrado para '{ctx.raw}'. Veja o {ctx.prefix}menu."
        lines = [f"🔎 Resultados para '{ctx.raw}':", ""]
        lines += _cmd_lines(ctx, found)
        return "\n".join(lines)

    @reg.command("ping", category="sistema", description="Verifica se o bot está respondendo", aliases=("p",))
    def ping(ctx):
        ts = ctx.msg.timestamp
        ms = max(0, int((ctx.bot.clock() - ts) * 1000)) if ts else 0
        return f"🏓 Pong! Latência aproximada: {ms} ms."

    @reg.command("status", category="sistema", description="Estado dos serviços do bot")
    def status(ctx):
        h = ctx.bot.health()
        ok = lambda b: "✅" if b else "⚪ não configurado"
        return "\n".join([
            f"📡 *Status do {ctx.cfg.bot_name}*",
            f"• Banco de dados: {'✅ íntegro' if h['ok'] else '❌ com problemas'} (esquema v{h['versao_schema']})",
            f"• IA: {ok(h['ia_configurada'])}",
            f"• Tradução externa: {ok(h['traducao_configurada'])}",
            f"• Clima: {'✅ habilitado' if ctx.cfg.weather_enabled else '⚪ desabilitado'}",
            f"• Comandos: {h['comandos']} • mensagens: {h['mensagens']} • erros: {h['erros']}",
            f"• Online há {fmt_duration(h['uptime_s'])}",
        ])

    @reg.command("info", category="sistema", description="Informações sobre o bot", aliases=("sobre", "bot"))
    def info(ctx):
        c = ctx.registry.counts()
        return (f"🤖 *{ctx.cfg.bot_name}* v{__version__}\n"
                f"Comandos reais: {c['comandos']} • aliases: {c['aliases']} • atalhos: {c['atalhos']}\n"
                f"Python {platform.python_version()} • banco SQLite\n"
                f"Prefixo atual: {ctx.prefix}\nUse {ctx.prefix}menu para começar.")

    @reg.command("dono", category="sistema", description="Informações públicas do responsável pelo bot",
                 aliases=("criador",))
    def dono(ctx):
        if not ctx.cfg.owner_name and not ctx.cfg.owner_contact:
            return "👤 O responsável pelo bot ainda não configurou informações públicas."
        parts = ["👤 *Responsável pelo bot*"]
        if ctx.cfg.owner_name:
            parts.append(f"Nome: {ctx.cfg.owner_name}")
        if ctx.cfg.owner_contact:
            parts.append(f"Contato: {ctx.cfg.owner_contact}")
        return "\n".join(parts)

    @reg.command("prefixo", category="admin", description="Consulta ou altera o prefixo dos comandos neste grupo",
                 usage="[novo]", example="prefixo !", group_only=True)
    def prefixo(ctx):
        if not ctx.args:
            return f"🔧 Prefixo atual: *{ctx.prefix}*"
        if ctx.role < ROLE_ADMIN:
            raise CommandError("Apenas administradores podem alterar o prefixo.")
        new = ctx.args[0]
        if not 1 <= len(new) <= 3 or any(ch.isalnum() or ch.isspace() for ch in new):
            raise CommandError("O prefixo deve ter de 1 a 3 símbolos (sem letras, números ou espaços).")
        ctx.db.set_group(ctx.chat, prefix=new)
        ctx.db.log(ctx.chat, ctx.sender, "prefixo", detail=new, now=ctx.now)
        return f"✅ Prefixo alterado para *{new}*. Exemplo: {new}menu"

    def _module_name(ctx):
        name = norm(ctx.args[0])
        mods = ctx.registry.modules()
        if name not in mods:
            raise CommandError("Módulo inexistente. Use " + ctx.prefix + "modulos para ver a lista.")
        return name

    @reg.command("ativar", category="admin", description="Ativa um módulo neste grupo", usage="<módulo>",
                 example="ativar jogos", min_role=ROLE_ADMIN, min_args=1, group_only=True)
    def ativar(ctx):
        name = _module_name(ctx)
        off = set(ctx.group["disabled_modules"])
        off.discard(name)
        ctx.db.set_group(ctx.chat, disabled_modules=list(off))
        ctx.db.log(ctx.chat, ctx.sender, "ativar", detail=name, now=ctx.now)
        return f"✅ Módulo *{name}* ativado."

    @reg.command("desativar", category="admin", description="Desativa um módulo neste grupo", usage="<módulo>",
                 example="desativar economia", min_role=ROLE_ADMIN, min_args=1, group_only=True)
    def desativar(ctx):
        name = _module_name(ctx)
        if name in PROTECTED_MODULES:
            raise CommandError(f"O módulo '{name}' é essencial e não pode ser desativado.")
        off = set(ctx.group["disabled_modules"]) | {name}
        ctx.db.set_group(ctx.chat, disabled_modules=list(off))
        ctx.db.log(ctx.chat, ctx.sender, "desativar", detail=name, now=ctx.now)
        return f"🔒 Módulo *{name}* desativado neste grupo."

    @reg.command("modulos", category="admin", description="Lista os módulos e se estão ativos")
    def modulos(ctx):
        off = ctx.group["disabled_modules"] if ctx.msg.is_group else []
        lines = ["🧩 *Módulos*"]
        for name, cmds in sorted(ctx.registry.modules().items()):
            state = "🔒" if name in off else "✅"
            lines.append(f"{state} {name} ({len(cmds)} comandos)")
        return "\n".join(lines)

    @reg.command("cmdoff", category="admin", description="Desativa um comando específico neste grupo",
                 usage="<comando>", example="cmdoff apostar", min_role=ROLE_ADMIN, min_args=1, group_only=True)
    def cmdoff(ctx):
        found = ctx.registry.resolve(ctx.args[0].lstrip(ctx.prefix))
        if not found:
            raise CommandError("Comando não encontrado.")
        cmd = found[0]
        if cmd.module in PROTECTED_MODULES:
            raise CommandError("Comandos essenciais não podem ser desativados.")
        off = set(ctx.group["disabled_commands"]) | {cmd.name}
        ctx.db.set_group(ctx.chat, disabled_commands=list(off))
        ctx.db.log(ctx.chat, ctx.sender, "cmdoff", detail=cmd.name, now=ctx.now)
        return f"🔒 Comando *{ctx.prefix}{cmd.name}* desativado neste grupo."

    @reg.command("cmdon", category="admin", description="Reativa um comando desativado neste grupo",
                 usage="<comando>", example="cmdon apostar", min_role=ROLE_ADMIN, min_args=1, group_only=True)
    def cmdon(ctx):
        found = ctx.registry.resolve(ctx.args[0].lstrip(ctx.prefix))
        if not found:
            raise CommandError("Comando não encontrado.")
        off = set(ctx.group["disabled_commands"])
        off.discard(found[0].name)
        ctx.db.set_group(ctx.chat, disabled_commands=list(off))
        return f"✅ Comando *{ctx.prefix}{found[0].name}* reativado."

    @reg.command("desligarbot", category="sistema", description="[dono] Desliga o bot (mantém a conta conectada para ligar depois)",
                 aliases=("pararbot", "stopbot"), example="desligarbot", min_role=ROLE_OWNER, cooldown=5)
    def desligarbot(ctx):
        ctx.db.log(ctx.chat, ctx.sender, "desligarbot", now=ctx.now)
        return Reply(text="🔌 Desligando o bot. A sessão do WhatsApp fica salva: para ligar de novo, rode *bash start.sh* no Termux.",
                     actions=[{"type": "shutdown", "chat_id": ctx.chat}])

    @reg.command("desconectar", category="sistema", usage="confirmar",
                 description="[dono] Desconecta o bot do WhatsApp (apaga a sessão; será preciso parear de novo)",
                 aliases=("sairconta", "logoutbot"), example="desconectar confirmar", min_role=ROLE_OWNER, cooldown=5)
    def desconectar(ctx):
        if not ctx.args or ctx.args[0].lower() not in {"confirmar", "confirmo"}:
            return (f"⚠️ Isto sai da conta do WhatsApp e *apaga a sessão* (você terá que parear de novo).\n"
                    f"Para só desligar o bot, use *{ctx.prefix}desligarbot*.\n"
                    f"Para continuar: *{ctx.prefix}desconectar confirmar*")
        ctx.db.log(ctx.chat, ctx.sender, "desconectar", now=ctx.now)
        return Reply(text="👋 Desconectando da conta do WhatsApp e apagando a sessão. Até mais!",
                     actions=[{"type": "logout", "chat_id": ctx.chat}])
