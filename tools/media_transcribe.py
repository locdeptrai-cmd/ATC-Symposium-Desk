"""Transcribe English from a recording file (not the microphone)."""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
import wave
from pathlib import Path

import numpy as np

import app_paths
import media_transcode as tx
from asr_dataset.hotwords import hotwords_for

MAX_UPLOAD_BYTES = tx.MAX_UPLOAD_BYTES
# CPU CTranslate2 / faster-whisper, English ATC radio only. No GPU / no torch
# at inference. Local turbo CT2 (ATCO2 + ATCoSIM, published WER 7.83%).
# Override with ATC_WHISPER_MODEL.
ATC_WHISPER_TURBO_DIR = app_paths.whisper_turbo_dir()
ATC_PROMPT = "Viet Nam Vietjet TSN Tower. Cleared to land. Squawk. QNH."
LIVE_OVERLAP_SEC = 1.5
STREAM_HOP_SEC = float(os.environ.get("ATC_STT_HOP", "2.0"))
STREAM_OVERLAP_SEC = 0.35
STREAM_MIN_RMS = 0.012
WHISPER_BEAM = max(1, int(os.environ.get("ATC_WHISPER_BEAM", "1")))
# VHF band + de-click + light denoise. No gate/dynaudnorm: those chop PTT onsets
# and pump hiss between syllables.
RADIO_AF = (
    "highpass=f=200:poles=2,lowpass=f=3600:poles=2,adeclick,"
    "afftdn=nr=6:nf=-20,acompressor=threshold=-24dB:ratio=3:attack=15:release=120,"
    "alimiter=limit=0.89"
)
RADIO_AF_FALLBACK = "highpass=f=200,lowpass=f=3600,alimiter=limit=0.89"

_live_tail: np.ndarray | None = None
_live_tail_sr = 16000


def reset_live_tail() -> None:
    global _live_tail
    _live_tail = None


def _apply_live_overlap(samples: np.ndarray, sr: int, src_name: str) -> tuple[np.ndarray, float]:
    global _live_tail, _live_tail_sr
    if not str(src_name or "").lower().startswith("live-"):
        _live_tail = None
        return samples, 0.0
    overlap = 0.0
    n = max(1, int(LIVE_OVERLAP_SEC * sr))
    if _live_tail is not None and len(_live_tail) and _live_tail_sr == sr:
        samples = np.concatenate([_live_tail, samples])
        overlap = float(len(_live_tail) / sr)
    _live_tail = np.array(samples[-n:], dtype=np.float32, copy=True)
    _live_tail_sr = sr
    return samples, overlap


def _drop_overlap_turns(turns: list[dict], overlap: float) -> list[dict]:
    if overlap <= 0.05:
        return turns
    kept: list[dict] = []
    for turn in turns:
        t_end = float(turn.get("t_end") or 0)
        t_start = float(turn.get("t_start") or 0)
        if t_end <= overlap:
            continue
        turn["t_start"] = max(0.0, t_start - overlap)
        turn["t_end"] = max(turn["t_start"], t_end - overlap)
        kept.append(turn)
    return kept


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
        folder = app_paths.bundle_root() / "models" / "whisper"
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        folder = app_paths.app_home() / "models" / "whisper"
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
    turbo = app_paths.whisper_turbo_dir()
    if _local_ct2_ready(turbo):
        return str(turbo)
    return str(turbo)


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
        turbo = app_paths.whisper_turbo_dir()
        if env:
            candidates.append(env)
        if str(turbo) not in candidates:
            candidates.append(str(turbo))
        last_exc: Exception | None = None
        for name in candidates:
            try:
                print("  Transcribe EN: dang tai model '%s' (%s/%s)..." % (name, WHISPER_DEVICE, WHISPER_COMPUTE), flush=True)
                threads = max(2, int(os.environ.get("ATC_WHISPER_THREADS") or 0) or max(4, (os.cpu_count() or 4) - 1))
                kwargs_model = dict(
                    device=WHISPER_DEVICE,
                    compute_type=WHISPER_COMPUTE,
                    download_root=str(_model_cache_dir()),
                )
                try:
                    _MODEL = WhisperModel(name, cpu_threads=threads, num_workers=1, **kwargs_model)
                except TypeError:
                    _MODEL = WhisperModel(name, **kwargs_model)
                # First CTranslate2 run compiles kernels; do it at boot, not on the clip.
                try:
                    list(
                        _MODEL.transcribe(
                            np.zeros(8000, dtype=np.float32),
                            language="en",
                            beam_size=1,
                            vad_filter=False,
                            without_timestamps=True,
                        )
                    )
                except Exception:
                    pass
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


