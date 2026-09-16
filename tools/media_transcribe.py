"""Transcribe English from a recording file (not the microphone)."""
from __future__ import annotations

import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

import os
import media_transcode as tx

MAX_UPLOAD_BYTES = tx.MAX_UPLOAD_BYTES
# Fine-tuned on ATCO2 + UWB-ATCC (ICAO English radiotelephony). CTranslate2
# weights for faster-whisper — CPU int8, no GPU / no torch.
# HF: jacktol/whisper-medium.en-fine-tuned-for-ATC-faster-whisper  (WER 15.08%
# on ATC vs 94.59% for stock medium.en). Override with ATC_WHISPER_MODEL.
ATC_WHISPER_DEFAULT = "jacktol/whisper-medium.en-fine-tuned-for-ATC-faster-whisper"
ATC_PROMPT = (
    "Air traffic control radiotelephony. Cleared to land. Cleared for take-off. "
    "Line up and wait. Hold short of runway. Go around. Squawk. Contact tower. "
    "Contact approach. Climb. Descend. Maintain. Flight level. QNH. Roger. Wilco. Affirm. Negative."
)

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
_MODEL = None
_MODEL_LOCK = threading.Lock()
_MODEL_ERROR = ""


def _job_update(job_id: str, **fields) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return
        job.update(fields)


def job_snapshot(job_id: str) -> dict | None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        return {
            "id": job["id"],
            "percent": float(job.get("percent") or 0),
            "stage": job.get("stage") or "",
            "text": job.get("text") or "",
            "turns": list(job.get("turns") or []),
            "analysis": job.get("analysis") or None,
            "done": bool(job.get("done")),
            "error": job.get("error") or "",
        }


def sweep_jobs(max_age: float = 900) -> None:
    now = time.time()
    with _JOBS_LOCK:
        stale = [jid for jid, job in _JOBS.items() if now - float(job.get("created") or 0) > max_age]
    for jid in stale:
        with _JOBS_LOCK:
            job = _JOBS.pop(jid, None)
        if not job:
            continue
        src = job.get("src")
        if src:
            try:
                Path(src).unlink(missing_ok=True)
            except OSError:
                pass


