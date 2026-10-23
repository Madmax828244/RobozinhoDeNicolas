"""Permissões, moderação automática, boas-vindas, horários, módulos e limites de uso."""
import unittest

from nicolas.core import Event
from nicolas.utils import local_dt
from tests.helpers import ADMIN, BOT, CHAT, MEMBER, MEMBER2, OWNER, actions, jid, make_bot, prime, say, texts


class PermissionTests(unittest.TestCase):
    def setUp(self):
        self.bot, self.clock = make_bot()
        prime(self.bot)

    def test_member_cannot_run_admin_commands(self):
        for cmd in [f".ban @{MEMBER2}", f".expulsar @{MEMBER2}", f".mute @{MEMBER2}", f".adv @{MEMBER2}", ".antilink on",
                    ".setregras x", ".ativar jogos", ".desativar jogos", f".cargo @{MEMBER2} mod", ".logs", ".horario off",
                    ".proibir golpe", ".prefixo !", f".resetadv @{MEMBER2}", ".cmdoff piada"]:
            out = say(self.bot, cmd, sender=MEMBER)
            self.assertTrue("Apenas" in texts(out) or "administradores" in texts(out), f"{cmd} -> {texts(out)!r}")
            self.assertEqual(actions(out), [], cmd)
        self.assertFalse(self.bot.db.is_banned(CHAT, MEMBER2))
        self.assertEqual(self.bot.db.group(CHAT)["antilink"], 0)

    def test_admin_ban_kicks_and_records(self):
        out = say(self.bot, f".ban @{MEMBER2} spam", sender=ADMIN)
        self.assertEqual(actions(out)[0]["type"], "kick")
        self.assertTrue(self.bot.db.is_banned(CHAT, MEMBER2))
        self.assertIn("ban", texts(say(self.bot, ".logs", sender=ADMIN)))

    def test_cannot_punish_admins_owner_or_bot(self):
        for target in (ADMIN, OWNER, BOT):
            out = say(self.bot, f".ban @{target}", sender=ADMIN)
            self.assertEqual(actions(out), [], target)
            self.assertFalse(self.bot.db.is_banned(CHAT, target))

    def test_ban_without_bot_admin_does_not_pretend_to_kick(self):
        out = say(self.bot, f".ban @{MEMBER2}", sender=ADMIN, bot_admin=False)
        self.assertEqual(actions(out), [])
        self.assertIn("não sou admin", texts(out).lower())

    def test_target_from_reply_and_mention_list(self):
        out = say(self.bot, ".adv motivo", sender=ADMIN, quoted=MEMBER2)
        self.assertEqual(self.bot.db.warning_count(CHAT, MEMBER2), 1)
        say(self.bot, ".adv", sender=ADMIN, mentioned=[MEMBER2])
        self.assertEqual(self.bot.db.warning_count(CHAT, MEMBER2), 2)

    def test_missing_target_gives_helpful_error(self):
        self.assertIn("Marque", texts(say(self.bot, ".ban", sender=ADMIN)))

    def test_warnings_escalate_to_kick(self):
        for i in range(2):
            out = say(self.bot, f".adv @{MEMBER2} x", sender=ADMIN)
            self.assertEqual(actions(out), [])
        out = say(self.bot, f".adv @{MEMBER2} x", sender=ADMIN)
        self.assertEqual(actions(out)[0]["type"], "kick")
        self.assertEqual(self.bot.db.warning_count(CHAT, MEMBER2), 0)

    def test_roles_moderator_limits(self):
        say(self.bot, f".cargo @{MEMBER2} mod", sender=ADMIN)
        self.assertEqual(self.bot.db.role(CHAT, MEMBER2), "mod")
        ok = say(self.bot, f".adv @{MEMBER} x", sender=MEMBER2)
        self.assertIn("advertência", texts(ok))
        denied = say(self.bot, f".ban @{MEMBER}", sender=MEMBER2)
        self.assertIn("Apenas", texts(denied))
        say(self.bot, f".desautorizar @{MEMBER2}", sender=ADMIN)
        self.assertEqual(self.bot.db.role(CHAT, MEMBER2), "membro")

    def test_only_platform_admins_can_grant_roles(self):
        say(self.bot, f".autorizar @{MEMBER2}", sender=MEMBER)
        self.assertEqual(self.bot.db.role(CHAT, MEMBER2), "membro")
        say(self.bot, f".autorizar @{MEMBER2}", sender=ADMIN)
        self.assertEqual(self.bot.db.role(CHAT, MEMBER2), "admin")
        # um "autorizado" pode usar comandos de admin do bot, mas não concede cargos
        self.assertIn("anti-link ativado", texts(say(self.bot, ".antilink on", sender=MEMBER2)).lower())
        say(self.bot, f".autorizar @{MEMBER}", sender=MEMBER2)
        self.assertEqual(self.bot.db.role(CHAT, MEMBER), "membro")

    def test_owner_has_all_permissions_without_being_group_admin(self):
        out = say(self.bot, f".ban @{MEMBER2}", sender=OWNER)
        self.assertTrue(self.bot.db.is_banned(CHAT, MEMBER2))
        self.assertEqual(actions(out)[0]["type"], "kick")

    def test_group_only_commands_refused_in_private(self):
        out = say(self.bot, f".ban @{MEMBER2}", sender=OWNER, group=False)
        self.assertIn("só funciona em grupos", texts(out))

    def test_missing_arguments_show_usage(self):
        out = texts(say(self.bot, ".calcular"))
        self.assertIn("Uso:", out)
        self.assertIn("Exemplo:", out)


