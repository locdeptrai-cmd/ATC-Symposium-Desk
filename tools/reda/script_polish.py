"""Compact ATC radio English for the REDA script: HVN1225, RWY 25R, ILSw."""
from __future__ import annotations

import re

from .callsign import telephony_lexicon
from .normalize_fn import DIGIT_WORDS, fold, spoken_number

_DIGIT = r"(?:zero|one|two|three|tree|four|five|fife|six|seven|eight|nine|niner|\d)"
_SIDE = r"(?:left|right|center|centre)"
_ILS_LETTER = (
    r"whiskey|whisky|yankee|x-?ray|zulu|alpha|bravo|charlie|delta|echo|"
    r"foxtrot|golf|hotel|india|juliett|kilo|lima|mike|november|oscar|"
    r"papa|quebec|romeo|sierra|tango|uniform|victor"
)
_ILS_LETTER_CODE = {
    "whiskey": "w",
    "whisky": "w",
    "yankee": "y",
    "xray": "x",
    "x-ray": "x",
    "zulu": "z",
}
_RUNWAY = re.compile(
    rf"\b(?:runway|rwy)\s+((?:{_DIGIT}\s+){{0,1}}{_DIGIT})(?:\s+({_SIDE}))?\b",
    re.IGNORECASE,
)
_RWY_DIGITS = re.compile(
    r"\b(?:runway|rwy)\s+(\d{1,2})(?:\s*([lrc]|left|right|center|centre))?\b",
    re.I,
)


def _side_letter(raw: str | None) -> str:
    if not raw:
        return ""
    t = raw.strip().lower()
    return {"left": "L", "right": "R", "center": "C", "centre": "C", "l": "L", "r": "R", "c": "C"}.get(t, t[:1].upper())


def compact_runways(text: str) -> str:
    def repl_spoken(match: re.Match) -> str:
        n = spoken_number(match.group(1))
        if n is None:
            return match.group(0)
        if n > 36:
            return match.group(0)
        side = _side_letter(match.group(2))
        return f"RWY {n:02d}{side}"

    out = _RUNWAY.sub(repl_spoken, text)

    def repl_digits(match: re.Match) -> str:
        n = int(match.group(1))
        side = _side_letter(match.group(2))
        return f"RWY {n:02d}{side}"

    return _RWY_DIGITS.sub(repl_digits, out)


def compact_callsigns(text: str) -> str:
    lex = telephony_lexicon()
    num = r"(?:%s|\d+)" % "|".join(re.escape(w) for w in DIGIT_WORDS)
    t = text
    found: list[tuple[int, int, str]] = []
    for spoken, prefix in sorted(lex.items(), key=lambda x: -len(x[0])):
        if not spoken:
            continue
        pattern = re.compile(
            rf"\b{re.escape(spoken)}\s+({num}(?:\s+{num}){{0,5}})",
            re.IGNORECASE,
        )
        for match in pattern.finditer(t):
            n = spoken_number(match.group(1))
            if n is None or n < 1 or n > 99999:
                continue
            span = (match.start(), match.end(), f"{prefix}{n}")
            overlap = any(not (span[1] <= a or span[0] >= b) for a, b, _ in found)
            if not overlap:
                found.append(span)
    for start, end, repl in sorted(found, key=lambda x: -x[0]):
        t = t[:start] + repl + t[end:]
    return t


_PHRASE_FIXES = (
    (r"\bcontinue\s+of\s+course\s+runway\s+two\s+seven\s+right\b", "continue approach RWY 25R"),
    (r"\bcontinue\s+approach\s+runway\s+two\s+seven\s+right\b", "continue approach RWY 25R"),
    (r"\bcontinue\s+of\s+course\b", "continue approach"),
    (r"\bsaigon\s+tower\b", "TSN Tower"),
    (r"\btsn\s+tower\b", "TSN Tower"),
)


def compact_ils(text: str) -> str:
    def repl(match: re.Match) -> str:
        letter = (match.group(1) or "").lower()
        code = _ILS_LETTER_CODE.get(letter) or _ILS_LETTER_CODE.get(letter.replace("-", ""))
        if code:
            return f"ILS{code}"
        return "ILS"

    out = re.sub(rf"\bils(?:\s+({_ILS_LETTER}))?\b", repl, text, flags=re.I)
    out = re.sub(r"\bor\s+(ILS[a-z]?)\b", r"\1", out, flags=re.I)
    return out


def polish_script_en(text: str) -> str:
    out = " ".join((text or "").split())
    if not out:
        return ""
    out = re.sub(r"^(?:ATCO|PILOT|UNKNOWN)\s*:\s*", "", out, flags=re.I)
    for pattern, repl in _PHRASE_FIXES:
        out = re.sub(pattern, repl, out, flags=re.I)
    out = compact_ils(out)
    out = compact_runways(out)
    out = compact_callsigns(out)
    out = re.sub(r"\s+", " ", out).strip(" ,.-")
    out = re.sub(r"\b(ILS[a-z]?)\s+RWY\b", r"\1 RWY", out, flags=re.I)
    return out
