from __future__ import annotations

import re

from .normalize_fn import fold, words_to_digits

LEX_REPLACEMENTS = [
    ("niner", "nine"),
    ("tree", "three"),
    ("fife", "five"),
    ("decimal", "decimal"),
]


def normalize_text(text: str, extra: list[tuple[str, str]] | None = None) -> str:
    t = fold(text)
    for src, dst in LEX_REPLACEMENTS + (extra or []):
        t = re.sub(rf"\b{re.escape(src)}\b", dst, t)
    t = t.replace("flightlevel", "flight level")
    t = t.replace("take off", "take-off")
    t = t.replace("takeoff", "take-off")
    t = re.sub(r"\s+", " ", t).strip()
    return t
