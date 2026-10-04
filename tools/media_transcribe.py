"""Transcribe English from a recording file (not the microphone)."""
from __future__ import annotations

import gc
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
import wave
from pathlib import Path


def _cpu_thread_budget() -> int:
    raw = str(os.environ.get("ATC_WHISPER_THREADS") or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return max(1, int(raw))
    return 2


def _apply_low_mem_env() -> None:
    """Cap MKL/OpenMP arenas before numpy or CTranslate2 load."""
    threads = str(_cpu_thread_budget())
    os.environ.setdefault("CT2_PACKED_GEMM", "0")
    os.environ.setdefault("OMP_NUM_THREADS", threads)
    os.environ.setdefault("MKL_NUM_THREADS", threads)
    os.environ.setdefault("OPENBLAS_NUM_THREADS", threads)
    os.environ.setdefault("NUMEXPR_NUM_THREADS", threads)
    os.environ.setdefault("KMP_BLOCKTIME", "0")
    os.environ.setdefault("KMP_AFFINITY", "disabled")


_apply_low_mem_env()

import numpy as np

import app_paths
import media_transcode as tx
from asr_dataset.hotwords import hotwords_for
from asr_dataset.recipe import resolve_model_id
from asr_dataset.vocabulary import vocabulary_revision

MAX_UPLOAD_BYTES = tx.MAX_UPLOAD_BYTES
# CPU CTranslate2 / faster-whisper, English ATC radio only. No GPU / no torch
# at inference. Local turbo CT2 (ATCO2 + ATCoSIM, published WER 7.83%).
# Override with ATC_WHISPER_MODEL.
ATC_WHISPER_TURBO_DIR = app_paths.whisper_turbo_dir()
ATC_PROMPT = "Viet Nam Vietjet TSN Tower. Cleared to land. Squawk. QNH."
LIVE_OVERLAP_SEC = 0.75
STREAM_READ_SEC = 0.25
PTT_CLOSED_HANG_SEC = 0.8
PTT_FORCE_SEC = 8.0
STREAM_HOP_SEC = float(os.environ.get("ATC_STT_HOP", "2.0"))
STREAM_OVERLAP_SEC = 0.35
STREAM_MIN_RMS = 0.012
WHISPER_BEAM = max(1, int(os.environ.get("ATC_WHISPER_BEAM", "1")))
WHISPER_RETRY_BEAM = max(WHISPER_BEAM, int(os.environ.get("ATC_WHISPER_RETRY_BEAM", "1")))
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


def _is_live_name(src_name: str) -> bool:
    return str(src_name or "").lower().startswith("live-")


def _take_live_prefix(sr: int, src_name: str) -> tuple[np.ndarray, float]:
    global _live_tail, _live_tail_sr
    if not _is_live_name(src_name):
        return np.zeros(0, dtype=np.float32), 0.0
    stamp = re.search(r"live-(\d+)", str(src_name).lower())
    if stamp and int(stamp.group(1)) == 0:
        _live_tail = None
        return np.zeros(0, dtype=np.float32), 0.0
    if _live_tail is None or _live_tail_sr != sr or not len(_live_tail):
        return np.zeros(0, dtype=np.float32), 0.0
    prefix = np.array(_live_tail, dtype=np.float32, copy=True)
    return prefix, float(len(prefix) / sr)


def _store_live_tail(samples: np.ndarray, sr: int, src_name: str) -> None:
    global _live_tail, _live_tail_sr
    if not _is_live_name(src_name) or samples is None or not len(samples):
        if not _is_live_name(src_name):
            _live_tail = None
        return
    n = max(1, int(LIVE_OVERLAP_SEC * sr))
    _live_tail = np.array(samples[-n:], dtype=np.float32, copy=True)
    _live_tail_sr = sr


def _apply_live_overlap(samples: np.ndarray, sr: int, src_name: str) -> tuple[np.ndarray, float]:
    prefix, overlap = _take_live_prefix(sr, src_name)
    if len(prefix):
        samples = np.concatenate([prefix, samples])
    _store_live_tail(samples, sr, src_name)
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
_INFER_LOCK = threading.Lock()
_FILE_JOB_LOCK = threading.Lock()
_MODEL_ERROR = ""
_MODEL_LOAD_STATE = {"phase": "idle", "progress": 0, "message": ""}


def _set_model_load_state(phase: str, progress: int | float, message: str) -> None:
    global _MODEL_LOAD_STATE
    pct = max(0, min(100, int(float(progress))))
    _MODEL_LOAD_STATE = {
        "phase": phase,
        "progress": pct,
        "message": str(message or ""),
    }


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
            "vocabulary_revision": job.get("vocabulary_revision") or "",
        }


