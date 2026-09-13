"""AVI/other containers to browser MP4/M4A with a shared conversion deadline."""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

MAX_UPLOAD_BYTES = 512 * 1024 * 1024
CONVERT_SECONDS = 285  # Leave time for the local upload/download within five minutes.
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
ProgressFn = Callable[[float, str], None]

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
_FFMPEG: str | None | bool = False
_GPU: tuple[str, list[str], str] | None | bool = False
_LAST_STRATEGY = ""

H264 = {"h264", "avc1"}
AAC = {"aac"}
REMUX_AUDIO = {"aac", "mp3", "mp2"}
CPU_X264 = (
    "libx264",
    [
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-crf",
        "28",
        "-threads",
        "0",
        "-bf",
        "0",
        "-refs",
        "1",
        "-g",
        "50",
    ],
    "Đang chuyển sang MP4…",
)
GPU_CANDIDATES = [
    ("h264_nvenc", ["-preset", "p1", "-rc", "vbr", "-cq", "28", "-b:v", "0", "-bf", "0"], "Đang encode GPU (NVENC)…"),
    ("h264_qsv", ["-preset", "veryfast", "-global_quality", "28"], "Đang encode GPU (QSV)…"),
    ("h264_amf", ["-quality", "speed", "-rc", "cqp", "-qp_i", "28"], "Đang encode GPU (AMD)…"),
]


@dataclass
class TranscodeResult:
    ok: bool
    mime: str = ""
    name: str = ""
    path: Path | None = None
    duration: float = 0.0
    error: str = ""


def find_ffmpeg() -> str | None:
    global _FFMPEG
    if _FFMPEG is not False:
        return None if _FFMPEG is None else str(_FFMPEG)
    found = shutil.which("ffmpeg")
    if not found:
        local = os.environ.get("LOCALAPPDATA") or ""
        candidates = [
            Path(local) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
        ]
        for item in candidates:
            if item.is_file() and item.name.lower().startswith("ffmpeg"):
                found = str(item)
                break
        if not found:
            packages = Path(local) / "Microsoft" / "WinGet" / "Packages"
            if packages.is_dir():
                matches = sorted(packages.glob("Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe"))
                if matches:
                    found = str(matches[-1])
    _FFMPEG = found or None
    return None if _FFMPEG is None else str(_FFMPEG)


def find_ffprobe(ffmpeg: str | None = None) -> str | None:
    found = shutil.which("ffprobe")
    if found:
        return found
    exe = Path(ffmpeg or find_ffmpeg() or "")
    if exe.is_file():
        probe = exe.with_name("ffprobe.exe" if exe.suffix.lower() == ".exe" else "ffprobe")
        if probe.is_file():
            return str(probe)
    return None


def _popen_flags() -> dict:
    flags: dict = {}
    if os.name == "nt":
        flags["creationflags"] = CREATE_NO_WINDOW
    return flags


def _kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt" and proc.pid:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            **_popen_flags(),
        )
    else:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=5)
    except Exception:
        pass


def _run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess[bytes]:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_popen_flags())
    try:
        out, err = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        raise


def _io_timeout(src: Path, base: int = 45) -> int:
    try:
        mb = src.stat().st_size / (1024 * 1024)
    except OSError:
        mb = 1
    return int(min(480, max(base, 30 + mb * 1.5)))


def _ok_file(path: Path, min_size: int = 64) -> bool:
    try:
        return path.is_file() and path.stat().st_size > min_size
    except OSError:
        return False


def _smoke_encoder(ffmpeg: str, codec: str, extra: list[str]) -> bool:
    folder = Path(tempfile.mkdtemp(prefix="atc-enc-"))
    out = folder / "t.mp4"
    try:
        proc = _run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=0.08:size=160x90:rate=10",
                "-c:v",
                codec,
                *extra,
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(out),
            ],
            timeout=8,
        )
        return proc.returncode == 0 and _ok_file(out, 32)
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        try:
            if out.is_file():
                out.unlink()
            folder.rmdir()
        except OSError:
            pass


def gpu_encoder(ffmpeg: str) -> tuple[str, list[str], str] | None:
    global _GPU
    if _GPU is not False:
        return None if _GPU is None else _GPU
    for codec, extra, stage in GPU_CANDIDATES:
        if _smoke_encoder(ffmpeg, codec, extra):
            _GPU = (codec, extra, stage)
            return _GPU
    _GPU = None
    return None