class AutoModerationTests(unittest.TestCase):
    def setUp(self):
        self.bot, self.clock = make_bot()
        prime(self.bot)

    def test_antilink_removes_and_warns_members_but_not_admins(self):
        say(self.bot, ".antilink on", sender=ADMIN)
        out = say(self.bot, "olha isso https://exemplo.com/x", sender=MEMBER)
        self.assertEqual(actions(out)[0]["type"], "delete")
        self.assertIn("1/3", texts(out))
        self.assertEqual(say(self.bot, "https://exemplo.com", sender=ADMIN), [])
        self.assertEqual(self.bot.db.warning_count(CHAT, ADMIN), 0)

    def test_antilink_detects_whatsapp_invites_and_kicks_at_limit(self):
        say(self.bot, ".antilink on", sender=ADMIN)
        say(self.bot, "chat.whatsapp.com/ABC", sender=MEMBER)
        say(self.bot, "www.site.com", sender=MEMBER)
        out = say(self.bot, "wa.me/5511999999999", sender=MEMBER)
        self.assertEqual([a["type"] for a in actions(out)], ["delete", "kick"])

    def test_antilink_off_ignores_links(self):
        self.assertEqual(say(self.bot, "https://exemplo.com", sender=MEMBER), [])

    def test_plain_text_is_not_a_link(self):
        say(self.bot, ".antilink on", sender=ADMIN)
        for text in ["oi tudo bem?", "preço 3.50 reais", "fim.começo", "versão 2.0 saiu"]:
            self.assertEqual(say(self.bot, text, sender=MEMBER), [], text)

    def test_badwords_accent_and_case_insensitive(self):
        say(self.bot, ".proibir golpe", sender=ADMIN)
        out = say(self.bot, "Isso é um GOLPÉ!", sender=MEMBER)
        self.assertIn("palavra proibida", texts(out))
        self.assertEqual(say(self.bot, "golpe", sender=ADMIN), [])
        self.assertEqual(say(self.bot, "golpeado", sender=MEMBER), [])  # só palavra inteira
        say(self.bot, ".liberar golpe", sender=ADMIN)
        self.assertEqual(say(self.bot, "golpe", sender=MEMBER), [])

    def test_antiflood_mutes_and_deletes(self):
        say(self.bot, ".antiflood on", sender=ADMIN)
        out = []
        for i in range(6):
            out = say(self.bot, f"msg {i}", sender=MEMBER)
        self.assertIn("anti-flood", texts(out))
        self.assertGreater(self.bot.db.mute_until(CHAT, MEMBER, self.clock()), 0)
        later = say(self.bot, "ainda falando", sender=MEMBER)
        self.assertEqual(actions(later)[0]["type"], "delete")
        self.clock.advance(301)
        self.assertEqual(say(self.bot, "voltei", sender=MEMBER), [])

    def test_flood_spread_over_time_is_fine(self):
        say(self.bot, ".antiflood on", sender=ADMIN)
        for i in range(12):
            self.clock.advance(5)
            self.assertEqual(say(self.bot, f"msg {i}", sender=MEMBER), [])

    def test_manual_mute_and_expiry(self):
        say(self.bot, f".mute @{MEMBER} 10m", sender=ADMIN)
        self.assertEqual(actions(say(self.bot, "oi", sender=MEMBER))[0]["type"], "delete")
        out = say(self.bot, ".ping", sender=MEMBER)  # silenciado também não executa comandos
        self.assertNotIn("Pong", texts(out))
        self.clock.advance(601)
        self.assertIn("Pong", texts(say(self.bot, ".ping", sender=MEMBER)))
        say(self.bot, f".mute @{MEMBER} 1h", sender=ADMIN)
        say(self.bot, f".desmute @{MEMBER}", sender=ADMIN)
        self.assertEqual(say(self.bot, "oi", sender=MEMBER), [])

    def test_banned_user_message_triggers_kick(self):
        say(self.bot, f".ban @{MEMBER2}", sender=ADMIN)
        out = say(self.bot, "voltei", sender=MEMBER2)
        self.assertEqual(actions(out)[0]["type"], "kick")
        say(self.bot, f".desban @{MEMBER2}", sender=ADMIN)
        self.assertNotIn("kick", [a["type"] for a in actions(say(self.bot, "oi", sender=MEMBER2))])

    def test_moderators_are_exempt_from_automatic_rules(self):
        say(self.bot, ".antilink on", sender=ADMIN)
        say(self.bot, f".cargo @{MEMBER2} mod", sender=ADMIN)
        self.assertEqual(say(self.bot, "https://exemplo.com", sender=MEMBER2), [])