WHISPER_MODEL = os.environ.get("ATC_WHISPER_MODEL", ATC_WHISPER_DEFAULT)
WHISPER_DEVICE = os.environ.get("ATC_WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.environ.get("ATC_WHISPER_COMPUTE", "int8")


def _model_cache_dir() -> Path:
    env = os.environ.get("ATC_WHISPER_CACHE")
    if env:
        folder = Path(env)
    else:
        # Keep weights on the project drive. %LOCALAPPDATA% (C:) is often too small
        # for the ATC medium.en CTranslate2 checkpoint (~3 GB).
        folder = Path(__file__).resolve().parents[1] / "models" / "whisper"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def load_model():
    global _MODEL, _MODEL_ERROR
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            _MODEL_ERROR = "May nay chua cai faster-whisper. pip install faster-whisper."
            return None
        try:
            print("  Transcribe EN: dang tai model '%s' (%s/%s)..." % (WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE), flush=True)
            _MODEL = WhisperModel(
                WHISPER_MODEL,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE,
                download_root=str(_model_cache_dir()),
            )
            _MODEL_ERROR = ""
            return _MODEL
        except Exception as exc:
            _MODEL_ERROR = "Khong tai duoc mo hinh Whisper: %s" % exc
            return None


def warm_model() -> None:
    model = load_model()
    if model is not None:
        print("  Transcribe EN: whisper %s (%s/%s)" % (WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE), flush=True)


def _extract_wav(src: Path, wav: Path, ffmpeg: str) -> tuple[bool, str]:
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-af",
        # VHF radiotelephony band (~300–3400 Hz) + level normalize for radio fade.
        "highpass=f=300,lowpass=f=3400,dynaudnorm=f=150:g=15",
        "-c:a",
        "pcm_s16le",
        str(wav),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=max(90, int(src.stat().st_size / (256 * 1024))),
            **tx._popen_flags(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "Khong tach duoc am thanh: %s" % exc
    if proc.returncode != 0 or not wav.is_file() or wav.stat().st_size < 64:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()
        return False, "File khong co kenh tieng." + ((" " + err[:180]) if err else "")
    return True, ""


def transcribe_with_turns(src: Path, on_progress=None) -> tuple[str, list[dict], str]:
    def note(pct: float, stage: str, text: str = "") -> None:
        if on_progress:
            on_progress(pct, stage, text)

    ffmpeg = tx.find_ffmpeg()
    if not ffmpeg:
        return "", [], "May nay chua co ffmpeg."
    if not src.is_file() or src.stat().st_size <= 0:
        return "", [], "File rong."
    note(4, "Đang tách kênh tiếng…")
    folder = Path(tempfile.mkdtemp(prefix="atc-stt-"))
    wav = folder / "voice.wav"
    try:
        ok, err = _extract_wav(src, wav, ffmpeg)
        if not ok:
            return "", [], err
        note(12, "Đang tải mô hình English…")
        model = load_model()
        if model is None:
            return "", [], _MODEL_ERROR or "Khong co Whisper."
        note(18, "Đang ghi lời English từ file…")
        parts: list[str] = []
        turns: list[dict] = []
        segments, info = model.transcribe(
            str(wav),
            language="en",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400, "speech_pad_ms": 200},
            # Each radio burst is independent; carrying prior text invents readbacks.
            condition_on_previous_text=False,
            initial_prompt=ATC_PROMPT,
            temperature=0.0,
            word_timestamps=False,
        )
        duration = float(getattr(info, "duration", 0) or 0)
        for seg in segments:
            chunk = (seg.text or "").strip()
            if not chunk:
                continue
            parts.append(chunk)
            turns.append(
                {
                    "t_start": float(getattr(seg, "start", 0) or 0),
                    "t_end": float(getattr(seg, "end", 0) or 0),
                    "text": chunk,
                }
            )
            joined = " ".join(parts)
            end = float(getattr(seg, "end", 0) or 0)
            pct = 18.0
            if duration > 0 and end > 0:
                pct = min(92.0, 18.0 + 74.0 * (end / duration))
            note(pct, "Đang ghi lời English…", joined)
        text = " ".join(parts).replace("  ", " ").strip()
        if not text:
            return "", [], "Whisper khong nghe ra loi English trong file nay."
        note(94, "Đang đối chiếu readback REDA…", text)
        return text, turns, ""
    finally:
        try:
            if wav.is_file():
                wav.unlink()
            folder.rmdir()
        except OSError:
            pass


def transcribe_file(src: Path, on_progress=None) -> tuple[str, str]:
    text, _turns, err = transcribe_with_turns(src, on_progress=on_progress)
    return text, err


def _analyze_turns(turns: list[dict], filename: str) -> dict | None:
    try:
        from reda.engine import analyze
    except Exception:
        return None
    try:
        return analyze(turns, filename=filename)
    except Exception:
        return None


def start_job(src: Path) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "id": job_id,
            "percent": 1.0,
            "stage": "Đã nhận file, bắt đầu ghi lời…",
            "text": "",
            "turns": [],
            "analysis": None,
            "done": False,
            "error": "",
            "src": src,
            "created": time.time(),
        }
    threading.Thread(target=_run_job, args=(job_id, src), daemon=True).start()
    return job_id


def _run_job(job_id: str, src: Path) -> None:
    def on_progress(pct: float, stage: str, text: str = "") -> None:
        fields = {"percent": round(pct, 1), "stage": stage}
        if text:
            fields["text"] = text
        _job_update(job_id, **fields)

    text, turns, err = transcribe_with_turns(src, on_progress=on_progress)
    name = src.name if src else "clip"
    try:
        src.unlink(missing_ok=True)
    except OSError:
        pass
    if err:
        _job_update(job_id, done=True, error=err, percent=100)
        return
    analysis = _analyze_turns(turns, name)
    _job_update(
        job_id,
        done=True,
        percent=100,
        stage="Xong.",
        text=text,
        turns=turns,
        analysis=analysis,
        error="",
    )
