"""Perfil, níveis, rankings, medalhas e personalização."""
from __future__ import annotations

from ..achievements import ACHIEVEMENTS, SHOP, TITLES
from ..core import CommandError
from ..registry import ROLE_NAMES
from ..security import role_of
from ..utils import level_for, norm, num, tag, xp_for_level


def _bar(value: int, total: int, size: int = 10) -> str:
    filled = 0 if total <= 0 else min(size, int(size * value / total))
    return "▰" * filled + "▱" * (size - filled)


def setup(reg):
    @reg.command("ajustarperfis", category="perfil", group_only=True, min_role=3, cooldown=5,
                 description="[dono] Aplica neste grupo o XP e as moedas configurados para os dois perfis iniciais")
    def ajustarperfis(ctx):
        from ..initial_users import apply_to_chat
        rows = apply_to_chat(ctx.db, ctx.chat)
        ctx.db.log(ctx.chat, ctx.sender, "ajustarperfis", now=ctx.now)
        lines = [f"• +{r['user_id']}: {r['xp']} XP (nível {level_for(r['xp'])}) • {r['coins']} moedas" for r in rows]
        return "✅ *Perfis ajustados neste grupo:*\n" + "\n".join(lines) + f"\nVeja com *{ctx.prefix}rank*."

    @reg.command("perfil", category="perfil", description="Mostra o perfil de um participante", usage="[@usuário]",
                 aliases=("profile",))
    def perfil(ctx):
        uid = ctx.target() or ctx.sender
        user = ctx.db.user(uid)
        st = ctx.db.stats(ctx.chat, uid)
        lvl = level_for(st["xp"])
        floor_xp, ceil_xp = xp_for_level(lvl), xp_for_level(lvl + 1)
        w = ctx.db.wallet(uid)
        medals = ctx.db.achievements(uid)
        title = f" — {user['title']}" if user["title"] else ""
        lines = [
            f"👤 *{user['name'] or tag(uid)}*{title}",
            f"📝 {user['bio'] or 'Sem bio. Use ' + ctx.prefix + 'setbio <texto>'}",
            f"⭐ Nível {lvl} {_bar(st['xp'] - floor_xp, ceil_xp - floor_xp)} ({st['xp']}/{ceil_xp} XP)",
            f"💬 {st['msgs']} mensagens • 💰 {w['coins']} moedas virtuais",
            f"🏅 {len(medals)}/{len(ACHIEVEMENTS)} conquistas",
        ]
        return ctx.reply("\n".join(lines), mentions=[uid])

    @reg.command("rank", category="perfil", description="Ranking do grupo por xp, msgs ou ricos", usage="[xp|msgs|ricos]",
                 example="rank msgs", group_only=True, aliases=("ranking", "top"))
    def rank(ctx):
        order = norm(ctx.args[0]) if ctx.args else "xp"
        if order not in {"xp", "msgs", "ricos"}:
            raise CommandError("Opções: xp, msgs ou ricos.")
        rows = ctx.db.top_members(ctx.chat, order, 10)
        if not rows:
            return "📊 Ainda não há ninguém no ranking."
        unit = {"xp": "XP", "msgs": "mensagens", "ricos": "moedas"}[order]
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, r in enumerate(rows):
            position = medals[i] if i < 3 else f"{i + 1}."
            name = r["name"] or "+" + r["user_id"]
            level = level_for(int(r.get("xp", 0)))
            if order == "xp":
                detail = f"⭐ Nv. {level} • {int(r['xp'])} XP"
            else:
                detail = f"⭐ Nv. {level} • {r['score']} {unit} • {int(r.get('xp', 0))} XP"
            lines.append(f"{position} {name} — {detail}")
        return f"🏆 *Ranking ({order})*\n" + "\n".join(lines)

    @reg.command("nivel", category="perfil", description="Mostra seu nível e quanto falta para o próximo",
                 aliases=("level", "xp"))
    def nivel(ctx):
        st = ctx.db.stats(ctx.chat, ctx.sender)
        lvl = level_for(st["xp"])
        nxt = xp_for_level(lvl + 1)
        return f"⭐ Nível *{lvl}* • {st['xp']} XP • faltam {nxt - st['xp']} XP para o nível {lvl + 1}."

    @reg.command("medalhas", category="perfil", description="Lista suas conquistas desbloqueadas", usage="[@usuário]",
                 aliases=("conquistas",))
    def medalhas(ctx):
        uid = ctx.target() or ctx.sender
        mine = set(ctx.db.achievements(uid))
        lines = [f"{'✅' if k in mine else '🔒'} {name} — {desc}" for k, (name, desc) in ACHIEVEMENTS.items()]
        return ctx.reply(f"🏅 *Conquistas de {tag(uid)}* ({len(mine)}/{len(ACHIEVEMENTS)})\n" + "\n".join(lines), mentions=[uid])

    @reg.command("setbio", category="personalizacao", description="Define a bio do seu perfil (até 120 caracteres)",
                 usage="<texto>", example="setbio Amo café e código", min_args=1)
    def setbio(ctx):
        ctx.db.set_user_field(ctx.sender, "bio", ctx.raw[:120])
        return "✅ Bio atualizada!"

    @reg.command("titulo", category="personalizacao", description="Escolhe um título comprado na loja para o perfil",
                 usage="<título>|remover", example="titulo Lenda")
    def titulo(ctx):
        if not ctx.args:
            owned = [t for t, item in TITLES.items() if ctx.db.has_item(ctx.sender, item)]
            return "🎓 Títulos que você possui: " + (", ".join(owned) if owned else "nenhum (veja a loja).")
        if norm(ctx.args[0]) in {"remover", "limpar"}:
            ctx.db.set_user_field(ctx.sender, "title", "")
            return "✅ Título removido."
        wanted = ctx.raw.strip().capitalize()
        if wanted not in TITLES or not ctx.db.has_item(ctx.sender, TITLES[wanted]):
            raise CommandError("Você não possui esse título. Compre na loja.")
        ctx.db.set_user_field(ctx.sender, "title", wanted)
        return f"✅ Título definido: *{wanted}*."
