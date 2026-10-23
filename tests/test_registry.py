import unittest

from nicolas.registry import CATEGORIES, Command, DuplicateCommandError, Registry, load_plugins

REQUIRED = ["menu", "ajuda", "comandos", "ping", "status", "info", "dono", "prefixo", "ativar", "desativar", "rank",
            "perfil", "regras", "sorteio", "ia", "calcular", "traduzir", "tempo"]


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = load_plugins()

    def test_loads_without_problems(self):
        self.assertEqual(self.reg.validate(), [])
        self.assertGreater(self.reg.counts()["comandos"], 100)

    def test_required_commands_exist(self):
        for name in REQUIRED:
            self.assertIsNotNone(self.reg.resolve(name), f"comando obrigatório ausente: {name}")

    def test_counts_are_consistent(self):
        c = self.reg.counts()
        self.assertEqual(c["total_nomes"], len(self.reg.commands) + len(self.reg.aliases))
        self.assertEqual(c["aliases"] + c["atalhos"], len(self.reg.aliases))

    def test_every_command_is_wired_to_a_module_and_category(self):
        for cmd in self.reg.commands.values():
            self.assertIn(cmd.category, CATEGORIES, cmd.name)
            self.assertTrue(cmd.module, f"{cmd.name} sem módulo")
            self.assertTrue(callable(cmd.handler), cmd.name)
            self.assertTrue(cmd.description.strip(), cmd.name)

    def test_documented_examples_use_real_commands(self):
        for cmd in self.reg.commands.values():
            if cmd.example:
                self.assertIsNotNone(self.reg.resolve(cmd.example.split()[0]), f"{cmd.name}: exemplo inválido '{cmd.example}'")

    def test_aliases_point_to_existing_commands(self):
        for alias, (target, _) in self.reg.aliases.items():
            self.assertIn(target, self.reg.commands, alias)

    def test_duplicate_detection(self):
        reg = Registry()
        reg.register(Command(name="x", handler=lambda c: None, category="sistema", description="d"))
        with self.assertRaises(DuplicateCommandError):
            reg.register(Command(name="X", handler=lambda c: None, category="sistema", description="d"))
        with self.assertRaises(DuplicateCommandError):
            reg.register(Command(name="y", handler=lambda c: None, category="sistema", description="d", aliases=("x",)))

    def test_unknown_category_rejected(self):
        with self.assertRaises(ValueError):
            Registry().register(Command(name="z", handler=lambda c: None, category="nao-existe", description="d"))

    def test_accent_insensitive_resolution(self):
        self.assertIsNotNone(self.reg.resolve("calculá"))  # sem acento -> "calcula" (alias)
        self.assertIsNotNone(self.reg.resolve("CALCULAR"))

    def test_search_and_suggest(self):
        found = [c.name for c in self.reg.search("senha")]
        self.assertIn("senha", found)
        self.assertIn("ping", self.reg.suggest("pign"))
        self.assertEqual(self.reg.search(""), [])

    def test_modules_cover_all_commands(self):
        total = sum(len(v) for v in self.reg.modules().values())
        self.assertEqual(total, len(self.reg.commands))

    def test_only_filter_loads_subset(self):
        reg = load_plugins(only=["sistema"])
        self.assertTrue(set(reg.modules()) == {"sistema"})


if __name__ == "__main__":
    unittest.main()
