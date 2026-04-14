import sqlite3
from datetime import datetime, timezone

from loguru import logger

from db.database import get_connection


class UserRepository:
    """Data-access object for the users table."""

    def create(
        self,
        username: str,
        hashed_password: str,
        spelling_speed: str,
    ) -> int:
        """Insert a new user and return the new row id."""
        ts = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, hashed_password, spelling_speed, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, hashed_password, spelling_speed, ts),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]

    def find_by_username(self, username: str) -> sqlite3.Row | None:
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()

    def find_by_id(self, user_id: int) -> sqlite3.Row | None:
        with get_connection() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()

    def update_speed(self, user_id: int, speed: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET spelling_speed = ? WHERE id = ?",
                (speed, user_id),
            )
            conn.commit()


class TelemetryRepository:
    """Data-access object for the unhandled_interruptions telemetry table."""

    def log_unhandled(
        self,
        session_id: str,
        user_id: int | None,
        raw_text: str,
        normalized: str,
        phase: str,
        current_word: str,
    ) -> None:
        """Persist one unhandled interruption row."""
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO unhandled_interruptions
                        (timestamp, session_id, user_id, raw_text, normalized, phase, current_word)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (ts, session_id, user_id, raw_text, normalized, phase, current_word),
                )
                conn.commit()
            logger.info(
                f"[TELEMETRY] Logged unhandled interruption "
                f"session={session_id} user={user_id} text='{raw_text}'"
            )
        except Exception as exc:
            logger.error(f"[TELEMETRY] Failed to write to DB: {exc}")
