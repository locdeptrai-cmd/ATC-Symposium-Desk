"""WER/CER and ATC entity accuracy. Taxonomy of HUMAN vs ASR diffs."""

from __future__ import annotations

import re
from collections import Counter

from asr_dataset.entities import entity_fields, extract_entities
from reda.normalize_fn import fold

_WORD = re.compile(r"[a-z0-9']+")
_TELEPHONY = re.compile(
    r"\b(?:vietjet|viet nam|vietnam|bamboo|pacific|vasco|charlie jet|sion)\b",
    re.I,
)
_STATION = re.compile(
    r"\b(?:saigon|sai gon|sona|noi bai|noy bai|tan son nhat|danang|cam ranh)\b",
    re.I,
)
_ICAO_NUM = re.compile(r"\b(?:niner|tree|fife|wun|decimal|fellay)\b", re.I)
_PHRASE = re.compile(
    r"\b(?:cleared to land|line up|hold short|continue approach|squawk|qnh)\b",
    re.I,
)


def tokenize(text: str) -> list[str]:
    return _WORD.findall(fold(text or ""))


def chars(text: str) -> list[str]:
    return list(re.sub(r"\s+", "", fold(text or "")))


def levenshtein(ref: list[str], hyp: list[str]) -> int:
    if not ref:
        return len(hyp)
    if not hyp:
        return len(ref)
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i]
        for j, h in enumerate(hyp, start=1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if r == h else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def wer(ref: str, hyp: str) -> float:
    r, h = tokenize(ref), tokenize(hyp)
    if not r:
        return 0.0 if not h else 1.0
    return levenshtein(r, h) / len(r)


def cer(ref: str, hyp: str) -> float:
    r, h = chars(ref), chars(hyp)
    if not r:
        return 0.0 if not h else 1.0
    return levenshtein(r, h) / len(r)


def classify_error(before: str, after: str) -> str:
    b, a = before or "", after or ""
    if not a.strip():
        return "other"
    if len(tokenize(b)) >= 8 and len(set(tokenize(b))) <= 3:
        return "hallucination"
    if _STATION.search(a) and not _STATION.search(b):
        return "station"
    if _TELEPHONY.search(a) and (not _TELEPHONY.search(b) or fold(a) != fold(b)):
        if extract_entities(a).get("callsign") != extract_entities(b).get("callsign"):
            return "callsign"
        return "telephony_vn"
    if _ICAO_NUM.search(b) or _ICAO_NUM.search(a):
        return "icao_number"
    if re.search(r"\brunway\b", a, re.I) or re.search(r"\brunway\b", b, re.I):
        return "runway"
    if extract_entities(a).get("callsign") != extract_entities(b).get("callsign"):
        return "callsign"
    if _PHRASE.search(a) and not _PHRASE.search(b):
        return "phraseology"
    if wer(a, b) >= 0.8 and len(tokenize(b)) > len(tokenize(a)) + 4:
        return "hallucination"
    return "other"


def entity_match(ref_text: str, hyp_text: str) -> dict[str, bool | None]:
    ref_e = extract_entities(ref_text)
    hyp_e = extract_entities(hyp_text)
    out: dict[str, bool | None] = {}
    for field in entity_fields():
        rv, hv = ref_e.get(field), hyp_e.get(field)
        if rv is None and hv is None:
            out[field] = None
        else:
            out[field] = str(rv or "").upper() == str(hv or "").upper()
    return out


def summarize_pairs(pairs: list[tuple[str, str]]) -> dict:
    """pairs: (hyp_asr, ref_human)."""
    n = len(pairs)
    wer_sum = 0.0
    cer_sum = 0.0
    hits: dict[str, list[int]] = {f: [0, 0] for f in entity_fields()}
    tax = Counter()
    examples: dict[str, list[dict]] = {}
    for hyp, ref in pairs:
        wer_sum += wer(ref, hyp)
        cer_sum += cer(ref, hyp)
        kind = classify_error(hyp, ref)
        tax[kind] += 1
        if len(examples.get(kind) or []) < 8 and fold(hyp) != fold(ref):
            examples.setdefault(kind, []).append({"hyp": hyp, "ref": ref})
        for field, ok in entity_match(ref, hyp).items():
            if ok is None:
                continue
            hits[field][1] += 1
            if ok:
                hits[field][0] += 1
    entity_acc = {}
    for field, (ok, total) in hits.items():
        entity_acc[field] = None if total == 0 else round(ok / total, 4)
    return {
        "n": n,
        "wer": None if n == 0 else round(wer_sum / n, 4),
        "cer": None if n == 0 else round(cer_sum / n, 4),
        "entity_accuracy": entity_acc,
        "taxonomy": dict(tax),
        "examples": examples,
    }
