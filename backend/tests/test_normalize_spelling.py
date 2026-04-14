"""Tests for the normalize_spelling utility function."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bot import normalize_spelling


def test_letters_spaced():
    assert normalize_spelling("C A T") == "cat"


def test_letters_comma():
    assert normalize_spelling("C, A, T") == "cat"


def test_letters_hyphen():
    assert normalize_spelling("c-a-t") == "cat"


def test_all_caps_word():
    assert normalize_spelling("CAT") == "cat"


def test_lowercase_word():
    assert normalize_spelling("cat") == "cat"


def test_letters_with_periods():
    assert normalize_spelling("C. A. T.") == "cat"


def test_empty_string():
    assert normalize_spelling("") == ""


def test_whitespace_only():
    assert normalize_spelling("   ") == ""


def test_single_letter():
    assert normalize_spelling("C") == "c"


def test_mixed_case_spaced():
    assert normalize_spelling("C a T") == "cat"


def test_long_word_spaced():
    assert normalize_spelling("N E C E S S A R Y") == "necessary"


def test_word_said_directly():
    assert normalize_spelling("rhythm") == "rhythm"


def test_extra_whitespace():
    assert normalize_spelling("  c  a  t  ") == "cat"