def _read_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        sr = handle.getframerate()
        nch = handle.getnchannels()
        frames = handle.readframes(handle.getnframes())
    pcm = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if nch > 1:
        pcm = pcm.reshape(-1, nch).mean(axis=1)
    return pcm, sr


def ptt_windows(samples, sr: int, min_dur: float = 0.4, merge_gap: float = 0.65, max_span: float = 14.0) -> list[tuple[float, float]]:
    hop = max(1, int(sr * 0.03))
    energy = []
    for i in range(0, max(0, len(samples) - hop), hop):
        chunk = samples[i : i + hop]
        energy.append(float(np.sqrt(np.mean(chunk * chunk) + 1e-12)))
    if not energy:
        return [(0.0, len(samples) / float(sr or 1))]
    frames = np.array(energy, dtype=np.float32)
    p20 = float(np.percentile(frames, 20))
    p90 = float(np.percentile(frames, 90))
    span = max(0.0, p90 - p20)
    thr = max(0.015, p20 + 0.35 * span)
    if p90 < 0.04:
        return [(0.0, len(samples) / float(sr or 1))]
    raw: list[tuple[float, float]] = []
    start = None
    hang = 10
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
    out = " ".join((text or "").split())
    if not out:
        return ""
    prev = None
    while prev != out:
        prev = out
        out = re.sub(r"\b((?:\S+\s+){0,5}\S+)(?:\s+\1){2,}\b", r"\1", out, flags=re.I)
    return out


_RADIO_FIXES = (
    (r"\b(?:charlie|charley)\s+jet\b", "Vietjet"),
    (r"\bsion\s+(?=one|two|three|four|five|six|seven|eight|nine|zero)", "Vietjet "),
    (r"\bviet\s*jet(?:air)?\b", "Vietjet"),
    (r"\bvietnam(?:\s+airlines?)?\b", "Viet Nam"),
    (r"\bviet\s*nam(?:\s+airlines?)?\b", "Viet Nam"),
    (r"\bair\s*france\b", "AirFrans"),
    (r"\bkorean\s*air\b", "Korean Air"),
    (r"\bcathay(?:\s+pacific)?\b", "Cathay"),
    (r"\bchina\s+south(?:ern)?\b", "China Southern"),
    (r"\brejet\b", "Vietjet"),
    (r"\b(?:qi|qq|qqe)\s+nine(?:\s+zero){0,2}\s+nine\b", "Viet Nam nine zero nine"),
    (r"\bsona\s+tower\b", "TSN Tower"),
    (r"\bsai\s*gon\s+tower\b", "TSN Tower"),
    (r"\bsaigon\s+tower\b", "TSN Tower"),
    (r"\btan\s+son\s+nhat\b", "Tan Son Nhat"),
    (r"\bnoy?\s*bai\b", "Noi Bai"),
    (r"\blater\s+to\s+land\b", "cleared to land"),
    (r"\bcontinue\s+of\s+course\b", "continue approach"),
    (r"\bcontinue\s+approach\s+over\s+to\s+ukraine\b", "continue approach"),
    (r"\bover\s+to\s+ukraine\b", ""),
    (r"\btwo\s+fellay\b", "two five"),
    (r"\bfellay\b", "five"),
    (r"\brunway\s+two\s+final\b", "runway two five"),
    (r"\bniner\b", "nine"),
    (r"\btree\b", "three"),
    (r"\bfife\b", "five"),
    (r"\bwun\b", "one"),
    (r"\bdegree\b", "degrees"),
)


def repair_radio_text(text: str) -> str:
    from reda.script_polish import polish_script_en

    out = collapse_loops(text or "")
    for pattern, repl in _RADIO_FIXES:
        out = re.sub(pattern, repl, out, flags=re.I)
    out = re.sub(r"\s+", " ", out).strip(" ,.-")
    out = collapse_loops(out)
    return polish_script_en(out)


