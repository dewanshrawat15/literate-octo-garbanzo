"""SQL DDL strings for all application tables."""

USERS_DDL = """
    CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        username        TEXT    NOT NULL UNIQUE,
        hashed_password TEXT    NOT NULL,
        spelling_speed  TEXT    NOT NULL DEFAULT 'normal',
        created_at      TEXT    NOT NULL
    )
"""

UNHANDLED_INTERRUPTIONS_DDL = """
    CREATE TABLE IF NOT EXISTS unhandled_interruptions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp    TEXT    NOT NULL,
        session_id   TEXT    NOT NULL,
        user_id      INTEGER,
        raw_text     TEXT    NOT NULL,
        normalized   TEXT,
        phase        TEXT    NOT NULL,
        current_word TEXT
    )
"""
