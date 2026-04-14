"""Tests for the word list data."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from word_list import WORD_LIST, WORDS_PER_GAME


def test_word_list_length():
    assert len(WORD_LIST) >= 20, "Word list should have at least 20 entries"


def test_entry_schema():
    for entry in WORD_LIST:
        assert "word" in entry, f"Entry missing 'word' key: {entry}"
        assert "sentence" in entry, f"Entry missing 'sentence' key: {entry}"
        assert isinstance(entry["word"], str), "word must be a string"
        assert isinstance(entry["sentence"], str), "sentence must be a string"
        assert len(entry["word"]) > 0, "word must not be empty"
        assert len(entry["sentence"]) > 0, "sentence must not be empty"


def test_words_per_game_smaller_than_list():
    assert WORDS_PER_GAME < len(WORD_LIST), (
        "WORDS_PER_GAME must be smaller than WORD_LIST so random.sample works"
    )


def test_no_duplicate_words():
    words = [entry["word"] for entry in WORD_LIST]
    assert len(words) == len(set(words)), "WORD_LIST contains duplicate words"
