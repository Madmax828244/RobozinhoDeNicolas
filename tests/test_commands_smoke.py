"""Garante que CADA comando registrado executa de verdade (sem erro interno), sem depender de rede."""
import re
import unittest
from unittest import mock

from nicolas.net import NetError
from tests.helpers import ADMIN, CHAT, jid, make_bot, say, texts


def offline(*args, **kwargs):
    raise NetError("sem rede (teste)")


class EveryCommandTests(unittest.TestCase):
    def _patches(self):
        targets = ["nicolas.plugins.informacoes.request_json", "nicolas.plugins.utilidades.request_json",
                   "nicolas.ai_client.request_json"]
        return [mock.patch(t, offline) for t in targets]

    def test_every_command_executes_without_internal_error(self):
        probe, _ = make_bot()
        names = sorted(probe.registry.commands)
        self.assertGreater(len(names), 100)
        problems = []
        patches = self._patches()
        for p in patches:
            p.start()
        try:
            for name in names:
                bot, clock = make_bot()
                cmd = bot.registry.commands[name]
                args = ""
                if cmd.example:
                    args = cmd.example[len(cmd.example.split()[0]):].strip()
                elif cmd.min_args:
                    args = " ".join(["teste"] * cmd.min_args)
                replies = say(bot, f".{name} {args}".strip(), sender=ADMIN, group=True)
                out = texts(replies)
                if bot.stats["errors"]:
                    problems.append(f".{name}: exceção interna")
                elif "erro interno" in out:
                    problems.append(f".{name}: respondeu erro interno")
                elif "não encontrado" in out and "Comando" in out:
                    problems.append(f".{name}: dispatcher não achou o comando")
                elif not replies:
                    problems.append(f".{name}: sem resposta")
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(problems, [], "\n".join(problems))

    def test_every_alias_resolves_to_a_working_command(self):
        bot, _ = make_bot()
        for alias, (target, preset) in bot.registry.aliases.items():
            cmd, pre = bot.registry.resolve(alias)
            self.assertEqual(cmd.name, target)
            self.assertEqual(pre, preset)

    def test_unit_shortcuts_work_end_to_end(self):
        bot, _ = make_bot()
        self.assertIn("6.213712", texts(say(bot, ".km-mi 10")))
        self.assertIn("212", texts(say(bot, ".c-f 100")))
        self.assertIn("1000", texts(say(bot, ".gb-mb 1")))

    def test_dice_shortcuts(self):
        bot, _ = make_bot()
        self.assertIn("d20", texts(say(bot, ".d20")))
        self.assertIn("d100", texts(say(bot, ".d100")))

    def test_menu_pages_are_all_reachable_and_counts_are_real(self):
        bot, _ = make_bot()
        first = texts(say(bot, ".menu"))
        total = int(re.search(r"página 1/(\d+)", first).group(1))
        real = bot.registry.counts()["comandos"]
        self.assertIn(f"*{real}* comandos registrados", first)
        for n in range(1, total + 1):
            out = texts(say(bot, f".menu {n}"))
            self.assertIn(f"página {n}/{total}", out)
        self.assertIn("inválida", texts(say(bot, f".menu {total + 1}")))
        self.assertIn("Administração", texts(say(bot, ".menu admin")))
        self.assertIn("não encontrada", texts(say(bot, ".menu xyz")))

    def test_menu_lists_every_visible_command_exactly_once(self):
        bot, _ = make_bot()
        total = int(re.search(r"página 1/(\d+)", texts(say(bot, ".menu"))).group(1))
        pages = "\n".join(texts(say(bot, f".menu {n}")) for n in range(2, total + 1))
        for name in bot.registry.commands:
            self.assertEqual(len(re.findall(rf"^• \*\.{re.escape(name)}\*", pages, re.M)), 1, name)

    def test_search_command(self):
        bot, _ = make_bot()
        self.assertIn(".senha", texts(say(bot, ".comandos senha")))
        self.assertIn("Nada encontrado", texts(say(bot, ".comandos zzzzzz")))

    def test_help_for_a_command(self):
        bot, _ = make_bot()
        out = texts(say(bot, ".ajuda calcular"))
        self.assertIn("Uso:", out)
        self.assertIn("Aliases:", out)

    def test_unknown_command_suggests_similar(self):
        bot, _ = make_bot()
        self.assertIn(".ping", texts(say(bot, ".pign")))

    def test_ping_status_info_dono(self):
        bot, _ = make_bot(owner_name="Fulano", owner_contact="@fulano")
        self.assertIn("Pong", texts(say(bot, ".ping")))
        st = texts(say(bot, ".status"))
        self.assertIn("íntegro", st)
        self.assertIn("IA: ⚪ não configurado", st)
        self.assertIn(str(bot.registry.counts()["comandos"]), texts(say(bot, ".info")))
        self.assertIn("Fulano", texts(say(bot, ".dono")))


if __name__ == "__main__":
    unittest.main()
