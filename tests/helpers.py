"""Auxiliares compartilhados pelos testes."""
from __future__ import annotations

import random
import itertools

from nicolas.config import Config
from nicolas.core import Message
from nicolas.db import Database
from nicolas.dispatcher import Bot
from nicolas.registry import load_plugins

OWNER = "5511900000001"
ADMIN = "5511900000002"
MEMBER = "5511900000003"
MEMBER2 = "5511900000004"
BOT = "5500000000000"
CHAT = "120363000000000001@g.us"
# 2025-10-09 15:00:00 UTC = 12:00 no fuso -3 (padrão do bot)
T0 = 1_760_022_000.0
_MESSAGE_IDS = itertools.count(1)


def jid(number: str) -> str:
    return f"{number}@s.whatsapp.net"


class Clock:
    def __init__(self, t: float = T0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def make_bot(db_path: str = ":memory:", **cfg_over):
    cfg_kwargs = dict(owner_ids=(OWNER,), rate_limit_count=10_000)
    cfg_kwargs.update(cfg_over)
    clock = Clock()
    bot = Bot(Config(**cfg_kwargs), Database(db_path), load_plugins(), clock=clock, rng=random.Random(42))
    return bot, clock


def say(bot, text, sender=MEMBER, chat=CHAT, group=True, admin=None, bot_admin=True, mentioned=(), quoted=None,
        admins=(ADMIN,)):
    if admin is None:
        admin = sender in admins
    msg = Message(
        chat_id=chat if group else jid(sender), sender=jid(sender), text=text, is_group=group,
        sender_name=f"U{sender[-2:]}", sender_is_admin=admin, bot_is_admin=bot_admin, bot_id=jid(BOT),
        mentioned=[jid(m) for m in mentioned], quoted_sender=jid(quoted) if quoted else None,
        message_id=f"MSG{next(_MESSAGE_IDS)}", timestamp=bot.clock(), group_name="Grupo de teste",
        group_admins=[jid(a) for a in admins], group_size=5,
    )
    return bot.handle_message(msg)


def texts(replies) -> str:
    return "\n".join(r.text for r in replies if r.text)


def actions(replies) -> list:
    return [a for r in replies for a in r.actions]


def prime(bot, *users, chat=CHAT):
    """Envia uma mensagem inicial de cada usuário (consome a conquista 'Primeiros passos' e o aviso de nível)."""
    for user in users or (MEMBER, MEMBER2, ADMIN, OWNER):
        say(bot, "oi", sender=user, chat=chat)
