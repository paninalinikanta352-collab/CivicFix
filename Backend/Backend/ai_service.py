"""Single CivicFix risk engine (merged from Member-3's tested heuristic).

Explainable 0-100 priority score, not a calibrated probability:
- baseline score from the API category (roads/water/electricity/cleanliness = 40, other = 10)
- +10 lifted to the high band when a high-risk keyword appears in the description
- +5 lifted to the medium band for a medium-risk keyword
- +10 when the address/landmark sits near a sensitive location (school, hospital, market, ...)
Matching is case-insensitive, whitespace-normalized, and word-boundary aware
("fireworks" is not "fire"). Keep tests/test_risk.py in sync with every change.
"""

from __future__ import annotations

import re

HIGH_RISK_SCORE = 70
MEDIUM_RISK_SCORE = 40
UNKNOWN_CATEGORY_SCORE = 10

# models.Category values -> baseline priority.
_CATEGORY_BASELINE = {
    "roads": MEDIUM_RISK_SCORE,
    "water": MEDIUM_RISK_SCORE,
    "electricity": MEDIUM_RISK_SCORE,
    "cleanliness": MEDIUM_RISK_SCORE,
    "other": UNKNOWN_CATEGORY_SCORE,
}

HIGH_RISK_KEYWORDS = (
    "fire",
    "accident",
    "flood",
    "gas leak",
    "collapse",
    "electrocution",
    "electric shock",
    "injury",
    "death",
    "explosion",
)
MEDIUM_RISK_KEYWORDS = (
    "water logging",
    "waterlogging",
    "pothole",
    "garbage",
    "drainage",
    "broken streetlight",
    "sewage",
    "road damage",
    "leak",
    "blocked",
    "dangerous",
    "dark",
)
SENSITIVE_LOCATION_TERMS = (
    "school",
    "hospital",
    "market",
    "highway",
    "railway station",
    "bus stop",
)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _contains_phrase(text: str, phrase: str) -> bool:
    """Match a phrase on word boundaries, allowing flexible inner spacing."""
    words = phrase.split()
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(word) for word in words) + r"(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def calculate_risk_percentage(category: str, description: str, location: str = "") -> int:
    """Return a 0-100 heuristic priority score for a civic report.

    category: one of roads / water / electricity / cleanliness / other
    location: free-text address or landmark; optional (defaults to "")
    Raises TypeError for non-strings and ValueError for empty
    category/description. Location may be empty.
    """
    values = (category, description, location)
    if any(not isinstance(value, str) for value in values):
        raise TypeError("category, description, and location must be strings")
    if not category.strip() or not description.strip():
        raise ValueError("category and description must not be empty")

    category_text, description_text, location_text = map(_normalize, values)
    score = _CATEGORY_BASELINE.get(category_text, UNKNOWN_CATEGORY_SCORE)

    if any(_contains_phrase(description_text, term) for term in HIGH_RISK_KEYWORDS):
        score = max(score, HIGH_RISK_SCORE) + 10
    elif any(_contains_phrase(description_text, term) for term in MEDIUM_RISK_KEYWORDS):
        score = max(score, MEDIUM_RISK_SCORE) + 5

    if any(_contains_phrase(location_text, term) for term in SENSITIVE_LOCATION_TERMS):
        score += 10

    return max(0, min(100, score))
