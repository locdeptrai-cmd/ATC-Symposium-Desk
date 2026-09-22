"""Unit-aware ATC hotwords. Telephony + station, not the full library dump."""

from __future__ import annotations

import csv
import json
import os
import re
from functools import lru_cache
from pathlib import Path

try:
    import app_paths
except ImportError:
    app_paths = None  # type: ignore
from asr_dataset.paths import gold_root
from asr_dataset.vocabulary import excel_phrases

CORE_PHRASEOLOGY = (
    "cleared to land",
    "continue approach",
    "line up and wait",
    "hold short",
    "squawk",
    "QNH",
    "flight level",
)

_VN_ICAO = {"HVN", "VJC", "BAV", "PIC", "VAG", "VFC", "SPQ", "VSM", "SAV", "HAI", "TVJ"}

_UNIT_KEYS = (
    ("sgn", ("sgn", "vvts", "saigon", "tan son nhat", "118.7", "118.70")),
    ("han", ("han", "vvnb", "noi bai", "hanoi", "ha noi", "120.1")),
    ("dad", ("dad", "vvdn", "danang", "da nang")),
    ("cxr", ("cxr", "vvcr", "cam ranh")),
    ("pqc", ("pqc", "vvpq", "phu quoc")),
)


def _spoken_tsv() -> Path | None:
    if app_paths is not None:
        path = app_paths.data_file("data", "vn-airline-spoken.tsv")
        if path.is_file():
            return path
    root = Path(__file__).resolve().parents[2]
    path = root / "data" / "vn-airline-spoken.tsv"
    return path if path.is_file() else None


def _seeded_glossary_path() -> Path:
    return gold_root() / "glossary_phrases.json"


def _seeded_glossary_phrases() -> list[str]:
    path = _seeded_glossary_path()
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("phrases") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in rows:
        phrase = str(raw or "").strip()
        key = phrase.lower()
        if not phrase or key in seen:
            continue
        seen.add(key)
        out.append(phrase)
    return out[:1200]


@lru_cache(maxsize=1)
def _rows() -> tuple[dict[str, str], ...]:
    path = _spoken_tsv()
    if path is None:
        return ()
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            return tuple(dict(row) for row in csv.DictReader(fh, delimiter="\t"))
    except OSError:
        return ()


def infer_unit(filename: str = "", unit: str | None = None) -> str | None:
    if unit and str(unit).strip():
        return str(unit).strip().lower()
    env = (os.environ.get("ATC_UNIT") or "").strip()
    if env:
        return env.lower()
    blob = fold_name(filename)
    for key, needles in _UNIT_KEYS:
        if any(n in blob for n in needles):
            return key
    return None


def fold_name(text: str) -> str:
    t = (text or "").lower().replace("\\", "/")
    t = re.sub(r"[^a-z0-9.]+", " ", t)
    return f" {t} "


def _station_matches(row: dict[str, str], unit: str | None) -> bool:
    if (row.get("kind") or "").strip() != "station":
        return False
    if not unit:
        return True
    blob = " ".join(
        [
            row.get("spoken_en") or "",
            row.get("telephony") or "",
            row.get("note") or "",
            row.get("source") or "",
            row.get("aliases") or "",
        ]
    ).lower()
    for key, needles in _UNIT_KEYS:
        if key == unit and any(n in blob for n in needles):
            return True
    return unit in blob


def hotwords_for(filename: str = "", unit: str | None = None) -> str:
    resolved = infer_unit(filename, unit)
    bits: list[str] = list(CORE_PHRASEOLOGY)
    seen = {b.lower() for b in bits}
    for phrase in excel_phrases(filename):
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            bits.append(phrase)
    for row in _rows():
        kind = (row.get("kind") or "").strip()
        icao = (row.get("icao") or "").strip().upper()
        spoken = (row.get("spoken_en") or "").strip()
        if not spoken:
            continue
        if kind == "airline":
            country = (row.get("country") or "").lower()
            vn = "việt nam" in country or "viet nam" in country or icao in _VN_ICAO
            if not vn:
                continue
        elif kind == "station":
            if not _station_matches(row, resolved):
                continue
        else:
            continue
        key = spoken.lower()
        if key not in seen:
            seen.add(key)
            bits.append(spoken)
    if "vietjet" not in seen:
        bits[0:0] = ["Vietjet", "Viet Nam"]
    # Whisper's prompt has a small token budget. A full library dump silently
    # loses the tail and wastes decoding time. Prioritize human Excel hints.
    bits.extend(_seeded_glossary_phrases())
    selected, used = [], set()
    words_left = 75
    for phrase in bits:
        key = phrase.lower()
        size = len(phrase.split())
        if key in used or size > words_left:
            continue
        selected.append(phrase)
        used.add(key)
        words_left -= size
        if not words_left:
            break
    return ", ".join(selected)