def pick_video_encoder(ffmpeg: str) -> tuple[str, list[str], str]:
    gpu = gpu_encoder(ffmpeg)
    return gpu if gpu else CPU_X264


def warm_encoder() -> None:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return
    gpu = gpu_encoder(ffmpeg)
    if gpu:
        print("  Convert video: benchmark %s / libx264" % gpu[0], flush=True)
    else:
        print("  Convert video: libx264 ultrafast", flush=True)


def _safe_stem(name: str) -> str:
    stem = Path(name or "clip").stem.strip() or "clip"
    cleaned = "".join(ch if ch.isalnum() or ch in "-_ ." else "_" for ch in stem)
    return cleaned[:80] or "clip"


_VIDEO_FCC = {
    b"H264": "h264",
    b"h264": "h264",
    b"AVC1": "h264",
    b"avc1": "h264",
    b"X264": "h264",
    b"x264": "h264",
    b"XVID": "mpeg4",
    b"DIVX": "mpeg4",
    b"DX50": "mpeg4",
    b"MP4V": "mpeg4",
    b"MP42": "mpeg4",
    b"MP43": "mpeg4",
    b"FMP4": "mpeg4",
    b"DIV3": "mpeg4",
    b"MJPG": "mjpeg",
    b"mjpg": "mjpeg",
    b"JPEG": "mjpeg",
}


def peek_avi(src: Path) -> dict:
    """Read only the AVI header (≤256 KB). Never scan the whole 250 MB file."""
    info = {
        "duration": 0.0,
        "vcodec": "",
        "acodec": "",
        "width": 0,
        "height": 0,
        "has_video": False,
        "has_audio": False,
    }
    try:
        with src.open("rb") as fh:
            buf = fh.read(262144)
    except OSError:
        return info
    if len(buf) < 44 or buf[0:4] != b"RIFF" or buf[8:12] not in (b"AVI ", b"AVIX"):
        return info

    def walk(start: int, end: int) -> None:
        i = start
        while i + 8 <= end:
            ck = buf[i : i + 4]
            sz = int.from_bytes(buf[i + 4 : i + 8], "little")
            data = i + 8
            nxt = data + sz + (sz & 1)
            if nxt > end + 1 or sz < 0:
                break
            chunk_end = min(data + sz, end)
            if ck == b"LIST" and data + 4 <= chunk_end:
                walk(data + 4, chunk_end)
            elif ck == b"avih" and sz >= 40:
                usec = int.from_bytes(buf[data : data + 4], "little")
                frames = int.from_bytes(buf[data + 16 : data + 20], "little")
                if usec and frames:
                    info["duration"] = frames * usec / 1_000_000.0
                info["width"] = int.from_bytes(buf[data + 32 : data + 36], "little")
                info["height"] = int.from_bytes(buf[data + 36 : data + 40], "little")
            elif ck == b"strh" and sz >= 8:
                fcc = buf[data : data + 4]
                handler = buf[data + 4 : data + 8]
                if fcc == b"vids":
                    info["has_video"] = True
                    info["vcodec"] = _VIDEO_FCC.get(handler, handler.decode("latin-1", "replace").lower().strip("\x00"))
                elif fcc == b"auds":
                    info["has_audio"] = True
            elif ck == b"strf" and sz >= 2 and info["has_audio"] and not info["acodec"]:
                tag = int.from_bytes(buf[data : data + 2], "little")
                if tag == 1:
                    info["acodec"] = "pcm_s16le"
                elif tag == 85:
                    info["acodec"] = "mp3"
                elif tag in (255, 7468, 41222):
                    info["acodec"] = "aac"
            i = nxt

    walk(12, len(buf))
    if not info["has_video"]:
        info["has_video"] = True
    return info


