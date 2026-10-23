"""Montagem do bot (config + banco + plugins)."""
from __future__ import annotations

import logging

from .config import Config, load_dotenv
from .db import Database
from .dispatcher import Bot
from .registry import load_plugins


def build_bot(cfg: Config | None = None, db_path: str | None = None, clock=None) -> Bot:
    if cfg is None:
        load_dotenv()
        cfg = Config.from_env()
    db = Database(db_path or cfg.db_path)
    # O bootstrap de contas é idempotente; só usa banco persistente e faz backup antes de alterar saldos/XP.
    if db.path != ":memory:":
        from .initial_users import apply_initial_progression
        apply_initial_progression(db)
    registry = load_plugins()
    problems = registry.validate()
    if problems:
        raise RuntimeError("Registro de comandos inválido: " + "; ".join(problems))
    kwargs = {"clock": clock} if clock else {}
    return Bot(cfg, db, registry, **kwargs)


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, level, logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
