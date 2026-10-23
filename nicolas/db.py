"""Camada de banco de dados (SQLite) com migrações versionadas e transações."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from .utils import level_for, num

# Cada migração é uma lista de instruções aplicadas dentro de uma transação.
MIGRATIONS: list[tuple[int, str, list[str]]] = [
    (1, "esquema inicial", [
        """CREATE TABLE groups (
            chat_id TEXT PRIMARY KEY,
            prefix TEXT NOT NULL DEFAULT '',
            rules TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            welcome TEXT NOT NULL DEFAULT '',
            goodbye TEXT NOT NULL DEFAULT '',
            welcome_on INTEGER NOT NULL DEFAULT 0,
            antilink INTEGER NOT NULL DEFAULT 0,
            antiflood INTEGER NOT NULL DEFAULT 0,
            antifake INTEGER NOT NULL DEFAULT 0,
            hours_on INTEGER NOT NULL DEFAULT 0,
            open_min INTEGER NOT NULL DEFAULT 0,
            close_min INTEGER NOT NULL DEFAULT 1439,
            max_warns INTEGER NOT NULL DEFAULT 3,
            disabled_modules TEXT NOT NULL DEFAULT '[]',
            disabled_commands TEXT NOT NULL DEFAULT '[]',
            created_at REAL NOT NULL
        )""",
        """CREATE TABLE users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            bio TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        )""",
        """CREATE TABLE member_stats (
            chat_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0,
            msgs INTEGER NOT NULL DEFAULT 0,
            last_xp REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )""",
        """CREATE TABLE roles (
            chat_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY (chat_id, user_id)
        )""",
        """CREATE TABLE warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            by_user TEXT NOT NULL DEFAULT '',
            ts REAL NOT NULL
        )""",
        "CREATE INDEX idx_warn ON warnings(chat_id, user_id)",
        """CREATE TABLE mutes (
            chat_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            until REAL NOT NULL,
            by_user TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (chat_id, user_id)
        )""",
        """CREATE TABLE bans (
            chat_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            by_user TEXT NOT NULL DEFAULT '',
            ts REAL NOT NULL,
            PRIMARY KEY (chat_id, user_id)
        )""",
        """CREATE TABLE badwords (
            chat_id TEXT NOT NULL,
            word TEXT NOT NULL,
            PRIMARY KEY (chat_id, word)
        )""",
        """CREATE TABLE admin_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '',
            ts REAL NOT NULL
        )""",
        """CREATE TABLE wallets (
            user_id TEXT PRIMARY KEY,
            coins INTEGER NOT NULL DEFAULT 0 CHECK (coins >= 0),
            last_daily TEXT NOT NULL DEFAULT '',
            streak INTEGER NOT NULL DEFAULT 0,
            last_work REAL NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE inventory (
            user_id TEXT NOT NULL,
            item TEXT NOT NULL,
            qty INTEGER NOT NULL CHECK (qty >= 0),
            PRIMARY KEY (user_id, item)
        )""",
        """CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT NOT NULL,
            to_user TEXT NOT NULL,
            amount INTEGER NOT NULL,
            kind TEXT NOT NULL,
            ts REAL NOT NULL
        )""",
        """CREATE TABLE progress (
            user_id TEXT NOT NULL,
            day TEXT NOT NULL,
            key TEXT NOT NULL,
            value INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, day, key)
        )""",
        """CREATE TABLE mission_claims (
            user_id TEXT NOT NULL,
            day TEXT NOT NULL,
            mission TEXT NOT NULL,
            PRIMARY KEY (user_id, day, mission)
        )""",
        """CREATE TABLE achievements (
            user_id TEXT NOT NULL,
            key TEXT NOT NULL,
            ts REAL NOT NULL,
            PRIMARY KEY (user_id, key)
        )""",
        """CREATE TABLE reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            due REAL NOT NULL,
            text TEXT NOT NULL,
            sent INTEGER NOT NULL DEFAULT 0
        )""",
        "CREATE INDEX idx_rem_due ON reminders(sent, due)",
        """CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            text TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        )""",
        """CREATE TABLE game_state (
            chat_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            data TEXT NOT NULL,
            updated REAL NOT NULL,
            PRIMARY KEY (chat_id, kind)
        )""",
    ]),
    (2, "modo esperto (IA no grupo)", [
        "ALTER TABLE groups ADD COLUMN esperto INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE groups ADD COLUMN esperto_proativo INTEGER NOT NULL DEFAULT 1",
    ]),
    (3, "deduplicação de mensagens e pisos iniciais", [
        "CREATE TABLE seed_applications (seed_key TEXT PRIMARY KEY, user_id TEXT NOT NULL, chat_id TEXT NOT NULL DEFAULT '', applied_at REAL NOT NULL)",
        "CREATE TABLE processed_messages (chat_id TEXT NOT NULL, message_id TEXT NOT NULL, processed_at REAL NOT NULL, PRIMARY KEY(chat_id, message_id))",
        "CREATE INDEX idx_processed_messages_ts ON processed_messages(processed_at)",
    ]),
]

GROUP_SETTABLE = {
    "prefix", "rules", "description", "welcome", "goodbye", "welcome_on", "antilink",
    "antiflood", "antifake", "hours_on", "open_min", "close_min", "max_warns",
    "disabled_modules", "disabled_commands", "esperto", "esperto_proativo",
}
_JSON_FIELDS = {"disabled_modules", "disabled_commands"}


class InsufficientFunds(Exception):
    pass


class Database:
    def __init__(self, path: str = ":memory:"):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self._depth = 0
        self._message_claim_count = 0
        with self.lock:
            if path != ":memory:":
                try:  # alguns sistemas de arquivos (ex.: armazenamento compartilhado do Android) não suportam WAL
                    self.conn.execute("PRAGMA journal_mode=WAL")
                except sqlite3.DatabaseError:
                    self.conn.execute("PRAGMA journal_mode=DELETE")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.execute("PRAGMA synchronous=FULL")  # o celular pode apagar/descarregar a qualquer momento
        self.migrate()

    # ------------------------------------------------------------------ base
    def execute(self, sql: str, params: tuple = ()):
        with self.lock:
            return self.conn.execute(sql, params)

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        with self.lock:
            row = self.conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    @contextmanager
    def transaction(self):
        with self.lock:
            outer = self._depth == 0
            if outer:
                self.conn.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield self
            except BaseException:
                self._depth -= 1
                if outer:
                    self.conn.execute("ROLLBACK")
                raise
            else:
                self._depth -= 1
                if outer:
                    self.conn.execute("COMMIT")

    def close(self):
        with self.lock:
            self.conn.close()

    def backup_to(self, dest: str) -> None:
        """Cópia consistente do banco (API de backup do SQLite) para o arquivo dest."""
        tmp = dest + ".tmp"
        out = sqlite3.connect(tmp)
        try:
            with self.lock:
                self.conn.backup(out)
        finally:
            out.close()
        os.replace(tmp, dest)

    # ------------------------------------------------------------- migrações
    def schema_version(self) -> int:
        row = self.one("SELECT MAX(version) AS v FROM schema_migrations")
        return int(row["v"] or 0) if row else 0

    def migrate(self) -> list[int]:
        applied: list[int] = []
        with self.lock:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at REAL NOT NULL)"
            )
            current = self.schema_version()
            for version, name, statements in MIGRATIONS:
                if version <= current:
                    continue
                with self.transaction():
                    for stmt in statements:
                        self.conn.execute(stmt)
                    self.conn.execute(
                        "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?,?,?)",
                        (version, name, time.time()),
                    )
                applied.append(version)
        return applied

    def integrity_ok(self) -> bool:
        row = self.one("PRAGMA integrity_check")
        return bool(row) and list(row.values())[0] == "ok"

    def claim_message(self, chat_id: str, message_id: str, now: float, retention: float = 14 * 86400) -> bool:
        """Registra um ID recebido uma vez; False significa evento duplicado."""
        if not chat_id or not message_id:
            return True
        with self.transaction():
            cur = self.execute(
                "INSERT OR IGNORE INTO processed_messages(chat_id,message_id,processed_at) VALUES (?,?,?)",
                (chat_id, message_id, now),
            )
            if cur.rowcount == 0:
                return False
            self._message_claim_count += 1
            if self._message_claim_count % 500 == 0:
                self.execute("DELETE FROM processed_messages WHERE processed_at<?", (now - retention,))
            return True

    # ---------------------------------------------------------------- grupos
    def group(self, chat_id: str) -> dict:
        row = self.one("SELECT * FROM groups WHERE chat_id=?", (chat_id,))
        if row is None:
            self.execute("INSERT OR IGNORE INTO groups(chat_id, created_at) VALUES (?,?)", (chat_id, time.time()))
            row = self.one("SELECT * FROM groups WHERE chat_id=?", (chat_id,))
        for f in _JSON_FIELDS:
            try:
                row[f] = json.loads(row[f])
            except (TypeError, ValueError):
                row[f] = []
        return row

    def set_group(self, chat_id: str, **fields) -> None:
        self.group(chat_id)
        for key, value in fields.items():
            if key not in GROUP_SETTABLE:
                raise ValueError(f"campo inválido: {key}")
            if key in _JSON_FIELDS:
                value = json.dumps(sorted(set(value)))
            elif isinstance(value, bool):
                value = int(value)
            self.execute(f"UPDATE groups SET {key}=? WHERE chat_id=?", (value, chat_id))

    # -------------------------------------------------------------- usuários
    def _resolve_uid(self, uid: str, table: str | None = None, chat_id: str | None = None) -> str:
        """Reutiliza registros existentes quando o telefone aparece com/sem o 9º dígito brasileiro."""
        raw = num(uid)
        from .initial_users import initial_user_for
        profile = initial_user_for(raw)
        if not profile:
            return raw
        ids = sorted(profile["ids"])
        marks = ",".join("?" for _ in ids)
        # Procura primeiro a conta já existente na tabela consultada (e no grupo, para XP).
        if table in {"users", "wallets", "member_stats", "roles", "inventory", "progress", "mission_claims",
                     "achievements", "reminders", "tasks"}:
            if table == "member_stats" and chat_id is not None:
                row = self.one(
                    f"SELECT user_id FROM {table} WHERE chat_id=? AND user_id IN ({marks}) "
                    "ORDER BY CASE WHEN user_id=? THEN 0 ELSE 1 END, user_id LIMIT 1",
                    (chat_id, *ids, profile["canonical_id"]),
                )
                if row:
                    return row["user_id"]
            else:
                row = self.one(
                    f"SELECT user_id FROM {table} WHERE user_id IN ({marks}) "
                    "ORDER BY CASE WHEN user_id=? THEN 0 ELSE 1 END, user_id LIMIT 1",
                    (*ids, profile["canonical_id"]),
                )
                if row:
                    return row["user_id"]
        # Se a tabela ainda não tem registro, reutiliza o identificador que já aparece nas tabelas centrais.
        scores: dict[str, int] = {}
        for core in ("wallets", "users", "member_stats"):
            if core == "member_stats" and chat_id is not None:
                rows = self.query(
                    f"SELECT user_id,COUNT(*) AS n FROM {core} WHERE user_id IN ({marks}) GROUP BY user_id",
                    tuple(ids),
                )
            else:
                rows = self.query(
                    f"SELECT user_id,COUNT(*) AS n FROM {core} WHERE user_id IN ({marks}) GROUP BY user_id",
                    tuple(ids),
                )
            for row in rows:
                scores[row["user_id"]] = scores.get(row["user_id"], 0) + int(row["n"])
        if scores:
            return sorted(scores, key=lambda candidate: (-scores[candidate], candidate != profile["canonical_id"], candidate))[0]
        return profile["canonical_id"]

    def touch_user(self, uid: str, name: str = "") -> None:
        u = self._resolve_uid(uid, "users")
        self.execute("INSERT OR IGNORE INTO users(user_id, name, created_at) VALUES (?,?,?)", (u, name, time.time()))
        if name:
            self.execute("UPDATE users SET name=? WHERE user_id=? AND name<>?", (name, u, name))

    def user(self, uid: str) -> dict:
        u = self._resolve_uid(uid, "users")
        self.touch_user(u)
        return self.one("SELECT * FROM users WHERE user_id=?", (u,))

    def set_user_field(self, uid: str, field: str, value: str) -> None:
        if field not in {"bio", "title", "name"}:
            raise ValueError("campo inválido")
        self.touch_user(uid)
        u = self._resolve_uid(uid, "users")
        self.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, u))

    def stats(self, chat_id: str, uid: str) -> dict:
        u = self._resolve_uid(uid, "member_stats", chat_id)
        row = self.one("SELECT * FROM member_stats WHERE chat_id=? AND user_id=?", (chat_id, u))
        return row or {"chat_id": chat_id, "user_id": u, "xp": 0, "msgs": 0, "last_xp": 0}

    def register_message(self, chat_id: str, uid: str, now: float, xp_gain: int, xp_cooldown: float = 60):
        """Conta a mensagem e concede XP (com cooldown). Retorna (nível_antigo, nível_novo, msgs)."""
        u = self._resolve_uid(uid, "member_stats", chat_id)
        from .initial_users import _seed_key_xp, initial_xp_for
        initial_xp = initial_xp_for(u)
        with self.transaction():
            inserted = self.execute(
                "INSERT OR IGNORE INTO member_stats(chat_id,user_id,xp) VALUES (?,?,?)",
                (chat_id, u, initial_xp),
            )
            if inserted.rowcount and initial_xp:
                self.execute(
                    "INSERT OR IGNORE INTO seed_applications(seed_key,user_id,chat_id,applied_at) VALUES (?,?,?,?)",
                    (_seed_key_xp(chat_id, u), u, chat_id, now),
                )
            row = self.one("SELECT xp,msgs,last_xp FROM member_stats WHERE chat_id=? AND user_id=?", (chat_id, u))
            old = level_for(row["xp"])
            gain = xp_gain if now - row["last_xp"] >= xp_cooldown else 0
            self.execute(
                "UPDATE member_stats SET msgs=msgs+1, xp=xp+?, last_xp=CASE WHEN ?>0 THEN ? ELSE last_xp END "
                "WHERE chat_id=? AND user_id=?",
                (gain, gain, now, chat_id, u),
            )
            return old, level_for(row["xp"] + gain), row["msgs"] + 1

    def add_xp(self, chat_id: str, uid: str, amount: int) -> None:
        u = self._resolve_uid(uid, "member_stats", chat_id)
        from .initial_users import _seed_key_xp, initial_xp_for
        initial_xp = initial_xp_for(u)
        with self.transaction():
            inserted = self.execute(
                "INSERT OR IGNORE INTO member_stats(chat_id,user_id,xp) VALUES (?,?,?)",
                (chat_id, u, initial_xp),
            )
            if inserted.rowcount and initial_xp:
                self.execute(
                    "INSERT OR IGNORE INTO seed_applications(seed_key,user_id,chat_id,applied_at) VALUES (?,?,?,?)",
                    (_seed_key_xp(chat_id, u), u, chat_id, time.time()),
                )
            self.execute("UPDATE member_stats SET xp=MAX(0,xp+?) WHERE chat_id=? AND user_id=?", (amount, chat_id, u))

    def top_members(self, chat_id: str, order: str = "xp", limit: int = 10) -> list[dict]:
        if order == "ricos":
            return self.query(
                "SELECT m.user_id, m.xp, COALESCE(w.coins,0) AS score, u.name FROM member_stats m "
                "LEFT JOIN wallets w ON w.user_id=m.user_id LEFT JOIN users u ON u.user_id=m.user_id "
                "WHERE m.chat_id=? ORDER BY score DESC, m.user_id ASC LIMIT ?", (chat_id, limit))
        col = "msgs" if order == "msgs" else "xp"
        return self.query(
            f"SELECT m.user_id, m.xp, m.{col} AS score, u.name FROM member_stats m "
            "LEFT JOIN users u ON u.user_id=m.user_id WHERE m.chat_id=? ORDER BY score DESC, m.user_id ASC LIMIT ?",
            (chat_id, limit))

    def known_members(self, chat_id: str) -> list[str]:
        return [r["user_id"] for r in self.query("SELECT user_id FROM member_stats WHERE chat_id=?", (chat_id,))]

    # ---------------------------------------------------------------- cargos
    def role(self, chat_id: str, uid: str) -> str:
        row = self.one("SELECT role FROM roles WHERE chat_id=? AND user_id=?", (chat_id, self._resolve_uid(uid, "roles")))
        return row["role"] if row else "membro"

    def set_role(self, chat_id: str, uid: str, role: str) -> None:
        u = self._resolve_uid(uid, "roles")
        if role == "membro":
            self.execute("DELETE FROM roles WHERE chat_id=? AND user_id=?", (chat_id, u))
        else:
            self.execute("INSERT OR REPLACE INTO roles(chat_id,user_id,role) VALUES (?,?,?)", (chat_id, u, role))

    def roles_in(self, chat_id: str) -> list[dict]:
        return self.query("SELECT user_id, role FROM roles WHERE chat_id=? ORDER BY role, user_id", (chat_id,))

    # ---------------------------------------------------- moderação e logs
    def log(self, chat_id: str, actor: str, action: str, target: str = "", detail: str = "", now: float | None = None):
        self.execute(
            "INSERT INTO admin_log(chat_id,actor,action,target,detail,ts) VALUES (?,?,?,?,?,?)",
            (chat_id, num(actor) or actor, action, num(target) or target, detail[:300], now or time.time()),
        )

    def logs(self, chat_id: str, limit: int = 10) -> list[dict]:
        return self.query("SELECT * FROM admin_log WHERE chat_id=? ORDER BY id DESC LIMIT ?", (chat_id, limit))

    def add_warning(self, chat_id: str, uid: str, reason: str, by: str, now: float) -> int:
        with self.transaction():
            self.execute(
                "INSERT INTO warnings(chat_id,user_id,reason,by_user,ts) VALUES (?,?,?,?,?)",
                (chat_id, num(uid), reason[:200], num(by) or by, now),
            )
            return self.warning_count(chat_id, uid)

    def warning_count(self, chat_id: str, uid: str) -> int:
        return self.one("SELECT COUNT(*) AS c FROM warnings WHERE chat_id=? AND user_id=?", (chat_id, num(uid)))["c"]

    def warnings(self, chat_id: str, uid: str) -> list[dict]:
        return self.query("SELECT * FROM warnings WHERE chat_id=? AND user_id=? ORDER BY id", (chat_id, num(uid)))

    def clear_warnings(self, chat_id: str, uid: str) -> int:
        return self.execute("DELETE FROM warnings WHERE chat_id=? AND user_id=?", (chat_id, num(uid))).rowcount

    def set_mute(self, chat_id: str, uid: str, until: float, by: str) -> None:
        self.execute("INSERT OR REPLACE INTO mutes(chat_id,user_id,until,by_user) VALUES (?,?,?,?)",
                     (chat_id, num(uid), until, num(by) or by))

    def clear_mute(self, chat_id: str, uid: str) -> bool:
        return self.execute("DELETE FROM mutes WHERE chat_id=? AND user_id=?", (chat_id, num(uid))).rowcount > 0

    def mute_until(self, chat_id: str, uid: str, now: float) -> float:
        row = self.one("SELECT until FROM mutes WHERE chat_id=? AND user_id=?", (chat_id, num(uid)))
        if not row:
            return 0
        if row["until"] <= now:
            self.clear_mute(chat_id, uid)
            return 0
        return row["until"]

    def ban(self, chat_id: str, uid: str, reason: str, by: str, now: float) -> None:
        self.execute("INSERT OR REPLACE INTO bans(chat_id,user_id,reason,by_user,ts) VALUES (?,?,?,?,?)",
                     (chat_id, num(uid), reason[:200], num(by) or by, now))

    def unban(self, chat_id: str, uid: str) -> bool:
        return self.execute("DELETE FROM bans WHERE chat_id=? AND user_id=?", (chat_id, num(uid))).rowcount > 0

    def is_banned(self, chat_id: str, uid: str) -> bool:
        return self.one("SELECT 1 FROM bans WHERE chat_id=? AND user_id=?", (chat_id, num(uid))) is not None

    def bans(self, chat_id: str) -> list[dict]:
        return self.query("SELECT * FROM bans WHERE chat_id=? ORDER BY ts DESC", (chat_id,))

    def badwords(self, chat_id: str) -> list[str]:
        return [r["word"] for r in self.query("SELECT word FROM badwords WHERE chat_id=? ORDER BY word", (chat_id,))]

    def add_badword(self, chat_id: str, word: str) -> bool:
        return self.execute("INSERT OR IGNORE INTO badwords(chat_id,word) VALUES (?,?)", (chat_id, word)).rowcount > 0

    def del_badword(self, chat_id: str, word: str) -> bool:
        return self.execute("DELETE FROM badwords WHERE chat_id=? AND word=?", (chat_id, word)).rowcount > 0

    # --------------------------------------------------------------- economia
    def wallet(self, uid: str) -> dict:
        u = self._resolve_uid(uid, "wallets")
        self.execute("INSERT OR IGNORE INTO wallets(user_id) VALUES (?)", (u,))
        return self.one("SELECT * FROM wallets WHERE user_id=?", (u,))

    def add_coins(self, uid: str, amount: int, kind: str, now: float) -> int:
        """Soma (ou subtrai) moedas de forma atômica. Levanta InsufficientFunds se faltar saldo."""
        u = num(uid)
        with self.transaction():
            w = self.wallet(u)
            u = w["user_id"]
            if w["coins"] + amount < 0:
                raise InsufficientFunds()
            self.execute("UPDATE wallets SET coins=coins+? WHERE user_id=?", (amount, u))
            if amount >= 0:
                self.execute("INSERT INTO transactions(from_user,to_user,amount,kind,ts) VALUES ('sistema',?,?,?,?)",
                             (u, amount, kind, now))
            else:
                self.execute("INSERT INTO transactions(from_user,to_user,amount,kind,ts) VALUES (?,'sistema',?,?,?)",
                             (u, -amount, kind, now))
            return w["coins"] + amount

    def transfer(self, src: str, dst: str, amount: int, now: float) -> None:
        a, b = num(src), num(dst)
        if a == b or amount <= 0:
            raise ValueError("transferência inválida")
        with self.transaction():
            wa = self.wallet(a)
            wb = self.wallet(b)
            a, b = wa["user_id"], wb["user_id"]
            if a == b:
                raise ValueError("transferência inválida")
            if wa["coins"] < amount:
                raise InsufficientFunds()
            self.execute("UPDATE wallets SET coins=coins-? WHERE user_id=?", (amount, a))
            self.execute("UPDATE wallets SET coins=coins+? WHERE user_id=?", (amount, b))
            self.execute("INSERT INTO transactions(from_user,to_user,amount,kind,ts) VALUES (?,?,?,?,?)",
                         (a, b, amount, "transferencia", now))

    def claim_daily(self, uid: str, today: str, yesterday: str):
        """Resgata a recompensa diária uma única vez por dia. Retorna (recompensa, sequência) ou None."""
        u = num(uid)
        with self.transaction():
            w = self.wallet(u)
            u = w["user_id"]
            if w["last_daily"] == today:
                return None
            streak = w["streak"] + 1 if w["last_daily"] == yesterday else 1
            reward = 100 + min(streak, 7) * 20
            self.execute("UPDATE wallets SET coins=coins+?, last_daily=?, streak=? WHERE user_id=?",
                         (reward, today, streak, u))
            self.execute("INSERT INTO transactions(from_user,to_user,amount,kind,ts) VALUES ('sistema',?,?,?,?)",
                         (u, reward, "diario", time.time()))
            return reward, streak

    def claim_work(self, uid: str, now: float, cooldown: float, reward: int):
        """Retorna (True, novo_saldo) ou (False, segundos_restantes)."""
        u = num(uid)
        with self.transaction():
            w = self.wallet(u)
            u = w["user_id"]
            wait = w["last_work"] + cooldown - now
            if wait > 0:
                return False, wait
            self.execute("UPDATE wallets SET coins=coins+?, last_work=? WHERE user_id=?", (reward, now, u))
            self.execute("INSERT INTO transactions(from_user,to_user,amount,kind,ts) VALUES ('sistema',?,?,?,?)",
                         (u, reward, "trabalho", now))
            return True, w["coins"] + reward

    def buy_item(self, uid: str, item: str, price: int, now: float) -> int:
        u = self.wallet(uid)["user_id"]
        with self.transaction():
            self.add_coins(u, -price, f"compra:{item}", now)
            self.execute(
                "INSERT INTO inventory(user_id,item,qty) VALUES (?,?,1) "
                "ON CONFLICT(user_id,item) DO UPDATE SET qty=qty+1", (u, item))
            return self.wallet(u)["coins"]

    def inventory(self, uid: str) -> list[dict]:
        u = self._resolve_uid(uid, "inventory")
        return self.query("SELECT item, qty FROM inventory WHERE user_id=? AND qty>0 ORDER BY item", (u,))

    def has_item(self, uid: str, item: str) -> bool:
        u = self._resolve_uid(uid, "inventory")
        return self.one("SELECT 1 FROM inventory WHERE user_id=? AND item=? AND qty>0", (u, item)) is not None

    # ------------------------------------------------- missões e conquistas
    def add_progress(self, uid: str, day: str, key: str, amount: int = 1) -> int:
        u = num(uid)
        self.execute(
            "INSERT INTO progress(user_id,day,key,value) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id,day,key) DO UPDATE SET value=value+?", (u, day, key, amount, amount))
        return self.one("SELECT value FROM progress WHERE user_id=? AND day=? AND key=?", (u, day, key))["value"]

    def get_progress(self, uid: str, day: str) -> dict:
        return {r["key"]: r["value"] for r in
                self.query("SELECT key,value FROM progress WHERE user_id=? AND day=?", (num(uid), day))}

    def claim_mission(self, uid: str, day: str, mission: str, reward: int, now: float) -> bool:
        """Registra o resgate e paga a recompensa na mesma transação (sem duplicação)."""
        u = num(uid)
        with self.transaction():
            cur = self.execute("INSERT OR IGNORE INTO mission_claims(user_id,day,mission) VALUES (?,?,?)", (u, day, mission))
            if cur.rowcount == 0:
                return False
            self.add_coins(u, reward, f"missao:{mission}", now)
            return True

    def claimed_missions(self, uid: str, day: str) -> set:
        return {r["mission"] for r in
                self.query("SELECT mission FROM mission_claims WHERE user_id=? AND day=?", (num(uid), day))}

    def grant_achievement(self, uid: str, key: str, now: float) -> bool:
        return self.execute("INSERT OR IGNORE INTO achievements(user_id,key,ts) VALUES (?,?,?)",
                            (num(uid), key, now)).rowcount > 0

    def achievements(self, uid: str) -> list[str]:
        return [r["key"] for r in self.query("SELECT key FROM achievements WHERE user_id=? ORDER BY ts", (num(uid),))]

    # -------------------------------------------------- lembretes e tarefas
    def add_reminder(self, chat_id: str, uid: str, due: float, text: str) -> int:
        return self.execute("INSERT INTO reminders(chat_id,user_id,due,text) VALUES (?,?,?,?)",
                            (chat_id, num(uid), due, text[:300])).lastrowid

    def pending_reminders(self, chat_id: str, uid: str) -> list[dict]:
        return self.query("SELECT * FROM reminders WHERE chat_id=? AND user_id=? AND sent=0 ORDER BY due",
                          (chat_id, num(uid)))

    def due_reminders(self, now: float) -> list[dict]:
        with self.transaction():
            rows = self.query("SELECT * FROM reminders WHERE sent=0 AND due<=? ORDER BY due LIMIT 50", (now,))
            for r in rows:
                self.execute("UPDATE reminders SET sent=1 WHERE id=?", (r["id"],))
            return rows

    def add_task(self, chat_id: str, uid: str, text: str, now: float) -> int:
        return self.execute("INSERT INTO tasks(chat_id,user_id,text,created_at) VALUES (?,?,?,?)",
                            (chat_id, num(uid), text[:200], now)).lastrowid

    def tasks(self, chat_id: str, uid: str) -> list[dict]:
        return self.query("SELECT * FROM tasks WHERE chat_id=? AND user_id=? ORDER BY id", (chat_id, num(uid)))

    def set_task_done(self, task_id: int) -> None:
        self.execute("UPDATE tasks SET done=1 WHERE id=?", (task_id,))

    def delete_task(self, task_id: int) -> None:
        self.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    # ------------------------------------------------------------------ jogos
    def game_get(self, chat_id: str, kind: str) -> dict | None:
        row = self.one("SELECT data FROM game_state WHERE chat_id=? AND kind=?", (chat_id, kind))
        return json.loads(row["data"]) if row else None

    def game_set(self, chat_id: str, kind: str, data: dict, now: float) -> None:
        self.execute("INSERT OR REPLACE INTO game_state(chat_id,kind,data,updated) VALUES (?,?,?,?)",
                     (chat_id, kind, json.dumps(data), now))

    def game_del(self, chat_id: str, kind: str) -> None:
        self.execute("DELETE FROM game_state WHERE chat_id=? AND kind=?", (chat_id, kind))