def sweep_jobs(max_age: float = 900) -> None:
    now = time.time()
    with _JOBS_LOCK:
        stale = [jid for jid, job in _JOBS.items() if job.get("done") and now - float(job.get("finished") or job.get("created") or 0) > max_age]
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
        return resolve_model_id(env)
    turbo = app_paths.whisper_turbo_dir()
    if _local_ct2_ready(turbo):
        return str(turbo)
    return str(turbo)


WHISPER_MODEL = _resolve_model_id()


def _is_memory_error(exc: BaseException | str) -> bool:
    text = str(exc or "").lower()
    needles = (
        "mkl_malloc",
        "failed to allocate",
        "cannot allocate",
        "out of memory",
        "memoryerror",
        "std::bad_alloc",
        "not enough memory",
        "paged out",
    )
    return any(needle in text for needle in needles)


def memory_status() -> dict:
    """Probe physical RAM + commit/pagefile (Windows MEMORYSTATUSEX)."""
    out: dict = {
        "ok": True,
        "platform": os.name,
        "pagefile_enabled": None,
        "ram_total_mb": None,
        "ram_avail_mb": None,
        "commit_total_mb": None,
        "commit_avail_mb": None,
    }
    if os.name != "nt":
        return out
    try:
        import ctypes
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return out
        ram_total = int(stat.ullTotalPhys)
        commit_total = int(stat.ullTotalPageFile)
        out["ram_total_mb"] = round(ram_total / (1024 * 1024))
        out["ram_avail_mb"] = round(int(stat.ullAvailPhys) / (1024 * 1024))
        out["commit_total_mb"] = round(commit_total / (1024 * 1024))
        out["commit_avail_mb"] = round(int(stat.ullAvailPageFile) / (1024 * 1024))
        # Pagefile present when commit limit clearly exceeds physical RAM.
        out["pagefile_enabled"] = commit_total > ram_total + 256 * 1024 * 1024
        out["memory_load_pct"] = int(stat.dwMemoryLoad)
    except Exception as exc:
        out["ok"] = False
        out["error"] = str(exc)
    return out


def _friendly_model_error(exc: BaseException | str) -> str:
    raw = str(exc).strip() or "không tải được mô hình"
    if not _is_memory_error(exc):
        return "Không tải được mô hình Whisper: " + raw
    mem = memory_status()
    page_on = mem.get("pagefile_enabled")
    avail = mem.get("ram_avail_mb")
    bits = ["Hết RAM khi nạp bộ nhận dạng (mkl_malloc)."]
    if avail is not None:
        bits.append("RAM trống khoảng %s MB." % avail)
    if page_on is True:
        bits.append(
            "Pagefile Windows đang bật — đóng app nặng (Edge/Chrome nhiều tab, IDE), "
            "rồi khởi động lại ATC Desk; không cần bật lại pagefile."
        )
    elif page_on is False:
        bits.append(
            "Pagefile đang tắt hoặc rất nhỏ — bật Virtual Memory trong Windows, "
            "rồi khởi động lại ATC Desk."
        )
    else:
        bits.append("Đóng app khác rồi khởi động lại ATC Desk.")
    bits.append("Chi tiết: " + raw)
    return " ".join(bits)


def _unload_model() -> None:
    global _MODEL
    _MODEL = None
    gc.collect()


def _model_candidates() -> list[str]:
    names: list[str] = []
    env = (os.environ.get("ATC_WHISPER_MODEL") or "").strip()
    turbo = str(app_paths.whisper_turbo_dir())
    if env:
        names.append(resolve_model_id(env))
    if turbo not in names:
        names.append(turbo)
    return names


def _thread_attempts() -> list[int]:
    budget = _cpu_thread_budget()
    seen: list[int] = []
    for value in (budget, 1):
        if value not in seen:
            seen.append(value)
    return seen


def _warmup_model(model) -> None:
    segments, _info = model.transcribe(
        np.zeros(4000, dtype=np.float32),
        language="en",
        beam_size=1,
        vad_filter=False,
        without_timestamps=True,
    )
    list(segments)


