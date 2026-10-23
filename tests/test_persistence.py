"""Lembretes e dados sobrevivem a reinício do bot (banco em arquivo) e há backup com rotação."""
import os
import tempfile
import time
import unittest

from nicolas.backup import make_backup
from nicolas.db import Database

from .helpers import ADMIN, CHAT, MEMBER, T0, make_bot, prime, say, texts


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "data", "nicolas.db")

    def test_reminder_survives_restart_and_is_delivered_late(self):
        bot, clock = make_bot(db_path=self.path)
        prime(bot)
        clock.advance(60)
        out = say(bot, ".lembrar 10m tomar água", sender=MEMBER)
        self.assertIn("combinado", texts(out).lower())
        self.assertEqual(len(bot.db.pending_reminders(CHAT, MEMBER)), 1)
        bot.db.close()  # bot desligado / celular sem bateria

        bot2, clock2 = make_bot(db_path=self.path)  # ligado de novo, muito depois
        clock2.advance(3 * 3600)
        due = [d for d in bot2.due_reminders() if "ligado e funcionando" not in d["reply"]["text"]]
        self.assertEqual(len(due), 1)
        self.assertIn("tomar água", due[0]["reply"]["text"])
        self.assertEqual(bot2.due_reminders(), [])  # não repete

    def test_group_settings_and_xp_survive_restart(self):
        bot, clock = make_bot(db_path=self.path)
        bot.db.set_group(CHAT, rules="regra 1", antilink=True)
        bot.db.close()
        bot2, _ = make_bot(db_path=self.path)
        g = bot2.db.group(CHAT)
        self.assertEqual(g["rules"], "regra 1")
        self.assertTrue(g["antilink"])

    def test_backup_is_valid_and_rotates(self):
        db = Database(self.path)
        db.set_group(CHAT, rules="guardado")
        for i in range(5):
            f = make_backup(db, keep=3)
            time.sleep(1.05)  # nomes têm resolução de segundos
        files = sorted(os.listdir(os.path.join(self.dir.name, "data", "backups")))
        self.assertEqual(len(files), 3)
        restored = Database(os.path.join(self.dir.name, "data", "backups", files[-1]))
        self.assertEqual(restored.group(CHAT)["rules"], "guardado")
        db.close()
        restored.close()

    def test_memory_db_backup_is_noop(self):
        self.assertIsNone(make_backup(Database(":memory:")))


if __name__ == "__main__":
    unittest.main()


class StartupNoticeTests(unittest.TestCase):
    def test_owner_is_told_when_bot_comes_back(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "nicolas.db")
            bot, clock = make_bot(db_path=path)
            first = bot.due_reminders()
            self.assertEqual(len(first), 1)  # aviso de "ligado"
            self.assertIn("ligado", first[0]["reply"]["text"])
            self.assertEqual(bot.due_reminders(), [])  # só uma vez por execução
            bot.db.close()
            bot2, clock2 = make_bot(db_path=path)
            clock2.advance(2 * 3600)  # celular ficou desligado
            note = bot2.due_reminders()[0]["reply"]["text"]
            self.assertIn("fora por cerca de 120 min", note)