def _write_wav_slice(src_samples, sr: int, t0: float, t1: float, dest: Path) -> None:
    a = max(0, int(t0 * sr))
    b = min(len(src_samples), int(t1 * sr))
    if b <= a:
        b = min(len(src_samples), a + int(0.4 * sr))
    chunk = np.asarray(src_samples[a:b], dtype=np.float32)
    peak = float(np.max(np.abs(chunk))) if len(chunk) else 0.0
    if 1e-4 < peak < 0.38:
        chunk = chunk * (0.72 / peak)
    pcm = np.clip(chunk * 32767.0, -32767, 32767).astype(np.int16)
    with wave.open(str(dest), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(pcm.tobytes())


def _decode_samples(model, samples: np.ndarray, hotwords: str) -> str:
    duration_s = max(0.4, len(samples) / 16000.0)
    token_cap = max(16, min(48, int(duration_s * 10) + 8))
    kwargs = {
        "language": "en",
        "beam_size": WHISPER_BEAM,
        "best_of": 1,
        "vad_filter": False,
        "without_timestamps": True,
        "condition_on_previous_text": False,
        "initial_prompt": ATC_PROMPT,
        "temperature": 0.0,
        "repetition_penalty": 1.08,
        "no_repeat_ngram_size": 3,
        "compression_ratio_threshold": 2.2,
        "log_prob_threshold": -0.85,
        "no_speech_threshold": 0.6,
        "max_new_tokens": token_cap,
        "word_timestamps": False,
    }
    if hotwords:
        kwargs["hotwords"] = hotwords
    audio = np.asarray(samples, dtype=np.float32)
    try:
        segments, _info = model.transcribe(audio, **kwargs)
    except (TypeError, ValueError):
        fd, tmp_name = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            _write_wav_slice(audio, 16000, 0.0, len(audio) / 16000.0, tmp)
            segments, _info = model.transcribe(str(tmp), **kwargs)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    bits = []
    for seg in segments:
        chunk = repair_radio_text((seg.text or "").strip())
        if chunk and len(chunk) >= 3:
            bits.append(chunk)
    return repair_radio_text(" ".join(bits))


def _open_pcm_pipe(ffmpeg: str, src: Path, af: str) -> subprocess.Popen:
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-af",
        af,
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "pipe:1",
    ]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        **tx._popen_flags(),
    )


def _read_pcm(proc: subprocess.Popen, n_samples: int) -> np.ndarray:
    if proc.stdout is None or n_samples <= 0:
        return np.zeros(0, dtype=np.float32)
    data = proc.stdout.read(n_samples * 2)
    if not data:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0


def _decode_window(model, wav: Path, duration_s: float, hotwords: str, streaming: bool = False) -> list[dict]:
    samples, sr = _read_wav_mono(wav)
    if sr != 16000 and sr > 0:
        # Pipe path always uses 16 kHz; file fallback already extracted at 16 kHz.
        pass
    text = _decode_samples(model, samples, hotwords)
    if not text:
        return []
    return [{"t_start": 0.0, "t_end": float(duration_s), "text": text}]


def transcribe_with_turns(src: Path, on_progress=None, on_turns=None) -> tuple[str, list[dict], str]:
    def note(pct: float, stage: str, text: str = "") -> None:
        if on_progress:
            on_progress(pct, stage, text)

    ffmpeg = tx.find_ffmpeg()
    if not ffmpeg:
        return "", [], "May nay chua co ffmpeg."
    if not src.is_file() or src.stat().st_size <= 0:
        return "", [], "File rong."
    note(4, "Đang mở luồng tiếng…")
    model = load_model()
    if model is None:
        return "", [], _MODEL_ERROR or "Khong co Whisper."
    hotwords = hotwords_for(filename=src.name)
    text, turns, err = _transcribe_stream(src, ffmpeg, model, hotwords, note, on_turns)
    if not err:
        return text, turns, ""
    note(10, "Luồng PCM lỗi, tách cả file…")
    return _transcribe_file_fallback(src, ffmpeg, model, hotwords, note, on_turns)


