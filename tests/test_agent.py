"""Modo esperto como administrador ('Ei bot, organize o grupo'). A IA é simulada; nenhuma rede é usada."""
import json
import unittest
from unittest import mock

from nicolas import agent
from nicolas.core import Message

from .helpers import ADMIN, BOT, CHAT, MEMBER, MEMBER2, OWNER, jid, make_bot, prime, say, texts

AI = dict(ai_provider="groq", ai_model="m", ai_api_key="CHAVE-SECRETA-DE-TESTE")


def plan(resposta="feito", comandos=()):
    return json.dumps({"resposta": resposta, "comandos": list(comandos)})


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.bot, self.clock = make_bot(**AI)
        prime(self.bot)
        self.clock.advance(60)
        self.prompts = []
        self.answer = plan()

        def fake(cfg, prompt, history=(), system="", max_tokens=700):
            self.prompts.append((prompt, system))
            return self.answer
        p = mock.patch("nicolas.esperto.ask", fake)
        p.start()
        self.addCleanup(p.stop)
        say(self.bot, "/ativaesperto", sender=ADMIN)
        self.clock.advance(5)

    def send(self, text, sender=ADMIN, mentioned=(), **k):
        m = Message(chat_id=CHAT, sender=jid(sender), text=text, is_group=True, sender_name="Adm", bot_is_admin=True,
                    bot_id=jid(BOT), timestamp=self.clock(), group_admins=[jid(ADMIN)],
                    mentioned=[jid(x) for x in mentioned], **k)
        out = self.bot.handle_message(m)
        self.clock.advance(5)
        return out

    def test_call_detection(self):
        for t in ("Ei bot organize o grupo", "ei bot, organiza", "Nicolas, arruma isso", "bot faz algo", "Ok robô nicolas fecha"):
            self.assertTrue(agent.addressed(Message(chat_id="c", sender="s"), t), t)
        for t in ("o bot é legal", "vamos organizar o grupo", "robótica é massa"):
            self.assertFalse(agent.addressed(Message(chat_id="c", sender="s"), t), t)

    def test_admin_request_runs_planned_commands(self):
        self.answer = plan("Organizei! ✅", [".setdesc Grupo da turma", ".setregras 1. Respeito\n2. Sem spam",
                                              ".antilink on", ".bemvindo on"])
        out = self.send("Ei bot organize o grupo")
        body = texts(out)
        self.assertIn("Organizei", body)
        g = self.bot.db.group(CHAT)
        self.assertEqual(g["description"], "Grupo da turma")
        self.assertIn("Respeito", g["rules"])
        self.assertTrue(g["antilink"])
        self.assertTrue(g["welcome_on"])
        self.assertTrue(any(a["type"] == "set_description" for r in out for a in r.actions))
        # o prompt não carrega conversa do grupo, só o pedido do admin
        self.assertIn("organize o grupo", self.prompts[-1][0])
        self.assertNotIn("CHAVE-SECRETA", self.prompts[-1][0])

    def test_member_cannot_use_the_agent(self):
        self.answer = plan("ok", [".antilink on"])
        out = self.send("Ei bot organize o grupo", sender=MEMBER)
        self.assertFalse(self.bot.db.group(CHAT)["antilink"])
        self.assertNotIn("Organizei", texts(out))
        # membro cai no fluxo normal do modo esperto (sem plano): nenhum JSON/ comando é executado
        self.assertTrue(all("agent_prompt" not in (r.text or "") for r in out))

    def test_not_in_allowlist_or_owner_only_is_refused(self):
        self.answer = plan("ok", [".desligarbot", ".cargo @x admin", ".ban 5511999990000"])
        out = self.send("Ei bot faz tudo", sender=ADMIN)
        self.assertNotIn("Bot desligando", texts(out))
        self.assertFalse(any(a["type"] == "shutdown" for r in out for a in r.actions))

    def test_punishment_needs_a_marked_target_and_ignores_numbers_from_ai(self):
        self.answer = plan("ok", [".expulsar 5511999990009"])
        out = self.send("Ei bot expulsa o fulano")
        self.assertIn("marque", texts(out))
        self.assertFalse(any(a["type"] == "kick" for r in out for a in r.actions))
        self.answer = plan("ok", [".expulsar 5511999990009"])
        out = self.send("Ei bot expulsa esse", mentioned=[MEMBER2])
        kicks = [a for r in out for a in r.actions if a["type"] == "kick"]
        self.assertEqual(len(kicks), 1)
        self.assertEqual(kicks[0]["users"], [jid(MEMBER2)])  # só quem o admin marcou

    def test_max_six_commands_and_garbage_output(self):
        p = agent.parse_plan(plan("x", [".antilink on"] * 20))
        self.assertEqual(len(p["comandos"]), 6)
        self.assertEqual(agent.parse_plan("texto solto sem json")["comandos"], [])
        self.assertEqual(agent.parse_plan('{"comandos": "rm -rf"}')["comandos"], [])

    def test_plain_question_gets_plain_answer(self):
        self.answer = plan("São 12h!", [])
        self.assertIn("12h", texts(self.send("Ei bot que horas são?")))

    def test_close_open_and_rename_commands(self):
        self.answer = plan("ok", [".renomear Turma 2026", ".fechargrupo"])
        out = self.send("Ei bot muda o nome para Turma 2026 e fecha o grupo")
        types = [a["type"] for r in out for a in r.actions]
        self.assertIn("set_subject", types)
        self.assertIn("set_announce", types)
        self.assertTrue(any(a.get("announce") is True for r in out for a in r.actions))

    def test_agent_only_when_esperto_is_on(self):
        say(self.bot, "/desligaresperto", sender=ADMIN)
        self.clock.advance(5)
        self.answer = plan("ok", [".antilink on"])
        self.send("Ei bot organize o grupo")
        self.assertFalse(self.bot.db.group(CHAT)["antilink"])


