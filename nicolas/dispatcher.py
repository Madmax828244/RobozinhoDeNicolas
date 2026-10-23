"""Coração do bot: recebe mensagens/eventos, aplica segurança e executa comandos."""
from __future__ import annotations

import logging
import random
import re
import time
from collections import defaultdict, deque

from .achievements import award
from .config import Config
from .esperto import Esperto
from .core import CommandError, Event, Message, Reply
from .db import Database, InsufficientFunds
from .registry import PROTECTED_MODULES, ROLE_ADMIN, ROLE_MOD, ROLE_NAMES, Registry
from .security import RateLimiter, is_owner, role_of
from .utils import jid_from_number, norm, num, tag, today_str

log = logging.getLogger("nicolas")

LINK_RE = re.compile(
    r"(https?://|www\.|chat\.whatsapp\.com/|wa\.me/|\b[a-z0-9-]+\.(?:com|net|org|io|gg|me|xyz|info|br|link|app|site)\b)",
    re.IGNORECASE,
)
MENTION_RE = re.compile(r"@(\d{8,15})")
NAME_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
FLOOD_MUTE_SECONDS = 300


class Context:
    """Tudo que um comando precisa para trabalhar."""

    def __init__(self, bot: "Bot", msg: Message, cmd, args: list, raw: str, prefix: str, role: int, now: float,
                 invoked: str = ""):
        self.bot, self.msg, self.cmd, self.invoked = bot, msg, cmd, invoked or cmd.name
        self.args, self.raw, self.prefix, self.role, self.now = args, raw, prefix, role, now
        self._group = None

    @property
    def db(self) -> Database:
        return self.bot.db

    @property
    def cfg(self) -> Config:
        return self.bot.cfg

    @property
    def registry(self) -> Registry:
        return self.bot.registry

    @property
    def chat(self) -> str:
        return self.msg.chat_id

    @property
    def sender(self) -> str:
        return self.msg.sender

    @property
    def group(self) -> dict:
        if self._group is None:
            self._group = self.db.group(self.chat)
        return self._group

    def refresh_group(self) -> dict:
        self._group = None
        return self.group

    @property
    def today(self) -> str:
        return today_str(self.now, self.cfg.tz_offset)

    def reply(self, text: str, mentions=(), actions=(), **kw) -> Reply:
        return Reply(text=text, mentions=list(mentions), actions=list(actions), **kw)

    def target(self):
        """Alvo do comando: menção, mensagem respondida ou número digitado."""
        if self.msg.mentioned:
            return self.msg.mentioned[0]
        if self.msg.quoted_sender:
            return self.msg.quoted_sender
        for a in self.args:
            digits = num(a)
            if 8 <= len(digits) <= 15 and (a.startswith("@") or a.startswith("+") or a.isdigit()):
                return jid_from_number(digits)
        return None

    def is_protected(self, uid) -> bool:
        """Administradores, dono e o próprio bot nunca são alvos de punições."""
        n = num(uid)
        admins = {num(a) for a in self.msg.group_admins}
        return n in admins or is_owner(self.cfg, uid) or n == num(self.msg.bot_id)

    def kick_action(self, uid) -> dict:
        return {"type": "kick", "chat_id": self.chat, "users": [uid]}


def _normalize(result) -> list[Reply]:
    if result is None:
        return []
    if isinstance(result, Reply):
        return [result]
    if isinstance(result, str):
        return [Reply(text=result)]
    if isinstance(result, (list, tuple)):
        out: list[Reply] = []
        for item in result:
            out.extend(_normalize(item))
        return out
    return [Reply(text=str(result))]


