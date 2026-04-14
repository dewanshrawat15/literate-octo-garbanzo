"""Input classification for the spelling bee pipeline.

Distinguishes between a genuine spelling attempt, a recognised game command,
and an out-of-scope question or statement that the bot cannot handle.
"""
import re
from typing import Literal

InputClass = Literal[
    "spelling",
    "repeat_command",
    "skip_command",
    "quit_command",
    "question",
]

# ---------------------------------------------------------------------------
# Trigger phrase sets (all lowercase, stripped of punctuation)
# ---------------------------------------------------------------------------

_REPEAT_TRIGGERS: frozenset[str] = frozenset({
    "repeat",
    "again",
    "pardon",
    "say again",
    "say it again",
    "come again",
    "what was the word",
    "what's the word",
    "whats the word",
    "can you repeat",
    "can you repeat that",
    "could you repeat",
    "could you repeat that",
})

_SKIP_TRIGGERS: frozenset[str] = frozenset({
    "skip",
    "pass",
    "next",
    "give up",
    "i give up",
    "i don't know",
    "i dont know",
    "next word",
    "skip this word",
    "pass this word",
})

_QUIT_TRIGGERS: frozenset[str] = frozenset({
    "quit",
    "end",
    "exit",
    "stop",
    "i want to stop",
})


def classify_input(text: str) -> InputClass:
    """Classify raw STT transcription into one of the five input categories.

    Order of checks:
    1. All single-letter tokens → letter-by-letter spelling (fast path).
    2. Single multi-character token → check against one-word commands, else spelling.
    3. Multi-word phrase → check against trigger phrase sets, else question.
    """
    # Strip non-alphabetic characters for matching but keep spaces
    clean = re.sub(r"[^a-zA-Z\s]", " ", text).strip().lower()
    tokens = clean.split()

    if not tokens:
        return "spelling"

    # ── Fast path: every token is a single letter → letter-by-letter spelling ──
    if all(len(t) == 1 for t in tokens):
        return "spelling"

    # ── Single multi-character token ────────────────────────────────────────────
    if len(tokens) == 1:
        word = tokens[0]
        if word in {"repeat", "again", "pardon"}:
            return "repeat_command"
        if word in {"skip", "pass", "next"}:
            return "skip_command"
        if word in {"quit", "stop", "end", "exit"}:
            return "quit_command"
        # Single word that isn't a command → treat as a whole-word spelling attempt
        return "spelling"

    # ── Multi-word: check trigger sets ──────────────────────────────────────────
    phrase = " ".join(tokens)

    for trigger in _REPEAT_TRIGGERS:
        if phrase == trigger or phrase.startswith(trigger + " "):
            return "repeat_command"

    for trigger in _SKIP_TRIGGERS:
        if trigger in phrase:
            return "skip_command"

    for trigger in _QUIT_TRIGGERS:
        if trigger in phrase:
            return "quit_command"

    # Multi-word, no command match → out-of-scope question or statement
    return "question"
