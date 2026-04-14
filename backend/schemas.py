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


class UpdateSpeedRequest(BaseModel):
    spelling_speed: SpellingSpeed


class UserProfile(BaseModel):
    id: int
    username: str
    spelling_speed: SpellingSpeed


class ConnectResponse(BaseModel):
    wsUrl: str


class LogRequest(BaseModel):
    event: str
    ts: int | None = None
    # Accept arbitrary extra fields from the frontend diagnostic logger
    model_config = {"extra": "allow"}
