import os
import random
import re
from enum import Enum

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    Frame,
    InterruptionFrame,
    TextFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame
from pipecat.processors.frameworks.rtvi.observer import RTVIObserverParams
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from word_list import WORD_LIST, WORDS_PER_GAME

load_dotenv()


# ---------------------------------------------------------------------------
# Spelling normalizer
# ---------------------------------------------------------------------------

def normalize_spelling(text: str) -> str:
    """
    Converts user spelling input to a lowercase word for comparison.

    Handles:
      "C, A, T"  → "cat"
      "c-a-t"    → "cat"
      "C A T"    → "cat"
      "CAT"      → "cat"
      "cat"      → "cat"
      "C. A. T." → "cat"
    """
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", text)
    tokens = [t for t in cleaned.split() if t]

    if not tokens:
        return ""

    # Every token is a single letter → user spelled it out letter by letter
    if all(len(t) == 1 for t in tokens):
        return "".join(tokens).lower()

    # Single multi-character token → user said the whole word
    if len(tokens) == 1:
        return tokens[0].lower()

    # Mixed: take the longest token as the word attempt
    longest = max(tokens, key=len)
    if len(longest) > 1:
        return longest.lower()

    return "".join(tokens).lower()


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------

class GamePhase(str, Enum):
    WAITING_FOR_SPELLING = "waiting_for_spelling"
    BETWEEN_WORDS = "between_words"
    GAME_OVER = "game_over"


# ---------------------------------------------------------------------------
# Custom FrameProcessor
# ---------------------------------------------------------------------------

