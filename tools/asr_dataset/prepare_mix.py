"""Download ATCO2-test-set-1h into the gold mix pool (70/30 LoRA, held-out eval)."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from asr_dataset.audio_io import write_wav_mono
from asr_dataset.paths import mix_manifest_path, mix_root
from asr_dataset.recipe import ATCO2_HF_DATASET, recipe_status

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _update(job_id: str, **fields: object) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job:
            job.update(fields)


def job_snapshot(job_id: str) -> dict | None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        return dict(job)


def write_mix_records(rows: list[dict], dest: Path | None = None) -> dict:
    root = dest or mix_root()
    wav_dir = root / "wav"
    wav_dir.mkdir(parents=True, exist_ok=True)
    manifest = root / "manifest.jsonl"
    written = 0
    with manifest.open("w", encoding="utf-8") as handle:
        for index, row in enumerate(rows):
            text = str(row.get("text") or "").strip()
            samples = row.get("samples")
            sr = int(row.get("sr") or 16000)
            if not text or samples is None:
                continue
            uid = str(row.get("id") or f"atco2-{index:04d}")
            rel = f"wav/{uid}.wav"
            write_wav_mono(samples, sr, root / rel)
            split = str(row.get("split") or ("test" if index % 5 == 0 else "train"))
            record = {
                "id": uid,
                "audio": rel,
                "text": text,
                "speaker": row.get("speaker") or "UNKNOWN",
                "split": split,
                "source": "atco2-1h",
                "t_start": float(row.get("t_start") or 0),
                "t_end": float(row.get("t_end") or 0),
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
    return {"ok": True, "count": written, "manifest": str(manifest), "dir": str(root)}


def download_atco2_1h(progress=None) -> dict:
    try:
        from datasets import Audio, load_dataset
    except ImportError as exc:
        raise RuntimeError("Can pip install datasets de nap ATCO2-1h tu Hugging Face.") from exc
    ds = load_dataset(ATCO2_HF_DATASET, split="test")
    ds = ds.cast_column("audio", Audio(sampling_rate=16000))
    rows: list[dict] = []
    total = len(ds)
    for index, item in enumerate(ds):
        audio = item.get("audio") or {}
        array = audio.get("array")
        sr = int(audio.get("sampling_rate") or 16000)
        text = str(item.get("text") or "").strip()
        if array is None or not text:
            continue
        start = float(item.get("segment_start_time") or 0)
        end = float(item.get("segment_end_time") or 0)
        rows.append(
            {
                "id": str(item.get("id") or f"atco2-{index:04d}"),
                "text": text,
                "samples": array,
                "sr": sr,
                "t_start": start,
                "t_end": end,
                "split": "test" if index % 5 == 0 else "train",
            }
        )
        if progress is not None:
            progress(index + 1, total)
    return write_mix_records(rows)


def start_prepare() -> str:
    try:
        import datasets  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Cần pip install datasets để nạp ATCO2-1h từ Hugging Face.") from exc
    job_id = uuid.uuid4().hex[:12]
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "id": job_id,
            "percent": 2.0,
            "stage": "Đang tải ATCO2-test-set-1h…",
            "done": False,
            "error": "",
            "gold_added": 0,
            "created": time.time(),
        }
    threading.Thread(target=_run_prepare, args=(job_id,), daemon=True).start()
    return job_id


def _run_prepare(job_id: str) -> None:
    try:
        def progress(done: int, total: int) -> None:
            pct = 8 + int(80 * done / max(1, total))
            _update(job_id, percent=pct, stage=f"Đang ghi mix ATCO2… {done}/{total}")

        result = download_atco2_1h(progress=progress)
        _update(
            job_id,
            percent=100,
            stage=f"Đã nạp {result.get('count') or 0} câu ATCO2-1h (mix 30% khi LoRA).",
            done=True,
            gold_added=int(result.get("count") or 0),
            stats={"ok": True, "recipe": recipe_status()},
        )
    except Exception as exc:
        _update(job_id, done=True, error=str(exc), stage="Không nạp được ATCO2-1h.")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Nap ATCO2-1h vao mix LoRA / eval VHF.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if args.dry_run or not args.download:
        print(json.dumps({"ok": True, "recipe": recipe_status(), "next": "python tools/asr_dataset/prepare_mix.py --download"}, ensure_ascii=False, indent=2))
        return 0
    result = download_atco2_1h()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
