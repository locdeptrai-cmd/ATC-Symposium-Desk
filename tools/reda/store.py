"""Local SQLite audit store for REDA sessions (on-prem, no cloud)."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

try:
    import app_paths
except ImportError:
    app_paths = None  # type: ignore


def db_path() -> Path:
    if app_paths is not None:
        if app_paths.frozen():
            folder = app_paths.app_home() / "data"
        else:
            folder = app_paths.bundle_root() / "data"
    else:
        folder = Path(__file__).resolve().parents[2] / "data"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "reda-sessions.sqlite"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            filename TEXT,
            started_at REAL,
            source_type TEXT,
            processing_version TEXT,
            summary_json TEXT,
            script_en TEXT
        );
        CREATE TABLE IF NOT EXISTS utterances (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            t_start REAL,
            t_end REAL,
            speaker_role TEXT,
            raw_transcript TEXT,
            normalized_transcript TEXT,
            callsign TEXT,
            source TEXT,
            verified INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS clearances (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            utterance_id TEXT,
            callsign TEXT,
            status TEXT,
            commands_json TEXT,
            differences_json TEXT
        );
        CREATE TABLE IF NOT EXISTS corrections (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            utterance_id TEXT,
            before_text TEXT,
            after_text TEXT,
            reason TEXT,
            created_at REAL,
            source TEXT
        );
        CREATE TABLE IF NOT EXISTS session_audio (
            session_id TEXT PRIMARY KEY,
            audio_path TEXT,
            unit TEXT,
            freq TEXT
        );
        CREATE INDEX IF NOT EXISTS utt_cs ON utterances(callsign);
        CREATE INDEX IF NOT EXISTS clr_st ON clearances(status);
        CREATE INDEX IF NOT EXISTS utt_raw ON utterances(raw_transcript);
        """
    )
    return conn


def set_session_audio(session_id: str, audio_path: str, unit: str = "", freq: str = "") -> None:
    if not session_id or not audio_path:
        return
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO session_audio VALUES (?,?,?,?)",
            (session_id, audio_path, unit, freq),
        )
        conn.commit()
    finally:
        conn.close()


def save_analysis(analysis: dict, session_id: str | None = None) -> str:
    sid = session_id or uuid.uuid4().hex[:12]
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO sessions VALUES (?,?,?,?,?,?,?)",
            (
                sid,
                analysis.get("filename") or "",
                time.time(),
                analysis.get("source") or "AI",
                analysis.get("processing_version") or "",
                json.dumps(analysis.get("summary") or {}, ensure_ascii=False),
                analysis.get("script_en") or "",
            ),
        )
        conn.execute("DELETE FROM utterances WHERE session_id=?", (sid,))
        conn.execute("DELETE FROM clearances WHERE session_id=?", (sid,))
        for u in analysis.get("utterances") or []:
            cs = u.get("callsign") or {}
            conn.execute(
                "INSERT OR REPLACE INTO utterances VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    u.get("id") or uuid.uuid4().hex,
                    sid,
                    float(u.get("t_start") or 0),
                    float(u.get("t_end") or 0),
                    u.get("speaker_role") or "UNKNOWN",
                    u.get("asr_text") or "",
                    u.get("asr_text_norm") or u.get("normalized") or "",
                    cs.get("normalized") or "",
                    u.get("source") or "AI",
                    1 if u.get("verified") else 0,
                ),
            )
        for c in analysis.get("clearances") or []:
            conn.execute(
                "INSERT OR REPLACE INTO clearances VALUES (?,?,?,?,?,?,?)",
                (
                    c.get("id") or uuid.uuid4().hex,
                    sid,
                    c.get("utterance_id") or "",
                    c.get("callsign") or "",
                    c.get("status") or "",
                    json.dumps(c.get("commands") or [], ensure_ascii=False),
                    json.dumps(c.get("differences") or [], ensure_ascii=False),
                ),
            )
            conn.commit()
    finally:
        conn.close()
    analysis["session_id"] = sid
    audio_path = str(analysis.get("audio_path") or "")
    if audio_path:
        set_session_audio(
            sid,
            audio_path,
            str(analysis.get("unit") or ""),
            str(analysis.get("freq") or ""),
        )
    return sid


def save_correction(session_id: str, utterance_id: str, before: str, after: str, reason: str = "") -> str:
    cid = uuid.uuid4().hex[:12]
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO corrections VALUES (?,?,?,?,?,?,?,?)",
            (cid, session_id, utterance_id, before, after, reason, time.time(), "HUMAN"),
        )
        conn.execute(
            "UPDATE utterances SET raw_transcript=?, source=?, verified=1 WHERE id=?",
            (after, "HUMAN", utterance_id),
        )
        conn.commit()
    finally:
        conn.close()
    # Circular: asr_dataset.append_gold imports this module.
    try:
        from asr_dataset.append_gold import append_correction

        append_correction(session_id, utterance_id, after)
    except Exception:
        pass
    return cid


def search(query: str = "", callsign: str = "", status: str = "", speaker: str = "", limit: int = 80) -> list[dict]:
    conn = _connect()
    try:
        sql = """
            SELECT u.id, u.session_id, u.t_start, u.speaker_role, u.raw_transcript,
                   u.normalized_transcript, u.callsign, s.filename, c.status AS clearance_status
            FROM utterances u
            JOIN sessions s ON s.id = u.session_id
            LEFT JOIN clearances c ON c.utterance_id = u.id
            WHERE 1=1
        """
        args: list = []
        q = (query or "").strip()
        if q:
            sql += " AND (u.raw_transcript LIKE ? OR u.normalized_transcript LIKE ? OR u.callsign LIKE ?)"
            like = f"%{q}%"
            args.extend([like, like, like])
        if callsign:
            sql += " AND u.callsign LIKE ?"
            args.append(f"%{callsign.strip().upper()}%")
        if status:
            sql += " AND c.status = ?"
            args.append(status.strip().upper())
        if speaker:
            sql += " AND u.speaker_role = ?"
            args.append(speaker.strip().upper())
        sql += " ORDER BY s.started_at DESC, u.t_start ASC LIMIT ?"
        args.append(int(limit))
        rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
