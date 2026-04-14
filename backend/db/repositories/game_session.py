from datetime import datetime, timezone

from db.repositories.base import BaseRepository


class GameSessionRepository(BaseRepository):
    """Data-access object for the game_sessions table."""

    def create_session(
        self,
        session_id: str,
        user_id: int | None,
        spelling_speed: str,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        self._safe_write(
            "create_game_session",
            """
            INSERT INTO game_sessions (session_id, user_id, started_at, spelling_speed)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, user_id, ts, spelling_speed),
        )

    def end_session(
        self,
        session_id: str,
        total_words: int,
        correct_count: int,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        self._safe_write(
            "end_game_session",
            """
            UPDATE game_sessions
            SET ended_at = ?, total_words = ?, correct_count = ?
            WHERE session_id = ?
            """,
            (ts, total_words, correct_count, session_id),
        )
