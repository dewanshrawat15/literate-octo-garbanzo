"""Core game logic as a Pipecat FrameProcessor.

Turn-taking
-----------
Phase starts as BETWEEN_WORDS (bot speaking). When BotStoppedSpeakingFrame
arrives after normal completion, phase transitions to WAITING_FOR_SPELLING and
the frontend is notified — only then are TranscriptionFrames accepted.

Interruption handling
---------------------
When InterruptionFrame arrives while the bot is announcing a word
(BETWEEN_WORDS), an _interrupted flag is set. On the subsequent
BotStoppedSpeakingFrame the bot re-announces the same word instead of
accepting user input.

Input classification
--------------------
Transcriptions received in WAITING_FOR_SPELLING are routed through
classify_input() before evaluation. Recognised commands (repeat / skip / quit)
are handled directly. Out-of-scope questions are logged to the telemetry DB
and deflected with a short message.
"""
import random
import re

from loguru import logger

from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    Frame,
    InterruptionFrame,
    TextFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from classifier import classify_input
from constants import GamePhase, SpellingSpeed
from word_list import WORD_LIST, WORDS_PER_GAME


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_spelling(text: str) -> str:
    """Convert user spelling input to a lowercase word for comparison.

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

    if all(len(t) == 1 for t in tokens):
        return "".join(tokens).lower()

    if len(tokens) == 1:
        return tokens[0].lower()

    longest = max(tokens, key=len)
    if len(longest) > 1:
        return longest.lower()

    return "".join(tokens).lower()


def _ordinal(n: int) -> str:
    """Return the ordinal string for a positive integer (1 → 'first', etc.)."""
    _MAP = {
        1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
        6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
    }
    return _MAP.get(n, str(n))


# ---------------------------------------------------------------------------
# Game processor
# ---------------------------------------------------------------------------

class SpellingGameProcessor(FrameProcessor):

    def __init__(
        self,
        session_id: str = "",
        user_id: int | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._session_id = session_id
        self._user_id = user_id
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
        # InterruptionFrame: user spoke while bot was announcing a word.
        # ------------------------------------------------------------------
        if isinstance(frame, InterruptionFrame):
            if (
                self._phase == GamePhase.BETWEEN_WORDS
                and self._current_word
                and not self._repeating
            ):
                logger.info(f"User interrupted '{self._current_word}' — will repeat")
                self._interrupted = True
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
        # Only accepted when phase is WAITING_FOR_SPELLING.
        # ------------------------------------------------------------------
        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            if self._phase == GamePhase.WAITING_FOR_SPELLING:
                await self._handle_spelling_attempt(frame.text)
            return

        await self.push_frame(frame, direction)

    # ------------------------------------------------------------------
    # Spelling attempt router
    # ------------------------------------------------------------------

    async def _handle_spelling_attempt(self, raw_text: str) -> None:
        intent = classify_input(raw_text)

        if intent == "repeat_command":
            await self._handle_repeat()
            return
        if intent == "skip_command":
            await self._handle_skip()
            return
        if intent == "quit_command":
            await self._handle_quit()
            return
        if intent == "question":
            await self._handle_unrecognized(raw_text)
            return

        # ── Genuine spelling attempt ──────────────────────────────────────
        attempt = normalize_spelling(raw_text)
        correct_word = self._current_word.lower()
        is_correct = attempt == correct_word

        logger.info(
            f"Spelling attempt: raw='{raw_text}' normalized='{attempt}' "
            f"expected='{correct_word}' correct={is_correct}"
        )

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

        self._phase = GamePhase.BETWEEN_WORDS

        if self._word_index < WORDS_PER_GAME:
            self._advance_to_next_word()
            word_num = self._word_index
            response = (
                f"{feedback} — "
                f"word {word_num} is {self._current_word}, "
                f"as in: {self._current_sentence}."
            )
        else:
            self._phase = GamePhase.GAME_OVER
            response = (
                f"{feedback} — "
                f"game over, you scored {self._score} out of {WORDS_PER_GAME}."
            )
            await self._push_game_state()

        await self.push_frame(TTSSpeakFrame(text=response), FrameDirection.DOWNSTREAM)

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    async def _handle_repeat(self) -> None:
        """User asked to hear the current word again during the spelling phase."""
        logger.info(f"[GAME] Repeat requested for '{self._current_word}'")
        # Transition to BETWEEN_WORDS so BotStoppedSpeakingFrame will
        # correctly transition back to WAITING_FOR_SPELLING afterwards.
        self._phase = GamePhase.BETWEEN_WORDS
        # Set _repeating to prevent TTS echo triggering an infinite repeat loop.
        self._repeating = True
        repeat_text = (
            f"Of course — {self._current_word}, as in: {self._current_sentence}."
        )
        await self.push_frame(TTSSpeakFrame(text=repeat_text), FrameDirection.DOWNSTREAM)

    async def _handle_skip(self) -> None:
        """User skips the current word — counted as wrong, correct spelling revealed."""
        correct_word = self._current_word.lower()
        spaced = ", ".join(correct_word.upper())
        logger.info(f"[GAME] User skipped '{correct_word}'")

        self._history.append({
            "word": correct_word,
            "attempt": "[skipped]",
            "correct": False,
        })

        self._phase = GamePhase.BETWEEN_WORDS

        if self._word_index < WORDS_PER_GAME:
            self._advance_to_next_word()
            word_num = self._word_index
            response = (
                f"No problem — {correct_word} is spelled {spaced} — "
                f"word {word_num} is {self._current_word}, "
                f"as in: {self._current_sentence}."
            )
        else:
            self._phase = GamePhase.GAME_OVER
            response = (
                f"No problem — {correct_word} is spelled {spaced} — "
                f"game over, you scored {self._score} out of {WORDS_PER_GAME}."
            )
            await self._push_game_state()

        await self.push_frame(TTSSpeakFrame(text=response), FrameDirection.DOWNSTREAM)

    async def _handle_quit(self) -> None:
        """User ended the game early."""
        words_attempted = self._word_index - 1  # current word was announced but not evaluated
        logger.info(
            f"[GAME] User quit after {words_attempted} words, score={self._score}"
        )
        self._phase = GamePhase.GAME_OVER
        response = (
            f"Ending the game — you scored {self._score} "
            f"out of {words_attempted} words attempted."
        )
        await self._push_game_state()
        await self.push_frame(TTSSpeakFrame(text=response), FrameDirection.DOWNSTREAM)

    async def _handle_unrecognized(self, raw_text: str) -> None:
        """User said something outside the spelling bee scope.

        Logs the input to the telemetry DB for internal review, then
        redirects the user with a short in-scope message.
        """
        normalized = normalize_spelling(raw_text)
        logger.warning(
            f"[GAME] Unrecognized input phase={self._phase} raw='{raw_text}'"
        )

        try:
            from db.repositories import TelemetryRepository
            TelemetryRepository().log_unhandled(
                session_id=self._session_id,
                user_id=self._user_id,
                raw_text=raw_text,
                normalized=normalized,
                phase=str(self._phase.value),
                current_word=self._current_word,
            )
        except Exception as exc:
            logger.error(f"[GAME] Telemetry write failed: {exc}")

        # Temporarily switch to BETWEEN_WORDS so the BotStoppedSpeakingFrame
        # handler transitions back to WAITING_FOR_SPELLING after the deflection
        # message finishes playing.
        self._phase = GamePhase.BETWEEN_WORDS
        # Prevent TTS echo from triggering an infinite repeat loop.
        self._repeating = True
        response = (
            "I can only help with the spelling bee — "
            "please spell the word, or say repeat, skip, or quit."
        )
        await self.push_frame(TTSSpeakFrame(text=response), FrameDirection.DOWNSTREAM)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
