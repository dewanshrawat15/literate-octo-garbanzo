import os
import sqlite3

from loguru import logger

DB_PATH = os.getenv("DB_PATH", "spelling_bee.db")


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory set to sqlite3.Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_all_tables() -> None:
    """Create all application tables and run schema migrations idempotently."""
    from db.models import (
        GAME_SESSIONS_DDL,
        IS_ADMIN_MIGRATION,
        SPELLING_ATTEMPTS_DDL,
        UNHANDLED_INTERRUPTIONS_DDL,
        USERS_DDL,
    )

    with get_connection() as conn:
        conn.execute(USERS_DDL)
        conn.execute(UNHANDLED_INTERRUPTIONS_DDL)
        conn.execute(GAME_SESSIONS_DDL)
        conn.execute(SPELLING_ATTEMPTS_DDL)

        # Migration: add is_admin column — OperationalError means it already exists.
        try:
            conn.execute(IS_ADMIN_MIGRATION)
            logger.info("[DB] Migration: is_admin column added to users")
        except sqlite3.OperationalError:
            logger.debug("[DB] is_admin column already exists — skipping migration")

        conn.commit()

    logger.info(f"[DB] Tables initialised at {DB_PATH}")
