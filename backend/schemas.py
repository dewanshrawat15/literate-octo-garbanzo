from typing import Any

from pydantic import BaseModel, Field

from constants import SpellingSpeed


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    spelling_speed: SpellingSpeed = SpellingSpeed.NORMAL


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    username: str
    spelling_speed: SpellingSpeed
    is_admin: bool = False


class UpdateSpeedRequest(BaseModel):
    spelling_speed: SpellingSpeed


class UserProfile(BaseModel):
    id: int
    username: str
    spelling_speed: SpellingSpeed
    is_admin: bool = False


class ConnectResponse(BaseModel):
    wsUrl: str


class LogRequest(BaseModel):
    event: str
    ts: int | None = None
    # Accept arbitrary extra fields from the frontend diagnostic logger
    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Metrics response models
# ---------------------------------------------------------------------------

class SpellingStats(BaseModel):
    total_attempts: int
    correct: int
    incorrect: int
    accuracy_pct: float


class HardWord(BaseModel):
    word: str
    attempts: int
    correct_count: int
    accuracy_pct: float


class CommandUsage(BaseModel):
    repeat: int
    skip: int
    quit: int


class TopUnhandled(BaseModel):
    raw_text: str
    cnt: int


class MetricsResponse(BaseModel):
    speed_distribution: dict[str, int]
    total_users: int
    total_sessions: int
    completed_sessions: int
    spelling_stats: SpellingStats
    top_hard_words: list[HardWord]
    command_usage: CommandUsage
    unhandled_count: int
    top_unhandled: list[TopUnhandled]
    avg_score_pct: float | None
