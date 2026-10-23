"""Cópias de segurança automáticas do banco (lembretes, XP, configurações dos grupos...)."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

log = logging.getLogger("nicolas.backup")


def backup_dir(db_path: str) -> Path:
    return Path(db_path).parent / "backups"


def make_backup(db, keep: int = 7) -> Path | None:
    """Grava data/backups/nicolas-AAAAMMDD-HHMMSS.db e apaga as mais antigas (mantém `keep`)."""
    if db.path == ":memory:":
        return None
    folder = backup_dir(db.path)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / time.strftime("nicolas-%Y%m%d-%H%M%S.db")
    db.backup_to(str(dest))
    old = sorted(folder.glob("nicolas-*.db"))
    for f in old[: max(0, len(old) - max(1, keep))]:
        try:
            f.unlink()
        except OSError:
            pass
    return dest


def start_scheduler(db, hours: float, keep: int) -> threading.Event:
    """Faz um backup ao iniciar e outro a cada `hours` horas (em segundo plano). Devolve o Event de parada."""
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            try:
                path = make_backup(db, keep)
                if path:
                    log.info("backup do banco salvo em %s", path.name)
            except Exception as exc:  # backup nunca derruba o bot
                log.warning("backup falhou: %s: %s", type(exc).__name__, exc)
            stop.wait(max(0.1, hours) * 3600)

    threading.Thread(target=loop, daemon=True, name="backup").start()
    return stop
