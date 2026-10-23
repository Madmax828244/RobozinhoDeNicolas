"""Economia, jogos, ferramentas, IA, servidor HTTP e configuração (.env)."""
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

from nicolas.calc import CalcError, calculate
from nicolas.config import ROOT, parse_env_text
from nicolas.envfile import init_env, set_env
from nicolas.net import NetError
from nicolas.plugins.jogos import DAILY_GAME_CAP
from nicolas.plugins.seguranca import generate_password, strength
from nicolas.server import make_server
from nicolas.units import UnitError, convert
from tests.helpers import ADMIN, CHAT, MEMBER, MEMBER2, actions, jid, make_bot, prime, say, texts


class EconomyTests(unittest.TestCase):
    def setUp(self):
        self.bot, self.clock = make_bot()
        prime(self.bot)

    def coins(self, user):
        return self.bot.db.wallet(user)["coins"]

    def test_daily_once_per_day_with_streak(self):
        self.assertIn("120", texts(say(self.bot, ".diario")))
        self.assertIn("já resgatou", texts(say(self.bot, ".diario")))
        self.clock.advance(86400)
        self.assertIn("140", texts(say(self.bot, ".diario")))
        self.assertEqual(self.coins(MEMBER), 260)

    def test_transfer_rules(self):
        self.bot.db.add_coins(MEMBER, 100, "teste", self.clock())
        self.assertIn("enviou *40*", texts(say(self.bot, f".transferir @{MEMBER2} 40")))
        self.assertEqual((self.coins(MEMBER), self.coins(MEMBER2)), (60, 40))
        self.clock.advance(10)
        self.assertIn("insuficiente", texts(say(self.bot, f".transferir @{MEMBER2} 61")).lower())
        for bad in ("0", "-5", "abc"):
            self.clock.advance(10)
            say(self.bot, f".transferir @{MEMBER2} {bad}")
        self.clock.advance(10)
        say(self.bot, f".transferir @{MEMBER} 10")  # para si mesmo
        self.assertEqual((self.coins(MEMBER), self.coins(MEMBER2)), (60, 40))

    def test_shop_and_titles(self):
        self.assertIn("insuficiente", texts(say(self.bot, ".comprar trofeu")).lower())
        self.assertEqual(self.bot.db.inventory(MEMBER), [])
        self.bot.db.add_coins(MEMBER, 1000, "teste", self.clock())
        self.clock.advance(3)
        self.assertIn("Pão", texts(say(self.bot, ".comprar pao")))
        self.clock.advance(3)
        say(self.bot, ".comprar titulo_lenda")
        self.assertIn("Lenda", texts(say(self.bot, ".titulo Lenda")))
        self.assertIn("Lenda", texts(say(self.bot, ".perfil")))
        self.assertIn("não possui", texts(say(self.bot, ".titulo Mestre")))
        self.clock.advance(3)
        self.assertIn("inexistente", texts(say(self.bot, ".comprar naoexiste")).lower())

    def test_missions_pay_exactly_once(self):
        for i in range(21):
            self.clock.advance(1)
            say(self.bot, f"mensagem {i}")
        first = texts(say(self.bot, ".resgatar"))
        self.assertIn("Total", first)
        before = self.coins(MEMBER)
        self.assertIn("Nenhuma missão", texts(say(self.bot, ".resgatar")))
        self.assertEqual(self.coins(MEMBER), before)

    def test_betting_never_goes_negative_or_over_limit(self):
        self.bot.db.add_coins(MEMBER, 300, "teste", self.clock())
        self.assertIn("máxima", texts(say(self.bot, ".apostar 501")))
        self.clock.advance(10)
        self.assertIn("suficientes", texts(say(self.bot, ".apostar 400")))
        for _ in range(60):
            self.clock.advance(10)
            say(self.bot, ".apostar tudo")
            self.assertGreaterEqual(self.coins(MEMBER), 0)
            if self.coins(MEMBER) == 0:
                break

    def test_money_is_conserved_in_transfers(self):
        self.bot.db.add_coins(MEMBER, 500, "teste", self.clock())
        total = self.coins(MEMBER) + self.coins(MEMBER2)
        for i in range(20):
            self.clock.advance(10)
            say(self.bot, f".transferir @{MEMBER2} {7 + i}")
            self.clock.advance(10)
            say(self.bot, f".transferir @{MEMBER} 5", sender=MEMBER2)
        self.assertEqual(self.coins(MEMBER) + self.coins(MEMBER2), total)

    def test_ranking_and_wallet_text_is_virtual_only(self):
        self.assertIn("sem valor real", texts(say(self.bot, ".carteira")))
        self.assertIn("Ranking", texts(say(self.bot, ".topricos")))


