import sqlite3

from db.database import get_connection


class MetricsRepository:
    """Read-only queries that power the admin metrics dashboard.

    Exceptions propagate to callers — query failures surface as API errors.
    One connection is opened per get_metrics() call and passed to all helpers.
    """

    def get_metrics(self) -> dict:
        with get_connection() as conn:
            session_counts = self._session_counts(conn)
            return {
                "speed_distribution": self._speed_distribution(conn),
                "total_users": self._total_users(conn),
                "total_sessions": session_counts["total"],
                "completed_sessions": session_counts["completed"],
                "spelling_stats": self._spelling_stats(conn),
                "top_hard_words": self._hard_words(conn),
                "command_usage": self._command_usage(conn),
                "unhandled_count": self._unhandled_count(conn),
                "top_unhandled": self._top_unhandled(conn),
                "avg_score_pct": self._avg_score(conn),
            }

    # ------------------------------------------------------------------
    # Private query helpers — each accepts an open connection
    # ------------------------------------------------------------------

    def _speed_distribution(self, conn: sqlite3.Connection) -> dict[str, int]:
        rows = conn.execute(
            "SELECT spelling_speed, COUNT(*) as cnt FROM users GROUP BY spelling_speed"
        ).fetchall()
        distribution = {"slow": 0, "normal": 0, "fast": 0}
        for row in rows:
            if row["spelling_speed"] in distribution:
                distribution[row["spelling_speed"]] = row["cnt"]
        return distribution

    def _total_users(self, conn: sqlite3.Connection) -> int:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def _session_counts(self, conn: sqlite3.Connection) -> dict[str, int]:
        total = conn.execute("SELECT COUNT(*) FROM game_sessions").fetchone()[0]
        completed = conn.execute(
            "SELECT COUNT(*) FROM game_sessions WHERE ended_at IS NOT NULL"
        ).fetchone()[0]
        return {"total": total, "completed": completed}

    def _spelling_stats(self, conn: sqlite3.Connection) -> dict:
        row = conn.execute(
            """
            SELECT
                COUNT(*) as total_attempts,
                COALESCE(SUM(correct), 0) as correct_count,
                ROUND(100.0 * COALESCE(SUM(correct), 0) / NULLIF(COUNT(*), 0), 1) as accuracy_pct
            FROM spelling_attempts
            WHERE command_type IS NULL
            """
        ).fetchone()
        total = row["total_attempts"] or 0
        correct = row["correct_count"] or 0
        return {
            "total_attempts": total,
            "correct": correct,
            "incorrect": total - correct,
            "accuracy_pct": row["accuracy_pct"] or 0.0,
        }

    def _hard_words(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
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
        return [dict(r) for r in rows]

    def _command_usage(self, conn: sqlite3.Connection) -> dict[str, int]:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN command_type = 'repeat' THEN 1 ELSE 0 END), 0) as repeat_count,
                COALESCE(SUM(CASE WHEN command_type = 'skip'   THEN 1 ELSE 0 END), 0) as skip_count,
                COALESCE(SUM(CASE WHEN command_type = 'quit'   THEN 1 ELSE 0 END), 0) as quit_count
            FROM spelling_attempts
            WHERE command_type IS NOT NULL
            """
        ).fetchone()
        return {
            "repeat": row["repeat_count"],
            "skip": row["skip_count"],
            "quit": row["quit_count"],
        }

    def _unhandled_count(self, conn: sqlite3.Connection) -> int:
        return conn.execute(
            "SELECT COUNT(*) FROM unhandled_interruptions"
        ).fetchone()[0]

    def _top_unhandled(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            """
            SELECT raw_text, COUNT(*) as cnt
            FROM unhandled_interruptions
            GROUP BY raw_text
            ORDER BY cnt DESC
            LIMIT 5
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def _avg_score(self, conn: sqlite3.Connection) -> float | None:
        row = conn.execute(
            """
            SELECT ROUND(AVG(100.0 * correct_count / NULLIF(total_words, 0)), 1) as avg_pct
            FROM game_sessions
            WHERE ended_at IS NOT NULL
            """
        ).fetchone()
        return row["avg_pct"]
