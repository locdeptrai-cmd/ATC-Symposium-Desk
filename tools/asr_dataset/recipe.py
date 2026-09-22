"""Runtime + LoRA recipe for ATC Desk: turbo default, ATCO2 mix, tclin A/B."""

from __future__ import annotations

import json
import os
from pathlib import Path

from asr_dataset.paths import gold_root, manifest_path, mix_manifest_path, mix_root, repo_root

try:
    import app_paths
except ImportError:
    app_paths = None  # type: ignore

RUNTIME_HF = "SingularityUS/ATC-whisper-turbo-v1"
AB_HF = "tclin/whisper-large-v3-turbo-atcosim-finetune"
TRAIN_BASE = RUNTIME_HF
GOLD_MIX_RATIO = 0.7
ATCO2_MIX_RATIO = 0.3
ATCO2_HF_DATASET = "Jzuluaga/atco2_corpus_1h"
ATCO2_FREE_URL = "https://www.replaywell.com/atco2/download/ATCO2-ASRdataset-v1_beta.tgz"
RUNTIME_DIRNAME = "atc-turbo-ct2"
AB_DIRNAME = "tclin-turbo-ct2"


def whisper_root() -> Path:
    if app_paths is not None:
        return app_paths.bundle_root() / "models" / "whisper"
    return repo_root() / "models" / "whisper"


def runtime_ct2_dir() -> Path:
    if app_paths is not None:
        return app_paths.whisper_turbo_dir()
    return whisper_root() / RUNTIME_DIRNAME


def ab_ct2_dir() -> Path:
    return whisper_root() / AB_DIRNAME


def ct2_ready(folder: Path) -> bool:
    weights = folder / "model.bin"
    try:
        return (
            weights.is_file()
            and weights.stat().st_size > 400_000_000
            and (folder / "config.json").is_file()
        )
    except OSError:
        return False


def resolve_model_id(value: str | None = None) -> str:
    raw = (value if value is not None else os.environ.get("ATC_WHISPER_MODEL") or "").strip()
    key = raw.lower().replace("\\", "/")
    if not raw or key in {"turbo", "default", "singularity", "runtime", RUNTIME_DIRNAME}:
        return str(runtime_ct2_dir())
    if key in {"tclin", "ab", AB_DIRNAME, AB_HF.lower()}:
        return str(ab_ct2_dir())
    path = Path(raw)
    if path.suffix.lower() == ".bin":
        return str(path.parent)
    return raw


def mix_train_rows(gold: list[dict], extra: list[dict], gold_frac: float = GOLD_MIX_RATIO) -> list[dict]:
    if not extra:
        return list(gold)
    if not gold:
        return list(extra)
    frac = min(0.95, max(0.05, float(gold_frac)))
    extra_n = max(1, int(round(len(gold) * (1.0 - frac) / frac)))
    extra_n = min(extra_n, len(extra))
    return list(gold) + list(extra[:extra_n])


def _rows_from_manifest(path: Path, split: str | None = None) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if split and split != "all" and str(row.get("split") or "train") != split:
            continue
        text = str(row.get("text") or "").strip()
        audio = row.get("audio")
        if not text or not audio:
            continue
        wav = (path.parent / audio).resolve()
        if not wav.is_file():
            continue
        row["audio_path"] = str(wav)
        rows.append(row)
    return rows


def load_mix_rows(split: str = "train") -> list[dict]:
    return _rows_from_manifest(mix_manifest_path(), split)


def recipe_status() -> dict:
    mix_counts = {"train": 0, "dev": 0, "test": 0, "total": 0, "with_audio": 0}
    mix = mix_manifest_path()
    if mix.is_file():
        for line in mix.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            split = str(row.get("split") or "train")
            mix_counts[split] = mix_counts.get(split, 0) + 1
            mix_counts["total"] += 1
            if row.get("audio"):
                mix_counts["with_audio"] += 1
    runtime = runtime_ct2_dir()
    ab = ab_ct2_dir()
    return {
        "runtime_hf": RUNTIME_HF,
        "runtime_dir": str(runtime),
        "runtime_ready": ct2_ready(runtime),
        "ab_hf": AB_HF,
        "ab_dir": str(ab),
        "ab_ready": ct2_ready(ab),
        "train_base": TRAIN_BASE,
        "gold_mix_ratio": GOLD_MIX_RATIO,
        "atco2_mix_ratio": ATCO2_MIX_RATIO,
        "atco2_dataset": ATCO2_HF_DATASET,
        "atco2_url": ATCO2_FREE_URL,
        "mix_manifest": str(mix),
        "mix_dir": str(mix_root()),
        "mix_counts": mix_counts,
        "gold_manifest": str(manifest_path()),
        "note": (
            "REDA giu turbo Singularity. LoRA GPU: 70% gold VN + 30% ATCO2-1h. "
            "A/B tclin: convert CT2 roi ATC_WHISPER_MODEL=tclin."
        ),
    }
