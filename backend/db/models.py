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

# Run inside try/except sqlite3.OperationalError — safe to swallow if column already exists.
IS_ADMIN_MIGRATION = "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0"

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

GAME_SESSIONS_DDL = """
    CREATE TABLE IF NOT EXISTS game_sessions (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id     TEXT    NOT NULL UNIQUE,
        user_id        INTEGER,
        started_at     TEXT    NOT NULL,
        ended_at       TEXT,
        total_words    INTEGER NOT NULL DEFAULT 0,
        correct_count  INTEGER NOT NULL DEFAULT 0,
        spelling_speed TEXT    NOT NULL DEFAULT 'normal'
    )
"""

SPELLING_ATTEMPTS_DDL = """
    CREATE TABLE IF NOT EXISTS spelling_attempts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id   TEXT    NOT NULL,
        user_id      INTEGER,
        word         TEXT    NOT NULL,
        attempt      TEXT    NOT NULL,
        correct      INTEGER NOT NULL DEFAULT 0,
        command_type TEXT,
        timestamp    TEXT    NOT NULL
    )
"""
