# Game Flow

This document walks through a complete game session from the user's perspective and the system's perspective simultaneously.

---

## 1. User registration and login

```
User fills SignupScreen:
  username = "alice"
  password = "secret"
  spelling_speed = "normal"

→ POST /auth/signup
← 201 { token, username, spelling_speed, is_admin }

Token and profile are stored in localStorage by useAuth.
```

On subsequent visits:
```
User fills LoginScreen
→ POST /auth/login
← 200 { token, username, spelling_speed, is_admin }
```

---

## 2. Starting a game

User clicks **Start** on `StartScreen`.

```
useSpellBeeClient:
  1. GET /connect?token=<jwt>
     ← { wsUrl: "ws://localhost:8000/ws?token=<jwt>" }

  2. new RTVIClient({ transport: WebSocketTransport(wsUrl) })
     client.connect()

  3. WebSocket handshake to ws://localhost:8000/ws?token=<jwt>
```

Backend on WebSocket accept:
```
server.py / websocket_endpoint():
  - Decodes JWT → user_id = 1
  - Looks up user → spelling_speed = "normal" → stop_secs = 1.8
  - session_id = uuid4()
  - await run_bot(websocket, session_id, stop_secs, user_id, speed)
```

`run_bot()` builds and starts the Pipecat pipeline:
```
WebSocketServerTransport
  → SileroVADAnalyzer(stop_secs=1.8)
  → DeepgramSTTService(nova-2-general)
  → SpellingGameProcessor(session_id, user_id, speed)
  → CartesiaTTSService
  → WebSocketServerTransport (output)
```

---

## 3. Word announcement (bot turn)

`SpellingGameProcessor._announce_word()` runs at the start of each round:

```
Bot TTS says:
  "Word 1 of 10. Your word is: cat.
   Here is a sentence: the cat sat on the mat.
   Please spell the word."
```

Simultaneously the backend pushes a `RTVIServerMessageFrame`:
```json
{
  "phase": "waiting_for_spelling",
  "currentWord": "cat",
  "wordIndex": 0,
  "totalWords": 10,
  "score": 0,
  "history": []
}
```

Frontend `useSpellBeeClient` receives this and updates `gameState`, causing `GameScreen` to render with the current word index and score visible.

---

## 4. User spelling attempt

User speaks: **"C, A, T"**

```
Microphone audio (PCM 16kHz mono)
  → WebSocket binary frame
  → SileroVAD: detecting speech…
  → [1.8 seconds of silence]
  → VAD emits UserStoppedSpeakingFrame

Deepgram STT: transcribes audio → "C, A, T"
  → TranscriptionFrame("C, A, T")

SpellingGameProcessor.process_frame():
  1. classify_input("C, A, T") → "spelling"
  2. normalize("C, A, T") → "cat"
  3. "cat" == current_word "cat" → CORRECT ✓
  4. SpellingAttemptRepository.insert(
       session_id, user_id, word="cat", attempt="cat", correct=True
     )
  5. Push RTVIServerMessageFrame { phase: "between_words", score: 1, ... }
  6. Push TextFrame("Correct! The word was cat.")

CartesiaTTS synthesises "Correct! The word was cat."
  → audio frames → WebSocket → browser speaker

After TTS completes:
  → _announce_word() for word #2
```

---

## 5. Handling commands

### Repeat

User says: **"Can you repeat that?"**

```
classify_input("can you repeat that") → "repeat_command"
handlers.handle_repeat():
  → Push TextFrame(repeat announcement for current word)
```

No attempt is recorded. The phase stays `waiting_for_spelling`.

### Skip

User says: **"Skip"**

```
classify_input("skip") → "skip_command"
handlers.handle_skip():
  → SpellingAttemptRepository.insert(... command_type="skip", correct=False)
  → Push TextFrame("Okay, skipping. The word was <word>.")
  → advance to next word
```

### Quit

User says: **"Quit"**

```
classify_input("quit") → "quit_command"
handlers.handle_quit():
  → Save session with current score
  → Push RTVIServerMessageFrame { phase: "game_over", ... }
  → End pipeline
```

### Out-of-scope utterance

User says: **"What is the capital of France?"**

```
classify_input("what is the capital of france") → "question"
TelemetryRepository.insert(raw_text, session_id, user_id, phase, current_word)
→ Push TextFrame("I can only help you with spelling. Please spell the word.")
```

---

## 6. Interruption during bot speech

If Silero VAD detects the user speaking while the bot is producing TTS:

```
UserStartedSpeakingFrame received by SpellingGameProcessor
  → processor sets interruption_flag = True

When current TTS frame drains:
  → processor calls _announce_word() again (repeats the word)
```

This prevents the user from missing part of the sentence when they start speaking too early.

---

## 7. Game over

After 10 words (correct or skipped):

```
SpellingGameProcessor:
  → GameSessionRepository.close_session(session_id, total_words=10, correct_count=7)
  → Push RTVIServerMessageFrame { phase: "game_over", score: 7, history: [...] }
  → Push TextFrame("Game over! You scored 7 out of 10.")
  → pipeline.stop()
```

Frontend transitions to `EndScreen`, displaying score and word-by-word history.

---

## 8. Word list

10 words are randomly selected from a pool of 25 for each game session:

| Difficulty tier | Words |
|---|---|
| Easy | cat, dog, hat, apple, table, light |
| Medium | bridge, knight, phrase, colonel, rhythm, gauge |
| Hard | necessary, occurrence, lieutenant, pneumonia, bureaucracy |
| Very hard | conscientious, acquiesce, ephemeral, idiosyncrasy, mnemonic, phlegmatic, sacrilegious, supersede |

---

## 9. Spelling speed and VAD thresholds

The `spelling_speed` preference controls how long Silero VAD waits for silence before sending audio to STT. Slower speeds give users more time between letters.

| Speed | Silence threshold | Best for |
|---|---|---|
| `slow` | 2.5 seconds | Deliberate, letter-by-letter spellers |
| `normal` | 1.8 seconds | Default |
| `fast` | 1.0 second | Whole-word attempts or fast spellers |
