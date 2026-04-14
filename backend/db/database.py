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
    """Create all application tables if they do not already exist."""
    from db.models import UNHANDLED_INTERRUPTIONS_DDL, USERS_DDL

    with get_connection() as conn:
        conn.execute(USERS_DDL)
        conn.execute(UNHANDLED_INTERRUPTIONS_DDL)
        conn.commit()
    logger.info(f"[DB] Tables initialised at {DB_PATH}")
