from datetime import datetime, timezone

from loguru import logger

from db.repositories.base import BaseRepository


class TelemetryRepository(BaseRepository):
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
        ok = self._safe_write(
            "log_unhandled_interruption",
            """
            INSERT INTO unhandled_interruptions
                (timestamp, session_id, user_id, raw_text, normalized, phase, current_word)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ts, session_id, user_id, raw_text, normalized, phase, current_word),
        )
        if ok:
            logger.info(
                f"[TELEMETRY] Logged unhandled interruption "
                f"session={session_id} user={user_id} text='{raw_text}'"
            )
