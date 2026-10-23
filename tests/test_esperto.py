"""Modo esperto: IA responde no grupo (ask é simulado; nenhuma rede é usada)."""
import base64
import time
import unittest
from unittest import mock

from nicolas.db import Database, MIGRATIONS

from .helpers import ADMIN, CHAT, MEMBER, OWNER, make_bot, prime, say, texts

SECRET = "CHAVE-SECRETA-DE-TESTE"
AI = dict(ai_provider="gemini", ai_model="gemini-flash-latest", ai_api_key=SECRET)


def fake_ask(cfg, prompt, history=(), system="", max_tokens=700):
    fake_ask.calls.append({"prompt": prompt, "system": system})
    return "resposta da IA"


def fake_generate(cfg, prompt, system, media=(), tools=True, max_tokens=700):
    fake_ask.calls.append({"prompt": prompt, "system": system, "media": list(media)})
    return {"text": "resposta da IA", "calls": []}


class EspertoTests(unittest.TestCase):
    def setUp(self):
        fake_ask.calls = []
        for target, fake in (("nicolas.esperto.ask", fake_ask), ("nicolas.esperto.gemini_media.generate", fake_generate)):
            patcher = mock.patch(target, fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.bot, self.clock = make_bot(**AI)
        prime(self.bot)
        self.clock.advance(60)

    def on(self):
        out = say(self.bot, "/ativaesperto", sender=ADMIN)
        self.clock.advance(5)
        return out

    def test_only_admin_can_toggle(self):
        out = texts(say(self.bot, "/ativaesperto", sender=MEMBER))
        self.assertIn("Apenas", out)
        self.assertFalse(self.bot.db.group(CHAT)["esperto"])

    def test_requires_ai_configured(self):
        bot, _ = make_bot()
        out = texts(say(bot, "/ativaesperto", sender=ADMIN))
        self.assertIn("não foi configurada", out)
        self.assertFalse(bot.db.group(CHAT)["esperto"])

    def test_on_replies_to_normal_messages_and_off_stops(self):
        self.assertIn("Modo esperto ativado", texts(self.on()))
        self.assertTrue(self.bot.db.group(CHAT)["esperto"])
        out = say(self.bot, "qual a capital da França?", sender=MEMBER)
        self.assertEqual(texts(out), "resposta da IA")
        self.clock.advance(5)
        self.assertIn("desligado", texts(say(self.bot, "/desligaresperto", sender=ADMIN)))
        self.clock.advance(5)
        self.assertEqual(say(self.bot, "e agora?", sender=MEMBER), [])
        self.assertEqual(len(fake_ask.calls), 1)

    def test_commands_do_not_trigger_ai_but_unknown_slash_does(self):
        self.on()
        say(self.bot, ".ping", sender=MEMBER)
        self.assertEqual(fake_ask.calls, [])
        out = say(self.bot, "/qualquercoisa", sender=MEMBER)  # prefixo "/" desconhecido = conversa
        self.assertEqual(texts(out), "resposta da IA")

    def test_dot_prefix_unknown_command_still_reports(self):
        self.on()
        out = texts(say(self.bot, ".comandoinexistente", sender=MEMBER))
        self.assertIn("não encontrado", out)

    def test_group_rate_limit_is_respected(self):
        bot, clock = make_bot(esperto_per_minute=2, **AI)
        prime(bot); clock.advance(60)
        say(bot, "/ativaesperto", sender=ADMIN); clock.advance(5)
        replies = [texts(say(bot, f"mensagem {i}", sender=MEMBER)) for i in range(4)]
        self.assertEqual(replies.count("resposta da IA"), 2)
        clock.advance(61)
        self.assertEqual(texts(say(bot, "outra", sender=MEMBER)), "resposta da IA")

    def test_moderated_messages_get_no_ai_reply(self):
        self.on()
        self.bot.db.set_group(CHAT, antilink=True)
        out = say(self.bot, "olha https://spam.com", sender=MEMBER)
        self.assertNotIn("resposta da IA", texts(out))
        self.assertEqual(fake_ask.calls, [])

    def test_call_request_is_honest_and_does_not_call_ai(self):
        self.on()
        before = len(fake_ask.calls)
        out = texts(say(self.bot, "me liga agora", sender=MEMBER))
        self.assertIn("não consigo iniciar chamadas", out)
        self.assertEqual(len(fake_ask.calls), before)

    def test_text_provider_explains_audio_output_limit(self):
        bot, _clock = make_bot(ai_provider="groq", ai_model="llama-3.3-70b", ai_api_key=SECRET)
        prime(bot)
        bot.db.set_group(CHAT, esperto=True)
        with mock.patch("nicolas.tts._local_bin", return_value=None):
            out = texts(say(bot, "manda um áudio falando oi", sender=MEMBER))
        self.assertIn("Ainda não tenho uma voz configurada", out)
        self.assertIn("python3 -m nicolas voz", out)

    def test_ai_failure_is_reported_once_without_spam(self):
        from nicolas.net import NetError
        self.on()
        with mock.patch("nicolas.esperto.gemini_media.generate", side_effect=NetError("fora do ar")):
            first = texts(say(self.bot, "oi bot", sender=MEMBER))
            second = say(self.bot, "outra mensagem", sender=MEMBER)
        self.assertIn("IA está indisponível", first)
        self.assertEqual(second, [])

    def test_prompt_never_contains_the_key_and_has_context(self):
        self.on()
        say(self.bot, "primeira", sender=MEMBER); self.clock.advance(5)
        say(self.bot, "segunda", sender=OWNER)
        last = fake_ask.calls[-1]
        self.assertNotIn(SECRET, last["prompt"] + last["system"])
        self.assertIn("primeira", last["prompt"])
        self.assertIn("resposta da IA", last["prompt"])  # a própria resposta entra no contexto

    def test_deferred_mode_returns_job_for_server(self):
        from .helpers import jid, BOT
        from nicolas.core import Message
        self.on()
        msg = Message(chat_id=CHAT, sender=jid(MEMBER), text="oi", sender_name="Zé", bot_is_admin=True, bot_id=jid(BOT),
                      timestamp=self.clock(), group_admins=[jid(ADMIN)])
        self.assertEqual(self.bot.handle_message(msg, defer_ai=True), [])
        self.assertIsNotNone(msg.esperto_job)
        self.assertEqual(texts(self.bot.esperto.run(msg.esperto_job)), "resposta da IA")

    def _wait_outbox(self):
        for _ in range(100):
            out = self.bot.due_reminders()
            if out:
                return out
            time.sleep(0.02)
        return []

    def test_proactive_message_once_per_silence(self):
        self.on()
        say(self.bot, "bom dia", sender=MEMBER)
        self.assertEqual(self.bot.due_reminders(), [])  # ainda não ficou ocioso
        self.clock.advance(181 * 60)  # 15:00 local
        out = self._wait_outbox()
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["chat_id"], CHAT)
        self.assertEqual(out[0]["reply"]["text"], "resposta da IA")
        self.clock.advance(600)
        time.sleep(0.1)
        self.assertEqual(self.bot.due_reminders(), [])  # não repete enquanto ninguém falar

    def test_proactive_respects_flags_and_night(self):
        self.on()
        say(self.bot, "oi", sender=MEMBER)
        self.bot.db.set_group(CHAT, esperto_proativo=False)
        self.clock.advance(181 * 60)
        time.sleep(0.1)
        self.assertEqual(self.bot.due_reminders(), [])
        self.bot.db.set_group(CHAT, esperto_proativo=True)
        self.clock.advance(8 * 3600)  # 23:01 local: fora do horário
        time.sleep(0.1)
        self.assertEqual(self.bot.due_reminders(), [])

    def test_proactive_off_when_mode_off(self):
        say(self.bot, "oi", sender=MEMBER)
        self.clock.advance(181 * 60)
        time.sleep(0.1)
        self.assertEqual(self.bot.due_reminders(), [])
        self.assertEqual(fake_ask.calls, [])


