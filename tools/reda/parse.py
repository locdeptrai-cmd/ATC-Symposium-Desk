from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from .concept import AtcConcept, AtcParams, Intent, SpeakerRole
from .normalize_fn import (
    extract_callsign_from_utterance,
    fold,
    normalize_callsign,
    normalize_freq,
    normalize_heading,
    normalize_level,
    normalize_qnh,
    normalize_runway,
    normalize_squawk,
    spoken_number,
    words_to_digits,
)


@dataclass
class Template:
    template_id: str
    intent: str
    role: str
    regex: str
    param_map: dict
    must_readback: bool


ATCO_CUES = (
    "climb flight level",
    "descend flight level",
    "climb and maintain",
    "descend and maintain",
    "cleared to land",
    "continue approach",
    "cleared land",
    "cleared for take-off",
    "cleared for takeoff",
    "clear for takeoff",
    "line up and wait",
    "line up",
    "hold short",
    "contact ",
    "squawk ",
    "qnh ",
    "fly heading",
    "turn left heading",
    "turn right heading",
    "reduce speed",
    "increase speed",
    "maintain flight level",
    "runway ",
    "wind ",
)

PILOT_CUES = (
    "climbing",
    "descending",
    "roger",
    "wilco",
    "affirm",
    "negative",
    "holding short",
    "going around",
)


def infer_role(text: str, speaker_raw: str | None = None) -> SpeakerRole:
    if speaker_raw in {"ATCO", "PILOT"}:
        return SpeakerRole(speaker_raw)
    t = fold(text)
    atco_hit = any(c in t for c in ATCO_CUES)
    pilot_hit = any(c in t for c in PILOT_CUES)
    if "climbing" in t or "descending" in t:
        return SpeakerRole.PILOT
    if atco_hit and not pilot_hit:
        return SpeakerRole.ATCO
    if pilot_hit and not atco_hit:
        return SpeakerRole.PILOT
    if speaker_raw in {"SPEAKER_00", "A", "ATCO"}:
        return SpeakerRole.ATCO
    if speaker_raw in {"SPEAKER_01", "B", "PILOT"}:
        return SpeakerRole.PILOT
    if atco_hit:
        return SpeakerRole.ATCO
    return SpeakerRole.UNKNOWN


def _apply_param(params: AtcParams, field: str, raw: str) -> None:
    if field == "level":
        level, unit = normalize_level(f"flight level {raw}")
        if level is None:
            level, unit = normalize_level(raw)
        params.level = level
        params.level_unit = unit
    elif field == "heading":
        params.heading = normalize_heading(f"heading {raw}")
    elif field == "squawk":
        params.squawk = normalize_squawk(f"squawk {raw}")
    elif field == "freq":
        params.freq = normalize_freq(raw)
    elif field == "qnh":
        qnh, unit = normalize_qnh(f"qnh {raw}")
        params.qnh = qnh
        params.qnh_unit = unit
    elif field == "runway":
        params.runway = normalize_runway(f"runway {raw}") or raw.upper()
    elif field == "speed":
        n = spoken_number(raw)
        params.speed = n
        params.speed_unit = "KT"


def parse_utterance(
    text: str,
    templates: list[Template],
    utterance_id: str,
    t_start: float,
    t_end: float,
    speaker_raw: str | None = None,
    callsign_lexicon: dict[str, str] | None = None,
) -> list[AtcConcept]:
    role = infer_role(text, speaker_raw)
    raw_cs, cs_norm = extract_callsign_from_utterance(text, callsign_lexicon)
    folded = fold(text)
    digit_text = words_to_digits(folded)
    found: list[AtcConcept] = []
    for tpl in templates:
        try:
            m = re.search(tpl.regex, digit_text, flags=re.IGNORECASE) or re.search(
                tpl.regex, folded, flags=re.IGNORECASE
            )
        except re.error:
            continue
        if not m:
            continue
        params = AtcParams()
        for group, field in tpl.param_map.items():
            val = m.groupdict().get(group)
            if val:
                _apply_param(params, field, val)
        gcs = m.groupdict().get("cs")
        callsign = raw_cs
        callsign_norm = cs_norm
        if gcs and gcs.strip():
            callsign = gcs.strip()
            callsign_norm = normalize_callsign(gcs, callsign_lexicon) or cs_norm
        try:
            intent = Intent(tpl.intent)
        except ValueError:
            intent = Intent.OTHER
        must = tpl.must_readback and role == SpeakerRole.ATCO
        found.append(
            AtcConcept(
                id=str(uuid.uuid4()),
                utterance_id=utterance_id,
                callsign=callsign,
                callsign_norm=callsign_norm,
                intent=intent,
                params=params,
                must_readback=must,
                speaker=role,
                t_start=t_start,
                t_end=t_end,
                raw_text=text,
                confidence=0.8,
            )
        )
    if not found:
        found.append(
            AtcConcept(
                id=str(uuid.uuid4()),
                utterance_id=utterance_id,
                callsign=raw_cs,
                callsign_norm=cs_norm,
                intent=Intent.OTHER,
                params=AtcParams(),
                must_readback=False,
                speaker=role,
                t_start=t_start,
                t_end=t_end,
                raw_text=text,
                confidence=0.4,
            )
        )
    return found