def probe_media(src: Path, ffmpeg: str) -> dict:
    info = {
        "duration": 0.0,
        "vcodec": "",
        "acodec": "",
        "width": 0,
        "height": 0,
        "has_video": False,
        "has_audio": False,
    }
    probe = find_ffprobe(ffmpeg)
    if not probe:
        return info
    try:
        proc = _run(
            [
                probe,
                "-v",
                "error",
                "-probesize",
                "512000",
                "-analyzeduration",
                "500000",
                "-print_format",
                "json",
                "-show_entries",
                "format=duration,bit_rate,size:stream=codec_type,codec_name,width,height,duration,nb_frames",
                str(src),
            ],
            timeout=2,
        )
        data = json.loads((proc.stdout or b"{}").decode("utf-8", "replace") or "{}")
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, TypeError):
        return info
    try:
        info["duration"] = float((data.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        info["duration"] = 0.0
    for stream in data.get("streams") or []:
        kind = stream.get("codec_type")
        codec = str(stream.get("codec_name") or "").lower()
        if kind == "video" and not info["has_video"]:
            info["has_video"] = True
            info["vcodec"] = codec
            try:
                info["width"] = int(stream.get("width") or 0)
                info["height"] = int(stream.get("height") or 0)
            except (TypeError, ValueError):
                pass
        elif kind == "audio" and not info["has_audio"]:
            info["has_audio"] = True
            info["acodec"] = codec
    return info


def _parse_out_time(line: str) -> float | None:
    if line.startswith("out_time_us="):
        raw = line.split("=", 1)[1].strip()
        if raw.isdigit():
            return int(raw) / 1_000_000.0
    if line.startswith("out_time="):
        raw = line.split("=", 1)[1].strip()
        if not raw or raw == "N/A":
            return None
        try:
            hms, _, frac = raw.partition(".")
            parts = hms.split(":")
            if len(parts) != 3:
                return None
            seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            micro = int((frac + "000000")[:6]) if frac else 0
            return seconds + micro / 1_000_000.0
        except ValueError:
            return None
    return None


def _kill(proc: subprocess.Popen) -> None:
    _kill_tree(proc)


def _encode_progress(
    ffmpeg: str,
    args: list[str],
    duration: float,
    on_progress: ProgressFn | None,
    stage: str,
    timeout: int = 600,
    cancel: threading.Event | None = None,
) -> subprocess.CompletedProcess[bytes]:
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-stats_period",
        "0.25",
        "-progress",
        "pipe:1",
        "-y",
        *args,
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **_popen_flags(),
    )
    assert proc.stdout is not None
    err_box: list[bytes] = []

    def drain() -> None:
        try:
            if proc.stderr:
                err_box.append(proc.stderr.read() or b"")
        except OSError:
            pass

    err_thread = threading.Thread(target=drain, daemon=True)
    err_thread.start()
    lines: queue.Queue[bytes] = queue.Queue()

    def read_progress() -> None:
        try:
            for line in proc.stdout:
                lines.put(line)
        finally:
            lines.put(b"")

    threading.Thread(target=read_progress, daemon=True).start()
    started = time.monotonic()
    try:
        while True:
            if cancel is not None and cancel.is_set():
                _kill(proc)
                return subprocess.CompletedProcess(cmd, -9, b"", b"cancelled")
            if time.monotonic() - started > timeout:
                _kill(proc)
                raise subprocess.TimeoutExpired(cmd, timeout)
            try:
                line = lines.get(timeout=0.1)
            except queue.Empty:
                continue
            if not line:
                break
            text = line.decode("ascii", "replace").strip()
            seconds = _parse_out_time(text)
            if seconds is not None and on_progress:
                if duration > 0:
                    pct = min(99.0, max(8.0, 100.0 * seconds / duration))
                    label = "%s %d:%02d / %d:%02d" % (
                        stage,
                        int(seconds) // 60,
                        int(seconds) % 60,
                        int(duration) // 60,
                        int(duration) % 60,
                    )
                else:
                    elapsed = time.monotonic() - started
                    pct = min(90.0, 8.0 + elapsed / 6.0)
                    label = "%s đã xử lý %d:%02d" % (stage, int(seconds) // 60, int(seconds) % 60)
                on_progress(pct, label)
            if text == "progress=end":
                break
        if cancel is not None and cancel.is_set():
            _kill(proc)
            return subprocess.CompletedProcess(cmd, -9, b"", b"cancelled")
        code = proc.wait(timeout=max(0.01, timeout - (time.monotonic() - started)))
        err_thread.join(timeout=2)
        return subprocess.CompletedProcess(cmd, code, b"", err_box[0] if err_box else b"")
    except Exception:
        _kill(proc)
        raise


def _audio_encode_args(acodec: str, has_audio: bool) -> list[str]:
    if not has_audio:
        return ["-an"]
    if acodec in AAC:
        return ["-c:a", "copy"]
    return ["-c:a", "aac", "-ac", "1", "-ar", "16000", "-b:a", "48k"]


def _video_args(
    src: Path,
    dest: Path,
    codec: str,
    extra: list[str],
    acodec: str,
    has_audio: bool,
    vf: str | None,
) -> list[str]:
    args = [
        "-fflags",
        "+genpts+discardcorrupt",
        "-i",
        str(src),
        "-c:v",
        codec,
        *extra,
        "-pix_fmt",
        "yuv420p",
    ]
    if vf:
        args += ["-vf", vf]
    args += _audio_encode_args(acodec, has_audio)
    args += ["-max_muxing_queue_size", "4096", str(dest)]
    return args


def _try_copy(
    ffmpeg: str,
    src: Path,
    dest: Path,
    video_copy: bool,
    audio_copy: bool,
    has_audio: bool,
    timeout: float = 60,
) -> bool:
    args = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-fflags",
        "+genpts",
        "-y",
        "-i",
        str(src),
        "-c:v",
        "copy" if video_copy else "libx264",
    ]
    if not video_copy:
        args += ["-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv420p"]
    if has_audio:
        args += ["-c:a", "copy"] if audio_copy else ["-c:a", "aac", "-ac", "1", "-ar", "16000", "-b:a", "48k"]
    else:
        args += ["-an"]
    args.append(str(dest))
    try:
        copied = _run(args, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return False
    if copied.returncode == 0 and _ok_file(dest):
        return True
    try:
        dest.unlink(missing_ok=True)
    except OSError:
        pass
    return False


def _scale_filter(width: int, height: int) -> str | None:
    if width and height and (width % 2 or height % 2):
        return "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    return None


def _race_encode(
    ffmpeg: str,
    src: Path,
    dest: Path,
    duration: float,
    acodec: str,
    has_audio: bool,
    vf: str | None,
    on_progress: ProgressFn | None,
    timeout: int,
) -> str:
    """Run GPU (if any) and x264 at once; first finished good file wins."""
    cancel = threading.Event()
    winner: list[tuple[str, Path]] = []
    lock = threading.Lock()

    def note(pct: float, stage: str) -> None:
        if on_progress and not cancel.is_set():
            on_progress(pct, stage)

    def worker(codec: str, extra: list[str], stage: str, out: Path) -> None:
        if cancel.is_set():
            return
        args = _video_args(src, out, codec, extra, acodec, has_audio, vf)
        try:
            encoded = _encode_progress(
                ffmpeg, args, duration, note, stage, timeout=timeout, cancel=cancel
            )
        except (OSError, subprocess.TimeoutExpired):
            return
        if encoded.returncode == 0 and _ok_file(out) and not cancel.is_set():
            with lock:
                if not winner:
                    winner.append((codec, out))
                    cancel.set()

    jobs: list[tuple[str, list[str], str, Path]] = [
        (CPU_X264[0], CPU_X264[1], CPU_X264[2], dest.with_name(dest.stem + "-cpu.mp4")),
    ]
    gpu = gpu_encoder(ffmpeg)
    if gpu:
        jobs.append((gpu[0], gpu[1], gpu[2], dest.with_name(dest.stem + "-gpu.mp4")))
        if on_progress:
            on_progress(8, "GPU + CPU cùng chuyển, lấy đường nhanh hơn…")
    else:
        if on_progress:
            on_progress(8, CPU_X264[2])

    threads = [threading.Thread(target=worker, args=job, daemon=True) for job in jobs]
    for t in threads:
        t.start()
    deadline = time.time() + timeout + 8
    for t in threads:
        remain = max(0.2, deadline - time.time())
        t.join(timeout=remain)
    cancel.set()
    for t in threads:
        t.join(timeout=2)

    extras = [job[3] for job in jobs]
    if winner:
        codec, path = winner[0]
        try:
            if dest.exists():
                dest.unlink()
            path.replace(dest)
        except OSError:
            shutil.copyfile(path, dest)
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        for extra_path in extras:
            if extra_path != dest:
                try:
                    extra_path.unlink(missing_ok=True)
                except OSError:
                    pass
        return codec
    for extra_path in extras:
        try:
            extra_path.unlink(missing_ok=True)
        except OSError:
            pass
    return ""


def transcode_file(
    src: Path,
    orig_name: str,
    on_progress: ProgressFn | None = None,
) -> TranscodeResult:
    global _LAST_STRATEGY
    deadline = time.monotonic() + CONVERT_SECONDS
    keep_output = False

    def remaining() -> float:
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise subprocess.TimeoutExpired("convert", CONVERT_SECONDS)
        return seconds

    def note(pct: float, stage: str) -> None:
        nonlocal keep_output
        if pct == 100:
            keep_output = True
        if on_progress:
            on_progress(pct, stage)

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return TranscodeResult(
            ok=False,
            error="May nay chua co ffmpeg. Cai ffmpeg roi mo lai app de phat AVI.",
        )
    if not src.is_file() or src.stat().st_size <= 0:
        return TranscodeResult(ok=False, error="File rong.")
    if src.stat().st_size > MAX_UPLOAD_BYTES:
        return TranscodeResult(ok=False, error="File qua lon (toi da 512 MB).")

    note(5, "Đang nhận dạng file…")
    info = probe_media(src, ffmpeg)
    if not info.get("vcodec"):
        info = peek_avi(src) if src.suffix.lower() == ".avi" else info
    duration = float(info.get("duration") or 0)
    if duration <= 0:
        try:
            duration = max(0.0, src.stat().st_size / 140000.0)
        except OSError:
            duration = 0.0
    stem = _safe_stem(orig_name)
    tmp = Path(tempfile.mkdtemp(prefix="atc-transcode-"))
    mp4 = tmp / (stem + ".mp4")
    m4a = tmp / (stem + ".m4a")
    vcodec = str(info.get("vcodec") or "")
    acodec = str(info.get("acodec") or "")
    has_video = bool(info.get("has_video"))
    has_audio = bool(info.get("has_audio"))
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    _LAST_STRATEGY = ""

    try:
        if has_video and vcodec in H264:
            if acodec in REMUX_AUDIO or not has_audio:
                note(8, "Đang đóng gói nhanh (giữ H.264)…")
                if _try_copy(ffmpeg, src, mp4, True, acodec in REMUX_AUDIO, has_audio, remaining()):
                    _LAST_STRATEGY = "copy"
                    note(100, "Xong.")
                    return TranscodeResult(
                        ok=True, mime="video/mp4", name=stem + ".mp4", path=mp4, duration=duration
                    )
            note(10, "Giữ H.264, chỉ chuyển tiếng…")
            if _try_copy(ffmpeg, src, mp4, True, False, has_audio, remaining()):
                _LAST_STRATEGY = "copy_video"
                note(100, "Xong.")
                return TranscodeResult(
                    ok=True, mime="video/mp4", name=stem + ".mp4", path=mp4, duration=duration
                )

        ext = src.suffix.lower()
        if not has_video and ext in {".avi", ".mkv", ".mov", ".mp4", ".m4v"}:
            has_video = True
        if has_video:
            vf = _scale_filter(width, height)
            # Measure the actual input: GPU availability alone does not imply speed.
            candidates = [CPU_X264]
            gpu = gpu_encoder(ffmpeg)
            if gpu:
                candidates.insert(0, gpu)
            ranked = []
            sample = tmp / "speed-test.mp4"
            sample_seconds = min(5.0, duration) if duration > 0 else 5.0
            note(8, "Đang đo tốc độ chuyển đổi…")
            for codec, extra, stage in candidates:
                args = _video_args(src, sample, codec, extra, acodec, has_audio, vf)
                args[-1:-1] = ["-t", str(sample_seconds)]
                started = time.monotonic()
                try:
                    test = _encode_progress(ffmpeg, args, 0, None, stage,
                                            timeout=min(8, remaining()))
                    if test.returncode == 0 and _ok_file(sample):
                        ranked.append((time.monotonic() - started, codec, extra, stage))
                except subprocess.TimeoutExpired:
                    pass
            sample.unlink(missing_ok=True)
            ranked.sort(key=lambda item: item[0])
            if not ranked:
                ranked = [(8.0, *CPU_X264)]
            estimate = ranked[0][0] * duration / sample_seconds
            if duration > 0 and estimate > remaining() * 0.8:
                # Preserve the full timeline/audio; reduce only video workload.
                vf = "fps=10,scale=w='min(1280,iw)':h='min(720,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2"
                note(8, "Chuyển nhanh: video tối đa 720p / 10 fps, giữ đủ thời lượng…")
            detail = "encode failed"
            for _, codec, extra, stage in ranked:
                if vf and vf.startswith("fps="):
                    stage = "Đang chuyển MP4 720p / 10 fps…"
                encoded = _encode_progress(
                    ffmpeg,
                    _video_args(src, mp4, codec, extra, acodec, has_audio, vf),
                    duration,
                    on_progress,
                    stage,
                    timeout=remaining(),
                )
                if encoded.returncode == 0 and _ok_file(mp4):
                    _LAST_STRATEGY = "encode:" + codec
                    note(100, "Xong.")
                    return TranscodeResult(
                        ok=True, mime="video/mp4", name=stem + ".mp4", path=mp4, duration=duration
                    )
                detail = (encoded.stderr or b"").decode("utf-8", "replace").strip() or "encode failed"
            return TranscodeResult(ok=False, error="Không chuyển được video MP4: " + detail[:240])
        else:
            detail = ""

        note(20, "Không có video phát được — lấy kênh tiếng…")
        audio = _encode_progress(
            ffmpeg,
            [
                "-i",
                str(src),
                "-vn",
                "-c:a",
                "aac",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-b:a",
                "48k",
                str(m4a),
            ],
            duration,
            on_progress,
            "Đang tách tiếng…",
            timeout=remaining(),
        )
        if audio.returncode == 0 and _ok_file(m4a):
            _LAST_STRATEGY = "audio"
            note(100, "Xong.")
            return TranscodeResult(
                ok=True, mime="audio/mp4", name=stem + ".m4a", path=m4a, duration=duration
            )
        err = (audio.stderr or b"").decode("utf-8", "replace").strip() or detail
        return TranscodeResult(
            ok=False,
            error="ffmpeg khong chuyen duoc file nay" + ((": " + err[:240]) if err else "."),
        )
    except subprocess.TimeoutExpired:
        return TranscodeResult(ok=False, error="Đã dừng chuyển đổi trước giới hạn 5 phút. Máy chưa xử lý kịp toàn bộ video; file gốc vẫn được giữ để thử lại.")
    except OSError as exc:
        return TranscodeResult(ok=False, error="Khong chay duoc ffmpeg: %s" % exc)
    finally:
        if not keep_output:
            shutil.rmtree(tmp, ignore_errors=True)


def cleanup_result(result: TranscodeResult) -> None:
    if result.path is None:
        return
    folder = result.path.parent
    try:
        result.path.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        folder.rmdir()
    except OSError:
        pass


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
            "done": bool(job.get("done")),
            "error": job.get("error") or "",
            "mime": job.get("mime") or "",
            "name": job.get("name") or "",
            "duration": float(job.get("duration") or 0),
        }


def start_job(src: Path, orig_name: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "id": job_id,
            "percent": 1.0,
            "stage": "Đã nhận file, bắt đầu chuyển…",
            "done": False,
            "error": "",
            "mime": "",
            "name": "",
            "duration": 0.0,
            "path": None,
            "src": src,
            "created": time.time(),
        }
    threading.Thread(target=_run_job, args=(job_id, src, orig_name), daemon=True).start()
    return job_id


def _run_job(job_id: str, src: Path, orig_name: str) -> None:
    def on_progress(pct: float, stage: str) -> None:
        _job_update(job_id, percent=round(pct, 1), stage=stage)

    result = transcode_file(src, orig_name, on_progress=on_progress)
    try:
        src.unlink(missing_ok=True)
    except OSError:
        pass
    if not result.ok:
        cleanup_result(result)
        _job_update(
            job_id,
            done=True,
            error=result.error or "Khong chuyen duoc file.",
            percent=100,
            path=None,
        )
        return
    _job_update(
        job_id,
        done=True,
        percent=100,
        stage="Xong.",
        mime=result.mime,
        name=result.name,
        duration=result.duration,
        path=result.path,
        error="",
    )


def take_job_file(job_id: str) -> tuple[Path, str, str] | None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job or not job.get("done") or job.get("error") or not job.get("path"):
            return None
        path = Path(job["path"])
        mime = str(job.get("mime") or "video/mp4")
        name = str(job.get("name") or path.name)
        job["accessed"] = time.time()
        job["readers"] = int(job.get("readers", 0)) + 1
    if not path.is_file():
        release_job_file(job_id)
        return None
    return path, mime, name


def release_job_file(job_id: str) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job:
            job["readers"] = max(0, int(job.get("readers", 0)) - 1)
            job["accessed"] = time.time()


def sweep_jobs(max_age: float = 900) -> None:
    now = time.time()
    with _JOBS_LOCK:
        stale = [job_id for job_id, job in _JOBS.items()
                 if job.get("done") and not job.get("readers")
                 and now - float(job.get("accessed") or job.get("created") or 0) > max_age]
        expired = [_JOBS.pop(job_id) for job_id in stale]
    for job in expired:
        path = job.get("path")
        if path:
            cleanup_result(TranscodeResult(ok=True, path=Path(path)))
        src = job.get("src")
        if src:
            try:
                Path(src).unlink(missing_ok=True)
            except OSError:
                pass
