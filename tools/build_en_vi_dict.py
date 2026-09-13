#!/usr/bin/env python3
"""Build a compact EN→VI gloss map for ATC Symposium Desk.

Sources (downloaded into tools/cache/, not shipped):
  - yenthanh132/avdict-database-sqlite-converter  anhviet109K.txt
    (109k English–Vietnamese dictionary, FVDP / Hồ Ngọc Đức lineage)
  - first20hours/google-10000-english  20k.txt (word frequency filter)

The generated file keeps only a short first sense for common words plus
ATM/ATS extras. Specialized TERMS in glossary.js always override this map.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(__file__).resolve().parent / "cache"
OUT = ROOT / "web" / "js" / "dict-en-vi.js"

EV_URL = (
    "https://raw.githubusercontent.com/yenthanh132/"
    "avdict-database-sqlite-converter/master/anhviet109K.txt"
)
FREQ_URL = (
    "https://raw.githubusercontent.com/first20hours/"
    "google-10000-english/master/20k.txt"
)

ATM_EXTRA = """
airspace aerodrome airdrome aircraft airplane airline airlines airport airports
apron taxiway taxiways runway runways threshold thresholds holding hold
vector vectoring radar radars transponder squawk altitude altitudes flight
flights traffic sector sectors centre center centres centers unit units
watch roster rosters shift shifts duty duties fatigue fatigued staffing
endorsement endorsements competency competencies proficiency phraseology
occurrence occurrences incident incidents accident accidents hazard hazards
mitigation mitigations assurance occurrence reporting reporter voluntary
mandatory regulator regulators oversight surveillance navigation navigational
communication communications meteorological aeronautical collaborative
interoperability trajectory trajectories capacity capacities delay delays
congestion throughput spacing separation separations clearance clearances
approach approaches departure departures arrival arrivals climb descent
procedure procedures specification specifications performance performances
implementation implementations coordination coordinations contingency
contingencies fallback fallbacks outage outages workload complexity
predictability predictability slot slots flow flows demand demands peak
peaks night consecutive rest unfit self-report predictive proactive reactive
just-culture occurrence airprox incursion excursion go-around go-arounds
holding-pattern miles-in-trail ground-delay declared-capacity sectorisation
sectorization endorsement instructor instructors trainee trainees ab-initio
recency licensing licensed unlicensed unusual-situation unusual
radiotelephony phraseology intervention interventions plenary workshop
workshops symposium symposiums delegate delegates rapporteur rapporteurs
chair chairperson secretariat distinguished distinguished-speaker
implementation roadmap roadmaps timeframe timeframes timeline timelines
governance identity consume consumed service-provider service-providers
information-service data-quality letter-of-agreement letter-of-coordination
on-the-job instructor watch-supervisor supervisor supervisors
controller controllers pilot pilots operator operators airline-operator
turnaround off-block take-off takeoff landing landings taxi taxiing
pushback holding-point holding-points ILS VOR DME NDB LOC GS marker
localizer glideslope glideslope navaid navaids waypoint waypoints fix
fixes STAR SID RNAV RNP PBN CDO CCO TMA FIR ACC APP TWR GND ATFM ATFMC
SWIM SMS FRMS ATCO ATSEP ANSP ATS ATM ATC CNS AIS AIP NOTAM MET SAR
AMAN DMAN A-CDM CPDLC ADS-B ADS-C MLAT WAM PSR SSR RVSM GBAS SBAS
FIXM AIXM WXXM GANP ASBU FF-ICE TBO CBTA OJT OJTI LPR SPI SPT KPI
LoA LoC CAPA MOR QMS
protect protected protecting meet meets meeting meetings file files filed
filing report reports reported reporting requirement requirements
expectation expectations enforcement enforcements regulator's
controller's pilot's
""".split()

SKIP_HEADS = {
    "a", "an", "the", "o", "x", "e", "g", "n", "r", "s", "t", "u", "v", "w",
    "y", "z", "aa", "ab", "ad", "ah", "am", "pm",
}

PAREN = re.compile(r"\([^)]*\)")
IPA_SPLIT = re.compile(r"\s+/")


def fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000:
        return
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "ATC-Symposium-Desk/1.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
        dest.write_bytes(resp.read())


def clean_gloss(raw: str) -> str:
    s = raw.strip()
    if s.startswith("="):
        return ""
    s = s.split("+", 1)[0]
    s = PAREN.sub(" ", s)
    s = s.replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip(" -;,.")
    if not s:
        return ""
    s = re.split(r"[;]|,(?=\s)", s)[0].strip(" -;,.")
    # drop dictionary cross-refs
    if s.lower().startswith("xem ") or s.lower() in {"xem", "như", "như trên"}:
        return ""
    words = s.split()
    if len(words) > 8:
        s = " ".join(words[:8])
    if len(s) > 48:
        s = s[:48].rsplit(" ", 1)[0]
    if not re.search(r"[A-Za-zÀ-ỹàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", s):
        return ""
    return s.strip(" -;,.")


def parse_fvdp(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    current = None
    got = False
    for line in text.splitlines():
        if line.startswith("@"):
            current = IPA_SPLIT.split(line[1:].strip(), 1)[0].strip().lower()
            current = re.sub(r"\s+", " ", current)
            got = False
            continue
        if got or current is None:
            continue
        if line.startswith("-"):
            gloss = clean_gloss(line[1:])
            if gloss:
                entries[current] = gloss
                got = True
    return entries


def load_freq(path: Path) -> list[str]:
    words = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        w = line.strip().lower()
        if w.isalpha() and 2 <= len(w) <= 24:
            words.append(w)
    return words


def main() -> None:
    ev_path = CACHE / "anhviet109K.txt"
    freq_path = CACHE / "20k.txt"
    print("Downloading dictionary sources…")
    fetch(EV_URL, ev_path)
    fetch(FREQ_URL, freq_path)
    print(f"  EV dict: {ev_path.stat().st_size:,} bytes")
    print(f"  freq:    {freq_path.stat().st_size:,} bytes")

    ev = parse_fvdp(ev_path.read_text(encoding="utf-8", errors="replace"))
    print(f"  parsed heads: {len(ev):,}")

    freq = load_freq(freq_path)
    want = set(freq[:12000])
    for extra in ATM_EXTRA:
        extra = extra.strip().lower().replace("-", " ")
        if extra:
            want.add(extra)
            for part in extra.split():
                if len(part) >= 3:
                    want.add(part)

    out: dict[str, str] = {}
    for w in sorted(want, key=lambda x: (x.count(" "), x)):
        if w in SKIP_HEADS:
            continue
        gloss = ev.get(w)
        if not gloss:
            continue
        out[w] = gloss

    # Keep useful 2-word dictionary phrases when both tokens are common.
    common = set(freq[:8000]) | {x.lower() for x in ATM_EXTRA if x.isalpha()}
    for head, gloss in ev.items():
        parts = head.split()
        if len(parts) != 2:
            continue
        if any(len(p) < 3 for p in parts):
            continue
        if parts[0] in common and parts[1] in common and head not in out:
            out[head] = gloss

    items = sorted(out.items(), key=lambda kv: (-len(kv[0]), kv[0]))
    payload = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    js = (
        "(function (root) {\n"
        "  var ATC = root.ATC || (root.ATC = {});\n"
        "  /* Compact first-sense glosses from GitHub anhviet109K\n"
        "     (yenthanh132/avdict-database-sqlite-converter),\n"
        "     filtered by google-10000-english 20k frequency +\n"
        "     ATM/ATS extras. glossary.js TERMS override this map. */\n"
        f"  ATC.EN_VI_DICT = {payload};\n"
        "})(typeof globalThis !== \"undefined\" ? globalThis : this);\n"
    )
    OUT.write_text(js, encoding="utf-8")
    print(f"Wrote {OUT}  entries={len(out):,}  bytes={OUT.stat().st_size:,}")
    for sample in ("protect", "controller", "meeting", "report", "if", "after", "safety"):
        print(f"  {sample}: {out.get(sample, '—')}")


if __name__ == "__main__":
    main()
