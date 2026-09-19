from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SpeakerRole(str, Enum):
    ATCO = "ATCO"
    PILOT = "PILOT"
    UNKNOWN = "UNKNOWN"


class Intent(str, Enum):
    CLIMB = "CLIMB"
    DESCEND = "DESCEND"
    MAINTAIN = "MAINTAIN"
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"
    FLY_HEADING = "FLY_HEADING"
    SPEED = "SPEED"
    SQUAWK = "SQUAWK"
    CONTACT = "CONTACT"
    CLEARED_TO = "CLEARED_TO"
    CLEARED_TAKEOFF = "CLEARED_TAKEOFF"
    CLEARED_LAND = "CLEARED_LAND"
    HOLD_SHORT = "HOLD_SHORT"
    CROSS = "CROSS"
    ENTER = "ENTER"
    BACKTRACK = "BACKTRACK"
    TAXI = "TAXI"
    QNH = "QNH"
    TRANS_LEVEL = "TRANS_LEVEL"
    DIRECT = "DIRECT"
    HOLD = "HOLD"
    REPORT = "REPORT"
    LINE_UP = "LINE_UP"
    CLEARED_APPROACH = "CLEARED_APPROACH"
    REDUCE_SPEED = "REDUCE_SPEED"
    INCREASE_SPEED = "INCREASE_SPEED"
    OTHER = "OTHER"


class Severity(str, Enum):
    RED = "RED"
    AMBER = "AMBER"
    GREEN = "GREEN"


class IssueType(str, Enum):
    OK = "OK"
    OMISSION = "OMISSION"
    MISMATCH = "MISMATCH"
    MISSING_READBACK = "MISSING_READBACK"
    NON_STANDARD = "NON_STANDARD"
    CALLSIGN_ERROR = "CALLSIGN_ERROR"
    HEARBACK_GAP = "HEARBACK_GAP"


@dataclass
class AtcParams:
    level: str | None = None
    level_unit: str | None = None
    heading: int | None = None
    speed: int | None = None
    speed_unit: str | None = None
    squawk: str | None = None
    freq: str | None = None
    qnh: int | None = None
    qnh_unit: str | None = None
    runway: str | None = None
    route: str | None = None
    waypoint: str | None = None
    restriction: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class AtcConcept:
    id: str
    utterance_id: str
    intent: Intent
    speaker: SpeakerRole
    t_start: float
    t_end: float
    raw_text: str
    callsign: str | None = None
    callsign_norm: str | None = None
    params: AtcParams = field(default_factory=AtcParams)
    must_readback: bool = False
    confidence: float = 0.0


@dataclass
class CompareIssue:
    type: IssueType
    severity: Severity
    rule_id: str
    field: str | None = None
    expected: str | None = None
    got: str | None = None
    explanation_vi: str | None = None
    explanation_en: str | None = None


@dataclass
class PhraseologyRule:
    rule_id: str
    field: str
    severity: Severity
    compare_fn: str
    required_when: str
    source_doc: str
    description_vi: str
    intent: str | None = None
    aliases_ok: list | None = None
    source_clause: str | None = None
    description_en: str | None = None