def load_model():
    global _MODEL, _MODEL_ERROR, WHISPER_MODEL
    with _MODEL_LOCK:
        if _MODEL is not None:
            _set_model_load_state("ready", 100, "Bộ nhận dạng sẵn sàng")
            return _MODEL
        if _MODEL_ERROR:
            _set_model_load_state("error", 100, _MODEL_ERROR)
            return None
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            _MODEL_ERROR = "Máy này chưa cài faster-whisper. pip install faster-whisper."
            _set_model_load_state("error", 100, _MODEL_ERROR)
            return None
        last_exc: Exception | None = None
        candidates = _model_candidates()
        attempts = _thread_attempts()
        total = max(1, len(candidates) * len(attempts))
        for idx, name in enumerate(candidates):
            for jdx, threads in enumerate(attempts):
                progress = 10 + ((idx * len(attempts)) + jdx) * 80 / total
                _set_model_load_state(
                    "loading",
                    progress,
                    "Đang nạp bộ nhận dạng... %s (%s thread)" % (name, threads),
                )
                try:
                    print(
                        "  Transcribe EN: dang tai model '%s' (%s/%s, %s thread)..."
                        % (name, WHISPER_DEVICE, WHISPER_COMPUTE, threads),
                        flush=True,
                    )
                    kwargs_model = dict(
                        device=WHISPER_DEVICE,
                        compute_type=WHISPER_COMPUTE,
                        download_root=str(_model_cache_dir()),
                    )
                    try:
                        model = WhisperModel(
                            name, cpu_threads=threads, num_workers=1, **kwargs_model
                        )
                    except TypeError:
                        model = WhisperModel(name, **kwargs_model)
                    _warmup_model(model)
                    _MODEL = model
                    WHISPER_MODEL = name
                    _MODEL_ERROR = ""
                    _set_model_load_state("ready", 100, "Bộ nhận dạng sẵn sàng")
                    print(
                        "  Transcribe EN: whisper %s (%s/%s, %s thread)"
                        % (name, WHISPER_DEVICE, WHISPER_COMPUTE, threads),
                        flush=True,
                    )
                    return _MODEL
                except Exception as exc:
                    last_exc = exc
                    print("  Transcribe EN: bo qua '%s'/%s thread: %s" % (name, threads, exc), flush=True)
                    _unload_model()
        _MODEL_ERROR = _friendly_model_error(last_exc or "khong tai duoc mo hinh")
        _set_model_load_state("error", 100, _MODEL_ERROR)
        return None


def schedule_model_preload() -> None:
    if _MODEL is not None or _MODEL_ERROR:
        return
    if _MODEL_LOAD_STATE.get("phase") == "loading":
        return

    def worker() -> None:
        _set_model_load_state("loading", 6, "Đang nạp bộ nhận dạng...")
        load_model()

    threading.Thread(target=worker, daemon=True).start()


def model_status() -> dict:
    mem = memory_status()
    state = dict(_MODEL_LOAD_STATE)
    if _MODEL is not None:
        state.update({"phase": "ready", "progress": 100, "message": "Bộ nhận dạng sẵn sàng"})
    elif _MODEL_ERROR:
        state.update({"phase": "error", "progress": 100, "message": _MODEL_ERROR})
    elif _MODEL_LOAD_STATE.get("phase") in ("idle", "loading"):
        state.setdefault("phase", "loading")
        state.setdefault("progress", 0)
        state.setdefault("message", "Đang nạp bộ nhận dạng...")
    return {
        "ok": True,
        "ready": _MODEL is not None,
        "loading": _MODEL is None and not _MODEL_ERROR and state.get("phase") == "loading",
        "error": _MODEL_ERROR or "",
        "phase": state.get("phase", "idle"),
        "progress": int(state.get("progress", 0)),
        "message": state.get("message", ""),
        "model": WHISPER_MODEL,
        "compute": WHISPER_COMPUTE,
        "threads": _cpu_thread_budget(),
        "pagefile_enabled": mem.get("pagefile_enabled"),
        "ram_total_mb": mem.get("ram_total_mb"),
        "ram_avail_mb": mem.get("ram_avail_mb"),
        "commit_total_mb": mem.get("commit_total_mb"),
        "commit_avail_mb": mem.get("commit_avail_mb"),
    }


