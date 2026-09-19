"""Resolve bundle / AppData / repo paths for source runs and the frozen EXE."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_FOLDER = "ATC-Symposium-Desk"


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    if frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[1]


def exe_dir() -> Path:
    if frozen():
        return Path(sys.executable).resolve().parent
    return bundle_root()


def app_home() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / APP_FOLDER


def library_sqlite() -> Path:
    env = (os.environ.get("ATC_LIBRARY_DB") or "").strip()
    if env:
        return Path(env)
    candidates = [
        bundle_root() / "web" / "data" / "library.sqlite",
        app_home() / "web" / "data" / "library.sqlite",
        exe_dir() / "web" / "data" / "library.sqlite",
    ]
    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size > 1000:
                return path
        except OSError:
            continue
    return candidates[0]


def data_file(*parts: str) -> Path:
    rel = Path(*parts)
    candidates = [
        bundle_root() / rel,
        bundle_root() / "data" / rel.name,
        exe_dir() / rel,
        app_home() / rel,
    ]
    for path in candidates:
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return candidates[0]


def whisper_turbo_dir() -> Path:
    env = (os.environ.get("ATC_WHISPER_MODEL") or "").strip()
    if env:
        path = Path(env)
        if path.suffix:
            return path.parent if path.name.lower() == "model.bin" else path
        return path
    candidates = [
        bundle_root() / "models" / "whisper" / "atc-turbo-ct2",
        exe_dir() / "models" / "whisper" / "atc-turbo-ct2",
        app_home() / "models" / "whisper" / "atc-turbo-ct2",
    ]
    for path in candidates:
        weights = path / "model.bin"
        try:
            if weights.is_file() and weights.stat().st_size > 400_000_000:
                return path
        except OSError:
            continue
    return candidates[0]


def ffmpeg_candidates() -> list[Path]:
    found: list[Path] = []
    bundled = [
        bundle_root() / "bin" / "ffmpeg.exe",
        bundle_root() / "ffmpeg.exe",
        exe_dir() / "bin" / "ffmpeg.exe",
        exe_dir() / "ffmpeg.exe",
        app_home() / "bin" / "ffmpeg.exe",
    ]
    found.extend(bundled)
    which = os.environ.get("ATC_FFMPEG") or ""
    if which:
        found.append(Path(which))
    local = os.environ.get("LOCALAPPDATA") or ""
    found.extend(
        [
            Path(local) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
        ]
    )
    return found
