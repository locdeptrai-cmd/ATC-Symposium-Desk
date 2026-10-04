"""Compare notebook ASR experiments with the production decoder on gold audio."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import media_transcribe
from asr_dataset.audio_io import find_source_audio
from asr_dataset.metrics import summarize_pairs
from asr_dataset.paths import manifest_path

NOTEBOOK_FILTER = "highpass=f=300:poles=2,lowpass=f=3400:poles=2"
WINDOW_PAD_SEC = 0.18
PROFILES = (
    ("production", media_transcribe.RADIO_AF, None, None, False),
    ("beam5", media_transcribe.RADIO_AF, 5, 5, False),
    ("notebook_filter", NOTEBOOK_FILTER, None, None, True),
    ("notebook_filter_beam5", NOTEBOOK_FILTER, 5, 5, True),
)


def normalize_notebook_audio(samples: np.ndarray, target_db: float = -20.0) -> np.ndarray:
    """Mirror notebook peak/RMS normalization without trimming timestamps."""
    audio = np.asarray(samples, dtype=np.float32).copy()
    if not len(audio):
        return audio
    if not np.isfinite(audio).all():
        raise ValueError("Audio chứa NaN hoặc Inf.")
    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        audio *= 0.95 / peak
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
    if rms > 0:
        audio *= (10.0 ** (target_db / 20.0)) / rms
    return np.ascontiguousarray(np.clip(audio, -0.99, 0.99), dtype=np.float32)


def _resolve_audio(row: dict, manifest: Path) -> Path | None:
    raw = str(row.get("audio") or "").strip()
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = (manifest.parent / path).resolve()
        if path.is_file():
            return path
    return find_source_audio(str(row.get("filename") or ""))


def _read_audio_window(
    ffmpeg: str,
    source: Path,
    start: float,
    end: float,
    audio_filter: str,
) -> np.ndarray:
    window_start = max(0.0, float(start) - WINDOW_PAD_SEC)
    window_end = max(window_start + 0.4, float(end) + WINDOW_PAD_SEC)
    duration = window_end - window_start
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-ss",
        "%.3f" % window_start,
        "-i",
        str(source),
        "-t",
        "%.3f" % duration,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-af",
        audio_filter,
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "pipe:1",
    ]
    proc = subprocess.run(
        command,
        capture_output=True,
        check=False,
        timeout=max(90, int(duration * 4)),
    )
    if proc.returncode != 0 or len(proc.stdout) < 64:
        detail = (proc.stderr or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(detail[:240] or "Không tách được đoạn audio gold.")
    return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def _gold_rows(path: Path, split: str, limit: int | None) -> tuple[list[dict], int]:
    rows: list[dict] = []
    skipped_audio = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if split != "all" and str(row.get("split") or "train") != split:
            continue
        if not str(row.get("text") or "").strip():
            continue
        if _resolve_audio(row, path) is None:
            skipped_audio += 1
            continue
        try:
            start, end = float(row.get("t_start") or 0), float(row.get("t_end") or 0)
        except (TypeError, ValueError):
            skipped_audio += 1
            continue
        if end <= start:
            skipped_audio += 1
            continue
        rows.append(row)
        if limit and len(rows) >= limit:
            break
    return rows, skipped_audio


def evaluate(
    *,
    gold: Path | None = None,
    split: str = "test",
    limit: int | None = None,
) -> dict:
    manifest = gold or manifest_path()
    if not manifest.is_file():
        raise FileNotFoundError("Không tìm thấy gold manifest: %s" % manifest)
    rows, skipped_audio = _gold_rows(manifest, split, limit)
    if not rows:
        raise ValueError("Không có hàng HUMAN kèm audio phù hợp cho split=%s." % split)
    ffmpeg = media_transcribe.tx.find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("Không tìm thấy ffmpeg để đọc audio gold.")

    resolved_model = media_transcribe.WHISPER_MODEL
    model = media_transcribe.load_model()
    if model is None:
        raise RuntimeError(
            media_transcribe.model_status().get("error") or "Không nạp được model runtime."
        )
    pairs = {name: [] for name, *_ in PROFILES}
    failures: list[dict[str, str]] = []
    audio_cache: dict[tuple[str, float, float, str], np.ndarray] = {}

    for row in rows:
        source = _resolve_audio(row, manifest)
        if source is None:
            skipped_audio += 1
            continue
        start, end = float(row.get("t_start") or 0), float(row.get("t_end") or 0)
        ref = str(row.get("text") or "").strip()
        hotwords = media_transcribe.hotwords_for(
            filename=str(row.get("filename") or source.name)
        )
        for name, audio_filter, beam, best_of, notebook_norm in PROFILES:
            key = (str(source), start, end, audio_filter)
            try:
                samples = audio_cache.get(key)
                if samples is None:
                    samples = _read_audio_window(ffmpeg, source, start, end, audio_filter)
                    audio_cache[key] = samples
                if notebook_norm:
                    samples = normalize_notebook_audio(samples)
                hyp = media_transcribe.decode_for_evaluation(
                    model,
                    samples,
                    hotwords,
                    beam_size=beam,
                    best_of=best_of,
                )
                pairs[name].append((hyp, ref))
            except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
                failures.append({"profile": name, "id": str(row.get("id") or ""), "error": str(exc)})

    return {
        "model": resolved_model,
        "device": media_transcribe.WHISPER_DEVICE,
        "compute_type": media_transcribe.WHISPER_COMPUTE,
        "split": split,
        "rows_with_audio": len(rows),
        "skipped_audio": skipped_audio,
        "filter_note": "notebook_filter uses FFmpeg 300-3400 Hz; no trimming, to retain time alignment",
        "profiles": {name: summarize_pairs(values) for name, values in pairs.items()},
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A/B notebook ASR profiles against the production decoder on HUMAN gold audio."
    )
    parser.add_argument("--gold", type=Path, default=None, help="Gold JSONL manifest.")
    parser.add_argument("--split", choices=("train", "dev", "test", "all"), default="test")
    parser.add_argument("--limit", type=int, default=None, help="Maximum gold utterances to compare.")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit phải lớn hơn 0.")
    result = evaluate(gold=args.gold, split=args.split, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())