if __name__ == "__main__":
    unittest.main()


class OwnerTalksToEspertoTests(AgentTests):
    """O bot roda no número do dono: as mensagens do dono (from_me) também precisam funcionar no modo esperto."""

    def own(self, text):
        m = Message(chat_id=CHAT, sender=jid(BOT), text=text, is_group=True, sender_name="Dono", bot_is_admin=True,
                    bot_id=jid(BOT), timestamp=self.clock(), from_me=True, group_admins=[jid(BOT)])
        out = self.bot.handle_message(m)
        self.clock.advance(5)
        return out

    def test_owner_gets_answer_when_calling_the_bot(self):
        self.answer = plan("Oi, dono!", [])
        self.assertIn("Oi, dono", texts(self.own("Ei bot, tudo bem?")))

    def test_owner_can_organize_the_group(self):
        self.answer = plan("Feito", [".antilink on"])
        self.own("Nicolas organiza o grupo")
        self.assertTrue(self.bot.db.group(CHAT)["antilink"])

    def test_owner_plain_chat_and_slash_chat_are_answered(self):
        self.answer = plan("resposta", [])
        self.assertIn("resposta", texts(self.own("kkkk boa galera")))
        self.assertIn("resposta", texts(self.own("/qual a capital da França")))


class MathTests(unittest.TestCase):
    def test_commands(self):
        bot, _ = make_bot()
        prime(bot)
        for cmd, expect in ((".tabuada 7", "7 x 10 = 70"), (".primo 97", "é primo"), (".primo 12", "2 × 2 × 3"),
                            (".fibonacci 8", "0, 1, 1, 2, 3, 5, 8, 13"), (".mdc 12 18", "= *6*"), (".mmc 4 6", "= *12*"),
                            (".romano 2026", "MMXXVI"), (".romano MCMXC", "1990"), (".imc 70 1.75", "22.9"),
                            (".gorjeta 120 10 4", "33.00"), (".desconto 200 15", "170.00"), (".palindromo Socorram-me subi"
                             , "palíndromo"), (".inverter abc", "cba")):
            self.assertIn(expect, texts(say(bot, cmd, sender=MEMBER)), cmd)
        self.assertIn("Equipe 2", texts(say(bot, ".equipes 2 a b c d", sender=MEMBER)))
        self.assertIn("inválido", texts(say(bot, ".romano IIII9", sender=MEMBER)).lower())


class OwnerInDirectMessageTests(AgentTests):
    """Dono na conversa privada: a IA responde quando ele chama o bot, não quando conversa normalmente."""
    FRIEND = "5511888880000@s.whatsapp.net"

    def dm(self, text, chat=None, **k):
        m = Message(chat_id=chat or self.FRIEND, sender=jid(BOT), text=text, is_group=False, sender_name="Dono",
                    bot_id=jid(BOT), timestamp=self.clock(), from_me=True, **k)
        out = self.bot.handle_message(m)
        self.clock.advance(5)
        return out

    def test_owner_calling_the_bot_gets_an_answer_but_plain_talk_does_not(self):
        self.dm("/ativaesperto")
        self.clock.advance(11 * 60)
        self.answer = plan("Resposta no privado", [])
        self.assertEqual(self.dm("oi tudo bem?"), [])  # conversa normal com o amigo: IA quieta (e pausa o modo)
        self.assertIn("Resposta no privado", texts(self.dm("Ei bot, quanto é 2+2?")))
        self.assertIn("Resposta no privado", texts(self.dm("/quanto é 2+2")))

    def test_calling_the_bot_does_not_pause_the_friend_replies(self):
        self.dm("/ativaesperto")
        self.clock.advance(11 * 60)
        self.dm("Ei bot, oi")
        m = Message(chat_id=self.FRIEND, sender=self.FRIEND, text="e aí?", is_group=False, sender_name="Amigo",
                    bot_id=jid(BOT), timestamp=self.clock())
        self.assertTrue(self.bot.handle_message(m))  # o amigo continua sendo respondido

    def test_self_chat_talks_to_the_ai(self):
        selfchat = jid(BOT)
        self.dm("/ativaesperto", chat=selfchat)
        self.answer = plan("Oi, eu mesmo!", [])
        self.assertIn("Oi, eu mesmo", texts(self.dm("me explica o que é um buraco negro", chat=selfchat)))

    def test_off_means_off(self):
        self.answer = plan("não deveria", [])
        self.assertEqual(self.dm("Ei bot, oi"), [])
