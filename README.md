# Spell Bee Voice Bot

A real-time, voice-driven Spelling Bee game powered by a Python FastAPI backend and a React + TypeScript frontend. Players listen to a word spoken aloud in a sentence, then spell it back letter-by-letter (or as a whole word) using their microphone. The system understands natural speech commands — repeat, skip, quit — and tracks every attempt in a SQLite database.

---

## Demo

[Watch the demo](https://github.com/dewanshrawat15/literate-octo-garbanzo/raw/main/demo.mp4)

> Full walkthrough: signup → game session → spelling attempts → end screen.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
  - [Docker Compose (recommended)](#docker-compose-recommended)
  - [Manual Setup](#manual-setup)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Game Flow](#game-flow)
- [Database Schema](#database-schema)
- [Admin Tools](#admin-tools)
- [Development](#development)
- [Docs](#docs)

---

## Architecture Overview

```
Browser (React + Vite)
    │
    ├─── REST (HTTP/JSON) ──────────────► FastAPI backend
    │     auth, profile, metrics              │
    │                                         │
    └─── WebSocket (binary Protobuf) ────────►│
          real-time audio frames              │
          + game state messages               │
                                              │
                                    ┌─────────┴──────────┐
                                    │  Pipecat Pipeline  │
                                    │                    │
                                    │  WebSocket Input   │
                                    │  → VAD (Silero)    │
                                    │  → STT (Deepgram)  │
                                    │  → Game Processor  │
                                    │  → TTS (Cartesia)  │
                                    │  → WebSocket Out   │
                                    └─────────┬──────────┘
                                              │
                                         SQLite DB
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 3 |
| Backend | Python, FastAPI, Uvicorn (ASGI) |
| AI pipeline | [Pipecat](https://github.com/pipecat-ai/pipecat) |
| Speech-to-text | Deepgram `nova-2-general` |
| Text-to-speech | Cartesia |
| Voice activity detection | Silero VAD (local, no API key needed) |
| Auth | JWT (python-jose) + bcrypt |
| Database | SQLite (via Python `sqlite3`) |
| Transport | RTVI Protocol over binary WebSocket |

---

## Project Structure

```
curelink-submission/
├── backend/
│   ├── server.py               # FastAPI app, HTTP & WebSocket endpoints
│   ├── pipeline.py             # Pipecat AI pipeline construction & execution
│   ├── classifier.py           # STT text → intent classification
│   ├── auth.py                 # JWT creation & validation, bcrypt hashing
│   ├── constants.py            # SpellingSpeed enum, VAD thresholds
│   ├── schemas.py              # Pydantic request/response models
│   ├── word_list.py            # 25 spelling challenge words + example sentences
│   ├── manage.py               # Admin CLI (promote user to admin)
│   ├── game_processor/
│   │   ├── processor.py        # Core game state machine (FrameProcessor)
│   │   ├── handlers.py         # Command handlers: repeat, skip, quit
│   │   └── normalize.py        # Spelling normalization ("C, A, T" → "cat")
│   └── db/
│       ├── database.py         # SQLite connection + table init
│       ├── models.py           # SQL DDL statements
│       └── repositories/
│           ├── user.py         # CRUD for users table
│           ├── game_session.py # CRUD for game_sessions
│           ├── spelling_attempt.py # Insert/query spelling_attempts
│           ├── telemetry.py    # Unhandled utterance logging
│           └── metrics.py      # Aggregated admin metrics queries
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # Root router / screen switcher
│   │   ├── types.ts            # Shared TypeScript interfaces
│   │   ├── hooks/
│   │   │   ├── useAuth.ts      # Auth state + login/signup/logout
│   │   │   └── useSpellBeeClient.ts # Pipecat WebSocket client + game state
│   │   ├── components/         # Shared UI components
│   │   └── screens/            # Full-page views
│   │       ├── LoginScreen.tsx
│   │       ├── SignupScreen.tsx
│   │       ├── StartScreen.tsx
│   │       ├── GameScreen.tsx
│   │       ├── EndScreen.tsx
│   │       ├── ProfileScreen.tsx
│   │       └── MetricsScreen.tsx
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quick Start

### Docker Compose (recommended)

```bash
# 1. Copy and fill in your API keys
cp .env.example .env

# 2. Start both services
docker compose up --build

# Frontend → http://localhost:5173
# Backend  → http://localhost:8000
```

### Manual Setup

#### Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (copy and edit)
cp ../.env.example .env

# Start the server
python server.py
# → running on http://0.0.0.0:8000
```

#### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Point at the backend
echo "VITE_BACKEND_URL=http://localhost:8000" > .env

# Start the dev server
npm run dev
# → running on http://localhost:5173
```

---

## Configuration

### Backend environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DEEPGRAM_API_KEY` | Yes | — | Deepgram speech-to-text API key |
| `CARTESIA_API_KEY` | Yes | — | Cartesia text-to-speech API key |
| `CARTESIA_VOICE_ID` | No | `71a7ad14-091c-4e8e-a314-022ece01c121` | Cartesia voice identifier |
| `HOST` | No | `0.0.0.0` | Bind address for Uvicorn |
| `PORT` | No | `8000` | Port for Uvicorn |
| `JWT_SECRET` | No | `change-me-in-production` | Secret used to sign JWT tokens |
| `DB_PATH` | No | `spelling_bee.db` | Path to the SQLite database file |

### Frontend environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `VITE_BACKEND_URL` | Yes | `http://localhost:8000` | Base URL of the backend |

---

## API Reference

See [docs/api.md](docs/api.md) for the full API reference.

### Summary

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/signup` | None | Register a new user |
| `POST` | `/auth/login` | None | Authenticate and receive a JWT |
| `GET` | `/profile` | Bearer JWT | Get the current user's profile |
| `PATCH` | `/profile/speed` | Bearer JWT | Update spelling speed preference |
| `GET` | `/admin/metrics` | Bearer JWT (admin) | Aggregate game metrics |
| `GET` | `/connect` | JWT query param | Get the WebSocket URL for a session |
| `POST` | `/log` | None | Frontend diagnostic logging |
| `WS` | `/ws` | JWT query param | Real-time audio + game session |

---

## Game Flow

1. User logs in and clicks **Start Game**.
2. Frontend calls `GET /connect?token=<jwt>` to obtain the WebSocket URL.
3. Frontend opens a binary WebSocket to `/ws?token=<jwt>`.
4. Pipecat pipeline boots: VAD → STT → Game Processor → TTS.
5. Bot announces word #1 and reads an example sentence.
6. User spells the word by voice (letter-by-letter or whole word).
7. Classifier determines intent: `spelling | repeat_command | skip_command | quit_command`.
8. Game Processor evaluates the attempt and responds with TTS feedback.
9. After 10 words the game ends; results are saved and the End Screen is shown.

See [docs/game-flow.md](docs/game-flow.md) for a detailed walkthrough.

---

## Database Schema

| Table | Purpose |
|---|---|
| `users` | User accounts, hashed passwords, speed preference |
| `game_sessions` | Per-session metadata and aggregate scores |
| `spelling_attempts` | Every attempt, command, and its correctness |
| `unhandled_interruptions` | Out-of-scope utterances for telemetry |

See [docs/database.md](docs/database.md) for full schema details.

---

## Admin Tools

### Promote a user to admin

```bash
cd backend
python manage.py --set-admin <username>
```

Admin users can access `GET /admin/metrics`, which returns:
- Overall accuracy across all sessions
- Hardest words (most frequently missed)
- Command usage breakdown (repeat / skip / quit)
- Count of unhandled utterances per session

---

## Development

```bash
# Backend: run tests (if any) and lint
cd backend
python -m pytest

# Frontend: run unit tests
cd frontend
npm test

# Frontend: lint
npm run lint

# Frontend: production build
npm run build
```

---

## Docs

- [docs/architecture.md](docs/architecture.md) — Detailed system architecture
- [docs/api.md](docs/api.md) — Full REST & WebSocket API reference
- [docs/game-flow.md](docs/game-flow.md) — End-to-end game walkthrough
- [docs/database.md](docs/database.md) — Database schema and repository layer
- [docs/pipeline.md](docs/pipeline.md) — Pipecat AI pipeline internals
