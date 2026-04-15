# API Reference

Base URL: `http://localhost:8000` (configurable via `HOST` / `PORT` environment variables)

All request and response bodies are JSON. Authenticated endpoints require the header:

```
Authorization: Bearer <jwt_token>
```

---

## Authentication

### POST `/auth/signup`

Register a new user account.

**Request body**

```json
{
  "username": "alice",
  "password": "s3cr3t",
  "spelling_speed": "normal"
}
```

| Field | Type | Required | Values |
|---|---|---|---|
| `username` | string | Yes | Unique, non-empty |
| `password` | string | Yes | — |
| `spelling_speed` | string | Yes | `"slow"` \| `"normal"` \| `"fast"` |

**Response `201 Created`**

```json
{
  "token": "<jwt>",
  "username": "alice",
  "spelling_speed": "normal",
  "is_admin": false
}
```

**Errors**

| Status | Detail |
|---|---|
| `409` | Username already taken |

---

### POST `/auth/login`

Authenticate with username and password.

**Request body**

```json
{
  "username": "alice",
  "password": "s3cr3t"
}
```

**Response `200 OK`**

```json
{
  "token": "<jwt>",
  "username": "alice",
  "spelling_speed": "normal",
  "is_admin": false
}
```

**Errors**

| Status | Detail |
|---|---|
| `401` | Invalid username or password |

---

## Profile

### GET `/profile`

Get the authenticated user's profile.

**Headers**: `Authorization: Bearer <token>`

**Response `200 OK`**

```json
{
  "id": 1,
  "username": "alice",
  "spelling_speed": "normal",
  "is_admin": false
}
```

**Errors**

| Status | Detail |
|---|---|
| `401` | Missing or invalid token |
| `404` | User not found |

---

### PATCH `/profile/speed`

Update the user's spelling speed preference. This affects the VAD silence threshold for the next game session.

**Headers**: `Authorization: Bearer <token>`

**Request body**

```json
{
  "spelling_speed": "fast"
}
```

| Field | Values | VAD silence threshold |
|---|---|---|
| `"slow"` | 2.5 seconds of silence before STT fires |
| `"normal"` | 1.8 seconds |
| `"fast"` | 1.0 second |

**Response `200 OK`**

```json
{ "ok": true }
```

---

## Game Connection

### GET `/connect`

Returns the WebSocket URL to use for a game session. The JWT is echoed as a query parameter so the backend can resolve the user's speed preference when the socket connects.

**Query parameters**

| Parameter | Required | Description |
|---|---|---|
| `token` | Yes | JWT obtained from login/signup |

**Response `200 OK`**

```json
{
  "wsUrl": "ws://localhost:8000/ws?token=<jwt>"
}
```

---

## WebSocket `/ws`

Real-time audio and game state channel. Uses the [RTVI (Real-Time Voice Interface)](https://github.com/pipecat-ai/pipecat) binary frame protocol over WebSocket.

**Query parameters**

| Parameter | Required | Description |
|---|---|---|
| `token` | Yes | JWT (or `"anonymous"` for unauthenticated play) |

**Frame types (upstream, browser → server)**

| Frame | Description |
|---|---|
| Audio PCM | Raw microphone audio at 16 kHz mono |
| RTVI control frames | Pipecat client handshake messages |

**Frame types (downstream, server → browser)**

| Frame | Description |
|---|---|
| Audio PCM | TTS synthesised speech |
| `RTVIServerMessageFrame` | JSON game state payload (see below) |
| `BotStartedSpeakingFrame` | Bot TTS has begun |
| `BotStoppedSpeakingFrame` | Bot TTS has ended |
| `UserStartedSpeakingFrame` | VAD detected speech start |
| `UserStoppedSpeakingFrame` | VAD detected speech end |

**Game state message (`RTVIServerMessageFrame` payload)**

The backend pushes this JSON payload whenever game state changes:

```json
{
  "phase": "waiting_for_spelling",
  "currentWord": "knight",
  "wordIndex": 2,
  "totalWords": 10,
  "score": 2,
  "history": [
    { "word": "cat", "attempt": "cat", "correct": true },
    { "word": "dog", "attempt": "doc", "correct": false }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `phase` | string | `waiting_for_spelling` \| `between_words` \| `game_over` |
| `currentWord` | string | The word the user must spell (hidden in the UI until the round ends) |
| `wordIndex` | number | 0-based index of the current word |
| `totalWords` | number | Always `10` |
| `score` | number | Number of correct answers so far |
| `history` | array | All completed word results |

---

## Admin

### GET `/admin/metrics`

Returns aggregate metrics across all game sessions. Requires an admin account (see [Admin Tools](../README.md#admin-tools)).

**Headers**: `Authorization: Bearer <admin_token>`

**Response `200 OK`**

```json
{
  "total_sessions": 42,
  "total_attempts": 380,
  "overall_accuracy": 0.71,
  "hardest_words": [
    { "word": "sacrilegious", "attempts": 18, "correct": 4 },
    { "word": "mnemonic", "attempts": 15, "correct": 5 }
  ],
  "command_usage": {
    "repeat": 120,
    "skip": 45,
    "quit": 8
  },
  "unhandled_utterances": 33
}
```

**Errors**

| Status | Detail |
|---|---|
| `401` | Missing or invalid token |
| `403` | Admin access required |

---

## Diagnostics

### POST `/log`

Frontend posts diagnostic events so they appear in the backend log (correlated by session/timestamp).

**Request body**

```json
{
  "level": "info",
  "message": "transport connected",
  "data": { "sessionId": "abc-123" }
}
```

**Response `200 OK`**

```json
{ "ok": true }
```
