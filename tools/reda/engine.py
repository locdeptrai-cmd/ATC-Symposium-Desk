from __future__ import annotations

import re
import uuid
from typing import Any

from .compare import compare
from .concept import AtcConcept, IssueType, SpeakerRole
from .lexicon import RULES, TEACHING, TEMPLATES
from .normalize import normalize_text
from .pairing import pair_concepts
from .parse import infer_role, parse_utterance

WINDOW_SEC = 25.0
PILOT_SPLIT = re.compile(
    r"(?=\b(?:climbing|descending|roger|wilco|holding short|going around)\b)",
    re.IGNORECASE,
)


def _fmt_clock(sec: float) -> str:
    s = max(0, int(sec))
    return f"{s // 60:02d}:{s % 60:02d}"


def _as_turn(item: dict, index: int) -> dict:
    text = str(item.get("text") or item.get("asr_text") or "").strip()
    start = float(item.get("t_start") if item.get("t_start") is not None else index * 2.0)
    end = float(item.get("t_end") if item.get("t_end") is not None else start + 1.8)
    role = item.get("speaker_role") or item.get("speaker") or None
    return {"text": text, "t_start": start, "t_end": max(end, start + 0.2), "speaker_role": role}


def split_mixed_turns(turns: list[dict]) -> list[dict]:
    out: list[dict] = []
    for turn in turns:
        text = turn["text"]
        if not text:
            continue
        parts = [p.strip(" ,.;") for p in PILOT_SPLIT.split(text) if p and p.strip(" ,.;")]
        if len(parts) <= 1:
            out.append(turn)
            continue
        span = max(turn["t_end"] - turn["t_start"], 0.6)
        step = span / len(parts)
        for i, part in enumerate(parts):
            chunk = dict(turn)
            chunk["text"] = part
            chunk["t_start"] = turn["t_start"] + i * step
            chunk["t_end"] = turn["t_start"] + (i + 1) * step
            chunk["speaker_role"] = None
            out.append(chunk)
    return out


def turns_from_text(text: str) -> list[dict]:
    raw = (text or "").strip()
    if not raw:
        return []
    chunks = [c.strip() for c in re.split(r"(?<=[.!?])\s+|\n+", raw) if c.strip()]
    if len(chunks) < 2:
        return split_mixed_turns([{"text": raw, "t_start": 0.0, "t_end": 8.0, "speaker_role": None}])
    out = []
    t = 0.0
    for chunk in chunks:
        dur = max(1.6, min(6.0, 0.35 * len(chunk.split())))
        out.append({"text": chunk, "t_start": t, "t_end": t + dur, "speaker_role": None})
        t += dur + 0.4
    return split_mixed_turns(out)


def _params_overlap(a: AtcConcept, b: AtcConcept) -> bool:
    fields = ("level", "heading", "speed", "squawk", "freq", "qnh", "runway")
    for field in fields:
        va = getattr(a.params, field, None)
        vb = getattr(b.params, field, None)
        if va is not None and vb is not None:
            return True
    return a.intent == b.intent and a.intent.value != "OTHER"


def refine_roles(utterances: list[dict], concepts: list[AtcConcept]) -> None:
    """If Whisper labels two consecutive same-concept turns as ATCO, the second is the readback."""
    by_utt: dict[str, list[AtcConcept]] = {}
    for c in concepts:
        by_utt.setdefault(c.utterance_id, []).append(c)
    prev: AtcConcept | None = None
    for u in utterances:
        cs = by_utt.get(u["id"], [])
        role = SpeakerRole(u["speaker_role"])
        if prev is not None and role == SpeakerRole.ATCO:
            related = [c for c in cs if _params_overlap(c, prev) or c.intent == prev.intent]
            if related or not any(c.must_readback for c in cs):
                u["speaker_role"] = SpeakerRole.PILOT.value
                for c in cs:
                    c.speaker = SpeakerRole.PILOT
                    c.must_readback = False
                prev = None
                continue
        atcos = [c for c in cs if c.speaker == SpeakerRole.ATCO and c.must_readback]
        prev = atcos[0] if atcos else None


def _concept_label(c: AtcConcept) -> str:
    p = c.params
    if p.level:
        return str(p.level)
    if p.squawk:
        return f"SQ {p.squawk}"
    if p.heading is not None:
        return f"HDG {int(p.heading):03d}"
    if p.runway:
        return f"RWY {p.runway}"
    if p.qnh is not None:
        return f"QNH {p.qnh}"
    if p.freq:
        return str(p.freq)
    if p.speed is not None:
        return f"{p.speed}KT"
    return c.intent.value


def _issue_out(iss, atco: AtcConcept, pilot: AtcConcept | None) -> dict[str, Any]:
    return {
        "type": iss.type.value,
        "field": iss.field,
        "expected": iss.expected,
        "got": iss.got,
        "severity": iss.severity.value,
        "rule_id": iss.rule_id,
        "explanation_vi": iss.explanation_vi,
        "explanation_en": iss.explanation_en,
        "teaching_en": TEACHING.get(iss.type.value, ""),
        "t_start": atco.t_start,
        "t_end": (pilot.t_end if pilot else atco.t_end),
        "atco_text": atco.raw_text,
        "pilot_text": pilot.raw_text if pilot else "",
        "callsign": atco.callsign_norm or atco.callsign,
        "intent": atco.intent.value,
        "label": _concept_label(atco),
    }


