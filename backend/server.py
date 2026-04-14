import os
import sys
import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Force DEBUG-level logging so [GAME], [TAP], [BOOT] traces show up.
logger.remove()
logger.add(sys.stderr, level="DEBUG")

from bot import run_bot  # noqa: E402

app = FastAPI(title="Spell Bee Voice Bot")


@app.on_event("startup")
async def verify_tts_credentials():
    """Hit Cartesia directly with the configured API key + voice_id so a bad
    credential/voice surfaces as a loud error at boot — instead of silently
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
            logger.info(f"[STARTUP] Cartesia OK — voice exists: {r.json().get('name')!r}")
        else:
            logger.error(
                f"[STARTUP] Cartesia check FAILED status={r.status_code} body={r.text[:400]}"
            )
    except Exception as e:
        logger.exception(f"[STARTUP] Cartesia check exception: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/connect")
async def connect():
    """Frontend calls this to get the WebSocket URL before connecting."""
    host = os.getenv("HOST", "localhost")
    port = os.getenv("PORT", "8000")
    ws_host = "localhost" if host == "0.0.0.0" else host
    return {"wsUrl": f"ws://{ws_host}:{port}/ws"}


@app.post("/log")
async def client_log(req: Request):
    """Diagnostic endpoint — frontend POSTs JSON events so we can correlate
    browser-side behavior with backend logs."""
    try:
        body = await req.json()
    except Exception:
        body = {"raw": "unparseable"}
    logger.info(f"[FRONTEND] {body}")
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    try:
        await run_bot(websocket)
    except Exception as e:
        logger.error(f"Bot error: {e}")


if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        log_level="info",
    )