class Bot:
    def __init__(self, cfg: Config, db: Database, registry: Registry, clock=time.time, rng: random.Random | None = None):
        self.cfg, self.db, self.registry, self.clock = cfg, db, registry, clock
        self.rng = rng or random.SystemRandom()
        self.limiter = RateLimiter(cfg.rate_limit_count, cfg.rate_limit_window, clock)
        self.flood: dict[tuple, deque] = defaultdict(deque)
        self.stats = {"messages": 0, "commands": 0, "errors": 0, "started": clock()}
        self.ai_history: dict[tuple, deque] = defaultdict(lambda: deque(maxlen=8))
        self.esperto = Esperto(self)
        self._announced = False
        from pathlib import Path
        self.heartbeat_path = None if db.path == ":memory:" else Path(db.path).parent / "heartbeat"

    # ------------------------------------------------------------ mensagens
    def handle_message(self, msg: Message, defer_ai: bool = False) -> list[Reply]:
        """Processa uma mensagem. Com defer_ai=True, a resposta do modo esperto (rede) não é feita aqui:
        o job fica em msg.esperto_job para o chamador executar fora do lock (veja server.py)."""
        msg.esperto_job = None
        try:
            replies = self._handle(msg)
            if msg.esperto_job and not defer_ai:
                replies = replies + self.complete_job(msg)
                msg.esperto_job = None
            return replies
        except Exception as exc:  # nunca derruba o bot
            self.stats["errors"] += 1
            log.error("falha ao processar mensagem: %s: %s", type(exc).__name__, exc)
            return []

    def complete_job(self, msg: Message, lock=None) -> list[Reply]:
        """Roda a IA (rede, fora do lock) e, se for um pedido de admin, executa o plano (dentro do lock)."""
        job = msg.esperto_job
        replies = list(self.esperto.run(job))
        if job.get("agent") and job.get("plan") is not None:
            import contextlib
            try:
                with (lock or contextlib.nullcontext()):
                    replies += self._execute_plan(msg, job)
            except Exception as exc:
                self.stats["errors"] += 1
                log.error("falha ao executar plano do admin: %s: %s", type(exc).__name__, exc)
        return replies

    def _execute_plan(self, msg: Message, job: dict) -> list[Reply]:
        from . import agent
        plan, now = job["plan"], self.clock()
        role = role_of(self.cfg, self.db, msg)
        grp = self.db.group(msg.chat_id)
        prefix = grp["prefix"] or self.cfg.prefix
        out: list[Reply] = []
        if plan["resposta"]:
            out.append(Reply(text=plan["resposta"], quote=True))
        has_targets = bool(msg.mentioned or msg.quoted_sender)
        done = 0
        for line in plan["comandos"][:agent.MAX_COMMANDS]:
            if not self._is_prefixed(line, prefix):
                continue
            parts = line[len(prefix):].split()
            resolved = self.registry.resolve(norm(parts[0])) if parts else None
            if resolved is None:
                continue
            cmd, preset = resolved
            if cmd.name not in agent.ALLOWED or role < cmd.min_role:
                out.append(Reply(text=f"🚫 Não posso executar *{prefix}{cmd.name}* a seu pedido."))
                continue
            args = parts[1:]
            if cmd.name in agent.NEEDS_TARGET:
                if not has_targets:
                    out.append(Reply(text=f"⚠️ Para *{prefix}{cmd.name}* marque (@) ou responda a pessoa."))
                    continue
                args = []  # o alvo vem só das marcações do admin, nunca de texto escolhido pela IA
            raw = line[len(prefix):].strip()[len(parts[0]):].strip() if not cmd.name in agent.NEEDS_TARGET else ""
            self.db.log(msg.chat_id, msg.sender, "agente", detail=cmd.name, now=now)
            out.extend(self._run(msg, cmd, list(args) + list(preset), raw, prefix, role, grp, now, cmd.name))
            done += 1
        if done:
            log.info("agente: %d comando(s) executado(s) a pedido de um admin", done)
        return out

    def _handle(self, msg: Message) -> list[Reply]:
        text = (msg.text or "").strip()[:4000]
        if not msg.sender or not (text or msg.media):
            return []
        now = self.clock()
        # Reentregas do mesmo evento do WhatsApp não repetem comandos, XP nem chamadas à IA.
        if msg.message_id and not self.db.claim_message(msg.chat_id, msg.message_id, now):
            return []
        own = msg.from_me  # mensagens da própria conta têm permissão de dono; o bridge filtra respostas enviadas pelo bot.
        if own and not msg.is_group and num(msg.chat_id) != num(msg.bot_id):
            from . import agent
            called = agent.addressed(msg, text, {num(msg.bot_id)})
            if not called:
                self.esperto.takeover(msg.chat_id, now)  # dono falando com a pessoa: a IA dá espaço
            # comandos do dono (ex.: /ativaesperto) e chamadas ao bot ("Ei bot, ...") funcionam na conversa direta
            if not called and not any(self._is_prefixed(text, p) for p in (self.cfg.prefix, *self.cfg.extra_prefixes)):
                return []
        self.stats["messages"] += 1
        if not msg.mentioned:
            msg.mentioned = [jid_from_number(d) for d in MENTION_RE.findall(text)]
        self.db.touch_user(msg.sender, msg.sender_name)
        role = role_of(self.cfg, self.db, msg)
        grp = self.db.group(msg.chat_id) if msg.is_group else None
        replies: list[Reply] = []

        if grp is not None and not own:
            if role < ROLE_ADMIN and self.db.is_banned(msg.chat_id, msg.sender):
                return [Reply(actions=[{"type": "kick", "chat_id": msg.chat_id, "users": [msg.sender]}])] if msg.bot_is_admin else []
            if role < ROLE_MOD and self.db.mute_until(msg.chat_id, msg.sender, now):
                return [Reply(actions=[self._delete(msg)])] if msg.bot_is_admin else []
            if role < ROLE_MOD:
                moderated = self._moderate(msg, grp, text, now)
                if moderated:
                    return moderated
            old, new, msgs = self.db.register_message(msg.chat_id, msg.sender, now, self.rng.randint(5, 15))
            day = today_str(now, self.cfg.tz_offset)
            self.db.add_progress(msg.sender, day, "msgs")
            replies.extend(self._after_message(msg, old, new, msgs, now))

        main_prefix = (grp["prefix"] if grp and grp["prefix"] else self.cfg.prefix)
        prefix, silent_unknown = main_prefix, False
        if not self._is_prefixed(text, prefix):
            alt = next((p for p in self.cfg.extra_prefixes if self._is_prefixed(text, p)), None)
            if alt is None:
                return replies + self._maybe_esperto(msg, grp, text, role, now)
            prefix, silent_unknown = alt, True  # prefixos extras (ex.: "/") ignoram comandos desconhecidos
        in_hours = not (grp is not None and grp["hours_on"] and role < ROLE_MOD and not self._within_hours(grp, now))
        if not in_hours:
            return replies

        parts = text[len(prefix):].split()
        name = norm(parts[0])
        if not NAME_RE.match(name) or len(name) > 24:
            return replies + (self._maybe_esperto(msg, grp, text, role, now) if silent_unknown else [])
        args = parts[1:]
        raw = text[len(prefix):].strip()[len(parts[0]):].strip()
        resolved = self.registry.resolve(name)

        if resolved is None and own and not silent_unknown:
            return replies
        if resolved is None and silent_unknown:  # "/qualquer coisa": trata como conversa normal
            return replies + self._maybe_esperto(msg, grp, text, role, now)

        ok, notify = self.limiter.allow(num(msg.sender))
        if not ok:
            if notify:
                replies.append(Reply(text="⏳ Calma! Você está usando comandos rápido demais. Tente de novo em instantes."))
            return replies

        if resolved is None:
            tips = self.registry.suggest(name)
            hint = f" Você quis dizer: {', '.join(prefix + t for t in tips)}?" if tips else ""
            replies.append(Reply(text=f"❓ Comando *{prefix}{name}* não encontrado.{hint}\nUse *{prefix}menu* ou *{prefix}comandos <busca>*."))
            return replies

        cmd, preset = resolved
        args = args + list(preset)
        replies.extend(self._run(msg, cmd, args, raw, prefix, role, grp, now, name))
        return replies

    @staticmethod
    def _is_prefixed(text: str, prefix: str) -> bool:
        return text.startswith(prefix) and len(text) > len(prefix) and not text[len(prefix)].isspace()

    def _maybe_esperto(self, msg: Message, grp, text: str, role: int, now: float) -> list[Reply]:
        """Mensagem comum (não é comando): se o modo esperto estiver ligado, prepara a resposta da IA."""
        own_dm = msg.from_me and not msg.is_group
        if own_dm:
            # O dono na conversa direta: a IA só responde se ele chamar o bot ("Ei bot, ...", "/pergunta") ou se for a
            # conversa consigo mesmo ("Mensagens para você"). Mensagens do próprio bot são filtradas na ponte.
            from . import agent
            selfchat = num(msg.chat_id) == num(msg.bot_id)
            if not (selfchat or agent.addressed(msg, text, {num(msg.bot_id)})
                    or any(self._is_prefixed(text, p) for p in self.cfg.extra_prefixes)):
                return []
        if not self.esperto.enabled_for(msg, grp):
            if not msg.is_group and self.cfg.ai_configured:
                self.esperto.count("dm_off")
                log.info("DM de ...%s ignorada: modo esperto desligado nesta conversa "
                         "(o dono liga com /ativaesperto nela, ou /espertodm on para todas)", num(msg.sender)[-4:])
            return []
        if msg.is_group:
            if "ia" in grp["disabled_modules"]:
                return []
            if grp["hours_on"] and role < ROLE_MOD and not self._within_hours(grp, now):
                return []
        elif not own_dm and self.esperto.paused(msg.chat_id, now):
            self.esperto.count("dm_paused")
            return []
        msg.esperto_job = self.esperto.prepare(msg, text, now)
        if msg.esperto_job and msg.is_group and role >= ROLE_ADMIN:
            from . import agent
            bot_nums = {num(msg.bot_id)}
            if agent.addressed(msg, text, bot_nums):
                request = agent.request_text(text)
                state = {"nome": msg.group_name, "descricao": grp["description"], "regras": grp["rules"],
                         "boas_vindas_ligado": bool(grp["welcome_on"]), "antilink": bool(grp["antilink"]),
                         "antiflood": bool(grp["antiflood"]), "bot_e_admin": bool(msg.bot_is_admin)}
                prefix = grp["prefix"] or self.cfg.prefix
                msg.esperto_job.update(agent=True, plan=None, request=request, prefix=prefix,
                                       agent_prompt=agent.build_prompt(self.registry, prefix, request, state,
                                                                       bool(msg.mentioned or msg.quoted_sender)))
        return []

    def _run(self, msg, cmd, args, raw, prefix, role, grp, now, invoked: str = "") -> list[Reply]:
        if grp is not None and cmd.module not in PROTECTED_MODULES:
            if cmd.module in grp["disabled_modules"]:
                return [Reply(text=f"🔒 O módulo *{cmd.module}* está desativado neste grupo.")]
        if grp is not None and cmd.name in grp["disabled_commands"] and cmd.module not in PROTECTED_MODULES:
            return [Reply(text=f"🔒 O comando *{prefix}{cmd.name}* está desativado neste grupo.")]
        if cmd.group_only and not msg.is_group:
            return [Reply(text="👥 Este comando só funciona em grupos.")]
        if role < cmd.min_role:
            return [Reply(text=f"🚫 Apenas *{ROLE_NAMES[cmd.min_role]}* ou superior pode usar *{prefix}{cmd.name}*.")]
        if len(args) < cmd.min_args:
            usage = f"{prefix}{cmd.name} {cmd.usage}".strip()
            example = f"\nExemplo: {prefix}{cmd.example}" if cmd.example else ""
            return [Reply(text=f"⚠️ Faltam parâmetros.\nUso: *{usage}*{example}")]
        left = self.limiter.cooldown_left(num(msg.sender), cmd.name, cmd.cooldown)
        if left > 0:
            return [Reply(text=f"⏳ Aguarde {int(left) + 1}s para usar *{prefix}{cmd.name}* de novo.")]

        ctx = Context(self, msg, cmd, args, raw, prefix, role, now, invoked)
        try:
            result = cmd.handler(ctx)
        except CommandError as exc:
            result = Reply(text=f"⚠️ {exc}")
        except InsufficientFunds:
            result = Reply(text="💸 Saldo insuficiente de moedas virtuais.")
        except Exception as exc:
            self.stats["errors"] += 1
            log.error("erro no comando %s: %s: %s", cmd.name, type(exc).__name__, exc)
            result = Reply(text="⚠️ Ocorreu um erro interno ao executar o comando. Tente novamente mais tarde.")
        self.stats["commands"] += 1
        replies = _normalize(result)
        self.db.add_progress(msg.sender, today_str(now, self.cfg.tz_offset), "cmds")
        return replies

    # ------------------------------------------------------------- auxiliares
    def _delete(self, msg: Message) -> dict:
        return {"type": "delete", "chat_id": msg.chat_id, "message_id": msg.message_id, "participant": msg.sender}

    def _within_hours(self, grp: dict, now: float) -> bool:
        from .utils import local_dt
        dt = local_dt(now, self.cfg.tz_offset)
        minute = dt.hour * 60 + dt.minute
        a, b = grp["open_min"], grp["close_min"]
        return a <= minute <= b if a <= b else (minute >= a or minute <= b)

    def _after_message(self, msg, old, new, msgs, now) -> list[Reply]:
        out = []
        notes = []
        if msgs == 1:
            notes.append(award(self.db, msg.sender, "primeiros_passos", now))
        if msgs >= 100:
            notes.append(award(self.db, msg.sender, "tagarela", now))
        if new > old:
            out.append(Reply(text=f"🎉 {tag(msg.sender)} subiu para o *nível {new}*!", mentions=[msg.sender], quote=False))
            if new >= 5:
                notes.append(award(self.db, msg.sender, "veterano", now))
        for n in filter(None, notes):
            out.append(Reply(text=f"{tag(msg.sender)} {n}", mentions=[msg.sender], quote=False))
        return out

    def _moderate(self, msg: Message, grp: dict, text: str, now: float) -> list[Reply]:
        chat, sender = msg.chat_id, msg.sender
        if grp["antiflood"]:
            dq = self.flood[(chat, num(sender))]
            dq.append(now)
            while dq and now - dq[0] > self.cfg.flood_seconds:
                dq.popleft()
            if len(dq) >= self.cfg.flood_messages:
                dq.clear()
                self.db.set_mute(chat, sender, now + FLOOD_MUTE_SECONDS, "anti-flood")
                self.db.log(chat, "anti-flood", "mute", sender, "flood", now)
                actions = [self._delete(msg)] if msg.bot_is_admin else []
                return [Reply(text=f"🌊 {tag(sender)} foi silenciado por 5 minutos (anti-flood).", mentions=[sender],
                              actions=actions, quote=False)]
            if len(self.flood) > 50000:
                self.flood.clear()
        words = self.db.badwords(chat)
        if words:
            t = norm(text)
            tokens = set(re.findall(r"\w+", t))
            for w in words:
                w = norm(w)
                if (" " in w and w in t) or w in tokens:
                    return self._violation(msg, grp, "palavra proibida", now)
        if grp["antilink"] and LINK_RE.search(text):
            return self._violation(msg, grp, "link", now)
        return []

    def _violation(self, msg: Message, grp: dict, kind: str, now: float) -> list[Reply]:
        chat, sender = msg.chat_id, msg.sender
        actions = [self._delete(msg)] if msg.bot_is_admin else []
        count = self.db.add_warning(chat, sender, f"auto: {kind}", "automático", now)
        self.db.log(chat, "automático", "adv", sender, kind, now)
        limit = grp["max_warns"] or self.cfg.max_warns
        text = f"⚠️ {tag(sender)}, mensagem removida ({kind}). Advertência {count}/{limit}."
        if count >= limit:
            self.db.clear_warnings(chat, sender)
            if msg.bot_is_admin:
                actions.append({"type": "kick", "chat_id": chat, "users": [sender]})
                text += " Limite atingido: participante removido."
                self.db.log(chat, "automático", "kick", sender, "limite de advertências", now)
            else:
                text += " (Não tenho permissão de administrador para remover.)"
        return [Reply(text=text, mentions=[sender], actions=actions, quote=False)]

    # ---------------------------------------------------------------- eventos
    def handle_event(self, ev: Event) -> list[Reply]:
        try:
            return self._event(ev)
        except Exception as exc:
            self.stats["errors"] += 1
            log.error("falha no evento: %s: %s", type(exc).__name__, exc)
            return []

    @staticmethod
    def _template(text: str, uid: str, group_name: str, rules: str) -> str:
        return (text.replace("{usuario}", tag(uid)).replace("{grupo}", group_name or "grupo")
                .replace("{regras}", rules or "sem regras definidas"))

    def _event(self, ev: Event) -> list[Reply]:
        grp = self.db.group(ev.chat_id)
        now = self.clock()
        out: list[Reply] = []
        for uid in ev.users:
            if ev.type == "join":
                if self.db.is_banned(ev.chat_id, uid):
                    if ev.bot_is_admin:
                        out.append(Reply(actions=[{"type": "kick", "chat_id": ev.chat_id, "users": [uid]}]))
                    continue
                if grp["antifake"] and not any(num(uid).startswith(p) for p in self.cfg.antifake_prefixes):
                    self.db.log(ev.chat_id, "anti-fake", "kick", uid, "número fora dos prefixos permitidos", now)
                    if ev.bot_is_admin:
                        out.append(Reply(actions=[{"type": "kick", "chat_id": ev.chat_id, "users": [uid]}]))
                    continue
                if grp["welcome_on"]:
                    default = "👋 Bem-vindo(a) ao *{grupo}*, {usuario}!\n\n📜 Regras:\n{regras}"
                    text = self._template(grp["welcome"] or default, uid, ev.group_name, grp["rules"])
                    out.append(Reply(text=text, mentions=[uid], quote=False))
            elif ev.type == "leave" and grp["welcome_on"]:
                default = "👋 {usuario} saiu do grupo. Até mais!"
                text = self._template(grp["goodbye"] or default, uid, ev.group_name, grp["rules"])
                out.append(Reply(text=text, mentions=[uid], quote=False))
        return out

    def _heartbeat(self, now: float) -> list[dict]:
        """Grava o 'estou vivo' e, na 1ª consulta após ligar, avisa o dono (quanto tempo ficou fora)."""
        out: list[dict] = []
        path = self.heartbeat_path
        if path is None:
            return out
        try:
            if not self._announced:
                self._announced = True
                try:
                    last = float(path.read_text().strip())
                except (OSError, ValueError):
                    last = 0.0
                if self.cfg.startup_notice and self.cfg.owner_ids:
                    gap = int((now - last) // 60) if last else 0
                    note = f" Fiquei fora por cerca de {gap} min." if gap >= 3 else ""
                    owner = jid_from_number(self.cfg.owner_ids[0])
                    out.append({"chat_id": owner, "reply": Reply(text=f"✅ {self.cfg.bot_name} ligado e funcionando.{note}", quote=False).to_dict()})
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(int(now)))
        except OSError:
            pass
        return out

    def due_reminders(self) -> list[dict]:
        self.esperto.start_proactive(self.clock())
        out = self._heartbeat(self.clock()) + self.esperto.drain_outbox()
        for r in self.db.due_reminders(self.clock()):
            uid = jid_from_number(r["user_id"])
            reply = Reply(text=f"⏰ Lembrete para {tag(uid)}: {r['text']}", mentions=[uid], quote=False)
            out.append({"chat_id": r["chat_id"], "reply": reply.to_dict()})
        return out

    # ----------------------------------------------------------------- saúde
    def health(self) -> dict:
        try:
            db_ok = self.db.integrity_ok()
        except Exception:
            db_ok = False
        c = self.registry.counts()
        return {
            "ok": db_ok,
            "versao_schema": self.db.schema_version(),
            "comandos": c["comandos"],
            "nomes_registrados": c["total_nomes"],
            "ia_configurada": self.cfg.ai_configured,
            "traducao_configurada": self.cfg.translate_configured,
            "mensagens": self.stats["messages"],
            "comandos_executados": self.stats["commands"],
            "erros": self.stats["errors"],
            "uptime_s": int(self.clock() - self.stats["started"]),
        }
