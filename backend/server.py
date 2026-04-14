import os
import sys
import uuid

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Force DEBUG-level logging so [GAME], [TAP], [BOOT] traces show up.
logger.remove()
logger.add(sys.stderr, level="DEBUG")

from auth import create_token, decode_token, hash_password, verify_password  # noqa: E402
from constants import DEFAULT_SPEED, VAD_STOP_SECS, SpellingSpeed  # noqa: E402
from db.database import init_all_tables  # noqa: E402
from db.repositories import MetricsRepository, UserRepository  # noqa: E402
from pipeline import run_bot  # noqa: E402
from schemas import (  # noqa: E402
    AuthResponse,
    ConnectResponse,
    LoginRequest,
    LogRequest,
    MetricsResponse,
    SignupRequest,
    UpdateSpeedRequest,
    UserProfile,
)

app = FastAPI(title="Spell Bee Voice Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialise DB tables and verify third-party credentials at boot."""
    init_all_tables()
    await _verify_tts_credentials()


async def _verify_tts_credentials() -> None:
    """Hit Cartesia directly with the configured API key + voice_id so a bad
    credential/voice surfaces as a loud error at boot rather than silently
    failing inside the pipeline WebSocket."""
    import httpx

    api_key = os.getenv("CARTESIA_API_KEY", "")
    voice_id = os.getenv("CARTESIA_VOICE_ID", "71a7ad14-091c-4e8e-a314-022ece01c121")
    if not api_key:
        logger.error("[STARTUP] CARTESIA_API_KEY is empty!")
        return

    logger.info(f"[STARTUP] Verifying Cartesia voice_id={voice_id!r} ...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as hc:
            r = await hc.get(
                f"https://api.cartesia.ai/voices/{voice_id}",
                headers={
                    "X-API-Key": api_key,
                    "Cartesia-Version": "2024-11-13",
                },
            )
        if r.status_code == 200:
            logger.info(f"[STARTUP] Cartesia OK — voice: {r.json().get('name')!r}")
        else:
            logger.error(
                f"[STARTUP] Cartesia check FAILED status={r.status_code} body={r.text[:400]}"
            )
    except Exception as e:
        logger.exception(f"[STARTUP] Cartesia check exception: {e}")


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_user_id_from_header(request: Request) -> int:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = auth[len("Bearer "):]
    user_id = decode_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id


def _require_admin(request: Request) -> int:
    """Decode JWT → DB lookup → verify is_admin. Returns user_id or raises 403."""
    user_id = _get_user_id_from_header(request)
    row = UserRepository().find_by_id(user_id)
    if not row or not row["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/auth/signup", response_model=AuthResponse, status_code=201)
async def signup(req: SignupRequest):
    repo = UserRepository()
    if repo.find_by_username(req.username):
        raise HTTPException(status_code=409, detail="Username already taken")
    hashed = hash_password(req.password)
    user_id = repo.create(req.username, hashed, req.spelling_speed.value)
    token = create_token(user_id)
    return AuthResponse(
        token=token,
        username=req.username,
        spelling_speed=req.spelling_speed,
        is_admin=False,
    )


@app.post("/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    repo = UserRepository()
    row = repo.find_by_username(req.username)
    if not row or not verify_password(req.password, row["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(row["id"])
    return AuthResponse(
        token=token,
        username=row["username"],
        spelling_speed=SpellingSpeed(row["spelling_speed"]),
        is_admin=bool(row["is_admin"]),
    )


# ---------------------------------------------------------------------------
# Profile endpoints  (JWT passed as Authorization: Bearer <token>)
# ---------------------------------------------------------------------------

@app.get("/profile", response_model=UserProfile)
async def get_profile(request: Request):
    user_id = _get_user_id_from_header(request)
    row = UserRepository().find_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserProfile(
        id=row["id"],
        username=row["username"],
        spelling_speed=SpellingSpeed(row["spelling_speed"]),
        is_admin=bool(row["is_admin"]),
    )


@app.patch("/profile/speed")
async def update_speed(req: UpdateSpeedRequest, request: Request):
    user_id = _get_user_id_from_header(request)
    UserRepository().update_speed(user_id, req.spelling_speed.value)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@app.get("/admin/metrics", response_model=MetricsResponse)
async def get_metrics(request: Request):
    _require_admin(request)
    data = MetricsRepository().get_metrics()
    return data


# ---------------------------------------------------------------------------
# Game connection
# ---------------------------------------------------------------------------

@app.get("/connect", response_model=ConnectResponse)
async def connect(token: str = Query(default="anonymous")):
    """Return the WebSocket URL. The token is echoed as a query param so that
    the authenticated user's speed preference can be resolved when /ws is hit."""
    host = os.getenv("HOST", "localhost")
    port = os.getenv("PORT", "8000")
    ws_host = "localhost" if host == "0.0.0.0" else host
    return ConnectResponse(wsUrl=f"ws://{ws_host}:{port}/ws?token={token}")


# ---------------------------------------------------------------------------
# Diagnostic logging
# ---------------------------------------------------------------------------

@app.post("/log")
async def client_log(req: LogRequest):
    """Diagnostic endpoint — frontend POSTs JSON events so we can correlate
    browser-side behaviour with backend logs."""
    logger.info(f"[FRONTEND] {req.model_dump()}")
    return {"ok": True}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

def _resolve_user(token: str) -> tuple[int | None, SpellingSpeed]:
    """Decode the JWT and look up the user's speed preference.

    Returns (user_id, SpellingSpeed). Falls back to (None, NORMAL) for
    anonymous or invalid tokens.
    """
    if token in ("anonymous", ""):
        return None, DEFAULT_SPEED
    user_id = decode_token(token)
    if user_id is None:
        return None, DEFAULT_SPEED
    row = UserRepository().find_by_id(user_id)
    if not row:
        return None, DEFAULT_SPEED
    return user_id, SpellingSpeed(row["spelling_speed"])


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default="anonymous"),
):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    user_id, speed = _resolve_user(token)
    stop_secs = VAD_STOP_SECS[speed]
    logger.info(
        f"WebSocket accepted session={session_id} user={user_id} "
        f"speed={speed.value} stop_secs={stop_secs}"
    )
    try:
        await run_bot(
            websocket,
            session_id=session_id,
            stop_secs=stop_secs,
            user_id=user_id,
            spelling_speed=speed,
        )
    except Exception as e:
        logger.error(f"Bot error session={session_id}: {e}")


if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        log_level="info",
    )
