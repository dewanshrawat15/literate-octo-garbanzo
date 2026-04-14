"""Core game logic as a Pipecat FrameProcessor.

Turn-taking
-----------
Phase starts as BETWEEN_WORDS (bot speaking). When BotStoppedSpeakingFrame
arrives after normal completion, phase transitions to WAITING_FOR_SPELLING and
the frontend is notified — only then are TranscriptionFrames accepted.

Interruption handling
---------------------
When VADUserStartedSpeakingFrame arrives while the bot is announcing a word
(BETWEEN_WORDS), an _interrupted flag is set and InterruptionFrame is pushed
downstream to cancel TTS. On the subsequent BotStoppedSpeakingFrame the bot
re-announces the same word instead of accepting user input.

Input classification
--------------------
Transcriptions received in WAITING_FOR_SPELLING are routed through
classify_input() before evaluation. Recognised commands (repeat / skip / quit)
are handled directly. Out-of-scope questions are logged to the telemetry DB
and deflected with a short message.
"""
import random

from loguru import logger

from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    Frame,
    InterruptionFrame,
    TTSSpeakFrame,
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from classifier import classify_input
from constants import GamePhase, SpellingSpeed
from db.repositories import GameSessionRepository
from game_processor.handlers import CommandHandlersMixin
from word_list import WORD_LIST, WORDS_PER_GAME


class SpellingGameProcessor(CommandHandlersMixin, FrameProcessor):

    def __init__(
        self,
        session_id: str = "",
        user_id: int | None = None,
        spelling_speed: SpellingSpeed = SpellingSpeed.NORMAL,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._session_id = session_id
        self._user_id = user_id
        self._spelling_speed = spelling_speed
        self._words: list[dict] = random.sample(WORD_LIST, WORDS_PER_GAME)
        self._word_index: int = 0
        self._score: int = 0
        self._phase: GamePhase = GamePhase.BETWEEN_WORDS
        self._current_word: str = ""
        self._current_sentence: str = ""
        self._history: list[dict] = []
        # _interrupted: set when user interrupts a word announcement.
        # _repeating: set while the bot is repeating; blocks further
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
        GameSessionRepository().create_session(
            session_id=self._session_id,
            user_id=self._user_id,
            spelling_speed=self._spelling_speed.value,
        )
        return (
            f"Welcome to Spell Bee — "
            f"word 1 is {self._current_word}, as in: {self._current_sentence}."
        )

    # ------------------------------------------------------------------
    # FrameProcessor interface
    # ------------------------------------------------------------------

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        frame_name = type(frame).__name__
        if frame_name not in ("InputAudioRawFrame", "OutputAudioRawFrame"):
            logger.debug(
                f"[GAME] process_frame: {frame_name} dir={direction.name} "
                f"phase={self._phase.value} interrupted={self._interrupted} "
                f"repeating={self._repeating}"
            )

        # ------------------------------------------------------------------
        # VADUserStartedSpeakingFrame: user spoke while bot was announcing.
        # This is the frame Pipecat actually generates (not InterruptionFrame,
        # which only appears when an LLM aggregator is in the pipeline).
        # We set _interrupted and push InterruptionFrame downstream ourselves
        # to cancel in-progress TTS and trigger BotStoppedSpeakingFrame.
        # ------------------------------------------------------------------
        if isinstance(frame, VADUserStartedSpeakingFrame):
            if (
                self._phase == GamePhase.BETWEEN_WORDS
                and self._current_word
                and not self._repeating
            ):
                logger.info(f"User interrupted '{self._current_word}' — will repeat")
                self._interrupted = True
                await self.push_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
            await self.push_frame(frame, direction)
            return

        # ------------------------------------------------------------------
        # BotStoppedSpeakingFrame: authoritative signal for phase transitions.
        # ------------------------------------------------------------------
        if isinstance(frame, BotStoppedSpeakingFrame):
            if self._phase == GamePhase.BETWEEN_WORDS and self._current_word:
                if self._interrupted:
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
                    # Normal completion (or end of repeat / unrecognised deflection)
                    self._repeating = False
                    self._phase = GamePhase.WAITING_FOR_SPELLING
                    await self._push_game_state()
                    logger.info(f"Ready for spelling of '{self._current_word}'")
            await self.push_frame(frame, direction)
            return

        # ------------------------------------------------------------------
        # TranscriptionFrame: user spelled/said something.
        # Primary window is WAITING_FOR_SPELLING, but quit/skip are honoured
        # even during BETWEEN_WORDS — those are intent-to-exit signals that
        # should not be dropped just because the bot happens to be speaking.
        # ------------------------------------------------------------------
        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            if self._phase == GamePhase.WAITING_FOR_SPELLING:
                await self._handle_spelling_attempt(frame.text)
            elif self._phase == GamePhase.BETWEEN_WORDS and self._current_word:
                intent = classify_input(frame.text)
                if intent in ("quit_command", "skip_command"):
                    logger.info(
                        f"[GAME] {intent} received during BETWEEN_WORDS — "
                        f"cancelling TTS and honouring command"
                    )
                    self._interrupted = False
                    self._repeating = False
                    # Cancel any in-progress TTS (repeat or initial announcement)
                    await self.push_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
                    if intent == "quit_command":
                        await self._handle_quit()
                    else:
                        await self._handle_skip()
            return

        await self.push_frame(frame, direction)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _finalize_session(self) -> None:
        """Persist end-of-game stats to game_sessions."""
        GameSessionRepository().end_session(
            session_id=self._session_id,
            total_words=len(self._history),
            correct_count=self._score,
        )

    def _advance_to_next_word(self) -> None:
        entry = self._words[self._word_index]
        self._current_word = entry["word"]
        self._current_sentence = entry["sentence"]
        self._word_index += 1
        self._phase = GamePhase.BETWEEN_WORDS

    async def _push_game_state(self) -> None:
        """Push current game state to the frontend via RTVIServerMessageFrame."""
        state = {
            "type": "game_state",
            "payload": {
                "phase": self._phase.value,
                "currentWord": (
                    self._current_word if self._phase != GamePhase.GAME_OVER else ""
                ),
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
