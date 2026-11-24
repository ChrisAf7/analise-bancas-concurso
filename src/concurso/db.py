"""Conexão SQLite e migrações numeradas (ADR-003).

Uso:  python -m concurso.db migrate
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from .config import DB_PATH, MIGRATIONS


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=60)   # timeout: avaliadores A e B gravam em paralelo
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Aplica, em ordem, as migrações com número maior que PRAGMA user_version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    applied = []
    for f in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
        n = int(f.name[:3])
        if n <= current:
            continue
        with conn:  # transação: ou aplica tudo do arquivo, ou nada
            conn.executescript(f.read_text(encoding="utf-8"))
            conn.execute(f"PRAGMA user_version = {n}")
        applied.append(f.name)
    return applied


if __name__ == "__main__":
    if sys.argv[1:] == ["migrate"]:
        done = migrate(connect())
        print("migrações aplicadas:", done or "nenhuma (banco já atualizado)")
    else:
        print(__doc__)
