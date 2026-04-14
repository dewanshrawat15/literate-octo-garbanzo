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

    def set_admin(self, username: str) -> bool:
        """Promote a user to admin. Returns True if the user was found and updated."""
        with get_connection() as conn:
            cursor = conn.execute(
                "UPDATE users SET is_admin = 1 WHERE username = ?",
                (username,),
            )
            conn.commit()
            return cursor.rowcount > 0


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


class GameSessionRepository:
    """Data-access object for the game_sessions table."""

    def create_session(
        self,
        session_id: str,
        user_id: int | None,
        spelling_speed: str,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO game_sessions (session_id, user_id, started_at, spelling_speed)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, user_id, ts, spelling_speed),
                )
                conn.commit()
        except Exception as exc:
            logger.error(f"[TELEMETRY] Failed to create game_session: {exc}")

    def end_session(
        self,
        session_id: str,
        total_words: int,
        correct_count: int,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE game_sessions
                    SET ended_at = ?, total_words = ?, correct_count = ?
                    WHERE session_id = ?
                    """,
                    (ts, total_words, correct_count, session_id),
                )
                conn.commit()
        except Exception as exc:
            logger.error(f"[TELEMETRY] Failed to end game_session: {exc}")


class SpellingAttemptRepository:
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
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO spelling_attempts
                        (session_id, user_id, word, attempt, correct, command_type, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (session_id, user_id, word, attempt, int(correct), command_type, ts),
                )
                conn.commit()
        except Exception as exc:
            logger.error(f"[TELEMETRY] Failed to log spelling attempt: {exc}")


class MetricsRepository:
    """Read-only queries that power the admin metrics dashboard."""

    def get_metrics(self) -> dict:
        with get_connection() as conn:
            # ── Speed distribution ──────────────────────────────────────────
            rows = conn.execute(
                "SELECT spelling_speed, COUNT(*) as cnt FROM users GROUP BY spelling_speed"
            ).fetchall()
            speed_distribution = {"slow": 0, "normal": 0, "fast": 0}
            for row in rows:
                key = row["spelling_speed"]
                if key in speed_distribution:
                    speed_distribution[key] = row["cnt"]

            total_users: int = conn.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]

            # ── Session counts ──────────────────────────────────────────────
            total_sessions: int = conn.execute(
                "SELECT COUNT(*) FROM game_sessions"
            ).fetchone()[0]

            completed_sessions: int = conn.execute(
                "SELECT COUNT(*) FROM game_sessions WHERE ended_at IS NOT NULL"
            ).fetchone()[0]

            # ── Spelling stats (genuine attempts: command_type IS NULL) ──────
            stats_row = conn.execute(
                """
                SELECT
                    COUNT(*) as total_attempts,
                    COALESCE(SUM(correct), 0) as correct_count,
                    ROUND(100.0 * COALESCE(SUM(correct), 0) / NULLIF(COUNT(*), 0), 1) as accuracy_pct
                FROM spelling_attempts
                WHERE command_type IS NULL
                """
            ).fetchone()
            total_attempts = stats_row["total_attempts"] or 0
            correct_count_sp = stats_row["correct_count"] or 0
            spelling_stats = {
                "total_attempts": total_attempts,
                "correct": correct_count_sp,
                "incorrect": total_attempts - correct_count_sp,
                "accuracy_pct": stats_row["accuracy_pct"] or 0.0,
            }

            # ── Top 5 hardest words ─────────────────────────────────────────
            hard_rows = conn.execute(
                """
                SELECT
                    word,
                    COUNT(*) as attempts,
                    COALESCE(SUM(correct), 0) as correct_count,
                    ROUND(100.0 * COALESCE(SUM(correct), 0) / COUNT(*), 1) as accuracy_pct
                FROM spelling_attempts
                WHERE command_type IS NULL
                GROUP BY word
                HAVING COUNT(*) >= 3
                ORDER BY accuracy_pct ASC
                LIMIT 5
                """
            ).fetchall()
            top_hard_words = [dict(r) for r in hard_rows]

            # ── Command usage ───────────────────────────────────────────────
            cmd_row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN command_type = 'repeat' THEN 1 ELSE 0 END), 0) as repeat_count,
                    COALESCE(SUM(CASE WHEN command_type = 'skip'   THEN 1 ELSE 0 END), 0) as skip_count,
                    COALESCE(SUM(CASE WHEN command_type = 'quit'   THEN 1 ELSE 0 END), 0) as quit_count
                FROM spelling_attempts
                WHERE command_type IS NOT NULL
                """
            ).fetchone()
            command_usage = {
                "repeat": cmd_row["repeat_count"],
                "skip": cmd_row["skip_count"],
                "quit": cmd_row["quit_count"],
            }

            # ── Unhandled interruptions ─────────────────────────────────────
            unhandled_count: int = conn.execute(
                "SELECT COUNT(*) FROM unhandled_interruptions"
            ).fetchone()[0]

            top_unhandled_rows = conn.execute(
                """
                SELECT raw_text, COUNT(*) as cnt
                FROM unhandled_interruptions
                GROUP BY raw_text
                ORDER BY cnt DESC
                LIMIT 5
                """
            ).fetchall()
            top_unhandled = [dict(r) for r in top_unhandled_rows]

            # ── Average score % across completed sessions ───────────────────
            avg_row = conn.execute(
                """
                SELECT ROUND(AVG(100.0 * correct_count / NULLIF(total_words, 0)), 1) as avg_pct
                FROM game_sessions
                WHERE ended_at IS NOT NULL
                """
            ).fetchone()
            avg_score_pct = avg_row["avg_pct"]  # may be None if no completed sessions

        return {
            "speed_distribution": speed_distribution,
            "total_users": total_users,
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "spelling_stats": spelling_stats,
            "top_hard_words": top_hard_words,
            "command_usage": command_usage,
            "unhandled_count": unhandled_count,
            "top_unhandled": top_unhandled,
            "avg_score_pct": avg_score_pct,
        }