class EventTests(unittest.TestCase):
    def setUp(self):
        self.bot, self.clock = make_bot()

    def _join(self, *users):
        return self.bot.handle_event(Event(type="join", chat_id=CHAT, users=[jid(u) for u in users], group_name="Turma", bot_is_admin=True))

    def test_welcome_and_goodbye(self):
        self.assertEqual(self._join(MEMBER), [])  # desligado por padrão
        say(self.bot, ".bemvindo on", sender=ADMIN)
        say(self.bot, ".setregras Respeite todos", sender=ADMIN)
        out = self._join(MEMBER)
        self.assertIn("Turma", texts(out))
        self.assertIn("Respeite todos", texts(out))
        self.assertEqual(out[0].mentions, [jid(MEMBER)])
        say(self.bot, ".setbemvindo Oi {usuario}, bem-vindo ao {grupo}!", sender=ADMIN)
        self.assertIn(f"@{MEMBER}", texts(self._join(MEMBER)))
        bye = self.bot.handle_event(Event(type="leave", chat_id=CHAT, users=[jid(MEMBER)]))
        self.assertIn("saiu", texts(bye))

    def test_antifake_kicks_foreign_numbers(self):
        say(self.bot, ".antifake on", sender=ADMIN)
        out = self._join("14155550123")
        self.assertEqual(actions(out)[0]["type"], "kick")
        self.assertEqual(actions(self._join(MEMBER)), [])

    def test_banned_user_cannot_rejoin(self):
        say(self.bot, f".ban @{MEMBER2}", sender=ADMIN)
        self.assertEqual(actions(self._join(MEMBER2))[0]["type"], "kick")

    def test_events_never_raise(self):
        self.assertEqual(self.bot.handle_event(Event(type="join", chat_id=CHAT, users=[None])), [])


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.bot, self.clock = make_bot()
        prime(self.bot)

    def test_hours_restrict_members_but_not_admins(self):
        self.assertEqual(local_dt(self.clock(), -3).hour, 12)
        say(self.bot, ".horario 13:00 14:00", sender=ADMIN)
        self.assertEqual(say(self.bot, ".ping", sender=MEMBER), [])
        self.assertIn("Pong", texts(say(self.bot, ".ping", sender=ADMIN)))
        say(self.bot, ".horario 11:00 13:00", sender=ADMIN)
        self.assertIn("Pong", texts(say(self.bot, ".ping", sender=MEMBER)))
        say(self.bot, ".horario 22:00 06:00", sender=ADMIN)  # janela que cruza a meia-noite
        self.assertEqual(say(self.bot, ".ping", sender=MEMBER), [])
        say(self.bot, ".horario off", sender=ADMIN)
        self.assertIn("Pong", texts(say(self.bot, ".ping", sender=MEMBER)))

    def test_invalid_hours_rejected(self):
        self.assertIn("HH:MM", texts(say(self.bot, ".horario 25:00 26:00", sender=ADMIN)))

    def test_disable_and_enable_module(self):
        self.assertIn("desativado", texts(say(self.bot, ".desativar economia", sender=ADMIN)))
        self.assertIn("desativado", texts(say(self.bot, ".carteira", sender=MEMBER)))
        self.assertIn("Pong", texts(say(self.bot, ".ping", sender=MEMBER)))
        say(self.bot, ".ativar economia", sender=ADMIN)
        self.assertIn("Carteira", texts(say(self.bot, ".carteira", sender=MEMBER)))

    def test_essential_modules_cannot_be_disabled(self):
        self.assertIn("essencial", texts(say(self.bot, ".desativar sistema", sender=ADMIN)))
        self.assertIn("essencial", texts(say(self.bot, ".desativar admin", sender=ADMIN)))
        self.assertIn("inexistente", texts(say(self.bot, ".desativar naoexiste", sender=ADMIN)))

    def test_module_settings_are_per_group(self):
        say(self.bot, ".desativar jogos", sender=ADMIN, chat=CHAT)
        other = "120363000000000002@g.us"
        self.assertNotIn("desativado", texts(say(self.bot, ".ppt pedra", sender=MEMBER, chat=other)))
        self.assertIn("desativado", texts(say(self.bot, ".ppt pedra", sender=MEMBER, chat=CHAT)))

    def test_disable_single_command(self):
        say(self.bot, ".cmdoff piada", sender=ADMIN)
        self.assertIn("desativado", texts(say(self.bot, ".piada", sender=MEMBER)))
        say(self.bot, ".cmdon piada", sender=ADMIN)
        self.assertIn("😂", texts(say(self.bot, ".piada", sender=MEMBER)))
        self.assertIn("essenciais", texts(say(self.bot, ".cmdoff ping", sender=ADMIN)))

    def test_prefix_is_configurable_per_group(self):
        self.assertIn("Prefixo atual: *.*", texts(say(self.bot, ".prefixo", sender=MEMBER)))
        say(self.bot, ".prefixo !", sender=ADMIN)
        self.assertEqual(say(self.bot, ".ping", sender=MEMBER), [])
        self.assertIn("Pong", texts(say(self.bot, "!ping", sender=MEMBER)))
        self.assertIn("1 a 3 símbolos", texts(say(self.bot, "!prefixo abc", sender=ADMIN)))
        other = "120363000000000002@g.us"
        self.assertIn("Pong", texts(say(self.bot, ".ping", sender=MEMBER, chat=other)))

    def test_rules_and_description(self):
        self.assertIn("ainda não tem regras", texts(say(self.bot, ".regras", sender=MEMBER)))
        say(self.bot, ".setregras 1. Respeito", sender=ADMIN)
        self.assertIn("1. Respeito", texts(say(self.bot, ".regras", sender=MEMBER)))
        out = say(self.bot, ".setdesc Grupo da turma", sender=ADMIN)
        self.assertEqual(actions(out)[0]["type"], "set_description")

    def test_config_and_maxwarn(self):
        say(self.bot, ".antilink on", sender=ADMIN)
        say(self.bot, ".maxadv 2", sender=ADMIN)
        cfg = texts(say(self.bot, ".config", sender=ADMIN))
        self.assertIn("limite de advertências: 2", cfg)
        self.assertIn("✅ Anti-link", cfg)
        self.assertIn("2 a 10", texts(say(self.bot, ".maxadv 99", sender=ADMIN)))