def warm_model() -> None:
    if _MODEL is not None:
        _set_model_load_state("ready", 100, "Bộ nhận dạng sẵn sàng")
        return
    model = load_model()
    if model is not None:
        print(
            "  Transcribe EN: whisper %s (%s/%s, %s thread)"
            % (WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE, _cpu_thread_budget()),
            flush=True,
        )
        return
    if _MODEL_ERROR:
        print("  Transcribe EN: %s" % _MODEL_ERROR, flush=True)


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
        return []
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
        return []
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


def _energy_slices(samples: np.ndarray, sr: int, hop_sec: float = 3.0) -> list[tuple[float, float]]:
    if samples is None or not len(samples):
        return []
    hop = max(int(sr * hop_sec), int(sr * 0.8))
    out: list[tuple[float, float]] = []
    i = 0
    min_n = int(sr * 0.35)
    while i < len(samples):
        j = min(len(samples), i + hop)
        chunk = samples[i:j]
        if j - i >= min_n:
            rms = float(np.sqrt(np.mean(chunk * chunk) + 1e-12))
            if rms >= STREAM_MIN_RMS * 0.45:
                out.append((i / float(sr), j / float(sr)))
        i = j
    return out


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
    # ASR: "sion way" ≈ taxiway/runway; must run before "sion + digit → Vietjet".
    (r"\bsion\s+ways?\b", "taxiway"),
    (r"\bsion\s+(?=one|two|three|four|five|six|seven|eight|nine|zero)", "Vietjet "),
    (r"\bvietjen\b", "Vietjet"),
    (r"\bvietjin\b", "Vietjet"),
    (r"\bviet\s*jen\b", "Vietjet"),
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
    (r"\b(?:runway|rwy|taxiway|twy)\s+two\s+final(?:ly)?\b", "runway two five"),
    (r"\b(?:runway|rwy|taxiway|twy)\s+(\d)\s+final(?:ly)?\b", r"runway \1 five"),
    (r"\btwo\s+finally\b", "two five"),
    (r"\b(\d)\s+finally\b", r"\1 five"),
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


def _normalize_decode_audio(samples: np.ndarray) -> np.ndarray:
    audio = np.asarray(samples, dtype=np.float32)
    if not len(audio):
        return audio
    audio = audio - float(np.mean(audio))
    peak = float(np.max(np.abs(audio)))
    if peak > 0.98:
        audio = audio * (0.98 / peak)
    rms = float(np.sqrt(np.mean(audio * audio) + 1e-12))
    if 0 < rms < 0.045:
        gain = min(2.8, 0.075 / max(rms, 1e-6))
        audio = np.clip(audio * gain, -1.0, 1.0)
    return np.asarray(audio, dtype=np.float32)


def _score_text_quality(text: str) -> float:
    words = re.findall(r"[A-Za-z0-9']+", text or "")
    if not words:
        return -10.0
    score = float(min(16, len(words))) * 0.45
    low = " ".join(words).lower()
    hints = (
        "tower",
        "runway",
        "cleared",
        "approach",
        "squawk",
        "qnh",
        "descend",
        "climb",
        "flight level",
        "line up",
        "hold short",
    )
    score += 1.25 * sum(1 for hint in hints if hint in low)
    score -= 0.9 * len(re.findall(r"\b(\w+)(?:\s+\1){2,}\b", low))
    if len(words) <= 2:
        score -= 2.0
    return score


def _transcribe_texts(model, audio: np.ndarray, kwargs: dict, tmp_path: Path | None = None) -> list[str]:
    try:
        segments, _info = model.transcribe(audio, **kwargs)
        return [(seg.text or "").strip() for seg in segments]
    except Exception as exc:
        if _is_memory_error(exc):
            raise RuntimeError(_friendly_model_error(exc)) from exc
        if not isinstance(exc, (TypeError, ValueError)):
            raise
        fd, tmp_name = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            _write_wav_slice(audio, 16000, 0.0, len(audio) / 16000.0, tmp)
            segments, _info = model.transcribe(str(tmp), **kwargs)
            return [(seg.text or "").strip() for seg in segments]
        except Exception as inner:
            if _is_memory_error(inner):
                raise RuntimeError(_friendly_model_error(inner)) from inner
            raise
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass


def _safe_decode(model, window: np.ndarray, hotwords: str) -> tuple[str, str]:
    try:
        return _decode_samples(model, window, hotwords), ""
    except Exception as exc:
        if _is_memory_error(exc):
            return "", _friendly_model_error(exc)
        return "", "Ghi lời bị lỗi: %s" % exc


def _decode_samples(
    model,
    samples: np.ndarray,
    hotwords: str,
    *,
    beam_size: int | None = None,
    best_of: int | None = None,
) -> str:
    duration_s = max(0.4, len(samples) / 16000.0)
    token_cap = max(24, min(192, int(duration_s * 16) + 24))
    active_beam = WHISPER_BEAM if beam_size is None else max(1, int(beam_size))
    active_best_of = 1 if best_of is None else max(1, int(best_of))
    retry_beam = max(active_beam, WHISPER_RETRY_BEAM)
    kwargs = {
        "language": "en",
        "beam_size": active_beam,
        "best_of": active_best_of,
        "vad_filter": False,
        "without_timestamps": True,
        "condition_on_previous_text": False,
        "initial_prompt": ATC_PROMPT,
        "temperature": 0.0,
        "repetition_penalty": 1.08,
        "no_repeat_ngram_size": 3,
        "compression_ratio_threshold": 2.2,
        "log_prob_threshold": -0.85,
        "no_speech_threshold": 0.5,
        "max_new_tokens": token_cap,
        "word_timestamps": False,
    }
    if hotwords:
        tokenizer = getattr(model, "hf_tokenizer", None)
        if tokenizer is not None:
            tokens = tokenizer.encode(hotwords, add_special_tokens=False).ids
            hotwords = tokenizer.decode(tokens[:160])
        kwargs["hotwords"] = hotwords
    audio = _normalize_decode_audio(samples)
    with _INFER_LOCK:
        texts = _transcribe_texts(model, audio, kwargs)
        first = repair_radio_text(" ".join(t for t in texts if t))
        if (
            duration_s >= 0.9
            and retry_beam > active_beam
            and _score_text_quality(first) < 3.2
        ):
            kwargs_retry = dict(kwargs)
            kwargs_retry["beam_size"] = retry_beam
            kwargs_retry["best_of"] = min(3, retry_beam)
            retry_texts = _transcribe_texts(model, audio, kwargs_retry)
            retry = repair_radio_text(" ".join(t for t in retry_texts if t))
            if _score_text_quality(retry) >= _score_text_quality(first):
                texts = retry_texts
    bits = []
    for text in texts:
        chunk = repair_radio_text(text)
        if chunk and len(chunk) >= 3:
            bits.append(chunk)
    return repair_radio_text(" ".join(bits))