class GameTests(unittest.TestCase):
    def setUp(self):
        self.bot, self.clock = make_bot()
        prime(self.bot)

    def coins(self, user=MEMBER):
        return self.bot.db.wallet(user)["coins"]

    def solve_quiz(self, user=MEMBER):
        say(self.bot, ".quiz", sender=user)
        state = self.bot.db.game_get(CHAT, "quiz")
        return say(self.bot, f".resp {'abcd'[state['correct']]}", sender=user)

    def test_quiz_rewards_once_and_closes(self):
        out = self.solve_quiz()
        self.assertIn("acertou", texts(out))
        self.assertEqual(self.coins(), 15)
        self.assertIn("Não há quiz", texts(say(self.bot, ".resp a")))
        self.assertEqual(self.coins(), 15)

    def test_quiz_wrong_answer_only_once_per_user(self):
        say(self.bot, ".quiz")
        state = self.bot.db.game_get(CHAT, "quiz")
        wrong = "abcd"[(state["correct"] + 1) % 4]
        self.assertIn("não foi essa", texts(say(self.bot, f".resp {wrong}")))
        self.assertIn("já tentou", texts(say(self.bot, f".resp {wrong}")))
        self.assertIn("acertou", texts(say(self.bot, f".resp {'abcd'[state['correct']]}", sender=MEMBER2)))

    def test_quiz_timeout(self):
        say(self.bot, ".quiz")
        state = self.bot.db.game_get(CHAT, "quiz")
        self.clock.advance(120)
        self.assertIn("Tempo esgotado", texts(say(self.bot, f".resp {'abcd'[state['correct']]}")))
        self.assertEqual(self.coins(), 0)

    def test_game_rewards_are_capped_per_day(self):
        for _ in range(30):
            self.clock.advance(10)
            self.solve_quiz()
        self.assertEqual(self.coins(), DAILY_GAME_CAP)
        self.clock.advance(86400)
        self.solve_quiz()
        self.assertEqual(self.coins(), DAILY_GAME_CAP + 15)

    def test_tictactoe_full_game(self):
        out = say(self.bot, f".velha @{MEMBER2}")
        self.assertIn("Jogo da velha", texts(out))
        self.assertIn("Ainda não", texts(say(self.bot, ".jogar 1", sender=MEMBER2)))
        say(self.bot, ".jogar 1")
        self.assertIn("ocupada", texts(say(self.bot, ".jogar 1", sender=MEMBER2)))
        self.assertIn("não está nesta partida", texts(say(self.bot, ".jogar 2", sender=ADMIN)))
        for who, pos in ((MEMBER2, 4), (MEMBER, 2), (MEMBER2, 5)):
            say(self.bot, f".jogar {pos}", sender=who)
        out = say(self.bot, ".jogar 3")
        self.assertIn("venceu", texts(out))
        self.assertEqual(self.coins(), 25)
        self.assertIsNone(self.bot.db.game_get(CHAT, "velha"))

    def test_tictactoe_draw_and_cancel(self):
        say(self.bot, f".velha @{MEMBER2}")
        # empate: X O X / X O O / O X X
        for who, pos in ((MEMBER, 1), (MEMBER2, 2), (MEMBER, 3), (MEMBER2, 5), (MEMBER, 4), (MEMBER2, 6), (MEMBER, 8),
                         (MEMBER2, 7), (MEMBER, 9)):
            out = say(self.bot, f".jogar {pos}", sender=who)
        self.assertIn("Empate", texts(out))
        say(self.bot, f".velha @{MEMBER2}")
        self.assertIn("cancelada", texts(say(self.bot, ".velha cancelar")))
        self.assertIn("Não há partida", texts(say(self.bot, ".jogar 1")))

    def test_guess_number(self):
        say(self.bot, ".adivinhar 10")
        key = f"{CHAT}:{MEMBER}"
        secret = self.bot.db.game_get(key, "adivinhar")["n"]
        wrong = secret % 10 + 1
        self.assertRegex(texts(say(self.bot, f".chute {wrong}")), "maior|menor")
        self.assertIn("Acertou", texts(say(self.bot, f".chute {secret}")))
        self.assertIn("não tem jogo", texts(say(self.bot, ".chute 1")))

    def test_rock_paper_scissors_and_riddle(self):
        self.assertRegex(texts(say(self.bot, ".ppt pedra")), "venceu|Empate|Eu venci")
        self.assertIn("Escolha", texts(say(self.bot, ".ppt lagarto")))
        say(self.bot, ".charada")
        answer = self.bot.db.game_get(CHAT, "charada")["a"]
        self.assertIn("acertou", texts(say(self.bot, f".rc {answer}")))


