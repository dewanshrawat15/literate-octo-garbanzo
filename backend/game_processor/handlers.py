"""CommandHandlersMixin — all _handle_* methods for SpellingGameProcessor.

This mixin uses self attributes that live on the final composed class
(SpellingGameProcessor). Python's MRO wires them together at instantiation.
"""
from loguru import logger

from pipecat.frames.frames import TTSSpeakFrame
from pipecat.processors.frame_processor import FrameDirection

from classifier import classify_input
from constants import GamePhase
from db.repositories import SpellingAttemptRepository, TelemetryRepository
from game_processor.normalize import normalize_spelling
from word_list import WORDS_PER_GAME


class CommandHandlersMixin:

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

        SpellingAttemptRepository().log_attempt(
            session_id=self._session_id,
            user_id=self._user_id,
            word=correct_word,
            attempt=attempt,
            correct=is_correct,
        )

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
            self._finalize_session()
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

        SpellingAttemptRepository().log_attempt(
            session_id=self._session_id,
            user_id=self._user_id,
            word=self._current_word.lower(),
            attempt="[repeat]",
            correct=False,
            command_type="repeat",
        )

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

        SpellingAttemptRepository().log_attempt(
            session_id=self._session_id,
            user_id=self._user_id,
            word=correct_word,
            attempt="[skipped]",
            correct=False,
            command_type="skip",
        )

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
            self._finalize_session()
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

        SpellingAttemptRepository().log_attempt(
            session_id=self._session_id,
            user_id=self._user_id,
            word=self._current_word.lower(),
            attempt="[quit]",
            correct=False,
            command_type="quit",
        )

        self._phase = GamePhase.GAME_OVER
        self._finalize_session()
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

        TelemetryRepository().log_unhandled(
            session_id=self._session_id,
            user_id=self._user_id,
            raw_text=raw_text,
            normalized=normalized,
            phase=str(self._phase.value),
            current_word=self._current_word,
        )

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
