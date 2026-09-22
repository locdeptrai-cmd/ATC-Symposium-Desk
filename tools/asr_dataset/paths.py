"""On-prem gold corpus locations. WAV is never committed."""

from __future__ import annotations

import os
from pathlib import Path

from asr_dataset import DATASET_VERSION, GOLD_DIRNAME, MANIFEST_NAME

try:
    import app_paths
except ImportError:
    app_paths = None  # type: ignore


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def gold_root() -> Path:
    env = (os.environ.get("ATC_ASR_GOLD") or "").strip()
    if env:
        return Path(env)
    if app_paths is not None:
        if app_paths.frozen():
            return app_paths.app_home() / "data" / GOLD_DIRNAME
        return app_paths.bundle_root() / "data" / GOLD_DIRNAME
    return repo_root() / "data" / GOLD_DIRNAME


def audio_root() -> Path:
    env = (os.environ.get("ATC_ASR_AUDIO_ROOT") or "").strip()
    if env:
        return Path(env)
    return gold_root() / "source"


def wav_dir() -> Path:
    return gold_root() / DATASET_VERSION / "wav"


def mix_root() -> Path:
    return gold_root() / "mix" / "atco2-1h"


def mix_manifest_path() -> Path:
    return mix_root() / MANIFEST_NAME


def manifest_path() -> Path:
    return gold_root() / DATASET_VERSION / MANIFEST_NAME


def ensure_gold_dirs() -> Path:
    root = gold_root() / DATASET_VERSION
    (root / "wav").mkdir(parents=True, exist_ok=True)
    (root / "source").mkdir(parents=True, exist_ok=True)
    gold_root().mkdir(parents=True, exist_ok=True)
    return root