class ToolTests(unittest.TestCase):
    def test_calculator_values(self):
        self.assertEqual(calculate("2*(3+4)^2"), 98)
        self.assertEqual(calculate("2,5*2"), 5)
        self.assertAlmostEqual(calculate("sqrt(16)+10%"), 4.1)
        self.assertEqual(calculate("fatorial(5)"), 120)

    def test_calculator_rejects_dangerous_input(self):
        bad = ["__import__('os').system('ls')", "().__class__", "2**10000", "9**9**9", "open('x')", "a+1", "1;2",
               "lambda: 1", "[1,2]", "'a'*5", "True+1", "fatorial(501)", "sqrt(-1)", "1/0", "9999999999**999",
               "1+" * 150 + "1", "(" * 100 + "1" + ")" * 100, "print(1)", "x" * 300]
        for expr in bad:
            with self.assertRaises(CalcError, msg=expr):
                calculate(expr)

    def test_units(self):
        self.assertEqual(convert(100, "c", "f"), 212)
        self.assertEqual(convert(1, "km", "m"), 1000)
        self.assertAlmostEqual(convert(0, "k", "c"), -273.15)
        self.assertAlmostEqual(convert(1, "gib", "mib"), 1024)
        for args in ((1, "kg", "m"), (1, "xx", "m"), (-300, "c", "k")):
            with self.assertRaises(UnitError):
                convert(*args)

    def test_passwords(self):
        pwd = generate_password(24)
        self.assertEqual(len(pwd), 24)
        self.assertFalse(set(pwd) & set("Il1O0o"))
        self.assertTrue(any(c.isdigit() for c in pwd) and any(c.isupper() for c in pwd) and any(c.islower() for c in pwd))
        self.assertNotEqual(generate_password(24), generate_password(24))
        self.assertIn("fraca", strength("123456")[1])
        self.assertIn("forte", strength(generate_password(24))[1])

    def test_dev_tools_and_text(self):
        bot, _ = make_bot()
        prime(bot)
        self.assertIn("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", texts(say(bot, ".hash sha256 abc")))
        enc = texts(say(bot, ".base64 enc olá")).strip("`")
        self.assertEqual(enc, "b2zDoQ==")
        self.assertIn("olá", texts(say(bot, f".base64 dec {enc}")))
        self.assertIn("inválido", texts(say(bot, ".base64 dec !!!")))
        self.assertIn('"a": 1', texts(say(bot, '.json {"a":1}')))
        self.assertIn("inválido", texts(say(bot, ".json {a")))
        self.assertIn("0b11111111", texts(say(bot, ".binario 255")))
        self.assertIn("ola-mundo", texts(say(bot, ".slug Olá Mundo!")))
        self.assertIn("𝗢", texts(say(bot, ".texto negrito Oi")))
        self.assertIn("Estilos", texts(say(bot, ".texto xyz oi")))

    def test_dates(self):
        bot, _ = make_bot()
        prime(bot)
        self.assertIn("30", texts(say(bot, ".idade 15/03/1995")))
        self.assertIn("77", texts(say(bot, ".diasate 25/12")))
        self.assertIn("Peixes", texts(say(bot, ".signo 15/03")))
        self.assertIn("12:00", texts(say(bot, ".hora")))
        self.assertIn("data não existe", texts(say(bot, ".idade 31/02/2000")).replace("Essa data", "data"))

    def test_raffle_is_fair_and_validated(self):
        bot, clock = make_bot()
        prime(bot)
        out = texts(say(bot, ".sorteio 2 ana, bia, caio"))
        self.assertEqual(out.count("🏆"), 2)
        self.assertIn("Código de verificação", out)
        clock.advance(10)
        self.assertIn("Só há 2", texts(say(bot, ".sorteio 5 a, b")))
        clock.advance(10)
        self.assertIn("1 a 10", texts(say(bot, ".sorteio 99 a, b")))

    def test_weather_with_mocked_service(self):
        bot, clock = make_bot()
        prime(bot)
        geo = {"results": [{"name": "São Paulo", "admin1": "SP", "country": "Brasil", "latitude": -23.5, "longitude": -46.6}]}
        fc = {"current": {"temperature_2m": 25, "apparent_temperature": 26, "relative_humidity_2m": 60, "weather_code": 0,
                          "wind_speed_10m": 10},
              "daily": {"time": ["2025-10-09", "2025-10-10", "2025-10-11"], "weather_code": [0, 3, 61],
                        "temperature_2m_max": [30, 28, 26], "temperature_2m_min": [18, 17, 16],
                        "precipitation_probability_max": [0, 10, 60]}}
        with mock.patch("nicolas.plugins.informacoes.request_json", side_effect=[geo, fc]):
            out = texts(say(bot, ".tempo São Paulo"))
        self.assertIn("São Paulo", out)
        self.assertIn("25°C", out)
        clock.advance(10)
        with mock.patch("nicolas.plugins.informacoes.request_json", side_effect=NetError("sem rede")):
            self.assertIn("Não consegui consultar", texts(say(bot, ".tempo Recife")))
        clock.advance(10)
        with mock.patch("nicolas.plugins.informacoes.request_json", return_value={"results": []}):
            self.assertIn("Não encontrei", texts(say(bot, ".tempo Xyzzy")))

    def test_qr_degrades_gracefully_without_segno(self):
        bot, _ = make_bot()
        prime(bot)
        with mock.patch.dict(sys.modules, {"segno": None}):
            self.assertIn("segno", texts(say(bot, ".qr https://exemplo.com")))


