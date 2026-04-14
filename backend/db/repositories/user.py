import sqlite3
from datetime import datetime, timezone

from db.database import get_connection


class UserRepository:
    """Data-access object for the users table.

    Exceptions propagate to callers — auth failures must surface.
    """

    def create(self, username: str, hashed_password: str, spelling_speed: str) -> int:
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

    def set_admin(self, username: str) -> bool:
        """Promote a user to admin. Returns True if the user was found and updated."""
        with get_connection() as conn:
            cursor = conn.execute(
                "UPDATE users SET is_admin = 1 WHERE username = ?",
                (username,),
            )
            conn.commit()
            return cursor.rowcount > 0
