"""Base repository providing shared helpers for fire-and-forget telemetry writes.

TelemetryRepository, GameSessionRepository, and SpellingAttemptRepository inherit
from BaseRepository. Their DB failures are swallowed and logged so the game pipeline
never crashes.

UserRepository and MetricsRepository do NOT inherit — their exceptions propagate
intentionally (auth failures and metric query failures must surface to callers).
"""
from loguru import logger

from db.database import get_connection


class BaseRepository:
    def _safe_write(self, operation: str, sql: str, params: tuple) -> bool:
        """Execute a single write and return True on success, False on error."""
        try:
            with get_connection() as conn:
                conn.execute(sql, params)
                conn.commit()
            return True
        except Exception as exc:
            logger.error(f"[DB] {operation} failed: {exc}")
            return False
