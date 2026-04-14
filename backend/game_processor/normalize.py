import re


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
