# Architecture

## System Overview

Spell Bee is a full-stack real-time voice application. The user speaks into their browser; audio is streamed over a binary WebSocket to the backend, where an AI pipeline converts it to text, evaluates the spelling, and streams synthesized speech back.

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│                                                             │
│   React + TypeScript frontend                               │
│   ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌─────────┐  │
│   │ Auth     │  │  Game     │  │  Profile │  │ Metrics │  │
│   │ screens  │  │  Screen   │  │  Screen  │  │ Screen  │  │
│   └────┬─────┘  └─────┬─────┘  └────┬─────┘  └────┬────┘  │
│        │              │              │              │        │
│   useAuth hook   useSpellBeeClient hook             │        │
│        │              │                             │        │
└────────┼──────────────┼─────────────────────────────┼───────┘
         │              │                             │
    HTTP/JSON      WebSocket                     HTTP/JSON
    (REST)         (binary RTVI)                 (REST)
         │              │                             │
┌────────▼──────────────▼─────────────────────────────▼───────┐
│                      FastAPI backend                         │
│                                                             │
│  /auth/signup   /ws (WebSocket)          /admin/metrics      │
│  /auth/login    /connect                 /profile            │
│  /log                                                        │
│                                                             │
│              ┌──────────────────────────┐                   │
│              │     Pipecat Pipeline     │                   │
│              │                          │                   │
│              │  Transport (WebSocket)   │                   │
│              │        ↓                 │                   │
│              │  VAD (Silero, local)     │                   │
│              │        ↓                 │                   │
│              │  STT (Deepgram)          │ ──► Deepgram API  │
│              │        ↓                 │                   │
│              │  SpellingGameProcessor   │                   │
│              │        ↓                 │                   │
│              │  TTS (Cartesia)          │ ──► Cartesia API  │
│              │        ↓                 │                   │
│              │  Transport (WebSocket)   │                   │
│              └──────────┬───────────────┘                   │
│                         │                                   │
│                    SQLite DB                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Backend

### FastAPI application (`server.py`)

The backend is a single `FastAPI` application served by `Uvicorn`. It handles:

- Standard HTTP endpoints for auth, profile management, and admin metrics.
- A `GET /connect` endpoint that returns the WebSocket URL (allows the frontend to discover the correct host/port).
- A `WebSocket /ws` endpoint that accepts binary RTVI frames and delegates the entire session to the Pipecat pipeline.

On startup the application:
1. Initialises SQLite tables (idempotent `CREATE TABLE IF NOT EXISTS`).
2. Verifies the Cartesia API key and voice ID against the live API so a bad credential surfaces immediately at boot.

### Pipecat pipeline (`pipeline.py`)

Each WebSocket connection spawns a fresh Pipecat `Pipeline` coroutine. The pipeline is a linear chain of `FrameProcessor` objects:

```
WebSocketServerTransport (input frames)
    └─► SileroVADAnalyzer          # detects start/end of speech
    └─► DeepgramSTTService         # transcribes audio → text
    └─► SpellingGameProcessor      # game logic (see game_processor/)
    └─► CartesiaTTSService         # text → speech audio
    └─► WebSocketServerTransport (output frames)
```

The pipeline runs inside a `PipelineTask` managed by a `PipelineRunner`. When the game finishes or the WebSocket closes, the runner tears the task down cleanly.

### Game Processor (`game_processor/`)

`SpellingGameProcessor` is the core of the application. It subclasses Pipecat's `FrameProcessor` and intercepts `TranscriptionFrame` events (text from STT).

**Game phases:**

| Phase | Description |
|---|---|
| `WAITING_FOR_SPELLING` | Bot has announced the word; waiting for the user to spell it |
| `BETWEEN_WORDS` | Bot is transitioning between words |
| `GAME_OVER` | All 10 words have been played |

**Intent classification (`classifier.py`):**

Each STT transcription is classified into one of five intents:

| Intent | Example utterances |
|---|---|
| `spelling` | "C, A, T", "cat", "K-N-I-G-H-T" |
| `repeat_command` | "repeat", "say it again", "can you repeat that" |
| `skip_command` | "skip", "next word", "pass" |
| `quit_command` | "quit", "stop", "end the game" |
| `question` | anything else (logged as telemetry) |

