"""Simulador de console: conversa com o bot no terminal, sem WhatsApp (útil para testar)."""
from __future__ import annotations

import sys
import time

from .core import Message
from .utils import jid_from_number


def render(reply) -> str:
    lines = []
    if reply.text:
        lines.append(reply.text)
    if reply.image_base64:
        lines.append("[imagem anexada]")
    for a in reply.actions:
        lines.append(f"[ação da plataforma: {a['type']}]")
    return "\n".join(lines)


def run_console(bot, user: str = "5511999990001", admin: bool = True, chat: str = "console@g.us", group: bool = True,
                inp=sys.stdin, out=sys.stdout) -> None:
    state = {"user": user, "admin": admin}
    bot_id = "5500000000000@s.whatsapp.net"
    print(f"{bot.cfg.bot_name} — console de teste. /as <número>, /admin on|off, /quit", file=out)
    for line in inp:
        line = line.rstrip("\n")
        if line.strip() == "/quit":
            break
        if line.startswith("/as "):
            state["user"] = "".join(c for c in line[4:] if c.isdigit())
            print(f"(agora você é +{state['user']})", file=out)
            continue
        if line.startswith("/admin "):
            state["admin"] = line.split()[1] == "on"
            print(f"(admin: {state['admin']})", file=out)
            continue
        sender = jid_from_number(state["user"])
        admins = [sender] if state["admin"] else []
        msg = Message(chat_id=chat if group else sender, sender=sender, text=line, is_group=group,
                      sender_name=f"+{state['user']}", sender_is_admin=state["admin"], bot_is_admin=True,
                      bot_id=bot_id, group_admins=admins, group_name="Grupo de teste", group_size=5,
                      message_id=str(time.time()), timestamp=time.time())
        for reply in bot.handle_message(msg):
            text = render(reply)
            if text:
                print("🤖 " + text.replace("\n", "\n   "), file=out)
        for item in bot.due_reminders():
            print("🤖 " + item["reply"]["text"], file=out)
