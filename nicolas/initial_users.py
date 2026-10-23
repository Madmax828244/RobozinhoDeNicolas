"""Valores iniciais de XP e moedas de dois perfis, aplicados uma única vez (idempotente, com backup antes).

O nível é calculado a partir do XP (nível = floor(sqrt(XP / 100)) + 1), nunca guardado separado:
  • 1228 XP → nível 4      • 891 XP → nível 3 (o nível 4 começa em 900 XP).
"xp_mode"/"coins_mode": "set" define o valor exato uma vez; "min" só sobe até o valor (nunca reduz).
Depois de aplicado, XP e moedas evoluem normalmente (ganhos, gastos) e a configuração não é reaplicada.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from .utils import num

log = logging.getLogger("nicolas.progression")

# Os telefones fornecidos usam o formato brasileiro de 8 dígitos após o DDD.
# Aceitamos tanto o formato informado quanto a variante móvel atual com 9 adicional.
RAW_INITIAL_USERS = (
    # 55 81 9727-6369 → 891 XP e 789 moedas
    {"label": "A", "phone": "558197276369", "coins": 789, "coins_mode": "set", "xp_requested": 891, "xp_mode": "set"},
    # 55 81 7314-3183 → 1228 XP (nível 4) e mais de 1.090.000 moedas
    {"label": "B", "phone": "558173143183", "coins": 1_090_001, "coins_mode": "min", "xp_requested": 1228, "xp_mode": "set"},
)


def phone_variants(value: str) -> set[str]:
    """Normaliza número/JID e reconhece a variante brasileira com/sem 9º dígito."""
    n = num(value)
    variants = {n} if n else set()
    if n.startswith("55") and len(n) == 12 and n[4] in "6789":
        variants.add(n[:4] + "9" + n[4:])
    elif n.startswith("55") and len(n) == 13 and n[4] == "9":
        variants.add(n[:4] + n[5:])
    return variants


def _canonical_phone(phone: str) -> str:
    variants = phone_variants(phone)
    # Prefira o formato atual de 13 dígitos quando a regra brasileira o reconhecer.
    return next((v for v in variants if len(v) == 13), num(phone))


INITIAL_USERS = tuple(
    {
        **u,
        "ids": phone_variants(u["phone"]),
        "canonical_id": _canonical_phone(u["phone"]),
        "xp_target": int(u["xp_requested"]),
    }
    for u in RAW_INITIAL_USERS
)


def initial_xp_for(uid: str) -> int:
    n = num(uid)
    for user in INITIAL_USERS:
        if n in user["ids"]:
            return int(user["xp_target"])
    return 0


def initial_user_for(uid: str) -> dict | None:
    n = num(uid)
    return next((u for u in INITIAL_USERS if n in u["ids"]), None)


def _seed_key_wallet(user: dict) -> str:
    return f"wallet:v3:{user['canonical_id']}"


def _seed_key_xp(chat_id: str, uid: str) -> str:
    # v3: novos valores (1228 / 891 XP); a chave nova faz o ajuste valer mesmo para quem já tinha chaves antigas.
    return f"xp:v3:{chat_id}:{uid}"


def _needs_seed(db) -> bool:
    keys = {r["seed_key"] for r in db.query("SELECT seed_key FROM seed_applications")}
    for user in INITIAL_USERS:
        if _seed_key_wallet(user) not in keys:
            return True
    for row in db.query("SELECT chat_id,user_id FROM member_stats"):
        user = initial_user_for(row["user_id"])
        if user and _seed_key_xp(row["chat_id"], row["user_id"]) not in keys:
            return True
    return False


def apply_initial_progression(db) -> dict:
    """Aplica os valores uma única vez por carteira e por versão, com backup prévio.

    - Modo "set" define o valor exato (uma vez); modo "min" nunca reduz.
    - A carteira é global; XP é por grupo, como exige o esquema atual do ranking.
    - A chave de XP v2 repara os registros legados que já tinham uma chave v1,
      mas foram inicializados com XP abaixo do mínimo necessário ao nível pedido.
    - A tabela seed_applications impede reaplicar o piso em reinicializações futuras.
    """
    if not _needs_seed(db):
        return {"wallets": 0, "xp_rows": 0, "backup": None}

    backup_path = None
    db_path = getattr(db, "path", ":memory:")
    if db_path != ":memory:" and Path(db_path).is_file() and Path(db_path).stat().st_size > 0:
        folder = Path(db_path).resolve().parent / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = str(folder / f"pre-progression-{stamp}.db")
        db.backup_to(backup_path)

    wallets_seeded = 0
    xp_seeded = 0
    now = datetime.now().timestamp()
    with db.transaction():
        applied = {r["seed_key"] for r in db.query("SELECT seed_key FROM seed_applications")}
        for user in INITIAL_USERS:
            wallet_key = _seed_key_wallet(user)
            if wallet_key not in applied:
                ids = sorted(user["ids"])
                placeholders = ",".join("?" for _ in ids)
                rows = db.query(f"SELECT user_id,coins FROM wallets WHERE user_id IN ({placeholders})", tuple(ids))
                if rows:
                    # Atualiza a(s) conta(s) existente(s) em qualquer variante, sem inserir outra carteira.
                    expr = "?" if user.get("coins_mode") == "set" else "MAX(coins, ?)"
                    for row in rows:
                        db.execute(
                            f"UPDATE wallets SET coins={expr} WHERE user_id=?",
                            (user["coins"], row["user_id"]),
                        )
                else:
                    db.execute(
                        "INSERT OR IGNORE INTO wallets(user_id,coins) VALUES (?,?)",
                        (user["canonical_id"], user["coins"]),
                    )
                db.execute(
                    "INSERT OR IGNORE INTO seed_applications(seed_key,user_id,chat_id,applied_at) VALUES (?,?,?,?)",
                    (wallet_key, user["canonical_id"], "", now),
                )
                wallets_seeded += 1

        member_rows = db.query("SELECT chat_id,user_id,xp FROM member_stats ORDER BY chat_id,user_id")
        for row in member_rows:
            user = initial_user_for(row["user_id"])
            if not user:
                continue
            key = _seed_key_xp(row["chat_id"], row["user_id"])
            if key in applied:
                continue
            expr = "?" if user.get("xp_mode") == "set" else "MAX(xp, ?)"
            db.execute(
                f"UPDATE member_stats SET xp={expr} WHERE chat_id=? AND user_id=?",
                (user["xp_target"], row["chat_id"], row["user_id"]),
            )
            db.execute(
                "INSERT OR IGNORE INTO seed_applications(seed_key,user_id,chat_id,applied_at) VALUES (?,?,?,?)",
                (key, row["user_id"], row["chat_id"], now),
            )
            xp_seeded += 1

    if wallets_seeded or xp_seeded:
        log.info("Configuração inicial aplicada: %d carteira(s), %d registro(s) de XP; backup=%s",
                 wallets_seeded, xp_seeded, backup_path or "não necessário")
    return {"wallets": wallets_seeded, "xp_rows": xp_seeded, "backup": backup_path}


def apply_to_chat(db, chat_id: str) -> list[dict]:
    """Aplica agora os valores configurados NESTE grupo (cria a linha de ranking se ainda não existir).

    Usado pelo dono (.ajustarperfis) quando os dois perfis ainda não aparecem no ranking do grupo.
    Define o XP deste grupo e as moedas (conforme coins_mode) e marca as chaves para o ajuste automático não repetir.
    """
    now = datetime.now().timestamp()
    out = []
    with db.transaction():
        for user in INITIAL_USERS:
            uid = db._resolve_uid(user["canonical_id"], "member_stats", chat_id)
            db.touch_user(uid)
            db.execute("INSERT OR IGNORE INTO member_stats(chat_id,user_id,xp) VALUES (?,?,0)", (chat_id, uid))
            expr = "?" if user.get("xp_mode") == "set" else "MAX(xp, ?)"
            db.execute(f"UPDATE member_stats SET xp={expr} WHERE chat_id=? AND user_id=?",
                       (user["xp_target"], chat_id, uid))
            w = db.wallet(uid)
            cexpr = "?" if user.get("coins_mode") == "set" else "MAX(coins, ?)"
            db.execute(f"UPDATE wallets SET coins={cexpr} WHERE user_id=?", (user["coins"], w["user_id"]))
            for key in (_seed_key_xp(chat_id, uid), _seed_key_wallet(user)):
                db.execute("INSERT OR IGNORE INTO seed_applications(seed_key,user_id,chat_id,applied_at) VALUES (?,?,?,?)",
                           (key, uid, chat_id if key.startswith("xp:") else "", now))
            out.append({"user_id": uid, "xp": db.stats(chat_id, uid)["xp"], "coins": db.wallet(uid)["coins"]})
    return out


def report(db) -> list[dict]:
    """Situação atual dos dois perfis: moedas e XP em cada grupo onde já têm linha de ranking."""
    rows = []
    for user in INITIAL_USERS:
        ids = sorted(user["ids"])
        marks = ",".join("?" for _ in ids)
        coins = db.query(f"SELECT user_id,coins FROM wallets WHERE user_id IN ({marks})", tuple(ids))
        stats = db.query(f"SELECT chat_id,user_id,xp FROM member_stats WHERE user_id IN ({marks})", tuple(ids))
        rows.append({"phone": user["phone"], "target_xp": user["xp_target"], "target_coins": user["coins"],
                     "wallets": coins, "groups": stats})
    return rows