**Interruption handling:**

When Silero VAD detects the user speaking while the bot is producing TTS audio (e.g. during the word announcement), the pipeline emits `UserStartedSpeakingFrame`. The processor intercepts this signal and, once the current TTS frame drains, repeats the word announcement. This prevents situations where the user starts spelling before hearing the full sentence.

**Spelling normalization (`normalize.py`):**

Handles the many ways a user might spell "cat":
- Letter-by-letter with commas: `"C, A, T"`
- Letter-by-letter with spaces: `"C A T"`
- NATO-style: `"Charlie Alpha Tango"` (partial support)
- Whole-word: `"cat"`

All forms are normalised to a lowercase string before comparison.

### Database layer (`db/`)

A thin repository pattern wraps raw `sqlite3` calls. Each repository handles one table:

- `UserRepository` — create, find by id/username, update speed
- `GameSessionRepository` — open/close sessions with aggregate stats
- `SpellingAttemptRepository` — insert attempts and commands
- `TelemetryRepository` — log unhandled utterances
- `MetricsRepository` — aggregated SQL queries for the admin dashboard

---

## Frontend

### Routing (`App.tsx`)

The app has no router library. `App.tsx` maintains top-level state (`user`, `gameState`) and conditionally renders one of these screens:

```
Not logged in:
  LoginScreen | SignupScreen

Logged in, idle:
  StartScreen (sidebar) + (nothing in main area)

During game:
  GameScreen

Game over:
  EndScreen

Profile:
  ProfileScreen

Metrics (admin):
  MetricsScreen
```

### Auth hook (`useAuth.ts`)

Persists the JWT and user profile in `localStorage`. Exposes `login`, `signup`, `logout`, and `updateSpeed`. All REST calls go through this hook.

### Game client hook (`useSpellBeeClient.ts`)

Wraps the Pipecat `RTVIClient` and `WebSocketTransport`. Responsible for:

1. Calling `GET /connect?token=<jwt>` to get the WebSocket URL.
2. Opening the binary WebSocket and initialising the Pipecat client.
3. Listening for `RTVIEvent.BotReady`, `UserStartedSpeaking`, `BotStartedSpeaking`, etc.
4. Listening for custom `RTVIServerMessageFrame` events that carry the game state JSON payload pushed by the backend.
5. Exposing a `GameState` object that screens render from.

### Game state shape

```typescript
interface GameState {
  phase: "idle" | "connecting" | "waiting_for_spelling" | "between_words" | "game_over";
  currentWord: string;
  wordIndex: number;       // 0-based, out of 10
  totalWords: 10;
  score: number;
  history: Array<{
    word: string;
    attempt: string;
    correct: boolean;
  }>;
}
```

---

## Data flow: a single spelling attempt

```
1. User speaks: "K, N, I, G, H, T"

2. Browser microphone → raw PCM audio
   → Pipecat WebSocketTransport (binary frame)
   → Uvicorn WebSocket

3. Silero VAD: end-of-speech detected (silence > stop_secs)
   → AudioFrame batch sent downstream

4. Deepgram STT: "K, N, I, G, H, T"
   → TranscriptionFrame

5. SpellingGameProcessor receives TranscriptionFrame:
   a. classify_input("K, N, I, G, H, T") → "spelling"
   b. normalize("K, N, I, G, H, T") → "knight"
   c. compare "knight" == current_word "knight" → CORRECT
   d. persist SpellingAttempt to SQLite
   e. push RTVIServerMessageFrame { phase, score, history, ... } → frontend
   f. push TextFrame "Correct! The word was knight." → TTS

6. CartesiaTTS: synthesises speech audio
   → AudioFrame stream → WebSocket → browser speaker

7. Frontend useSpellBeeClient receives RTVIServerMessageFrame
   → updates GameState → React re-render → GameScreen shows ✓
```

---

## Security considerations

- CORS is currently set to `allow_origins=["*"]`. Restrict to your frontend origin in production.
- Set a strong `JWT_SECRET` (at least 32 random bytes) in production.
- The SQLite database file is stored on the local filesystem. Use a volume mount in Docker to persist it across restarts.
- API keys (`DEEPGRAM_API_KEY`, `CARTESIA_API_KEY`) must never be committed to version control; use the `.env` file or secrets management.
