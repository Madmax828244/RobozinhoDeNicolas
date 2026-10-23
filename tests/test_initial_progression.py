"""Valores iniciais de XP/moedas: idempotentes, com backup e sem mexer nos outros usuários."""
from __future__ import annotations

import os
import tempfile
import time
import unittest

from nicolas.db import Database
from nicolas.initial_users import INITIAL_USERS, apply_initial_progression
from nicolas.utils import level_for

CHAT = "120363000000000001@g.us"
CHAT2 = "120363000000000002@g.us"
OTHER = "5511888887777"


class InitialProgressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "data", "nicolas.db")
        self.db = Database(self.path)
        self.addCleanup(lambda: getattr(self.db, "close", lambda: None)())
        self.a, self.b = INITIAL_USERS  # a: 55 81 9727-6369 • b: 55 81 7314-3183

    def test_requested_values(self):
        self.assertEqual(self.a["phone"], "558197276369")
        self.assertEqual((self.a["xp_target"], self.a["coins"]), (891, 789))
        self.assertEqual(self.b["phone"], "558173143183")
        self.assertEqual(self.b["xp_target"], 1228)
        self.assertGreater(self.b["coins"], 1_090_000)
        self.assertGreaterEqual(level_for(1228), 4)
        self.assertEqual(level_for(891), 3)  # o nível 4 começa em 900 XP

    def test_replaces_old_seed_values_exactly_once(self):
        now = time.time()
        # situação da versão anterior: XP 8100/6400 e moedas 1279/1345, chaves antigas já gravadas
        for user, xp, coins in ((self.a, 8100, 1279), (self.b, 6400, 1345)):
            self.db.execute("INSERT OR REPLACE INTO wallets(user_id,coins) VALUES (?,?)", (user["canonical_id"], coins))
            self.db.execute("INSERT INTO member_stats(chat_id,user_id,xp) VALUES (?,?,?)", (CHAT, user["canonical_id"], xp))
            self.db.execute("INSERT OR IGNORE INTO seed_applications(seed_key,user_id,chat_id,applied_at) VALUES (?,?,?,?)",
                            (f"xp:v2:{CHAT}:{user['canonical_id']}", user["canonical_id"], CHAT, now))
            self.db.execute("INSERT OR IGNORE INTO seed_applications(seed_key,user_id,chat_id,applied_at) VALUES (?,?,?,?)",
                            (f"wallet:{user['canonical_id']}", user["canonical_id"], "", now))
        result = apply_initial_progression(self.db)
        self.assertTrue(result["backup"] and os.path.isfile(result["backup"]))
        self.assertEqual(self.db.stats(CHAT, self.a["canonical_id"])["xp"], 891)
        self.assertEqual(self.db.stats(CHAT, self.b["canonical_id"])["xp"], 1228)
        self.assertEqual(level_for(1228), 4)
        self.assertEqual(self.db.wallet(self.a["canonical_id"])["coins"], 789)
        self.assertEqual(self.db.wallet(self.b["canonical_id"])["coins"], 1_090_001)
        again = apply_initial_progression(self.db)
        self.assertEqual((again["wallets"], again["xp_rows"]), (0, 0))

    def test_later_progress_is_kept_after_restart_and_others_untouched(self):
        a_id, b_id = self.a["phone"], self.b["phone"]
        self.db.touch_user(a_id, "A")
        self.db.touch_user(b_id, "B")
        self.db.execute("INSERT INTO member_stats(chat_id,user_id,xp) VALUES (?,?,?)", (CHAT, a_id, 50))
        self.db.execute("INSERT INTO member_stats(chat_id,user_id,xp) VALUES (?,?,?)", (CHAT, b_id, 70))
        self.db.add_coins(OTHER, 88, "t", time.time())
        self.db.execute("INSERT INTO member_stats(chat_id,user_id,xp) VALUES (?,?,?)", (CHAT, OTHER, 77))
        result = apply_initial_progression(self.db)
        self.assertTrue(os.path.isfile(result["backup"]))
        self.assertEqual(self.db.stats(CHAT, self.a["canonical_id"])["xp"], 891)
        self.assertEqual(self.db.stats(CHAT, self.b["canonical_id"])["xp"], 1228)
        self.assertEqual(self.db.wallet(OTHER)["coins"], 88)
        self.assertEqual(self.db.stats(CHAT, OTHER)["xp"], 77)
        # a variante com o 9º dígito não cria uma segunda carteira nem outra linha de XP
        ids = sorted(self.b["ids"])
        marks = ",".join("?" for _ in ids)
        self.assertEqual(len(self.db.query(f"SELECT user_id FROM wallets WHERE user_id IN ({marks})", tuple(ids))), 1)
        self.assertEqual(len(self.db.query(f"SELECT user_id FROM member_stats WHERE chat_id=? AND user_id IN ({marks})", (CHAT, *ids))), 1)
        # gastos e ganhos normais depois da configuração valem e sobrevivem ao reinício
        self.db.add_coins(self.a["phone"], -9, "gasto", time.time())
        self.db.add_xp(CHAT, self.a["phone"], 20)
        self.db.close()
        self.db = Database(self.path)
        second = apply_initial_progression(self.db)
        self.assertEqual((second["wallets"], second["xp_rows"]), (0, 0))
        self.assertEqual(self.db.wallet(self.a["canonical_id"])["coins"], 780)
        self.assertEqual(self.db.stats(CHAT, self.a["canonical_id"])["xp"], 911)

    def test_first_seen_in_a_new_group_starts_with_the_configured_xp(self):
        apply_initial_progression(self.db)
        self.db.register_message(CHAT2, self.a["phone"], time.time(), 0)
        self.assertEqual(self.db.stats(CHAT2, self.a["canonical_id"])["xp"], 891)
        self.db.register_message(CHAT2, self.b["phone"], time.time(), 0)
        self.assertEqual(self.db.stats(CHAT2, self.b["canonical_id"])["xp"], 1228)

    def test_rank_lists_the_two_with_their_numbers(self):
        self.db.touch_user(self.a["phone"], "A")
        self.db.touch_user(self.b["phone"], "B")
        self.db.register_message(CHAT, self.a["phone"], time.time(), 0)
        self.db.register_message(CHAT, self.b["phone"], time.time(), 0)
        apply_initial_progression(self.db)
        rows = {r["user_id"]: r for r in self.db.top_members(CHAT, "xp", 10)}
        self.assertEqual(rows[self.b["canonical_id"]]["xp"], 1228)
        self.assertEqual(rows[self.a["canonical_id"]]["xp"], 891)
        self.assertEqual(self.db.top_members(CHAT, "xp", 10)[0]["user_id"], self.b["canonical_id"])


if __name__ == "__main__":
    unittest.main()


class ApplyToChatTests(unittest.TestCase):
    def test_owner_command_puts_both_profiles_in_the_group_rank(self):
        from tests.helpers import OWNER, MEMBER, make_bot, prime, say, texts
        bot, clock = make_bot()
        prime(bot)
        clock.advance(60)
        self.assertIn("Apenas", texts(say(bot, ".ajustarperfis", sender=MEMBER)))
        out = texts(say(bot, ".ajustarperfis", sender=OWNER))
        self.assertIn("1228 XP (nível 4)", out)
        self.assertIn("891 XP (nível 3)", out)
        rows = {r["user_id"]: r["xp"] for r in bot.db.top_members("120363000000000001@g.us", "xp", 20)}
        a, b = INITIAL_USERS
        self.assertEqual(rows[b["canonical_id"]], 1228)
        self.assertEqual(rows[a["canonical_id"]], 891)
        self.assertEqual(bot.db.wallet(a["phone"])["coins"], 789)
        self.assertGreater(bot.db.wallet(b["phone"])["coins"], 1_090_000)