class AITests(unittest.TestCase):
    def test_not_configured_is_explicit(self):
        bot, _ = make_bot()
        prime(bot)
        out = texts(say(bot, ".ia oi"))
        self.assertIn("ainda não foi configurada", out)
        self.assertIn("não configurado", texts(say(bot, ".status")))

    def test_configured_provider_and_key_never_leaks(self):
        key = "SECRET-KEY-123"
        bot, _ = make_bot(ai_provider="openai", ai_model="m", ai_api_key=key)
        prime(bot)
        reply = {"choices": [{"message": {"content": "Olá do modelo"}}]}
        with mock.patch("nicolas.ai_client.request_json", return_value=reply) as rj:
            out = texts(say(bot, ".ia oi"))
        self.assertIn("Olá do modelo", out)
        self.assertNotIn(key, out)
        self.assertEqual(rj.call_args.kwargs["headers"]["Authorization"], f"Bearer {key}")
        bot.clock.advance(60)
        with mock.patch("nicolas.ai_client.request_json", side_effect=NetError("o serviço respondeu com erro HTTP 401")):
            out = texts(say(bot, ".explicar gravidade"))
        self.assertIn("Não consegui falar com a IA", out)
        self.assertNotIn(key, out)
        self.assertNotIn(key, texts(say(bot, ".status")))

    def test_other_providers_parse_responses(self):
        for provider, reply in (("anthropic", {"content": [{"type": "text", "text": "Resp A"}]}),
                                ("gemini", {"candidates": [{"content": {"parts": [{"text": "Resp G"}]}}]})):
            bot, _ = make_bot(ai_provider=provider, ai_model="m", ai_api_key="k" * 12)
            prime(bot)
            with mock.patch("nicolas.ai_client.request_json", return_value=reply):
                self.assertIn("Resp", texts(say(bot, ".ia oi")))
        bot, _ = make_bot(ai_provider="desconhecido", ai_model="m", ai_api_key="k" * 12)
        prime(bot)
        self.assertIn("desconhecido", texts(say(bot, ".ia oi")))

    def test_conversation_context_is_kept_per_user(self):
        bot, clock = make_bot(ai_provider="openai", ai_model="m", ai_api_key="k" * 12)
        prime(bot)
        reply = {"choices": [{"message": {"content": "ok"}}]}
        with mock.patch("nicolas.ai_client.request_json", return_value=reply) as rj:
            say(bot, ".ia primeira")
            clock.advance(60)
            say(bot, ".ia segunda")
        sent = rj.call_args.kwargs["data"]["messages"]
        self.assertEqual([m["content"] for m in sent if m["role"] == "user"], ["primeira", "segunda"])
        say(bot, ".iareset")
        self.assertEqual(len(bot.ai_history[(CHAT, MEMBER)]), 0)

    def test_translate_requires_service(self):
        bot, _ = make_bot()
        prime(bot)
        self.assertIn("Nenhum serviço de tradução", texts(say(bot, ".traduzir en bom dia")))
        bot.clock.advance(10)
        self.assertIn("Idioma não reconhecido", texts(say(bot, ".traduzir klingon bom dia")))
        bot2, _ = make_bot(translate_url="http://localhost:9")
        prime(bot2)
        with mock.patch("nicolas.plugins.utilidades.request_json", return_value={"translatedText": "good morning"}):
            self.assertIn("good morning", texts(say(bot2, ".traduzir en bom dia")))


