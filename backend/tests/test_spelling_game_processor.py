"""Tests for SpellingGameProcessor using Pipecat's run_test utility."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import pytest_asyncio

from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    InterruptionFrame,
    TextFrame,
    TranscriptionFrame,
)
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from pipecat.tests.utils import run_test

from bot import GamePhase, SpellingGameProcessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_processor() -> SpellingGameProcessor:
    """Return a fresh SpellingGameProcessor with a deterministic word list."""
    p = SpellingGameProcessor()
    # Override the random word sample with a fixed list for determinism
    p._words = [
        {"word": "cat", "sentence": "the cat sat on the mat"},
        {"word": "dog", "sentence": "the dog barked"},
        {"word": "hat", "sentence": "she wore a hat"},
        {"word": "bat", "sentence": "a bat flew overhead"},
        {"word": "rat", "sentence": "the rat ran away"},
        {"word": "mat", "sentence": "the mat was dirty"},
        {"word": "fat", "sentence": "a fat cat"},
        {"word": "sat", "sentence": "she sat down"},
        {"word": "pat", "sentence": "he gave a pat"},
        {"word": "cap", "sentence": "he wore a cap"},
    ]
    return p


# ---------------------------------------------------------------------------
# Phase initial state
# ---------------------------------------------------------------------------

def test_initial_phase_is_between_words():
    p = make_processor()
    assert p._phase == GamePhase.BETWEEN_WORDS


def test_get_intro_text_keeps_between_words():
    p = make_processor()
    p.get_intro_text()
    assert p._phase == GamePhase.BETWEEN_WORDS, (
        "get_intro_text must NOT set WAITING_FOR_SPELLING — "
        "phase must stay BETWEEN_WORDS until bot finishes speaking"
    )


# ---------------------------------------------------------------------------
# BotStoppedSpeakingFrame → WAITING_FOR_SPELLING
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bot_stopped_speaking_triggers_waiting():
    p = make_processor()
    p.get_intro_text()  # loads word 1, phase = BETWEEN_WORDS

    down, _ = await run_test(
        p,
        frames_to_send=[BotStoppedSpeakingFrame()],
        send_end_frame=True,
    )

    assert p._phase == GamePhase.WAITING_FOR_SPELLING
    # Expect RTVIServerMessageFrame (game state update) + BotStoppedSpeakingFrame forwarded
    server_msgs = [f for f in down if isinstance(f, RTVIServerMessageFrame)]
    assert len(server_msgs) == 1
    payload = server_msgs[0].data["payload"]
    assert payload["phase"] == GamePhase.WAITING_FOR_SPELLING.value


@pytest.mark.asyncio
async def test_bot_stopped_no_transition_when_game_over():
    p = make_processor()
    p._phase = GamePhase.GAME_OVER
    p._current_word = "cat"

    down, _ = await run_test(
        p,
        frames_to_send=[BotStoppedSpeakingFrame()],
        send_end_frame=True,
    )

    assert p._phase == GamePhase.GAME_OVER
    server_msgs = [f for f in down if isinstance(f, RTVIServerMessageFrame)]
    assert len(server_msgs) == 0


@pytest.mark.asyncio
async def test_bot_stopped_no_transition_when_no_word_loaded():
    p = make_processor()
    # Phase is BETWEEN_WORDS but _current_word is empty (before get_intro_text)
    assert p._current_word == ""

    await run_test(
        p,
        frames_to_send=[BotStoppedSpeakingFrame()],
        send_end_frame=True,
    )

    # Should not transition since no word is ready
    assert p._phase == GamePhase.BETWEEN_WORDS


# ---------------------------------------------------------------------------
# TranscriptionFrame gating
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_transcription_blocked_during_between_words():
    p = make_processor()
    p.get_intro_text()  # phase = BETWEEN_WORDS

    down, _ = await run_test(
        p,
        frames_to_send=[TranscriptionFrame(text="cat", user_id="user", timestamp="")],
        send_end_frame=True,
    )

    # No TextFrame should be pushed (attempt was dropped)
    text_frames = [f for f in down if isinstance(f, TextFrame)]
    assert len(text_frames) == 0
    # Score unchanged
    assert p._score == 0


@pytest.mark.asyncio
async def test_transcription_accepted_after_bot_stops():
    p = make_processor()
    p.get_intro_text()  # loads "cat"

    down, _ = await run_test(
        p,
        frames_to_send=[
            BotStoppedSpeakingFrame(),       # opens spelling window
            TranscriptionFrame(text="cat", user_id="user", timestamp=""),
        ],
        send_end_frame=True,
    )

    text_frames = [f for f in down if isinstance(f, TextFrame)]
    assert len(text_frames) == 1, "A feedback TextFrame should be pushed"
    assert p._score == 1


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_correct_spelling_increments_score():
    p = make_processor()
    p.get_intro_text()  # word is "cat"

    await run_test(
        p,
        frames_to_send=[
            BotStoppedSpeakingFrame(),
            TranscriptionFrame(text="cat", user_id="user", timestamp=""),
        ],
        send_end_frame=True,
    )

    assert p._score == 1


@pytest.mark.asyncio
async def test_incorrect_spelling_no_score():
    p = make_processor()
    p.get_intro_text()  # word is "cat"

    await run_test(
        p,
        frames_to_send=[
            BotStoppedSpeakingFrame(),
            TranscriptionFrame(text="dog", user_id="user", timestamp=""),
        ],
        send_end_frame=True,
    )

    assert p._score == 0


@pytest.mark.asyncio
async def test_various_spellings_of_cat():
    """Normalizer + processor accept all valid spellings of 'cat'."""
    for spelling in ["C A T", "c,a,t", "C-A-T", "CAT", "c. a. t."]:
        p = make_processor()
        p.get_intro_text()

        await run_test(
            p,
            frames_to_send=[
                BotStoppedSpeakingFrame(),
                TranscriptionFrame(text=spelling, user_id="user", timestamp=""),
            ],
            send_end_frame=True,
        )

        assert p._score == 1, f"Expected correct for spelling '{spelling}'"


# ---------------------------------------------------------------------------
# Phase after evaluation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase_resets_to_between_words_after_attempt():
    p = make_processor()
    p.get_intro_text()

    await run_test(
        p,
        frames_to_send=[
            BotStoppedSpeakingFrame(),
            TranscriptionFrame(text="cat", user_id="user", timestamp=""),
        ],
        send_end_frame=True,
    )

    assert p._phase == GamePhase.BETWEEN_WORDS


@pytest.mark.asyncio
async def test_response_text_frame_pushed_downstream():
    p = make_processor()
    p.get_intro_text()

    down, _ = await run_test(
        p,
        frames_to_send=[
            BotStoppedSpeakingFrame(),
            TranscriptionFrame(text="cat", user_id="user", timestamp=""),
        ],
        send_end_frame=True,
    )

    text_frames = [f for f in down if isinstance(f, TextFrame)]
    assert len(text_frames) == 1
    assert "dog" in text_frames[0].text.lower(), "Next word should be in response"


# ---------------------------------------------------------------------------
# Game over
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_game_over_after_n_words():
    p = make_processor()
    from word_list import WORDS_PER_GAME

    for _ in range(WORDS_PER_GAME):
        p.get_intro_text() if p._word_index == 0 else None

        await run_test(
            p,
            frames_to_send=[
                BotStoppedSpeakingFrame(),
                TranscriptionFrame(
                    text=p._current_word, user_id="user", timestamp=""
                ),
            ],
            send_end_frame=True,
        )

        if p._phase == GamePhase.GAME_OVER:
            break

    assert p._phase == GamePhase.GAME_OVER
    assert p._score == WORDS_PER_GAME


@pytest.mark.asyncio
async def test_game_state_pushed_on_game_over():
    p = make_processor()
    from word_list import WORDS_PER_GAME

    # Advance to last word manually
    p.get_intro_text()
    p._word_index = WORDS_PER_GAME  # simulate all previous words done

    down, _ = await run_test(
        p,
        frames_to_send=[
            BotStoppedSpeakingFrame(),
            TranscriptionFrame(text=p._current_word, user_id="user", timestamp=""),
        ],
        send_end_frame=True,
    )

    server_msgs = [f for f in down if isinstance(f, RTVIServerMessageFrame)]
    game_over_msgs = [
        m for m in server_msgs
        if m.data.get("payload", {}).get("phase") == GamePhase.GAME_OVER.value
    ]
    assert len(game_over_msgs) >= 1


# ---------------------------------------------------------------------------
# Game state payload structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_game_state_payload_structure():
    p = make_processor()
    p.get_intro_text()

    down, _ = await run_test(
        p,
        frames_to_send=[BotStoppedSpeakingFrame()],
        send_end_frame=True,
    )

    server_msgs = [f for f in down if isinstance(f, RTVIServerMessageFrame)]
    assert len(server_msgs) >= 1
    msg = server_msgs[0]
    assert msg.data["type"] == "game_state"
    payload = msg.data["payload"]
    assert "phase" in payload
    assert "score" in payload
    assert "history" in payload
    assert "wordIndex" in payload
    assert "totalWords" in payload


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_history_appended_per_attempt():
    p = make_processor()
    p.get_intro_text()

    await run_test(
        p,
        frames_to_send=[
            BotStoppedSpeakingFrame(),
            TranscriptionFrame(text="cat", user_id="user", timestamp=""),
        ],
        send_end_frame=True,
    )

    assert len(p._history) == 1
    entry = p._history[0]
    assert entry["word"] == "cat"
    assert entry["attempt"] == "cat"
    assert entry["correct"] is True


# ---------------------------------------------------------------------------
# Interruption handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_interruption_during_between_words_sets_flag():
    p = make_processor()
    p.get_intro_text()  # phase = BETWEEN_WORDS

    await run_test(
        p,
        frames_to_send=[InterruptionFrame()],
        send_end_frame=True,
    )

    assert p._interrupted is True


@pytest.mark.asyncio
async def test_interruption_triggers_repeat_announcement():
    p = make_processor()
    p.get_intro_text()  # word = "cat", phase = BETWEEN_WORDS

    down, _ = await run_test(
        p,
        frames_to_send=[
            InterruptionFrame(),         # user interrupts
            BotStoppedSpeakingFrame(),   # bot stops after interruption
        ],
        send_end_frame=True,
    )

    # Bot should re-announce, not open spelling window
    assert p._phase == GamePhase.BETWEEN_WORDS, "Phase must stay BETWEEN_WORDS during repeat"
    assert p._interrupted is False, "_interrupted flag must be cleared after repeat"
    text_frames = [f for f in down if isinstance(f, TextFrame)]
    assert len(text_frames) == 1
    assert "repeat" in text_frames[0].text.lower() or "cat" in text_frames[0].text.lower()


@pytest.mark.asyncio
async def test_after_repeat_bot_stopped_transitions_to_waiting():
    p = make_processor()
    p.get_intro_text()  # phase = BETWEEN_WORDS, word = "cat"

    # Simulate: interrupt → bot stops → repeat plays → bot stops again
    await run_test(
        p,
        frames_to_send=[
            InterruptionFrame(),
            BotStoppedSpeakingFrame(),   # after interrupt → triggers repeat
        ],
        send_end_frame=True,
    )
    assert p._phase == GamePhase.BETWEEN_WORDS

    # Now bot finishes the repeat announcement
    await run_test(
        p,
        frames_to_send=[BotStoppedSpeakingFrame()],
        send_end_frame=True,
    )
    assert p._phase == GamePhase.WAITING_FOR_SPELLING


@pytest.mark.asyncio
async def test_interruption_during_waiting_does_not_set_flag():
    p = make_processor()
    p.get_intro_text()
    # Manually put in WAITING state (simulating bot finished speaking)
    p._phase = GamePhase.WAITING_FOR_SPELLING

    await run_test(
        p,
        frames_to_send=[InterruptionFrame()],
        send_end_frame=True,
    )

    assert p._interrupted is False
