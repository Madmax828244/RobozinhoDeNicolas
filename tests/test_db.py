import os
import sqlite3
import tempfile
import threading
import unittest

from nicolas.db import MIGRATIONS, Database, InsufficientFunds

NOW = 1_760_000_000.0
A = "5511000000001"
B = "5511000000002"


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def test_migrations_are_idempotent(self):
        self.assertEqual(self.db.schema_version(), MIGRATIONS[-1][0])
        self.assertEqual(self.db.migrate(), [])
        self.assertTrue(self.db.integrity_ok())

    def test_persistence_across_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "bot.db")  # cria a pasta se necessário
            db = Database(path)
            db.add_coins("5511", 50, "teste", NOW)
            db.close()
            again = Database(path)
            self.assertEqual(again.wallet("5511")["coins"], 50)
            self.assertEqual(again.schema_version(), MIGRATIONS[-1][0])
            again.close()

    def test_failed_migration_rolls_back(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.db")
            Database(path).close()
            import nicolas.db as dbmod
            original = list(dbmod.MIGRATIONS)
            dbmod.MIGRATIONS.append((99, "quebrada", ["CREATE TABLE ok_antes (a INT)", "INSERT INTO tabela_inexistente VALUES (1)"]))
            try:
                with self.assertRaises(sqlite3.Error):
                    Database(path)
            finally:
                dbmod.MIGRATIONS[:] = original
            db = Database(path)
            self.assertEqual(db.schema_version(), original[-1][0])
            self.assertIsNone(db.one("SELECT name FROM sqlite_master WHERE name='ok_antes'"))

    def test_group_defaults_and_validation(self):
        g = self.db.group("c@g.us")
        self.assertEqual(g["disabled_modules"], [])
        self.db.set_group("c@g.us", antilink=True, disabled_modules=["jogos", "jogos", "ia"])
        g = self.db.group("c@g.us")
        self.assertEqual(g["antilink"], 1)
        self.assertEqual(g["disabled_modules"], ["ia", "jogos"])
        with self.assertRaises(ValueError):
            self.db.set_group("c@g.us", created_at=1)

    def test_wallet_never_negative(self):
        self.db.add_coins(A, 10, "t", NOW)
        with self.assertRaises(InsufficientFunds):
            self.db.add_coins(A, -11, "t", NOW)
        self.assertEqual(self.db.wallet(A)["coins"], 10)

    def test_transfer_atomic_and_validated(self):
        self.db.add_coins(A, 100, "t", NOW)
        self.db.transfer(A, B, 40, NOW)
        self.assertEqual((self.db.wallet(A)["coins"], self.db.wallet(B)["coins"]), (60, 40))
        with self.assertRaises(InsufficientFunds):
            self.db.transfer(A, B, 61, NOW)
        for bad in (((A, A, 1)), (A, B, 0), (A, B, -5)):
            with self.assertRaises(ValueError):
                self.db.transfer(*bad, NOW)
        self.assertEqual(self.db.wallet(A)["coins"] + self.db.wallet(B)["coins"], 100)  # nada criado nem perdido

    def test_concurrent_transfers_cannot_double_spend(self):
        self.db.add_coins(A, 100, "t", NOW)
        results = []

        def go(dst):
            try:
                self.db.transfer(A, dst, 100, NOW)
                results.append(True)
            except InsufficientFunds:
                results.append(False)

        threads = [threading.Thread(target=go, args=(f"d{i}",)) for i in range(12)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(results.count(True), 1)
        self.assertEqual(self.db.wallet(A)["coins"], 0)

    def test_daily_only_once_per_day_and_streak(self):
        first = self.db.claim_daily(A, "2025-10-09", "2025-10-08")
        self.assertEqual(first, (120, 1))
        self.assertIsNone(self.db.claim_daily(A, "2025-10-09", "2025-10-08"))
        self.assertEqual(self.db.claim_daily(A, "2025-10-10", "2025-10-09"), (140, 2))
        self.assertEqual(self.db.claim_daily(A, "2025-10-13", "2025-10-12"), (120, 1))  # quebrou a sequência
        self.assertEqual(self.db.wallet(A)["coins"], 120 + 140 + 120)

    def test_daily_race_pays_once(self):
        out = []
        threads = [threading.Thread(target=lambda: out.append(self.db.claim_daily(A, "d", "y"))) for _ in range(10)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len([o for o in out if o]), 1)
        self.assertEqual(self.db.wallet(A)["coins"], 120)

    def test_mission_claim_pays_exactly_once(self):
        out = []
        threads = [threading.Thread(target=lambda: out.append(self.db.claim_mission(A, "d", "m1", 50, NOW))) for _ in range(10)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(out.count(True), 1)
        self.assertEqual(self.db.wallet(A)["coins"], 50)

    def test_work_cooldown(self):
        ok, bal = self.db.claim_work(A, NOW, 3600, 40)
        self.assertTrue(ok)
        ok, wait = self.db.claim_work(A, NOW + 100, 3600, 40)
        self.assertFalse(ok)
        self.assertAlmostEqual(wait, 3500)
        self.assertTrue(self.db.claim_work(A, NOW + 3601, 3600, 40)[0])

    def test_buy_is_atomic(self):
        self.db.add_coins(A, 30, "t", NOW)
        with self.assertRaises(InsufficientFunds):
            self.db.buy_item(A, "troféu", 500, NOW)
        self.assertEqual(self.db.inventory(A), [])
        self.db.buy_item(A, "pao", 30, NOW)
        self.db.add_coins(A, 30, "t", NOW)
        self.db.buy_item(A, "pao", 30, NOW)
        self.assertEqual(self.db.inventory(A), [{"item": "pao", "qty": 2}])

    def test_xp_cooldown_and_levels(self):
        old, new, msgs = self.db.register_message("c", A, NOW, 10)
        self.assertEqual((old, new, msgs), (1, 1, 1))
        self.db.register_message("c", A, NOW + 5, 10)  # dentro do cooldown: sem XP
        self.assertEqual(self.db.stats("c", A)["xp"], 10)
        self.assertEqual(self.db.stats("c", A)["msgs"], 2)
        self.db.register_message("c", A, NOW + 120, 95)
        self.assertEqual(self.db.stats("c", A)["xp"], 105)

    def test_reminders_fire_once(self):
        self.db.add_reminder("c", A, NOW + 10, "x")
        self.assertEqual(self.db.due_reminders(NOW), [])
        self.assertEqual(len(self.db.due_reminders(NOW + 11)), 1)
        self.assertEqual(self.db.due_reminders(NOW + 11), [])

    def test_ban_mute_roles_roundtrip(self):
        self.db.ban("c", A, "r", "adm", NOW)
        self.assertTrue(self.db.is_banned("c", A))
        self.assertTrue(self.db.unban("c", A))
        self.db.set_mute("c", A, NOW + 10, "adm")
        self.assertEqual(self.db.mute_until("c", A, NOW), NOW + 10)
        self.assertEqual(self.db.mute_until("c", A, NOW + 11), 0)  # expirou e foi limpo
        self.db.set_role("c", A, "mod")
        self.assertEqual(self.db.role("c", A), "mod")
        self.db.set_role("c", A, "membro")
        self.assertEqual(self.db.role("c", A), "membro")


if __name__ == "__main__":
    unittest.main()