def _build_minutes(
    filename: str,
    utterances: list[dict],
    issues: list[dict],
    summary: dict,
) -> str:
    lines = [
        "REDA — READBACK DEBRIEF MINUTES (EN)",
        "Safety net / training aid. Not a legal finding. Does not replace ATCO hearback.",
        "",
        f"File: {filename or '—'}",
        (
            f"Pairs checked: {summary['pairs']}. "
            f"Errors: {summary['red']} RED, {summary['amber']} AMBER. "
            f"Clean pairs: {summary['ok_pairs']}."
        ),
        "",
        "1. ENGLISH TRANSCRIPT",
    ]
    if not utterances:
        lines.append("  (no English speech recognised)")
    for u in utterances:
        lines.append(
            f"  [{_fmt_clock(u['t_start'])}–{_fmt_clock(u['t_end'])}] "
            f"{u['speaker_role']}: {u['asr_text']}"
        )
    lines += ["", "2. READBACK ERRORS"]
    if not issues:
        lines.append("  No concept-level readback error detected.")
    else:
        for i, iss in enumerate(issues, 1):
            lines.append(
                f"  {i}. {iss['severity']} {iss['type']}"
                f"  field={iss.get('field') or '—'}  {iss.get('label') or ''}".rstrip()
            )
            lines.append(f"     Expected: {iss.get('expected') or '—'}    Got: {iss.get('got') or '—'}")
            if iss.get("atco_text"):
                lines.append(f"     ATCO:  {iss['atco_text']}")
            if iss.get("pilot_text"):
                lines.append(f"     PILOT: {iss['pilot_text']}")
            if iss.get("explanation_en"):
                lines.append(f"     Note: {iss['explanation_en']}")
            if iss.get("teaching_en"):
                lines.append(f"     Teaching: {iss['teaching_en']}")
    points = []
    seen = set()
    for iss in issues:
        tip = iss.get("teaching_en") or ""
        if tip and tip not in seen:
            seen.add(tip)
            points.append(tip)
    lines += ["", "3. TEACHING POINTS FOR DEBRIEF"]
    if not points:
        lines.append("  Readback matched the clearance at concept level.")
    else:
        for i, tip in enumerate(points, 1):
            lines.append(f"  {i}. {tip}")
    lines += ["", "created by Lộc đẹp trai"]
    return "\n".join(lines)


def analyze(turns: list[dict] | None = None, filename: str = "", text: str = "") -> dict:
    raw = [_as_turn(t, i) for i, t in enumerate(turns or []) if str(t.get("text") or t.get("asr_text") or "").strip()]
    if not raw and text:
        raw = turns_from_text(text)
    else:
        raw = split_mixed_turns(raw)

    utterances: list[dict] = []
    concepts: list[AtcConcept] = []
    for item in raw:
        uid = str(uuid.uuid4())
        norm = normalize_text(item["text"])
        role = infer_role(norm, item.get("speaker_role"))
        parsed = parse_utterance(
            text=norm,
            templates=TEMPLATES,
            utterance_id=uid,
            t_start=item["t_start"],
            t_end=item["t_end"],
            speaker_raw=role.value,
        )
        if parsed:
            role = parsed[0].speaker
        utterances.append(
            {
                "id": uid,
                "t_start": item["t_start"],
                "t_end": item["t_end"],
                "speaker_role": role.value,
                "asr_text": item["text"],
                "asr_text_norm": norm,
            }
        )
        for c in parsed:
            if c.speaker == SpeakerRole.ATCO and c.intent.value != "OTHER":
                c.must_readback = True
            if c.speaker != SpeakerRole.ATCO:
                c.must_readback = False
            concepts.append(c)

    refine_roles(utterances, concepts)

    issues: list[dict] = []
    ok_pairs = 0
    pairs = 0
    for cand in pair_concepts(concepts, window_sec=WINDOW_SEC):
        if cand.status == "UNPAIRED":
            continue
        pairs += 1
        found = compare(cand.atco, cand.pilot, RULES)
        real = [iss for iss in found if iss.type != IssueType.OK]
        if not real:
            ok_pairs += 1
            continue
        for iss in real:
            issues.append(_issue_out(iss, cand.atco, cand.pilot))

    red = sum(1 for i in issues if i["severity"] == "RED")
    amber = sum(1 for i in issues if i["severity"] == "AMBER")
    summary = {
        "pairs": pairs,
        "ok_pairs": ok_pairs,
        "red": red,
        "amber": amber,
        "issue_count": len(issues),
    }
    concept_rows = [
        {
            "id": c.id,
            "utterance_id": c.utterance_id,
            "callsign": c.callsign,
            "callsign_norm": c.callsign_norm,
            "intent": c.intent.value,
            "params": {
                "level": c.params.level,
                "heading": c.params.heading,
                "speed": c.params.speed,
                "squawk": c.params.squawk,
                "freq": c.params.freq,
                "qnh": c.params.qnh,
                "runway": c.params.runway,
            },
            "must_readback": c.must_readback,
            "speaker_role": c.speaker.value,
            "t_start": c.t_start,
            "t_end": c.t_end,
            "raw_text": c.raw_text,
            "label": _concept_label(c),
        }
        for c in concepts
        if c.intent.value != "OTHER" or c.must_readback
    ]
    minutes = _build_minutes(filename, utterances, issues, summary)
    transcript = " ".join(u["asr_text"] for u in utterances).strip()
    return {
        "ok": True,
        "filename": filename,
        "transcript": transcript,
        "utterances": utterances,
        "concepts": concept_rows,
        "issues": issues,
        "summary": summary,
        "minutes_en": minutes,
    }


def analyze_text(text: str, filename: str = "") -> dict:
    return analyze(turns=None, filename=filename, text=text)
