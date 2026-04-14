# Compatibility shim — all logic has been extracted into dedicated modules.
# Import from the new modules directly for new code.
from constants import GamePhase  # noqa: F401
from game_processor import SpellingGameProcessor, normalize_spelling  # noqa: F401
from pipeline import run_bot  # noqa: F401
