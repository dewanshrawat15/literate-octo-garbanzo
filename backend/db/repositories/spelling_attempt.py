from datetime import datetime, timezone

from db.repositories.base import BaseRepository


class SpellingAttemptRepository(BaseRepository):
    """Data-access object for the spelling_attempts table."""

    def log_attempt(
        self,
        session_id: str,
        user_id: int | None,
        word: str,
        attempt: str,
        correct: bool,
        command_type: str | None = None,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        self._safe_write(
            "log_spelling_attempt",
            """
            INSERT INTO spelling_attempts
                (session_id, user_id, word, attempt, correct, command_type, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, user_id, word, attempt, int(correct), command_type, ts),
        )