def _transcribe_stream(
    src: Path,
    ffmpeg: str,
    model,
    hotwords: str,
    note,
    on_turns,
) -> tuple[str, list[dict], str]:
    proc = None
    carry = np.zeros(0, dtype=np.float32)
    for af in (RADIO_AF, RADIO_AF_FALLBACK):
        proc = _open_pcm_pipe(ffmpeg, src, af)
        probe = _read_pcm(proc, 1600)
        if len(probe) > 0:
            carry = probe
            break
        try:
            proc.kill()
        except OSError:
            pass
        proc = None
    if proc is None:
        return "", [], "File khong co kenh tieng."
    sr = 16000
    hop_n = max(int(sr * STREAM_HOP_SEC), int(sr * 0.8))
    ov_n = max(int(sr * STREAM_OVERLAP_SEC), 0)
    step_n = max(1, hop_n - ov_n)
    t_cursor = 0.0
    turns: list[dict] = []
    parts: list[str] = []
    hop_i = 0
    try:
        note(12, "Đang ghi lời từng đoạn ~%.1fs…" % STREAM_HOP_SEC)
        while True:
            more = _read_pcm(proc, hop_n)
            if len(more):
                carry = np.concatenate([carry, more]) if len(carry) else more
            eof = len(more) == 0
            while len(carry) >= hop_n or (eof and len(carry) >= int(sr * 0.4)):
                take = hop_n if len(carry) >= hop_n else len(carry)
                window = carry[:take]
                rms = float(np.sqrt(np.mean(window * window) + 1e-12))
                t0 = t_cursor
                t1 = t_cursor + take / float(sr)
                if rms >= STREAM_MIN_RMS:
                    chunk = _decode_samples(model, window, hotwords)
                    if chunk:
                        parts.append(chunk)
                        turns.append({"t_start": t0, "t_end": t1, "text": chunk})
                        if on_turns:
                            on_turns([dict(t) for t in turns])
                hop_i += 1
                if take == hop_n:
                    t_cursor += step_n / float(sr)
                    carry = carry[step_n:]
                else:
                    t_cursor += take / float(sr)
                    carry = np.zeros(0, dtype=np.float32)
                joined = repair_radio_text(" ".join(parts))
                note(min(92.0, 12.0 + hop_i * 4.0), "Đang ghi lời English…", joined)
            if eof:
                break
        text = repair_radio_text(" ".join(t["text"] for t in turns) if turns else " ".join(parts))
        if not text:
            return "", [], "Whisper khong nghe ra loi English trong file nay."
        note(94, "Đã ghi lời English.", text)
        return text, turns, ""
    finally:
        try:
            if proc and proc.poll() is None:
                proc.kill()
        except OSError:
            pass


def _transcribe_file_fallback(
    src: Path,
    ffmpeg: str,
    model,
    hotwords: str,
    note,
    on_turns,
) -> tuple[str, list[dict], str]:
    folder = Path(tempfile.mkdtemp(prefix="atc-stt-"))
    wav = folder / "voice.wav"
    try:
        ok, err = _extract_wav(src, wav, ffmpeg)
        if not ok:
            return "", [], err
        samples, sr = _read_wav_mono(wav)
        samples, overlap = _apply_live_overlap(samples, sr, src.name)
        duration = len(samples) / float(sr or 1)
        hop = STREAM_HOP_SEC
        windows = []
        t = 0.0
        while t < duration:
            windows.append((t, min(duration, t + hop)))
            t += hop - STREAM_OVERLAP_SEC
        if not windows:
            windows = [(0.0, duration)]
        parts: list[str] = []
        turns: list[dict] = []
        for idx, (t0, t1) in enumerate(windows):
            a = int(t0 * sr)
            b = int(t1 * sr)
            window = samples[a:b]
            if len(window) < int(sr * 0.35):
                continue
            rms = float(np.sqrt(np.mean(window * window) + 1e-12))
            if rms < STREAM_MIN_RMS:
                continue
            chunk = _decode_samples(model, window, hotwords)
            if not chunk:
                continue
            parts.append(chunk)
            turns.append({"t_start": t0, "t_end": t1, "text": chunk})
            joined = repair_radio_text(" ".join(parts))
            pct = min(92.0, 18.0 + 74.0 * (t1 / max(duration, 0.01)))
            note(pct, "Đang ghi lời English…", joined)
            if on_turns:
                on_turns(_drop_overlap_turns([dict(t) for t in turns], overlap))
        turns = _drop_overlap_turns(turns, overlap)
        text = repair_radio_text(" ".join(t["text"] for t in turns) if turns else " ".join(parts))
        if not text:
            return "", [], "Whisper khong nghe ra loi English trong file nay."
        note(94, "Đã ghi lời English.", text)
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

    text, turns, err = transcribe_with_turns(
        src, on_progress=on_progress,
        on_turns=lambda turns: _job_update(job_id, turns=turns),
    )
    name = src.name if src else "clip"
    try:
        src.unlink(missing_ok=True)
    except OSError:
        pass
    if err:
        _job_update(job_id, done=True, error=err, percent=100)
        return
    _job_update(
        job_id,
        done=True,
        percent=100,
        stage="Xong.",
        text=text,
        turns=turns,
        analysis=None,
        error="",
    )
