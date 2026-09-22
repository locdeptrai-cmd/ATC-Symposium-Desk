"""Read human Excel vocabulary directly from the persisted gold corpus.

No model training or transcript substitution: these are decoder hints only.
Content revisions let clients distinguish complete ASR from stale partial text.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from asr_dataset.paths import gold_root, manifest_path


def _stamp(path: Path) -> tuple[str, int, int]:
    try:
        stat = path.stat()
        return str(path), stat.st_mtime_ns, stat.st_size
    except OSError:
        return str(path), 0, 0


@lru_cache(maxsize=16)
def _read(stamp: tuple[str, int, int]) -> str:
    try:
        return Path(stamp[0]).read_text(encoding="utf-8")
    except OSError:
        return ""


def excel_phrases(filename: str = "") -> list[str]:
    records = []
    for line in _read(_stamp(manifest_path())).splitlines():
        try:
            row = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(row, dict) and row.get("source", "HUMAN") == "HUMAN":
            records.append(row)
    key = re.sub(r"[^a-z0-9]", "", Path(filename).stem.lower())
    # Prefer the same recording, then recent human vocabulary from other files.
    records.reverse()
    records.sort(key=lambda r: not (key and key in re.sub(r"[^a-z0-9]", "", str(r.get("filename", "")).lower())))
    phrases, seen = [], set()
    for row in records:
        # Keep short phrase groups; never feed the entire reference transcript.
        for clause in re.split(r"[,.;:!?\n]+", str(row.get("text") or "")):
            words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", clause)
            for i in range(0, len(words), 4):
                phrase = " ".join(words[i:i + 4])
                if phrase and phrase.lower() not in seen:
                    seen.add(phrase.lower())
                    phrases.append(phrase)
    return phrases


def vocabulary_revision() -> str:
    phrases = set(p.lower() for p in excel_phrases())
    for name in ("glossary_phrases.json", "learned_repairs.json"):
        raw = _read(_stamp(gold_root() / name))
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        if name.startswith("glossary"):
            phrases.update(str(p).lower() for p in (data.get("phrases", []) if isinstance(data, dict) else data))
        else:
            for rule in data.get("rules", []):
                phrases.add(str(rule.get("src", "")).lower() + "=>" + str(rule.get("dst", "")).lower())
    return hashlib.sha256("\n".join(sorted(phrases)).encode()).hexdigest()[:20]
