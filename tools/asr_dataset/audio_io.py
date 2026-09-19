"""Slice logger WAV to utterance windows (16 kHz mono PCM)."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

PTT_PAD_SEC = 0.18


def read_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        sr = handle.getframerate()
        nch = handle.getnchannels()
        frames = handle.readframes(handle.getnframes())
        sw = handle.getsampwidth()
    if sw == 1:
        pcm = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sw == 2:
        pcm = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        raise ValueError("Chi ho tro PCM 8/16-bit")
    if nch > 1:
        pcm = pcm.reshape(-1, nch).mean(axis=1)
    return pcm, sr


def write_wav_slice(
    samples: np.ndarray,
    sr: int,
    t0: float,
    t1: float,
    dest: Path,
    pad_sec: float = PTT_PAD_SEC,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    a = max(0, int((t0 - pad_sec) * sr))
    b = min(len(samples), int((t1 + pad_sec) * sr))
    if b <= a:
        b = min(len(samples), a + int(0.4 * sr))
    chunk = np.asarray(samples[a:b], dtype=np.float32)
    peak = float(np.max(np.abs(chunk))) if len(chunk) else 0.0
    if 1e-4 < peak < 0.38:
        chunk = chunk * (0.72 / peak)
    pcm = np.clip(chunk * 32767.0, -32767, 32767).astype(np.int16)
    with wave.open(str(dest), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(pcm.tobytes())


def find_source_audio(filename: str, extra_roots: list[Path] | None = None) -> Path | None:
    from asr_dataset.paths import audio_root, gold_root

    name = Path(str(filename or "").replace("\\", "/")).name
    if not name:
        return None
    roots = list(extra_roots or [])
    roots.extend([audio_root(), gold_root() / "source", gold_root() / "dataset_v1" / "source"])
    for folder in roots:
        try:
            cand = folder / name
            if cand.is_file() and cand.stat().st_size > 64:
                return cand
        except OSError:
            continue
        stem = Path(name).stem
        for ext in (".wav", ".WAV", ".mp3", ".mp4"):
            try:
                cand = folder / f"{stem}{ext}"
                if cand.is_file() and cand.stat().st_size > 64:
                    return cand
            except OSError:
                continue
    return None