class MigrationTests(unittest.TestCase):
    def test_v1_database_upgrades_to_latest_schema(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.db")
            with mock.patch("nicolas.db.MIGRATIONS", MIGRATIONS[:1]):
                Database(path).close()
            db = Database(path)
            self.assertEqual(db.schema_version(), MIGRATIONS[-1][0])
            g = db.group("a@g.us")
            self.assertEqual((g["esperto"], g["esperto_proativo"]), (0, 1))


if __name__ == "__main__":
    unittest.main()


class OwnAccountTests(unittest.TestCase):
    """Mensagens enviadas manualmente pelo dono no grupo podem receber resposta do modo esperto."""

    def setUp(self):
        self.bot, self.clock = make_bot(**AI)
        from .helpers import OWNER
        self.own = OWNER

    def own_say(self, text):
        from .helpers import jid, BOT
        from nicolas.core import Message
        msg = Message(chat_id=CHAT, sender=jid(self.own), text=text, sender_name="Eu", bot_is_admin=True,
                      bot_id=jid(BOT), timestamp=self.clock(), from_me=True)
        return self.bot.handle_message(msg)

    def test_own_command_runs(self):
        self.assertIn("Pong", texts(self.own_say(".ping")) + texts(self.own_say(".ping")))

    def test_own_plain_text_ignored_when_mode_off_but_unknown_slash_is_conversation(self):
        self.assertEqual(self.own_say("bom dia"), [])
        self.assertEqual(self.own_say(".comandoquenaoexiste"), [])
        self.assertEqual(self.own_say("/qualquercoisa"), [])

    def test_owner_plain_group_message_triggers_ai_when_enabled(self):
        fake_ask.calls = []
        with mock.patch("nicolas.esperto.gemini_media.generate", fake_generate):
            self.bot.db.set_group(CHAT, esperto=True)
            out = self.own_say("oi pessoal")
        self.assertEqual(texts(out), "resposta da IA")
        self.assertEqual(len(fake_ask.calls), 1)


class DuplicateMessageTests(unittest.TestCase):
    def test_same_whatsapp_message_id_is_processed_once(self):
        from nicolas.core import Message
        from .helpers import jid, BOT
        bot, clock = make_bot(**AI)
        prime(bot)
        clock.advance(60)
        bot.db.set_group(CHAT, esperto=True)
        msg = Message(chat_id=CHAT, sender=jid(MEMBER), text="pergunta com id repetido", sender_name="Membro",
                      bot_is_admin=True, bot_id=jid(BOT), timestamp=clock(), message_id="DUPLICATE-ID")
        before = bot.db.stats(CHAT, MEMBER)["msgs"]
        first = bot.handle_message(msg)
        repeated = Message.from_dict({k: v for k, v in msg.__dict__.items() if k != "esperto_job"})
        self.assertTrue(first)
        self.assertEqual(bot.handle_message(repeated), [])
        self.assertEqual(bot.db.stats(CHAT, MEMBER)["msgs"], before + 1)


class ControlCommandsTests(unittest.TestCase):
    def setUp(self):
        self.bot, self.clock = make_bot()

    def test_only_owner_can_shutdown_or_logout(self):
        for cmd in (".desligarbot", ".desconectar confirmar", "/pararbot"):
            out = say(self.bot, cmd, sender=ADMIN)
            self.assertIn("Apenas", texts(out))
            self.assertEqual([a for r in out for a in r.actions], [])

    def test_owner_shutdown_emits_control_action(self):
        out = say(self.bot, ".desligarbot", sender=OWNER)
        self.assertEqual([a["type"] for r in out for a in r.actions], ["shutdown"])
        self.assertIn("start.sh", texts(out))

    def test_logout_requires_confirmation(self):
        out = say(self.bot, ".desconectar", sender=OWNER)
        self.assertEqual([a for r in out for a in r.actions], [])
        self.assertIn("confirmar", texts(out))
        self.clock.advance(10)
        out = say(self.bot, ".desconectar confirmar", sender=OWNER)
        self.assertEqual([a["type"] for r in out for a in r.actions], ["logout"])

    def test_works_in_private_chat_too(self):
        out = say(self.bot, ".desligarbot", sender=OWNER, group=False)
        self.assertEqual([a["type"] for r in out for a in r.actions], ["shutdown"])


class OwnerRecognitionTests(unittest.TestCase):
    def test_brazilian_ninth_digit_variants(self):
        from nicolas.config import Config
        from nicolas.security import is_owner
        cfg = Config(owner_ids=("558188616931",))  # digitado sem o 9
        self.assertTrue(is_owner(cfg, "5581988616931@s.whatsapp.net"))  # JID com o 9
        self.assertTrue(is_owner(cfg, "558188616931"))
        self.assertFalse(is_owner(cfg, "5581988616932"))
        self.assertFalse(is_owner(cfg, "5511988616931"))
        cfg2 = Config(owner_ids=("5581988616931",))
        self.assertTrue(is_owner(cfg2, "558188616931@s.whatsapp.net"))
        self.assertFalse(is_owner(Config(owner_ids=()), "5581988616931"))

    def test_connected_account_is_owner_even_if_not_in_owner_ids(self):
        from nicolas.core import Message
        from nicolas.security import role_of
        from nicolas.registry import ROLE_OWNER, ROLE_MEMBER
        bot, _ = make_bot(owner_ids=())
        mine = Message(chat_id=CHAT, sender="5599@s.whatsapp.net", text=".x", from_me=True)
        other = Message(chat_id=CHAT, sender="5599@s.whatsapp.net", text=".x")
        self.assertEqual(role_of(bot.cfg, bot.db, mine), ROLE_OWNER)
        self.assertEqual(role_of(bot.cfg, bot.db, other), ROLE_MEMBER)


def _media_cfg():
    return dict(ai_provider="gemini", ai_model="m", ai_api_key=SECRET)


class MediaAndDmTests(unittest.TestCase):
    """Áudio, imagem, voz e conversas diretas (Gemini simulado)."""

    def setUp(self):
        self.bot, self.clock = make_bot(**_media_cfg())
        prime(self.bot)
        self.clock.advance(60)
        say(self.bot, "/ativaesperto", sender=ADMIN)
        self.clock.advance(5)

    def msg(self, text="", media=(), group=True, sender=MEMBER, from_me=False, chat_id=None):
        from .helpers import jid, BOT
        from nicolas.core import Message
        chat = chat_id or (CHAT if group else jid(sender))
        return Message(chat_id=chat, sender=jid(sender), text=text, is_group=group, sender_name="Zé", bot_is_admin=True,
                       bot_id=jid(BOT), timestamp=self.clock(), media=list(media), from_me=from_me)

    def test_audio_only_message_is_answered_and_audio_sent_to_model(self):
        seen = {}

        def gen(cfg, prompt, system, media=(), tools=True, max_tokens=700):
            seen["media"], seen["tools"] = list(media), tools
            return {"text": "entendi o áudio", "calls": []}
        with mock.patch("nicolas.esperto.gemini_media.generate", gen), \
             mock.patch("nicolas.esperto.gemini_media.speak", side_effect=__import__("nicolas.net").net.NetError("sem voz")):
            out = self.bot.handle_message(self.msg("", media=[{"kind": "audio", "mime": "audio/ogg", "data": "QUJD"}]))
        self.assertEqual(seen["media"][0]["data"], "QUJD")
        self.assertEqual(texts(out), "entendi o áudio")  # TTS falhou: cai para texto

    def test_voice_note_gets_voice_reply_when_tts_works(self):
        fake = {"data": b"OGGDATA", "mimetype": "audio/ogg; codecs=opus", "ptt": True}
        with mock.patch("nicolas.esperto.gemini_media.generate",
                        lambda *a, **k: {"text": "oi!", "calls": []}), \
             mock.patch("nicolas.esperto.gemini_media.speak", return_value=fake):
            out = self.bot.handle_message(self.msg("", media=[{"kind": "audio", "mime": "audio/ogg", "data": "QUJD"}]))
        self.assertEqual(len(out), 1)
        self.assertEqual(__import__("base64").b64decode(out[0].audio_base64), b"OGGDATA")
        self.assertTrue(out[0].ptt)

    def test_function_call_generates_image_and_audio(self):
        with mock.patch("nicolas.esperto.gemini_media.generate",
                        lambda *a, **k: {"text": "Aqui está!", "calls": [{"name": "gerar_imagem", "args": {"descricao": "um gato"}}]}), \
             mock.patch("nicolas.esperto.gemini_media.make_image", return_value=("image/png", "SU1H")) as mk:
            out = self.bot.handle_message(self.msg("desenha um gato"))
        mk.assert_called_once()
        self.assertEqual((out[0].image_base64, out[0].text), ("SU1H", "Aqui está!"))
        self.clock.advance(20)
        fake = {"data": b"X", "mimetype": "audio/wav", "ptt": False}
        with mock.patch("nicolas.esperto.gemini_media.generate",
                        lambda *a, **k: {"text": "", "calls": [{"name": "falar_em_audio", "args": {"texto": "olá"}}]}), \
             mock.patch("nicolas.esperto.gemini_media.speak", return_value=fake):
            out = self.bot.handle_message(self.msg("manda um áudio dizendo olá"))
        self.assertEqual(out[0].audio_mimetype, "audio/wav")
        self.assertFalse(out[0].ptt)

    def test_image_failure_reports_honestly(self):
        from nicolas.net import NetError
        with mock.patch("nicolas.esperto.gemini_media.generate",
                        lambda *a, **k: {"text": "", "calls": [{"name": "gerar_imagem", "args": {"descricao": "x"}}]}), \
             mock.patch("nicolas.esperto.gemini_media.make_image", side_effect=NetError("cota")):
            out = self.bot.handle_message(self.msg("faz uma imagem"))
        self.assertIn("Não consegui gerar", texts(out))

    def test_wants_media_only_when_mode_on_and_gemini(self):
        es = self.bot.esperto
        self.assertTrue(es.wants_media(CHAT, True, self.clock()))
        self.assertFalse(es.wants_media("outro@g.us", True, self.clock()))
        bot2, _ = make_bot(ai_provider="anthropic", ai_model="m", ai_api_key=SECRET)
        bot2.db.set_group(CHAT, esperto=True)
        self.assertFalse(bot2.esperto.wants_media(CHAT, True, 0))  # sem transcrição de voz neste provedor
        bot3, _ = make_bot(ai_provider="groq", ai_model="m", ai_api_key=SECRET)
        bot3.db.set_group(CHAT, esperto=True)
        self.assertTrue(bot3.esperto.wants_media(CHAT, True, 0))  # Groq transcreve voz com Whisper

    def test_dm_mode_owner_only_and_replies(self):
        dm = lambda text, sender=MEMBER, **k: self.bot.handle_message(self.msg(text, group=False, sender=sender, **k))
        with mock.patch("nicolas.esperto.gemini_media.generate", lambda *a, **k: {"text": "oi no privado", "calls": []}):
            self.assertEqual(dm("oi"), [])  # desligado por padrão
            self.assertIn("Apenas", texts(dm(".espertodm on")))  # membro não pode
            self.assertIn("ligada", texts(dm(".espertodm on", sender=OWNER)))
            self.clock.advance(5)
            self.assertEqual(texts(dm("tudo bem?")), "oi no privado")
            # dono assume a conversa: IA silencia pelo tempo configurado
            self.assertEqual(self.bot.handle_message(self.msg("deixa comigo", group=False, from_me=True)), [])
            self.clock.advance(5)
            self.assertEqual(dm("e aí?"), [])
            self.clock.advance(11 * 60)
            self.assertEqual(texts(dm("voltei")), "oi no privado")

    def test_owner_enables_per_chat_in_a_dm_and_others_cannot(self):
        mk = lambda text, **k: self.bot.handle_message(self.msg(text, group=False, **k))
        dm_chat = "5511888880000@s.whatsapp.net"
        with mock.patch("nicolas.esperto.gemini_media.generate", lambda *a, **k: {"text": "oi no privado", "calls": []}):
            self.assertEqual(mk("oi", chat_id=dm_chat), [])  # desligado
            self.assertEqual(self.bot.esperto.counters["dm_off"], 1)
            self.assertIn("Apenas", texts(mk("/ativaesperto", chat_id=dm_chat)))  # contato não liga
            # o dono escreve /ativaesperto na própria conversa direta (mensagem do próprio número)
            out = mk("/ativaesperto", chat_id=dm_chat, from_me=True)
            self.assertIn("conversa direta", texts(out))
            self.clock.advance(11 * 60)  # passa a pausa do dono
            self.assertEqual(texts(mk("tudo bem?", chat_id=dm_chat)), "oi no privado")
            # outra conversa continua desligada
            self.assertEqual(mk("oi", chat_id="5511777770000@s.whatsapp.net"), [])
            self.clock.advance(5)
            mk("/desligaresperto", chat_id=dm_chat, from_me=True)
            self.clock.advance(11 * 60)
            self.assertEqual(mk("e agora?", chat_id=dm_chat), [])

    def test_own_plain_message_in_dm_is_not_a_command(self):
        self.assertEqual(self.bot.handle_message(self.msg("oi, tudo bem", group=False, from_me=True,
                                                          chat_id="5511888880000@s.whatsapp.net")), [])

    def test_commands_work_in_direct_chat(self):
        out = self.bot.handle_message(self.msg(".ping", group=False))
        self.assertIn("Pong", texts(out))


class GatewayMediaTests(unittest.TestCase):
    """HTTP: /wants e /message com áudio grande (a ponte -> Python)."""
    TOKEN = "t" * 24

    def setUp(self):
        import threading
        from nicolas.server import make_server
        self.bot, self.clock = make_bot(**_media_cfg())
        self.server = make_server(self.bot, "127.0.0.1", 0, self.TOKEN)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (self.server.shutdown(), self.server.server_close()))

    def post(self, path, payload):
        import json, urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json", "X-Bridge-Token": self.TOKEN})
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())

    def test_wants_follows_mode_and_large_audio_is_accepted(self):
        self.assertEqual(self.post("/wants", {"chat_id": CHAT, "is_group": True}), {"media": False})
        self.bot.db.set_group(CHAT, esperto=True)
        self.assertEqual(self.post("/wants", {"chat_id": CHAT, "is_group": True}), {"media": True})
        big = base64.b64encode(b"x" * 3_000_000).decode()  # ~4 MB em base64, bem acima dos antigos 64 KB
        seen = {}

        def gen(cfg, prompt, system, media=(), tools=True, max_tokens=700):
            seen["n"] = len(media[0]["data"])
            return {"text": "ouvi", "calls": []}
        with mock.patch("nicolas.esperto.gemini_media.generate", gen), mock.patch("nicolas.esperto.gemini_media.speak", side_effect=OSError):
            res = self.post("/message", {"chat_id": CHAT, "sender": "5511900000003@s.whatsapp.net", "text": "", "is_group": True,
                                         "media": [{"kind": "audio", "mime": "audio/ogg", "data": big}]})
        self.assertEqual(seen["n"], len(big))
        self.assertIn("ouvi", [r["text"] for r in res["replies"]])
