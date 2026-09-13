from __future__ import annotations

from dataclasses import dataclass

from .concept import AtcConcept, SpeakerRole


@dataclass
class PairCandidate:
    atco: AtcConcept
    pilot: AtcConcept | None
    window_sec: float
    status: str  # MATCHED | MISSING_RB | UNPAIRED


def _in_window(atco: AtcConcept, pilot: AtcConcept, window_sec: float) -> bool:
    if pilot.t_start < atco.t_end - 0.05:
        return False
    return pilot.t_start <= atco.t_end + window_sec


def pair_concepts(
    concepts: list[AtcConcept],
    window_sec: float = 25.0,
) -> list[PairCandidate]:
    atcos = [c for c in concepts if c.speaker == SpeakerRole.ATCO and c.must_readback]
    pilots = [c for c in concepts if c.speaker == SpeakerRole.PILOT]
    used: set[str] = set()
    pairs: list[PairCandidate] = []

    def take_pilot(atco: AtcConcept, require_callsign: bool) -> AtcConcept | None:
        match: AtcConcept | None = None
        for pilot in pilots:
            if pilot.id in used:
                continue
            if not _in_window(atco, pilot, window_sec):
                continue
            if require_callsign:
                if atco.callsign_norm and pilot.callsign_norm:
                    if atco.callsign_norm != pilot.callsign_norm:
                        continue
                elif atco.callsign_norm and not pilot.callsign_norm:
                    continue
            if match is None or pilot.t_start < match.t_start:
                match = pilot
        return match

    for atco in sorted(atcos, key=lambda c: c.t_start):
        match = take_pilot(atco, require_callsign=True)
        if match is None:
            match = take_pilot(atco, require_callsign=False)
        if match is None:
            pairs.append(PairCandidate(atco=atco, pilot=None, window_sec=window_sec, status="MISSING_RB"))
        else:
            used.add(match.id)
            pairs.append(PairCandidate(atco=atco, pilot=match, window_sec=window_sec, status="MATCHED"))

    return pairs
