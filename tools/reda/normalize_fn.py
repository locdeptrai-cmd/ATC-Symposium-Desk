"""ICAO numeric / callsign normalization and compare functions."""

from __future__ import annotations

import re

DIGIT_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "tree": "3",
    "four": "4",
    "five": "5",
    "fife": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "niner": "9",
}

NUMBER_WORDS = {
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
}

FILLERS = {
    "roger": "ACK_ONLY",
    "wilco": "ACK_ONLY",
}

CALLSIGN_PREFIX = {
    "vietnam": "HVN",
    "viet nam": "HVN",
    "viet-nam": "HVN",
    "hvn": "HVN",
    "vietnam airlines": "HVN",
    "bamboo": "BAV",
    "vietjet": "VJC",
    "vietjetair": "VJC",
    "pacific airlines": "PIC",
    "vasco": "VFC",
    "speedbird": "BAW",
    "qantas": "QFA",
    "cathay": "CPA",
    "singapore": "SIA",
}


def fold(text: str) -> str:
    t = text.lower()
    t = t.replace("-", " ")
    t = re.sub(r"(?<=[a-z])\.+", " ", t)
    t = re.sub(r"[^\w.\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def words_to_digits(text: str) -> str:
    tokens = fold(text).split()
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in DIGIT_WORDS:
            run = [DIGIT_WORDS[tok]]
            i += 1
            while i < len(tokens) and tokens[i] in DIGIT_WORDS:
                run.append(DIGIT_WORDS[tokens[i]])
                i += 1
            out.append("".join(run))
            continue
        out.append(tok)
        i += 1
    return " ".join(out)


def spoken_number(text: str) -> int | None:
    """Parse mixed ICAO digit-words / number-words into an integer."""
    tokens = re.sub(r"\band\b", " ", fold(text)).split()
    if not tokens:
        return None
    digits_only = []
    all_digit_words = True
    for tok in tokens:
        if tok in DIGIT_WORDS:
            digits_only.append(DIGIT_WORDS[tok])
        elif tok.isdigit():
            digits_only.append(tok)
        else:
            all_digit_words = False
            break
    if all_digit_words and digits_only:
        return int("".join(digits_only))

    total = 0
    current = 0
    used = False
    for tok in tokens:
        if tok in DIGIT_WORDS:
            current += int(DIGIT_WORDS[tok])
            used = True
        elif tok.isdigit():
            current += int(tok)
            used = True
        elif tok in NUMBER_WORDS:
            val = NUMBER_WORDS[tok]
            if val == 100:
                current = (current or 1) * 100
            elif val == 1000:
                total += (current or 1) * 1000
                current = 0
            else:
                current += val
            used = True
        elif tok in {"feet", "foot", "metres", "meters", "knots", "mach"}:
            continue
        else:
            continue
    if not used:
        return None
    return total + current


def normalize_level(text: str) -> tuple[str | None, str | None]:
    t = fold(text)
    t = t.replace("flightlevel", "flight level")
    has_feet = re.search(r"\b(?:feet|foot|ft)\b", t)
    has_metres = re.search(r"\b(?:metres|meters|metre|meter)\b", t)
    has_fl = "flight level" in t or re.search(r"(?:^|\s)fl(?:\s|$)", t)
    if has_fl and not has_feet:
        rest = re.sub(r".*?(?:flight\s+level|(?:^|\s)fl)\s*", "", t, count=1)
        n = spoken_number(rest)
        if n is None and re.search(r"\d", rest):
            n = int(re.sub(r"\D", "", rest) or 0) or None
        if n is not None:
            return f"FL{n:03d}" if n < 1000 else f"FL{n}", "FL"
    if has_feet:
        chunk = re.sub(r"\b(?:feet|foot|ft)\b.*", "", t).strip()
        n = spoken_number(chunk)
        if n is not None:
            return f"{n}FT", "FT"
    if has_metres:
        chunk = re.sub(r"\b(?:metres|meters|metre|meter)\b.*", "", t).strip()
        n = spoken_number(chunk)
        if n is not None:
            return f"{n}M", "M"
    return None, None


def normalize_heading(text: str) -> int | None:
    t = fold(text)
    m = re.search(
        r"(?:heading|head)\s+(.+?)(?:\s+degrees?)?$",
        t,
    )
    chunk = m.group(1) if m else t
    n = spoken_number(chunk)
    if n is None:
        digits = re.sub(r"\D", "", words_to_digits(chunk))
        if digits:
            n = int(digits)
    if n is None:
        return None
    n = n % 360 if n != 360 else 360
    if n == 0:
        n = 360
    return n


def normalize_squawk(text: str) -> str | None:
    t = fold(text)
    t = re.sub(r".*\bsquawk\s+", "", t)
    digits = re.sub(r"\D", "", words_to_digits(t))
    if len(digits) >= 4:
        return digits[:4]
    n = spoken_number(t)
    if n is None:
        return None
    return f"{n:04d}"[-4:]


def normalize_freq(text: str) -> str | None:
    t = fold(text)
    t = t.replace("decimal", ".")
    t = words_to_digits(t)
    m = re.search(r"(\d{3})\s*[.]\s*(\d{1,3})", t)
    if m:
        whole, frac = m.group(1), m.group(2).ljust(3, "0")[:3]
        return f"{whole}.{frac}"
    m = re.search(r"(\d{3})\s+(\d{1,3})", t)
    if m:
        return f"{m.group(1)}.{m.group(2).ljust(3, '0')[:3]}"
    m = re.search(r"(1[1-3]\d\.\d{1,3})", t)
    if m:
        whole, frac = m.group(1).split(".")
        return f"{whole}.{frac.ljust(3, '0')[:3]}"
    return None


def normalize_qnh(text: str) -> tuple[int | None, str | None]:
    t = fold(text)
    t = re.sub(r".*\b(?:qnh|qfe|altimeter)\s+", "", t)
    n = spoken_number(t)
    if n is None:
        digits = re.sub(r"\D", "", words_to_digits(t))
        if digits:
            n = int(digits)
    if n is None:
        return None, None
    unit = "INHG" if n < 50 else "HPA"
    return n, unit


def normalize_runway(text: str) -> str | None:
    t = fold(text)
    m = re.search(r"runway\s+(\d{1,2})\s*([lrc])?", t)
    if m:
        num = int(m.group(1))
        side = (m.group(2) or "").upper()
        return f"{num:02d}{side}"
    m = re.search(r"\b(\d{2})\s*(left|right|center|centre|[lrc])\b", t)
    if m:
        side_map = {"left": "L", "right": "R", "center": "C", "centre": "C"}
        side = side_map.get(m.group(2), m.group(2).upper())
        return f"{int(m.group(1)):02d}{side}"
    return None


def normalize_callsign(text: str, lexicon: dict[str, str] | None = None) -> str | None:
    t = fold(text)
    prefixes = {**CALLSIGN_PREFIX, **(lexicon or {})}
    for spoken, prefix in sorted(prefixes.items(), key=lambda x: -len(x[0])):
        if t.startswith(spoken) or f" {spoken} " in f" {t} ":
            rest = t.replace(spoken, " ", 1)
            n = spoken_number(rest)
            if n is None:
                digits = re.sub(r"\D", "", words_to_digits(rest))
                if digits:
                    n = int(digits)
            if n is not None:
                return f"{prefix}{n}"
    m = re.search(r"\b([a-z]{2,3})\s*(\d{1,5})\b", t)
    if m:
        return f"{m.group(1).upper()}{int(m.group(2))}"
    return None


def extract_callsign_from_utterance(text: str, lexicon: dict[str, str] | None = None) -> tuple[str | None, str | None]:
    t = fold(text)
    prefixes = {**CALLSIGN_PREFIX, **(lexicon or {})}
    for spoken, prefix in sorted(prefixes.items(), key=lambda x: -len(x[0])):
        m = re.search(rf"\b{re.escape(spoken)}\s+((?:[a-z0-9]+\s*){{1,6}})", t)
        if not m:
            continue
        tokens = m.group(1).split()
        num_tokens: list[str] = []
        for tok in tokens:
            if tok in DIGIT_WORDS or tok.isdigit():
                num_tokens.append(tok)
            else:
                break
        if not num_tokens:
            continue
        n = spoken_number(" ".join(num_tokens))
        if n is not None:
            raw = f"{spoken} {' '.join(num_tokens)}"
            return raw, f"{prefix}{n}"
    m = re.search(r"\b([a-z]{2,3})\s*(\d{2,5})\b", t)
    if m:
        raw = m.group(0)
        return raw, f"{m.group(1).upper()}{int(m.group(2))}"
    return None, None


def is_ack_only(text: str) -> bool:
    t = fold(text)
    t = re.sub(r"\b(viet nam|vietnam|hvn|[a-z]{2,3}\s*\d+)\b", " ", t)
    t = re.sub(r"\d+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    tokens = [tok for tok in t.split() if tok not in {"and", "the"}]
    if not tokens:
        return False
    return all(tok in {"roger", "wilco", "copied", "copy", "ok", "okay", "affirm"} for tok in tokens)


def compare_numeric(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False
    ua = re.sub(r"[^A-Z]", "", a.upper()) or None
    ub = re.sub(r"[^A-Z]", "", b.upper()) or None
    na = re.sub(r"\D", "", a)
    nb = re.sub(r"\D", "", b)
    if not na or not nb:
        return False
    if ua and ub and ua != ub:
        return False
    return int(na) == int(nb)


def compare_heading(a: int | str | None, b: int | str | None) -> bool:
    if a is None or b is None:
        return False

    def as_deg(v: int | str) -> int:
        if isinstance(v, int):
            n = v
        else:
            n = int(re.sub(r"\D", "", str(v)) or 0)
        n = n % 360
        return 360 if n == 0 else n

    return as_deg(a) == as_deg(b)


def compare_freq(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False

    def canon(v: str) -> str:
        v = v.replace("decimal", ".")
        m = re.search(r"(\d{3})\.(\d{1,3})", v)
        if not m:
            digits = re.sub(r"\D", "", v)
            if len(digits) >= 4:
                return f"{digits[:3]}.{digits[3:].ljust(3, '0')[:3]}"
            return digits
        return f"{m.group(1)}.{m.group(2).ljust(3, '0')[:3]}"

    return canon(a) == canon(b)


def compare_exact_norm(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return False
    return re.sub(r"\s+", "", str(a).upper()) == re.sub(r"\s+", "", str(b).upper())


def compare_callsign(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return a.upper() == b.upper()


COMPARE_FNS = {
    "numeric": compare_numeric,
    "heading_deg": compare_heading,
    "freq_mhz": compare_freq,
    "exact_norm": compare_exact_norm,
    "callsign_fuzzy": compare_callsign,
    "ack_only": lambda _a, _b: False,
}
