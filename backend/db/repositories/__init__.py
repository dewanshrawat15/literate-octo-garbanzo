"""Repository package — re-exports all classes so existing imports continue to work.

Usage (unchanged from when this was a single file):
    from db.repositories import UserRepository, MetricsRepository
"""
from db.repositories.game_session import GameSessionRepository
from db.repositories.metrics import MetricsRepository
from db.repositories.spelling_attempt import SpellingAttemptRepository
from db.repositories.telemetry import TelemetryRepository
from db.repositories.user import UserRepository

__all__ = [
    "GameSessionRepository",
    "MetricsRepository",
    "SpellingAttemptRepository",
    "TelemetryRepository",
    "UserRepository",
]
