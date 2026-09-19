"""Callsign resolver: spoken telephony → ICAO, with UNCERTAIN when digits-only."""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

from .normalize_fn import DIGIT_WORDS, fold, spoken_number

try:
    import app_paths
except ImportError:
    app_paths = None  # type: ignore


def _data_file(name: str) -> Path | None:
    if app_paths is not None:
        path = app_paths.data_file("data", name)
        if path.is_file():
            return path
    root = Path(__file__).resolve().parents[2]
    path = root / "data" / name
    return path if path.is_file() else None


@lru_cache(maxsize=1)
def telephony_lexicon() -> dict[str, str]:
    """spoken phrase (lower) → ICAO prefix (HVN, VJC, …)."""
    lex: dict[str, str] = {
        "vietnam": "HVN",
        "viet nam": "HVN",
        "vietnam airlines": "HVN",
        "viet nam airlines": "HVN",
        "hvn": "HVN",
        "vietjet": "VJC",
        "viet jet": "VJC",
        "vietjetair": "VJC",
        "vjc": "VJC",
        "bamboo": "BAV",
        "pacific": "PIC",
        "pacific airlines": "PIC",
        "vasco": "VFC",
        "vasco air": "VFC",
        "speedbird": "BAW",
        "qantas": "QFA",
        "cathay": "CPA",
        "singapore": "SIA",
        "thai": "THA",
    }
    spoken = _data_file("vn-airline-spoken.tsv")
    if spoken:
        try:
            with spoken.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh, delimiter="\t"):
                    icao = (row.get("icao") or "").strip().upper()
                    if not icao:
                        continue
                    for key in ("spoken_en", "telephony"):
                        val = fold(row.get(key) or "")
                        if val:
                            lex[val] = icao
        except OSError:
            pass
    calls = _data_file("vn-callsigns.tsv")
    if calls:
        try:
            with calls.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh, delimiter="\t"):
                    abbr = (row.get("abbr") or "").strip().upper()
                    en = fold(row.get("en") or "")
                    if abbr.isalpha() and 2 <= len(abbr) <= 3 and en:
                        lex.setdefault(en.lower(), abbr)
                        lex.setdefault(abbr.lower(), abbr)
        except OSError:
            pass
    return lex


def resolve_callsign(text: str) -> dict:
    """Return spoken / normalized / confidence / uncertain for one utterance."""
    t = fold(text or "")
    lex = telephony_lexicon()
    for spoken, prefix in sorted(lex.items(), key=lambda x: -len(x[0])):
        if not spoken:
            continue
        m = re.search(rf"\b{re.escape(spoken)}\s+((?:[a-z0-9]+\s*){{1,6}})", t)
        if not m:
            continue
        num_tokens: list[str] = []
        for tok in m.group(1).split():
            if tok in DIGIT_WORDS or tok.isdigit():
                num_tokens.append(tok)
            else:
                break
        if not num_tokens:
            continue
        n = spoken_number(" ".join(num_tokens))
        if n is None:
            continue
        raw = f"{spoken} {' '.join(num_tokens)}"
        return {
            "spoken": raw,
            "normalized": f"{prefix}{n}",
            "confidence": 0.94,
            "uncertain": False,
        }
    m = re.search(r"\b([a-z]{3})\s*(\d{2,5})\b", t)
    if m:
        return {
            "spoken": m.group(0),
            "normalized": f"{m.group(1).upper()}{int(m.group(2))}",
            "confidence": 0.88,
            "uncertain": False,
        }
    # Digits only — do not invent an airline.
    tokens = t.split()
    num_tokens = [tok for tok in tokens if tok in DIGIT_WORDS or tok.isdigit()]
    if 2 <= len(num_tokens) <= 5:
        n = spoken_number(" ".join(num_tokens))
        if n is not None and 10 <= n <= 99999:
            return {
                "spoken": " ".join(num_tokens),
                "normalized": None,
                "confidence": 0.45,
                "uncertain": True,
            }
    return {
        "spoken": None,
        "normalized": None,
        "confidence": 0.0,
        "uncertain": False,
    }
