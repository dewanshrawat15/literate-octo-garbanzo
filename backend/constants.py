from enum import Enum
from typing import Final


class GamePhase(str, Enum):
    WAITING_FOR_SPELLING = "waiting_for_spelling"
    BETWEEN_WORDS = "between_words"
    GAME_OVER = "game_over"


class SpellingSpeed(str, Enum):
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"


# Maps each SpellingSpeed to the VAD stop_secs value used when the pipeline boots.
# SileroVADAnalyzer is constructor-only; the value is picked per game session based
# on the authenticated user's stored preference.
VAD_STOP_SECS: dict[SpellingSpeed, float] = {
    SpellingSpeed.SLOW: 2.5,    # ~2.5s silence required — deliberate spellers
    SpellingSpeed.NORMAL: 1.8,  # default — handles most letter-by-letter spelling
    SpellingSpeed.FAST: 1.0,    # quick, confident spellers
}

DEFAULT_SPEED: Final[SpellingSpeed] = SpellingSpeed.NORMAL