class SafetyTests(unittest.TestCase):
    def test_rate_limit_blocks_spammers_and_warns_once(self):
        bot, clock = make_bot(rate_limit_count=3, rate_limit_window=10)
        results = [texts(say(bot, ".ping", sender=MEMBER)) for _ in range(6)]
        self.assertEqual(sum("Pong" in r for r in results), 3)
        self.assertEqual(sum("rápido demais" in r for r in results), 1)
        clock.advance(11)
        self.assertIn("Pong", texts(say(bot, ".ping", sender=MEMBER)))
        self.assertIn("Pong", texts(say(bot, ".ping", sender=MEMBER2)))  # limite é por usuário

    def test_command_cooldown(self):
        bot, clock = make_bot()
        say(bot, ".piada", sender=MEMBER)
        self.assertIn("Aguarde", texts(say(bot, ".piada", sender=MEMBER)))
        clock.advance(4)
        self.assertIn("😂", texts(say(bot, ".piada", sender=MEMBER)))

    def test_messages_from_self_and_empty_are_ignored(self):
        bot, _ = make_bot()
        prime(bot, MEMBER)
        self.assertEqual(say(bot, "", sender=MEMBER), [])
        self.assertEqual(say(bot, "   ", sender=MEMBER), [])
        self.assertEqual(say(bot, ". ping", sender=MEMBER), [])
        self.assertEqual(say(bot, "..", sender=MEMBER), [])

    def test_weird_command_names_do_not_crash(self):
        bot, _ = make_bot()
        for text in [".'; DROP TABLE users;--", ".../etc/passwd", "." + "a" * 500, ".‮test", ".ping\x00", ".💥"]:
            say(bot, text, sender=MEMBER)
        self.assertEqual(bot.stats["errors"], 0)
        self.assertTrue(bot.db.integrity_ok())

    def test_handler_exceptions_are_contained(self):
        bot, _ = make_bot()
        bot.registry.commands["ping"].handler = lambda ctx: 1 / 0
        with self.assertLogs("nicolas", level="ERROR") as logs:
            out = say(bot, ".ping", sender=MEMBER)
        self.assertIn("ZeroDivisionError", "\n".join(logs.output))
        self.assertIn("erro interno", texts(out))
        self.assertNotIn("division", texts(out))  # não vaza detalhes
        self.assertEqual(bot.stats["errors"], 1)

    def test_level_up_and_first_message_achievement(self):
        bot, clock = make_bot()
        out = say(bot, "oi", sender=MEMBER)
        self.assertIn("Primeiros passos", texts(out))
        bot.db.add_xp(CHAT, MEMBER, 99 - bot.db.stats(CHAT, MEMBER)["xp"])  # 99 XP: falta pouco para o nível 2
        clock.advance(120)
        out = say(bot, "mais uma", sender=MEMBER)
        self.assertIn("nível 2", texts(out))

    def test_health(self):
        bot, _ = make_bot()
        h = bot.health()
        self.assertTrue(h["ok"])
        self.assertEqual(h["comandos"], bot.registry.counts()["comandos"])


if __name__ == "__main__":
    unittest.main()