class ServerTests(unittest.TestCase):
    TOKEN = "t" * 24

    def setUp(self):
        self.bot, self.clock = make_bot()
        self.server = make_server(self.bot, "127.0.0.1", 0, self.TOKEN)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def call(self, path, payload=None, token=TOKEN, method=None):
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Bridge-Token"] = token
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def msg(self, text=".ping", **over):
        base = {"chat_id": CHAT, "sender": jid(MEMBER), "text": text, "is_group": True, "bot_id": jid("5500000000000"),
                "timestamp": self.clock()}
        base.update(over)
        return base

    def test_requires_token(self):
        self.assertEqual(self.call("/message", self.msg(), token=None)[0], 401)
        self.assertEqual(self.call("/message", self.msg(), token="errado")[0], 401)
        self.assertEqual(self.call("/due", token=None)[0], 401)
        self.assertEqual(self.call("/event", {"type": "join", "chat_id": CHAT, "users": []}, token="x")[0], 401)

    def test_health_is_public_and_minimal(self):
        status, body = self.call("/health", token=None)
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"ok", "comandos"})

    def test_message_roundtrip(self):
        status, body = self.call("/message", self.msg())
        self.assertEqual(status, 200)
        self.assertTrue(any("Pong" in r["text"] for r in body["replies"]))

    def test_rejects_malformed_requests(self):
        self.assertEqual(self.call("/message", {"foo": 1})[0], 400)
        self.assertEqual(self.call("/message", {"chat_id": CHAT, "sender": 5, "text": "x"})[0], 400)
        self.assertEqual(self.call("/event", {"chat_id": CHAT, "type": "explodir", "users": []})[0], 400)
        self.assertEqual(self.call("/nada", self.msg())[0], 404)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("POST", "/message")
        conn.putheader("X-Bridge-Token", self.TOKEN)
        conn.putheader("Content-Length", str(13 * 1024 * 1024))
        conn.endheaders()
        self.assertEqual(conn.getresponse().status, 413)
        conn.close()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/message", body=b"{nao-json", headers={"X-Bridge-Token": self.TOKEN})
        self.assertEqual(conn.getresponse().status, 400)
        conn.close()

    def test_reminders_are_delivered_once(self):
        self.call("/message", self.msg(".lembrete 1m beber água"))
        self.assertEqual(self.call("/due")[1]["reminders"], [])
        self.clock.advance(61)
        due = self.call("/due")[1]["reminders"]
        self.assertEqual(len(due), 1)
        self.assertIn("beber água", due[0]["reply"]["text"])
        self.assertEqual(self.call("/due")[1]["reminders"], [])

    def test_event_endpoint(self):
        self.call("/message", self.msg(".bemvindo on", sender=jid(ADMIN), sender_is_admin=True, group_admins=[jid(ADMIN)]))
        status, body = self.call("/event", {"type": "join", "chat_id": CHAT, "users": [jid(MEMBER2)], "group_name": "Turma"})
        self.assertEqual(status, 200)
        self.assertIn("Turma", body["replies"][0]["text"])

    def test_server_requires_token_to_start(self):
        with self.assertRaises(ValueError):
            make_server(self.bot, "127.0.0.1", 0, "")


class EnvTests(unittest.TestCase):
    def test_parse_and_set_env(self):
        self.assertEqual(parse_env_text("BOT_NAME=Robô Nicolas 🤖\n# x\nA='b c'\n")["BOT_NAME"], "Robô Nicolas 🤖")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, ".env")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# comentário\nA=1\nB=2\n")
            set_env(path, "A", "novo")
            set_env(path, "C", "3")
            text = open(path, encoding="utf-8").read()
            self.assertEqual(text, "# comentário\nA=novo\nB=2\nC=3\n")
            for key, value in (("minusculo", "x"), ("A B", "x"), ("OK", "linha\nquebrada")):
                with self.assertRaises(ValueError):
                    set_env(path, key, value)

    def test_init_env_generates_private_token_once(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(ROOT / ".env.example", d)
            first = init_env(d)
            self.assertTrue(first["created"] and first["token_generated"])
            token = parse_env_text(open(os.path.join(d, ".env"), encoding="utf-8").read())["BRIDGE_TOKEN"]
            self.assertGreaterEqual(len(token), 32)
            if os.name == "posix":
                self.assertEqual(os.stat(os.path.join(d, ".env")).st_mode & 0o077, 0)
                self.assertEqual(os.stat(os.path.join(d, "auth")).st_mode & 0o077, 0)
            second = init_env(d)
            self.assertFalse(second["created"] or second["token_generated"])
            self.assertEqual(parse_env_text(open(os.path.join(d, ".env"), encoding="utf-8").read())["BRIDGE_TOKEN"], token)
            for folder in ("data", "logs", "auth"):
                self.assertTrue(os.path.isdir(os.path.join(d, folder)))

    def test_example_env_has_no_secrets(self):
        values = parse_env_text((ROOT / ".env.example").read_text(encoding="utf-8"))
        for key in ("BRIDGE_TOKEN", "AI_API_KEY", "TRANSLATE_API_KEY", "PAIRING_PHONE", "OWNER_IDS"):
            self.assertEqual(values.get(key, ""), "", key)


if __name__ == "__main__":
    unittest.main()
