"""Permissões e limitação de uso."""
from __future__ import annotations

from collections import defaultdict, deque

from .registry import ROLE_ADMIN, ROLE_MEMBER, ROLE_MOD, ROLE_OWNER
from .utils import num


def br_variants(uid) -> set:
    """Números brasileiros de celular podem aparecer com ou sem o 9º dígito (55 DD 9XXXX-XXXX x 55 DD XXXX-XXXX)."""
    n = num(uid)
    out = {n} if n else set()
    if n.startswith("55"):
        if len(n) == 12 and n[4] in "6789":
            out.add(n[:4] + "9" + n[4:])
        elif len(n) == 13 and n[4] == "9":
            out.add(n[:4] + n[5:])
    return out


def is_owner(cfg, uid) -> bool:
    mine = br_variants(uid)
    return bool(mine) and any(mine & br_variants(o) for o in cfg.owner_ids)


def role_of(cfg, db, msg) -> int:
    """Nível do remetente: dono > admin (da plataforma ou autorizado) > moderador > membro."""
    # A conta conectada ao bot é do dono por definição: mensagens "from_me" só vêm de quem controla a conta.
    if msg.from_me or is_owner(cfg, msg.sender):
        return ROLE_OWNER
    if not msg.is_group:
        return ROLE_MEMBER
    if msg.sender_is_admin or num(msg.sender) in {num(a) for a in msg.group_admins}:
        return ROLE_ADMIN
    stored = db.role(msg.chat_id, msg.sender)
    if stored == "admin":
        return ROLE_ADMIN
    if stored == "mod":
        return ROLE_MOD
    return ROLE_MEMBER


class RateLimiter:
    """Janela deslizante por usuário + cooldown por comando."""

    def __init__(self, count: int, window: float, clock):
        self.count, self.window, self.clock = count, window, clock
        self.hits: dict[str, deque] = defaultdict(deque)
        self.cool: dict[tuple, float] = {}
        self.warned: dict[str, float] = {}

    def allow(self, user: str) -> tuple[bool, bool]:
        """Retorna (permitido, deve_avisar). Avisa só uma vez por janela."""
        now = self.clock()
        q = self.hits[user]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.count:
            notify = now - self.warned.get(user, 0) > self.window
            if notify:
                self.warned[user] = now
            return False, notify
        q.append(now)
        return True, False

    def cooldown_left(self, user: str, command: str, cooldown: float) -> float:
        if cooldown <= 0:
            return 0
        now = self.clock()
        left = self.cool.get((user, command), 0) + cooldown - now
        if left > 0:
            return left
        self.cool[(user, command)] = now
        if len(self.cool) > 20000:  # evita crescimento ilimitado
            for key in [k for k, v in self.cool.items() if now - v > 3600]:
                del self.cool[key]
        return 0
