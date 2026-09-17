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
# CPU CTranslate2 / faster-whisper, English ATC radio only. No GPU / no torch
# at inference. Prefer the local turbo CT2 (ATCO2 + ATCoSIM, published WER
# 7.83%) then jacktol medium.en ATC (WER 15.08%). Override with ATC_WHISPER_MODEL.
ATC_WHISPER_TURBO_DIR = Path(__file__).resolve().parents[1] / "models" / "whisper" / "atc-turbo-ct2"
ATC_WHISPER_MEDIUM = "jacktol/whisper-medium.en-fine-tuned-for-ATC-faster-whisper"
ATC_WHISPER_DEFAULT = ATC_WHISPER_MEDIUM
ATC_PROMPT = (
    "Vietjet Viet Nam Saigon Tower Noi Bai. "
    "Cleared to land runway two five right. Continue approach. Squawk. QNH."
)
# VHF band + de-click + light denoise. No gate/dynaudnorm: those chop PTT onsets
# and pump hiss between syllables.
RADIO_AF = (
    "highpass=f=200:poles=2,lowpass=f=3600:poles=2,adeclick,"
    "afftdn=nr=6:nf=-20,acompressor=threshold=-24dB:ratio=3:attack=15:release=120,"
    "alimiter=limit=0.89"
)
RADIO_AF_FALLBACK = "highpass=f=200,lowpass=f=3600,alimiter=limit=0.89"
_VN_ICAO = {"HVN", "VJC", "BAV", "PIC", "VAG", "VFC", "SPQ", "VSM", "SAV", "HAI", "TVJ"}


def _vn_spoken_hotwords() -> str:
    bits = [
        "Vietjet",
        "Viet Nam",
        "Bamboo",
        "Pacific",
        "Vasco",
        "Saigon Tower",
        "Noi Bai",
        "Tan Son Nhat",
        "cleared to land",
        "continue approach",
        "runway two five",
        "squawk",
        "QNH",
    ]
    path = Path(__file__).resolve().parents[1] / "data" / "vn-airline-spoken.tsv"
    if not path.is_file():
        return " ".join(bits)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return " ".join(bits)
    for line in lines[1:]:
        cols = line.split("\t")
        if len(cols) < 5:
            continue
        kind, icao, spoken = cols[0].strip(), cols[1].strip(), (cols[4] or "").strip()
        if not spoken:
            continue
        if kind == "airline" and icao and icao not in _VN_ICAO:
            continue
        if spoken not in bits:
            bits.append(spoken)
    return " ".join(bits)


ATC_HOTWORDS = _vn_spoken_hotwords()

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


def _local_ct2_ready(folder: Path) -> bool:
    weights = folder / "model.bin"
    return (
        weights.is_file()
        and weights.stat().st_size > 400_000_000
        and (folder / "config.json").is_file()
        and (folder / "vocabulary.json").is_file()
    )


def _resolve_model_id() -> str:
    env = (os.environ.get("ATC_WHISPER_MODEL") or "").strip()
    if env:
        return env
    if _local_ct2_ready(ATC_WHISPER_TURBO_DIR):
        return str(ATC_WHISPER_TURBO_DIR)
    return ATC_WHISPER_MEDIUM


WHISPER_MODEL = _resolve_model_id()


def load_model():
    global _MODEL, _MODEL_ERROR, WHISPER_MODEL
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            _MODEL_ERROR = "May nay chua cai faster-whisper. pip install faster-whisper."
            return None
        candidates = []
        env = (os.environ.get("ATC_WHISPER_MODEL") or "").strip()
        if env:
            candidates.append(env)
        else:
            if _local_ct2_ready(ATC_WHISPER_TURBO_DIR):
                candidates.append(str(ATC_WHISPER_TURBO_DIR))
            candidates.append(ATC_WHISPER_MEDIUM)
        last_exc: Exception | None = None
        for name in candidates:
            try:
                print("  Transcribe EN: dang tai model '%s' (%s/%s)..." % (name, WHISPER_DEVICE, WHISPER_COMPUTE), flush=True)
                _MODEL = WhisperModel(
                    name,
                    device=WHISPER_DEVICE,
                    compute_type=WHISPER_COMPUTE,
                    download_root=str(_model_cache_dir()),
                )
                WHISPER_MODEL = name
                _MODEL_ERROR = ""
                return _MODEL
            except Exception as exc:
                last_exc = exc
                print("  Transcribe EN: bo qua '%s': %s" % (name, exc), flush=True)
                _MODEL = None
        _MODEL_ERROR = "Khong tai duoc mo hinh Whisper: %s" % last_exc
        return None


def warm_model() -> None:
    model = load_model()
    if model is not None:
        print("  Transcribe EN: whisper %s (%s/%s)" % (WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE), flush=True)


def _run_ffmpeg_wav(ffmpeg: str, src: Path, wav: Path, af: str, timeout: int) -> tuple[bool, str]:
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
        af,
        "-c:a",
        "pcm_s16le",
        str(wav),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout, **tx._popen_flags())
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "Khong tach duoc am thanh: %s" % exc
    if proc.returncode != 0 or not wav.is_file() or wav.stat().st_size < 64:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()
        return False, err[:180]
    return True, ""


