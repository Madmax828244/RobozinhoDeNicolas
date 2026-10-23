"""Gateway HTTP local: a ponte da plataforma envia mensagens e recebe as respostas/ações."""
from __future__ import annotations

import hmac
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import Event, Message

log = logging.getLogger("nicolas.server")
MAX_BODY = 12 * 1024 * 1024  # só loopback autenticado; áudio/imagem chegam em base64


def make_server(bot, host: str, port: int, token: str) -> ThreadingHTTPServer:
    if not token:
        raise ValueError("BRIDGE_TOKEN é obrigatório para iniciar o gateway.")
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "RoboNicolas"

        def log_message(self, fmt, *args):  # sem IPs/corpo nos logs
            log.debug("http: " + fmt, *args)

        def _send(self, code: int, payload: dict):
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            sent = self.headers.get("X-Bridge-Token", "")
            return hmac.compare_digest(sent.encode(), token.encode())

        def do_GET(self):
            if self.path == "/health":
                h = bot.health()
                self._send(200 if h["ok"] else 503, {"ok": h["ok"], "comandos": h["comandos"]})
            elif self.path == "/due":
                if not self._authorized():
                    return self._send(401, {"error": "não autorizado"})
                with lock:
                    self._send(200, {"reminders": bot.due_reminders()})
            else:
                self._send(404, {"error": "não encontrado"})

        def do_POST(self):
            if self.path not in ("/message", "/event", "/wants"):
                return self._send(404, {"error": "não encontrado"})
            if not self._authorized():
                return self._send(401, {"error": "não autorizado"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                size = -1
            if not 0 < size <= MAX_BODY:
                return self._send(413, {"error": "corpo inválido ou grande demais"})
            try:
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict) or not isinstance(data.get("chat_id"), str):
                    raise ValueError
                if self.path == "/wants":  # a ponte pergunta se deve baixar áudio/imagem desta conversa
                    with lock:
                        wants = bot.esperto.wants_media(data["chat_id"], bool(data.get("is_group", True)), bot.clock())
                    return self._send(200, {"media": wants})
                if self.path == "/message":
                    if not isinstance(data.get("sender"), str) or not isinstance(data.get("text", ""), str):
                        raise ValueError
                    obj = Message.from_dict(data)
                else:
                    if data.get("type") not in ("join", "leave") or not isinstance(data.get("users"), list):
                        raise ValueError
                    obj = Event.from_dict(data)
            except (ValueError, TypeError):
                return self._send(400, {"error": "JSON inválido"})
            with lock:
                replies = bot.handle_message(obj, defer_ai=True) if self.path == "/message" else bot.handle_event(obj)
            job = getattr(obj, "esperto_job", None)
            if job:  # chamada de rede à IA fora do lock, para não travar os outros grupos
                replies = list(replies) + bot.complete_job(obj, lock)
            self._send(200, {"replies": [r.to_dict() for r in replies]})

    return ThreadingHTTPServer((host, port), Handler)
