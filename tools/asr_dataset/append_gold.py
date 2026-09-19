"""Append one HUMAN correction to the gold manifest (and slice WAV if source exists)."""

from __future__ import annotations

import json
from pathlib import Path

from asr_dataset.audio_io import find_source_audio, read_wav_mono, write_wav_slice
from asr_dataset.export_gold import build_record
from asr_dataset.paths import ensure_gold_dirs, manifest_path, wav_dir
from reda import store as reda_store


def append_correction(session_id: str, utterance_id: str, after_text: str) -> Path | None:
    text = (after_text or "").strip()
    if not session_id or not utterance_id or not text:
        return None
    ensure_gold_dirs()
    conn = reda_store._connect()
    try:
        utt = conn.execute("SELECT * FROM utterances WHERE id=?", (utterance_id,)).fetchone()
        sess = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        audio_stored = None
        try:
            audio_stored = conn.execute(
                "SELECT audio_path FROM session_audio WHERE session_id=?", (session_id,)
            ).fetchone()
        except Exception:
            audio_stored = None
    finally:
        conn.close()
    if utt is None:
        return None
    filename = str(sess["filename"] if sess else "")
    started = float(sess["started_at"]) if sess and sess["started_at"] else None
    src = None
    if audio_stored and audio_stored[0]:
        cand = Path(str(audio_stored[0]))
        if cand.is_file():
            src = cand
    if src is None:
        src = find_source_audio(filename)
    audio_rel = None
    if src is not None:
        dest = wav_dir() / f"{utterance_id}.wav"
        try:
            samples, sr = read_wav_mono(src)
            write_wav_slice(
                samples,
                sr,
                float(utt["t_start"] or 0),
                float(utt["t_end"] or 0),
                dest,
            )
            audio_rel = f"wav/{utterance_id}.wav"
        except (OSError, ValueError):
            audio_rel = None
    rec = build_record(
        utterance_id=utterance_id,
        session_id=session_id,
        text=text,
        speaker=str(utt["speaker_role"] or "UNKNOWN"),
        t_start=float(utt["t_start"] or 0),
        t_end=float(utt["t_end"] or 0),
        filename=filename,
        started_at=started,
        audio_rel=audio_rel,
    )
    path = manifest_path()
    existing: list[str] = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                old = json.loads(line)
            except json.JSONDecodeError:
                existing.append(line)
                continue
            if str(old.get("utterance_id") or "") == utterance_id:
                continue
            existing.append(line)
    existing.append(json.dumps(rec, ensure_ascii=False))
    path.write_text("\n".join(existing) + "\n", encoding="utf-8")
    return path
