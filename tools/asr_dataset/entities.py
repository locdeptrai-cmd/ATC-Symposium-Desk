"""Extract ATC entities from spoken English for eval and gold labels."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[1]
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from reda.normalize_fn import (
    extract_callsign_from_utterance,
    fold,
    normalize_freq,
    normalize_heading,
    normalize_level,
    normalize_qnh,
    normalize_runway,
    normalize_squawk,
    words_to_digits,
)

_STOP = {
    "turn",
    "heading",
    "head",
    "squawk",
    "qnh",
    "qfe",
    "altimeter",
    "runway",
    "contact",
    "climb",
    "descend",
    "maintain",
    "cleared",
    "via",
    "direct",
    "speed",
    "mach",
}


def _window(text: str, cue: str, extra_stop: set[str] | None = None) -> str:
    t = fold(text or "")
    idx = t.find(cue)
    if idx < 0:
        return ""
    rest = t[idx + len(cue) :].strip().split()
    stop = _STOP | (extra_stop or set())
    cue_tok = cue.strip()
    if cue_tok in stop:
        stop.remove(cue_tok)
    out: list[str] = []
    for tok in rest:
        if tok in stop and out:
            break
        if tok in stop and not out:
            continue
        out.append(tok)
        if len(out) >= 8:
            break
    return f"{cue} {' '.join(out)}".strip()


def extract_entities(text: str) -> dict[str, str | int | None]:
    raw = fold(text or "")
    spoken, callsign = extract_callsign_from_utterance(text or "")
    level, level_unit = (None, None)
    if "flight level" in raw or re.search(r"(?:^|\s)fl(?:\s|$)", raw):
        cue = "flight level" if "flight level" in raw else "fl"
        level, level_unit = normalize_level(_window(text, cue))
    heading = None
    if "heading" in raw or re.search(r"\bhead\b", raw):
        cue = "heading" if "heading" in raw else "head"
        heading = normalize_heading(_window(text, cue, {"left", "right"}))
    squawk = normalize_squawk(_window(text, "squawk")) if "squawk" in raw else None
    qnh, qnh_unit = (None, None)
    if re.search(r"\b(?:qnh|qfe|altimeter)\b", raw):
        cue = "qnh" if "qnh" in raw else ("qfe" if "qfe" in raw else "altimeter")
        qnh, qnh_unit = normalize_qnh(_window(text, cue))
    freq = None
    if re.search(r"\b(?:contact|frequency|decimal)\b", raw):
        freq = normalize_freq(_window(text, "contact") or _window(text, "frequency") or text)
    runway = None
    if "runway" in raw:
        chunk = words_to_digits(_window(text, "runway"))
        runway = normalize_runway(chunk) or normalize_runway(words_to_digits(raw))
    return {
        "callsign_spoken": spoken,
        "callsign": callsign,
        "level": level,
        "level_unit": level_unit,
        "heading": heading,
        "squawk": squawk,
        "qnh": qnh,
        "qnh_unit": qnh_unit,
        "freq": freq,
        "runway": runway,
    }


def entity_fields() -> tuple[str, ...]:
    return ("callsign", "level", "heading", "runway", "squawk", "qnh", "freq")