class SpellingGameProcessor(FrameProcessor):
    """
    Core game logic as a Pipecat FrameProcessor.

    Turn-taking:
      Phase starts as BETWEEN_WORDS (bot speaking). When BotStoppedSpeakingFrame
      arrives after normal completion, phase transitions to WAITING_FOR_SPELLING
      and the frontend is notified — only then are TranscriptionFrames accepted.

    Interruption handling:
      When InterruptionFrame arrives while the bot is announcing a word
      (BETWEEN_WORDS), an _interrupted flag is set. On the subsequent
      BotStoppedSpeakingFrame the bot re-announces the same word instead of
      accepting user input, satisfying the requirement to "handle interruptions
      cleanly."
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._words: list[dict] = random.sample(WORD_LIST, WORDS_PER_GAME)
        self._word_index: int = 0
        self._score: int = 0
        self._phase: GamePhase = GamePhase.BETWEEN_WORDS
        self._current_word: str = ""
        self._current_sentence: str = ""
        self._history: list[dict] = []
        # Interruption handling flags.
        # _interrupted: set when user interrupts a word announcement.
        # _repeating: set while the bot is playing the repeat; blocks further
        #   interrupts so that TTS echo cannot trigger an infinite repeat loop.
        self._interrupted: bool = False
        self._repeating: bool = False

    # ------------------------------------------------------------------
    # Called once from on_client_ready to kick off the game
    # ------------------------------------------------------------------

    def get_intro_text(self) -> str:
        """Load word 1 and return the intro speech text.

        Phase is left as BETWEEN_WORDS. The phase will transition to
        WAITING_FOR_SPELLING only when BotStoppedSpeakingFrame arrives after
        the intro audio has fully played back.

        IMPORTANT: text must be a single sentence (no '.', '!', '?' in the
        middle). Pipecat TTS splits on sentence boundaries; a mid-text split
        causes the audio buffer to empty momentarily, triggering a premature
        BotStoppedSpeakingFrame and a false WAITING_FOR_SPELLING transition.
        """
        self._advance_to_next_word()
        return (
            f"Welcome to Spell Bee — "
            f"word 1 is {self._current_word}, as in: {self._current_sentence}."
        )

    # ------------------------------------------------------------------
    # FrameProcessor interface
    # ------------------------------------------------------------------

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # TRACE: log every frame type that reaches game_processor
        frame_name = type(frame).__name__
        if frame_name not in ("InputAudioRawFrame", "OutputAudioRawFrame"):
            logger.debug(
                f"[GAME] process_frame: {frame_name} dir={direction.name} "
                f"phase={self._phase.value} interrupted={self._interrupted} "
                f"repeating={self._repeating}"
            )

        # ------------------------------------------------------------------
        # Interruption: user spoke while bot was announcing a word.
        # Set flag so BotStoppedSpeakingFrame knows to re-announce instead
        # of opening the spelling window.
        # ------------------------------------------------------------------
        if isinstance(frame, InterruptionFrame):
            # Only accept the interruption if we are NOT already mid-repeat.
            # Without this guard, TTS echo is picked up by the mic → VAD fires
            # → InterruptionFrame → repeat → echo → InterruptionFrame → infinite loop.
            if (
                self._phase == GamePhase.BETWEEN_WORDS
                and self._current_word
                and not self._repeating
            ):
                logger.info(
                    f"User interrupted '{self._current_word}' — will repeat"
                )
                self._interrupted = True
            await self.push_frame(frame, direction)
            return

        # ------------------------------------------------------------------
        # BotStoppedSpeakingFrame: bot has finished playing all audio.
        # This is the authoritative signal for phase transitions.
        # ------------------------------------------------------------------
        if isinstance(frame, BotStoppedSpeakingFrame):
            if self._phase == GamePhase.BETWEEN_WORDS and self._current_word:
                if self._interrupted:
                    # Bot was cut off — repeat the current word.
                    # Set _repeating=True so any echo from this TTS playback
                    # cannot trigger another InterruptionFrame handling.
                    self._interrupted = False
                    self._repeating = True
                    repeat_text = (
                        f"Let me repeat that — "
                        f"{self._current_word}, as in: {self._current_sentence}."
                    )
                    logger.info(f"Re-announcing '{self._current_word}'")
                    await self.push_frame(
                        TTSSpeakFrame(text=repeat_text), FrameDirection.DOWNSTREAM
                    )
                else:
                    # Normal completion (or end of repeat) — user may now spell.
                    self._repeating = False
                    self._phase = GamePhase.WAITING_FOR_SPELLING
                    await self._push_game_state()
                    logger.info(f"Ready for spelling of '{self._current_word}'")
            await self.push_frame(frame, direction)
            return

        # ------------------------------------------------------------------
        # TranscriptionFrame: user spelled something.
        # Only accept when phase is WAITING_FOR_SPELLING (after bot stopped).
        # All other phases drop the frame silently.
        # ------------------------------------------------------------------
        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            if self._phase == GamePhase.WAITING_FOR_SPELLING:
                await self._handle_spelling_attempt(frame.text)
            # TranscriptionFrame is never forwarded downstream — no downstream
            # processor needs STT output in this pipeline.
            return

        # Forward all other frames unchanged
        await self.push_frame(frame, direction)

    # ------------------------------------------------------------------
    # Game logic
    # ------------------------------------------------------------------

    async def _handle_spelling_attempt(self, raw_text: str):
        attempt = normalize_spelling(raw_text)
        correct_word = self._current_word.lower()
        is_correct = attempt == correct_word

        logger.info(
            f"Spelling attempt: raw='{raw_text}' normalized='{attempt}' "
            f"expected='{correct_word}' correct={is_correct}"
        )

        # Single-sentence feedback — no '.', '!', '?' in the middle.
        # Split text causes TTS to produce separate audio chunks with a brief
        # gap, which triggers a spurious BotStoppedSpeakingFrame between them.
        if is_correct:
            feedback = "Correct"
        else:
            spaced = ", ".join(correct_word.upper())
            feedback = f"Not quite — {correct_word} is spelled {spaced}"

        if is_correct:
            self._score += 1

        self._history.append({
            "word": correct_word,
            "attempt": attempt,
            "correct": is_correct,
        })

        # Transition to BETWEEN_WORDS while bot speaks feedback.
        # Do NOT push game state yet — BotStoppedSpeakingFrame will push
        # WAITING_FOR_SPELLING (or GAME_OVER) at the right moment.
        self._phase = GamePhase.BETWEEN_WORDS

        if self._word_index < WORDS_PER_GAME:
            self._advance_to_next_word()  # sets BETWEEN_WORDS
            word_num = self._word_index
            response = (
                f"{feedback} — "
                f"word {word_num} is {self._current_word}, "
                f"as in: {self._current_sentence}."
            )
            # Phase stays BETWEEN_WORDS until BotStoppedSpeakingFrame arrives
        else:
            self._phase = GamePhase.GAME_OVER
            response = (
                f"{feedback} — "
                f"game over, you scored {self._score} out of {WORDS_PER_GAME}."
            )
            # GAME_OVER is terminal — push state immediately
            await self._push_game_state()

        await self.push_frame(TTSSpeakFrame(text=response), FrameDirection.DOWNSTREAM)

    def _advance_to_next_word(self):
        entry = self._words[self._word_index]
        self._current_word = entry["word"]
        self._current_sentence = entry["sentence"]
        self._word_index += 1
        # Phase is set to BETWEEN_WORDS (not WAITING_FOR_SPELLING).
        # The transition to WAITING_FOR_SPELLING happens only when
        # BotStoppedSpeakingFrame confirms the bot has finished speaking.
        self._phase = GamePhase.BETWEEN_WORDS

    async def _push_game_state(self):
        """Push current game state to the frontend via RTVIServerMessageFrame.

        RTVIServerMessageFrame is a SystemFrame — it bypasses the normal
        async frame queue and arrives at the client immediately, independent
        of any pending audio frames.
        """
        state = {
            "type": "game_state",
            "payload": {
                "phase": self._phase.value,
                "currentWord": self._current_word if self._phase != GamePhase.GAME_OVER else "",
                "wordIndex": self._word_index,
                "totalWords": WORDS_PER_GAME,
                "score": self._score,
                "history": self._history,
            },
        }
        await self.push_frame(
            RTVIServerMessageFrame(data=state),
            FrameDirection.DOWNSTREAM,
        )


# ---------------------------------------------------------------------------
# Pipeline builder
# ---------------------------------------------------------------------------

async def run_bot(websocket_client):
    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=ProtobufFrameSerializer(),
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(
                    # stop_secs=0.8: intentionally longer than default 0.2s.
                    # Letter-by-letter spelling ("C... A... T...") has natural
                    # pauses; we need more silence before treating an utterance
                    # as finished.
                    stop_secs=0.8,
                    # start_secs=0.3: require 300ms of continuous speech before
                    # triggering VAD (up from 0.2s default). TTS echo bursts are
                    # typically shorter than 300ms; genuine user speech is longer.
                    start_secs=0.3,
                    # confidence=0.7: higher threshold reduces echo false-triggers
                    # while still catching clear user speech.
                    confidence=0.7,
                )
            ),
        ),
    )

    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        # Disable smart formatting — it would reformat "C A T" into "CAT"
        # and add punctuation that breaks the spelling normalizer.
        settings=DeepgramSTTService.Settings(
            model="nova-2-general",
            language="en",
            punctuate=False,
            smart_format=False,
            interim_results=False,
        ),
    )

    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id=os.getenv("CARTESIA_VOICE_ID", "71a7ad14-091c-4e8e-a314-022ece01c121"),
    )

    game_processor = SpellingGameProcessor()

    class TapProcessor(FrameProcessor):
        """Tap that logs every non-audio frame at a given pipeline position."""
        def __init__(self, tag: str, **kwargs):
            super().__init__(**kwargs)
            self._tag = tag

        async def process_frame(self, frame: Frame, direction: FrameDirection):
            await super().process_frame(frame, direction)
            name = type(frame).__name__
            if name not in ("InputAudioRawFrame", "OutputAudioRawFrame"):
                logger.debug(f"[TAP:{self._tag}] {name} dir={direction.name}")
            await self.push_frame(frame, direction)

    pipeline = Pipeline([
        transport.input(),
        TapProcessor(tag="post-input"),
        stt,
        TapProcessor(tag="post-stt"),
        game_processor,
        TapProcessor(tag="post-game"),   # Did TextFrame actually leave game_processor?
        tts,
        TapProcessor(tag="post-tts"),    # Did TTS produce audio frames?
        transport.output(),
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            # Interruptions stay enabled. SpellingGameProcessor handles them:
            # when user interrupts a word announcement, the bot re-announces
            # the word rather than opening the spelling window prematurely.
            allow_interruptions=True,
            enable_metrics=False,
        ),
        rtvi_observer_params=RTVIObserverParams(
            # Only keep the events the frontend actually uses.
            # Everything else defaults to True and generates a WebSocket message
            # on every matching frame — including one per Deepgram result and
            # one per VAD trigger, which floods the connection.
            bot_speaking_enabled=True,       # → onBotStartedSpeaking / onBotStoppedSpeaking
            user_speaking_enabled=True,      # → onUserStartedSpeaking / onUserStoppedSpeaking
            user_transcription_enabled=False,  # handled server-side; no need to forward
            bot_tts_enabled=False,           # TTS start/stop events not used by frontend
            bot_output_enabled=False,        # no LLM streaming output
            bot_llm_enabled=False,           # no LLM
            user_llm_enabled=False,          # no LLM
            metrics_enabled=False,
        ),
    )

    @task.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        """Fires after RTVI handshake — audio pipeline is guaranteed live."""
        logger.info("[BOOT] on_client_ready fired")
        intro = game_processor.get_intro_text()  # loads word 1, phase = BETWEEN_WORDS
        logger.info(f"[BOOT] intro text: {intro!r}")
        logger.info(f"[BOOT] current_word={game_processor._current_word!r}")
        # Push BETWEEN_WORDS state first so frontend shows "Bot is speaking..."
        await game_processor._push_game_state()
        logger.info("[BOOT] pushed initial game_state")
        # Then queue the intro audio; WAITING_FOR_SPELLING will be pushed by
        # BotStoppedSpeakingFrame after the intro finishes playing
        await task.queue_frames([TTSSpeakFrame(text=intro)])
        logger.info("[BOOT] queued TextFrame — waiting for TTS to synthesize")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected — cancelling pipeline task")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