def _open_pcm_pipe(
    ffmpeg: str,
    src: Path,
    af: str,
    max_sec: float | None = None,
) -> subprocess.Popen:
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
    ]
    if max_sec and max_sec > 0:
        cmd += ["-t", "%.2f" % float(max_sec)]
    cmd += [
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


def _ready_ptt_slices(
    samples: np.ndarray,
    sr: int,
    *,
    eof: bool,
    emitted_until: float,
    origin: float,
) -> list[tuple[float, float, int, int]]:
    """Return closed PTT slices as (abs_start, abs_end, i0, i1) not yet emitted."""
    if samples is None or not len(samples):
        return []
    # Remove already decoded sound before estimating the noise floor. Otherwise
    # a loud first call can mask all later, quieter calls in the same buffer.
    skip = max(0, min(len(samples), int((emitted_until - origin) * sr)))
    remaining = samples[skip:]
    offset = skip / float(sr)
    windows = ptt_windows(remaining, sr)
    if not windows:
        windows = _energy_slices(remaining, sr, hop_sec=PTT_FORCE_SEC)
    windows = [(a + offset, b + offset) for a, b in windows]
    dur = len(samples) / float(sr or 1)
    abs_end = origin + dur
    out: list[tuple[float, float, int, int]] = []
    pad = int(0.06 * sr)
    for a, b in windows:
        abs_a = origin + a
        abs_b = origin + b
        if abs_b <= emitted_until + 0.05:
            continue
        abs_a = max(abs_a, emitted_until)
        span = abs_b - abs_a
        trailing = abs_end - abs_b
        force = span >= PTT_FORCE_SEC
        closed = eof or trailing >= PTT_CLOSED_HANG_SEC or force
        if not closed or abs_b - abs_a < 0.35:
            continue
        while abs_a < abs_b - 0.3:
            end = min(abs_b, abs_a + PTT_FORCE_SEC)
            if not eof and abs_b - end < 0.25 and trailing < PTT_CLOSED_HANG_SEC and end - abs_a < PTT_FORCE_SEC:
                break
            i0 = max(0, int((abs_a - origin) * sr) - pad)
            i1 = min(len(samples), int((end - origin) * sr) + pad)
            out.append((abs_a, end, i0, i1))
            abs_a = end
    return out


def transcribe_with_turns(src: Path, on_progress=None, on_turns=None, filename: str = "") -> tuple[str, list[dict], str]:
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
    hotwords = hotwords_for(filename=filename or src.name)
    text, turns, err = _transcribe_stream(src, ffmpeg, model, hotwords, note, on_turns)
    if not err and (text or turns):
        return text, turns, ""
    if err and _is_memory_error(err):
        return text, turns, err
    if _is_live_name(src.name):
        note(10, "Luồng LIVE lỗi, tách cả file…")
    else:
        note(10, "Đang tách cả file để ghi lời ổn định…")
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
    max_sec = 16.0 if _is_live_name(src.name) else None
    for af in (RADIO_AF, RADIO_AF_FALLBACK):
        proc = _open_pcm_pipe(ffmpeg, src, af, max_sec)
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
    prefix, overlap = _take_live_prefix(sr, src.name)
    if len(prefix):
        carry = np.concatenate([prefix, carry])
    origin = 0.0
    emitted_until = 0.0
    turns: list[dict] = []
    parts: list[str] = []
    read_n = max(int(sr * STREAM_READ_SEC), 800)
    heard = len(carry) / float(sr)
    tail = np.zeros(0, dtype=np.float32)
    try:
        note(12, "Đang ghi lời theo từng lần PTT…")
        while True:
            more = _read_pcm(proc, read_n)
            if len(more):
                carry = np.concatenate([carry, more]) if len(carry) else more
            eof = len(more) == 0
            heard = origin + len(carry) / float(sr)
            ready = _ready_ptt_slices(
                carry, sr, eof=eof, emitted_until=emitted_until, origin=origin
            )
            for abs_a, abs_b, i0, i1 in ready:
                window = carry[i0:i1]
                rms = float(np.sqrt(np.mean(window * window) + 1e-12))
                if rms < STREAM_MIN_RMS * 0.45:
                    emitted_until = max(emitted_until, abs_b)
                    continue
                chunk, derr = _safe_decode(model, window, hotwords)
                if derr:
                    joined = repair_radio_text(" ".join(parts))
                    note(100, derr, joined)
                    return joined, _drop_overlap_turns(turns, overlap), derr
                if chunk:
                    parts.append(chunk)
                    turns.append({"t_start": abs_a, "t_end": abs_b, "text": chunk})
                    if on_turns:
                        on_turns(_drop_overlap_turns([dict(t) for t in turns], overlap))
                emitted_until = max(emitted_until, abs_b)
                joined = repair_radio_text(" ".join(parts))
                pct = min(92.0, 12.0 + 80.0 * (emitted_until / max(heard, 0.5)))
                note(pct, "Đang ghi lời English…", joined)
            if not ready and len(carry) >= int(sr * 2.5):
                quiet_n = len(carry) - int(sr * 0.5)
                if quiet_n > int(sr * 0.8):
                    head = carry[:quiet_n]
                    rms = float(np.sqrt(np.mean(head * head) + 1e-12))
                    if rms < STREAM_MIN_RMS * 0.45:
                        emitted_until = max(emitted_until, origin + quiet_n / float(sr))
            trim = emitted_until - origin - 0.25
            if trim > 1.2:
                n = int(trim * sr)
                if 0 < n < len(carry):
                    if _is_live_name(src.name):
                        tail = np.concatenate([tail, carry[:n]]) if len(tail) else carry[:n].copy()
                    carry = carry[n:]
                    origin += n / float(sr)
            if eof:
                break
        if _is_live_name(src.name):
            whole = np.concatenate([tail, carry]) if len(tail) and len(carry) else (tail if len(tail) else carry)
            _store_live_tail(whole, sr, src.name)
        turns = _drop_overlap_turns(turns, overlap)
        text = repair_radio_text(" ".join(t["text"] for t in turns) if turns else " ".join(parts))
        if not text:
            if _is_live_name(src.name):
                note(100, "Đoạn yên.", "")
                return "", [], ""
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
        note(8, "Đang tách tiếng từ file…")
        ok, err = _extract_wav(src, wav, ffmpeg)
        if not ok:
            return "", [], err
        note(16, "Đang tìm từng lần PTT…")
        samples, sr = _read_wav_mono(wav)
        samples, overlap = _apply_live_overlap(samples, sr, src.name)
        duration = len(samples) / float(sr or 1)
        windows = ptt_windows(samples, sr)
        if not windows:
            windows = _energy_slices(samples, sr)
        if not windows and duration <= 20:
            windows = [(0.0, duration)]
        split: list[tuple[float, float]] = []
        for t0, t1 in windows:
            a = t0
            while a < t1:
                b = min(t1, a + PTT_FORCE_SEC)
                split.append((a, b))
                a = b
        windows = split or windows
        parts: list[str] = []
        turns: list[dict] = []
        pad = int(0.06 * (sr or 16000))
        total = max(len(windows), 1)
        for idx, (t0, t1) in enumerate(windows):
            if t1 - t0 > PTT_FORCE_SEC + 0.2:
                t1 = t0 + PTT_FORCE_SEC
            a = max(0, int(t0 * sr) - pad)
            b = min(len(samples), int(t1 * sr) + pad)
            window = samples[a:b]
            if len(window) < int(sr * 0.3):
                continue
            rms = float(np.sqrt(np.mean(window * window) + 1e-12))
            if rms < STREAM_MIN_RMS * 0.5:
                continue
            chunk, derr = _safe_decode(model, window, hotwords)
            if derr:
                joined = repair_radio_text(" ".join(parts))
                note(100, derr, joined)
                return joined, _drop_overlap_turns(turns, overlap), derr
            if not chunk:
                continue
            parts.append(chunk)
            turns.append({"t_start": t0, "t_end": t1, "text": chunk})
            joined = repair_radio_text(" ".join(parts))
            pct = min(92.0, 18.0 + 74.0 * ((idx + 1) / total))
            note(pct, "Đang ghi lời English…", joined)
            if on_turns:
                on_turns(_drop_overlap_turns([dict(t) for t in turns], overlap))
        turns = _drop_overlap_turns(turns, overlap)
        text = repair_radio_text(" ".join(t["text"] for t in turns) if turns else " ".join(parts))
        if not text:
            if _is_live_name(src.name):
                note(100, "Đoạn yên.", "")
                return "", [], ""
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


def start_job(src: Path, filename: str = "") -> str:
    job_id = uuid.uuid4().hex[:12]
    early_error = ""
    if _MODEL is None and _MODEL_ERROR:
        early_error = _MODEL_ERROR
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "id": job_id,
            "percent": 1.0,
            "stage": "Đã nhận file, bắt đầu ghi lời…",
            "text": "",
            "turns": [],
            "analysis": None,
            "done": bool(early_error),
            "error": early_error,
            "src": src,
            "filename": filename or src.name,
            "created": time.time(),
        }
    if early_error:
        return job_id
    threading.Thread(target=_run_job, args=(job_id, src), daemon=True).start()
    return job_id


def _run_job(job_id: str, src: Path) -> None:
    def on_progress(pct: float, stage: str, text: str = "") -> None:
        fields = {"percent": round(pct, 1), "stage": stage}
        if text:
            fields["text"] = text
        _job_update(job_id, **fields)

    text, turns, err = "", [], ""
    try:
        _job_update(job_id, stage="Đang nạp bộ nhận dạng (lần đầu có thể 2–4 phút)…")
        with _FILE_JOB_LOCK:
            _job_update(job_id, vocabulary_revision=vocabulary_revision())
            filename = _JOBS.get(job_id, {}).get("filename", "")
            extra = {"filename": filename} if filename else {}
            text, turns, err = transcribe_with_turns(
                src, on_progress=on_progress,
                on_turns=lambda turns: _job_update(job_id, turns=turns), **extra,
            )
    except Exception as exc:
        err = _friendly_model_error(exc) if _is_memory_error(exc) else ("Ghi lời bị lỗi: %s" % exc)
    _job_update(job_id, finished=time.time())
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