def _extract_wav(src: Path, wav: Path, ffmpeg: str) -> tuple[bool, str]:
    # Mono from the radio mix (TightVNC stereo is a duplicated channel).
    timeout = max(90, int(src.stat().st_size / (256 * 1024)))
    ok, err = _run_ffmpeg_wav(ffmpeg, src, wav, RADIO_AF, timeout)
    if ok:
        return True, ""
    ok, err2 = _run_ffmpeg_wav(ffmpeg, src, wav, RADIO_AF_FALLBACK, timeout)
    if ok:
        return True, ""
    return False, "File khong co kenh tieng." + ((" " + (err or err2)) if (err or err2) else "")


def _read_wav_mono(path: Path) -> tuple["object", int]:
    import wave

    import numpy as np

    with wave.open(str(path), "rb") as handle:
        sr = handle.getframerate()
        nch = handle.getnchannels()
        frames = handle.readframes(handle.getnframes())
    pcm = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if nch > 1:
        pcm = pcm.reshape(-1, nch).mean(axis=1)
    return pcm, sr


def ptt_windows(samples, sr: int, min_dur: float = 0.35, merge_gap: float = 0.45, max_span: float = 18.0) -> list[tuple[float, float]]:
    import numpy as np

    hop = max(1, int(sr * 0.03))
    energy = []
    for i in range(0, max(0, len(samples) - hop), hop):
        chunk = samples[i : i + hop]
        energy.append(float(np.sqrt(np.mean(chunk * chunk) + 1e-12)))
    if not energy:
        return [(0.0, len(samples) / float(sr or 1))]
    frames = np.array(energy, dtype=np.float32)
    med = float(np.median(frames))
    thr = max(med * 5.0, 0.018)
    raw: list[tuple[float, float]] = []
    start = None
    hang = 8
    quiet = 0
    for i, on in enumerate(frames > thr):
        if on:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet >= hang:
                a = start * hop / sr
                b = max(a + min_dur, (i - quiet + 1) * hop / sr)
                if b - a >= min_dur:
                    raw.append((a, b))
                start = None
                quiet = 0
    if start is not None:
        a = start * hop / sr
        b = len(samples) / float(sr)
        if b - a >= min_dur:
            raw.append((a, b))
    if not raw:
        return [(0.0, len(samples) / float(sr or 1))]
    grouped: list[tuple[float, float]] = []
    cur0, cur1 = raw[0]
    for a, b in raw[1:]:
        if a - cur1 <= merge_gap and (b - cur0) <= max_span:
            cur1 = b
        else:
            grouped.append((cur0, cur1))
            cur0, cur1 = a, b
    grouped.append((cur0, cur1))
    return grouped


def collapse_loops(text: str) -> str:
    import re

    out = " ".join((text or "").split())
    if not out:
        return ""
    prev = None
    while prev != out:
        prev = out
        out = re.sub(r"\b((?:\S+\s+){0,5}\S+)(?:\s+\1){2,}\b", r"\1", out, flags=re.I)
    return out


def _write_wav_slice(src_samples, sr: int, t0: float, t1: float, dest: Path) -> None:
    import wave

    import numpy as np

    a = max(0, int(t0 * sr))
    b = min(len(src_samples), int(t1 * sr))
    if b <= a:
        b = min(len(src_samples), a + int(0.4 * sr))
    pcm = np.clip(src_samples[a:b] * 32767.0, -32767, 32767).astype(np.int16)
    with wave.open(str(dest), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(pcm.tobytes())


def _decode_window(model, wav: Path) -> list[dict]:
    segments, _info = model.transcribe(
        str(wav),
        language="en",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 180, "speech_pad_ms": 120},
        condition_on_previous_text=False,
        initial_prompt=ATC_PROMPT,
        hotwords=ATC_HOTWORDS,
        temperature=0.0,
        repetition_penalty=1.12,
        no_repeat_ngram_size=4,
        compression_ratio_threshold=2.0,
        no_speech_threshold=0.5,
        hallucination_silence_threshold=0.5,
        word_timestamps=False,
    )
    turns = []
    for seg in segments:
        chunk = collapse_loops((seg.text or "").strip())
        if not chunk:
            continue
        turns.append(
            {
                "t_start": float(getattr(seg, "start", 0) or 0),
                "t_end": float(getattr(seg, "end", 0) or 0),
                "text": chunk,
            }
        )
    return turns


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
        note(16, "Đang cắt theo PTT…")
        samples, sr = _read_wav_mono(wav)
        duration = len(samples) / float(sr or 1)
        windows = ptt_windows(samples, sr)
        note(18, "Đang ghi lời English từ file…")
        parts: list[str] = []
        turns: list[dict] = []
        for idx, (t0, t1) in enumerate(windows):
            slice_wav = folder / ("ptt-%03d.wav" % idx)
            _write_wav_slice(samples, sr, max(0.0, t0 - 0.08), t1 + 0.08, slice_wav)
            try:
                segs = _decode_window(model, slice_wav)
            finally:
                try:
                    slice_wav.unlink(missing_ok=True)
                except OSError:
                    pass
            for seg in segs:
                chunk = seg["text"]
                if not chunk:
                    continue
                abs_start = t0 + float(seg.get("t_start") or 0)
                abs_end = t0 + float(seg.get("t_end") or 0)
                parts.append(chunk)
                turns.append({"t_start": abs_start, "t_end": abs_end, "text": chunk})
            joined = collapse_loops(" ".join(parts))
            pct = 18.0
            if duration > 0:
                pct = min(92.0, 18.0 + 74.0 * (t1 / duration))
            note(pct, "Đang ghi lời English…", joined)
        text = collapse_loops(" ".join(parts))
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
