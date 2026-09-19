"""Export HUMAN corrections to JSONL + PTT-sliced WAV. ASR-only rows are skipped."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from asr_dataset import DATASET_VERSION
from asr_dataset.audio_io import find_source_audio, read_wav_mono, write_wav_slice
from asr_dataset.entities import extract_entities
from asr_dataset.paths import ensure_gold_dirs, manifest_path, wav_dir
from reda import store as reda_store


def split_for_session(session_id: str, started_at: float | None) -> str:
    if started_at:
        day = datetime.fromtimestamp(float(started_at), tz=timezone.utc).strftime("%Y-%m-%d")
        seed = f"{day}:{session_id}"
    else:
        seed = session_id
    bucket = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % 10
    if bucket == 0:
        return "test"
    if bucket <= 2:
        return "dev"
    return "train"


def _utterance_row(conn, utterance_id: str):
    return conn.execute("SELECT * FROM utterances WHERE id=?", (utterance_id,)).fetchone()


def _session_row(conn, session_id: str):
    return conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()


def _audio_path_for(conn, session_id: str, filename: str, audio_roots: list[Path]) -> Path | None:
    try:
        row = conn.execute(
            "SELECT audio_path FROM session_audio WHERE session_id=?", (session_id,)
        ).fetchone()
    except Exception:
        row = None
    if row and row[0]:
        path = Path(str(row[0]))
        if path.is_file():
            return path
    return find_source_audio(filename, extra_roots=audio_roots)


def build_record(
    *,
    utterance_id: str,
    session_id: str,
    text: str,
    speaker: str,
    t_start: float,
    t_end: float,
    filename: str,
    started_at: float | None,
    audio_rel: str | None,
    unit: str = "",
    freq: str = "",
) -> dict:
    ents = extract_entities(text)
    return {
        "id": utterance_id,
        "audio": audio_rel,
        "text": text,
        "speaker": speaker or "UNKNOWN",
        "unit": unit,
        "freq": freq,
        "t_start": round(float(t_start), 3),
        "t_end": round(float(t_end), 3),
        "callsign": ents.get("callsign"),
        "entities": {k: v for k, v in ents.items() if v is not None},
        "split": split_for_session(session_id, started_at),
        "session_id": session_id,
        "utterance_id": utterance_id,
        "filename": filename,
        "dataset_version": DATASET_VERSION,
        "source": "HUMAN",
    }


def export_gold(audio_roots: list[Path] | None = None) -> dict:
    ensure_gold_dirs()
    roots = list(audio_roots or [])
    conn = reda_store._connect()
    written = 0
    skipped_no_human = 0
    skipped_no_audio = 0
    out_path = manifest_path()
    try:
        corrections = conn.execute(
            """
            SELECT c.id, c.session_id, c.utterance_id, c.after_text, c.before_text
            FROM corrections c
            WHERE c.source = 'HUMAN'
              AND TRIM(COALESCE(c.after_text, '')) != ''
            ORDER BY c.created_at
            """
        ).fetchall()
        seen: set[str] = set()
        with out_path.open("w", encoding="utf-8") as fh:
            for row in corrections:
                utt_id = str(row["utterance_id"] or "")
                if not utt_id or utt_id in seen:
                    continue
                utt = _utterance_row(conn, utt_id)
                if utt is None:
                    skipped_no_human += 1
                    continue
                if str(utt["source"] or "") != "HUMAN" and not utt["verified"]:
                    skipped_no_human += 1
                    continue
                seen.add(utt_id)
                sess = _session_row(conn, str(row["session_id"]))
                filename = str(sess["filename"] if sess else "")
                started = float(sess["started_at"]) if sess and sess["started_at"] else None
                text = str(row["after_text"] or utt["raw_transcript"] or "").strip()
                if not text:
                    skipped_no_human += 1
                    continue
                audio_rel = None
                src = _audio_path_for(conn, str(row["session_id"]), filename, roots)
                if src is not None:
                    dest = wav_dir() / f"{utt_id}.wav"
                    try:
                        samples, sr = read_wav_mono(src)
                        write_wav_slice(
                            samples,
                            sr,
                            float(utt["t_start"] or 0),
                            float(utt["t_end"] or 0),
                            dest,
                        )
                        audio_rel = f"wav/{utt_id}.wav"
                    except (OSError, ValueError):
                        skipped_no_audio += 1
                else:
                    skipped_no_audio += 1
                rec = build_record(
                    utterance_id=utt_id,
                    session_id=str(row["session_id"]),
                    text=text,
                    speaker=str(utt["speaker_role"] or "UNKNOWN"),
                    t_start=float(utt["t_start"] or 0),
                    t_end=float(utt["t_end"] or 0),
                    filename=filename,
                    started_at=started,
                    audio_rel=audio_rel,
                )
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1
    finally:
        conn.close()
    return {
        "manifest": str(out_path),
        "written": written,
        "skipped_no_human": skipped_no_human,
        "skipped_no_audio": skipped_no_audio,
        "dataset_version": DATASET_VERSION,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export HUMAN ATC transcripts to gold JSONL.")
    parser.add_argument(
        "--audio-root",
        action="append",
        default=[],
        help="Thu muc băng logger (co the lap lai). Khong dung ASR lam nhan.",
    )
    args = parser.parse_args()
    roots = [Path(p) for p in args.audio_root]
    stats = export_gold(audio_roots=roots)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
