# Pipecat AI Pipeline

The real-time voice processing is handled by [Pipecat](https://github.com/pipecat-ai/pipecat), an open-source framework for building voice AI applications. This document describes the pipeline stages, configuration, and the custom `SpellingGameProcessor`.

---

## Pipeline construction (`pipeline.py`)

`run_bot()` is called once per WebSocket connection. It builds and runs a linear `Pipeline`:

```python
transport = WebSocketServerTransport(websocket, params=WebSocketParams(audio_out_enabled=True))

stt = DeepgramSTTService(api_key=DEEPGRAM_API_KEY, live_options=LiveOptions(
    model="nova-2-general",
    language="en-US",
    punctuate=False,
    interim_results=False,
))

tts = CartesiaTTSService(api_key=CARTESIA_API_KEY, voice_id=CARTESIA_VOICE_ID)

vad = SileroVADAnalyzer(params=VADParams(stop_secs=stop_secs))

game = SpellingGameProcessor(
    session_id=session_id,
    user_id=user_id,
    spelling_speed=spelling_speed,
)

pipeline = Pipeline([
    transport.input(),
    vad,
    stt,
    game,
    tts,
    transport.output(),
])

task = PipelineTask(pipeline)
runner = PipelineRunner()
await runner.run(task)
```

---

## Pipeline stages

### 1. WebSocket Transport (input)

`transport.input()` receives binary RTVI frames from the browser, demuxes them, and emits:
- `InputAudioRawFrame` — raw PCM audio from the microphone
- RTVI control frames — handshake and metadata

### 2. Silero VAD Analyzer

`SileroVADAnalyzer` runs Silero's Voice Activity Detection model **locally** (no external API call). It monitors the audio stream and emits:
- `UserStartedSpeakingFrame` — speech onset
- `UserStoppedSpeakingFrame` — after `stop_secs` of silence following speech

The `stop_secs` parameter is the key tuning knob and is set per user based on their `spelling_speed` preference:

| Speed | `stop_secs` | Rationale |
|---|---|---|
| `slow` | `2.5` | Enough silence between letters for deliberate spellers |
| `normal` | `1.8` | Balanced for most users |
| `fast` | `1.0` | Minimal latency for confident whole-word input |

### 3. Deepgram STT

`DeepgramSTTService` streams audio frames to Deepgram's Nova-2 model over a persistent WebSocket connection. Configuration:

```python
LiveOptions(
    model="nova-2-general",
    language="en-US",
    punctuate=False,       # Punctuation off — cleaner for letter parsing
    interim_results=False, # Only final transcriptions
)
```

Output: `TranscriptionFrame(text="C, A, T")`

### 4. SpellingGameProcessor

Custom `FrameProcessor` (see section below). Sits between STT and TTS and drives all game logic.

### 5. Cartesia TTS

`CartesiaTTSService` converts `TextFrame` objects to speech audio using Cartesia's API. The voice is configured via `CARTESIA_VOICE_ID` (default: `71a7ad14-091c-4e8e-a314-022ece01c121`).

Cartesia produces streaming audio chunks that flow directly into the transport output without buffering the full utterance first, keeping latency low.

### 6. WebSocket Transport (output)

`transport.output()` muxes audio frames and RTVI server messages back to the browser over the same WebSocket connection.

---

## SpellingGameProcessor

Located at `backend/game_processor/processor.py`.

### Lifecycle

```
__init__()
  → select 10 random words from WORD_LIST
  → set phase = WAITING_FOR_SPELLING
  → open game session in DB

process_frame(frame, direction)
  → handle TranscriptionFrame  (STT output)
  → handle UserStartedSpeakingFrame  (VAD interrupt)
  → handle EndFrame  (pipeline teardown)
  → pass all other frames downstream unchanged

_announce_word()
  → push TextFrame with word number + sentence
  → push RTVIServerMessageFrame with current game state

_evaluate_spelling(text)
  → classify_input(text) → intent
  → route to _handle_spelling / handle_repeat / handle_skip / handle_quit

_end_game()
  → close game session in DB
  → push RTVIServerMessageFrame { phase: "game_over" }
  → push EndFrame to tear down pipeline
```

### Frame handling

The processor overrides `process_frame`:

```python
async def process_frame(self, frame: Frame, direction: FrameDirection):
    if isinstance(frame, TranscriptionFrame):
        await self._evaluate_spelling(frame.text)
    elif isinstance(frame, UserStartedSpeakingFrame):
        await self._handle_interruption()
    elif isinstance(frame, EndFrame):
        await self._cleanup()
        await self.push_frame(frame, direction)
    else:
        await self.push_frame(frame, direction)
```

Frames not explicitly handled are passed downstream unchanged via `push_frame`.

### Interruption handling

When VAD fires `UserStartedSpeakingFrame` while the bot is speaking (detected by tracking whether TTS frames are in flight), the processor:
1. Sets an internal `_interrupted` flag.
2. Once the in-flight TTS audio completes, calls `_announce_word()` again.

This ensures the user always hears the full word and sentence before they are expected to respond.

### Pushing game state to the frontend

Game state updates are sent as `RTVIServerMessageFrame` objects with a custom JSON payload. The frontend's `useSpellBeeClient` hook listens for these frames via the Pipecat client event system.

```python
await self.push_frame(
    RTVIServerMessageFrame(data={
        "phase": self._phase.value,
        "currentWord": self._current_word,
        "wordIndex": self._word_index,
        "totalWords": WORDS_PER_GAME,
        "score": self._score,
        "history": self._history,
    })
)
```

---

## Input classification (`classifier.py`)

`classify_input(text: str) -> str` uses a rule-based classifier (regex + keyword matching) to categorise transcribed speech into five intents:

| Intent | Trigger patterns |
|---|---|
| `spelling` | Single letters, comma/space-separated letters, or short words matching letter patterns |
| `repeat_command` | "repeat", "again", "say that again", "what was the word" |
| `skip_command` | "skip", "pass", "next", "move on" |
| `quit_command` | "quit", "stop", "exit", "end the game" |
| `question` | Anything that doesn't match the above |

The classifier is intentionally lightweight — no LLM or ML model is used here. This keeps latency negligible and makes the classification deterministic.

---

## Spelling normalisation (`normalize.py`)

Before comparing the user's transcription to the target word, it is normalised:

| Input form | Normalised |
|---|---|
| `"C, A, T"` | `"cat"` |
| `"C A T"` | `"cat"` |
| `"cat"` | `"cat"` |
| `"CAT"` | `"cat"` |
| `"c-a-t"` | `"cat"` |

The normaliser strips punctuation, collapses whitespace, joins single-character tokens, and lowercases the result.
