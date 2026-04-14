"""game_processor package — re-exports for backward compatibility.

Usage (unchanged from when this was a single file):
    from game_processor import SpellingGameProcessor
    from game_processor import normalize_spelling
"""
from game_processor.normalize import normalize_spelling
from game_processor.processor import SpellingGameProcessor

__all__ = [
    "SpellingGameProcessor",
    "normalize_spelling",
]
