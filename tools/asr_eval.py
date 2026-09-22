"""Evaluate ATC ASR against HUMAN transcripts (WER/CER + entity accuracy)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from asr_dataset.metrics import summarize_pairs
from asr_dataset.paths import manifest_path, mix_manifest_path
from asr_dataset.recipe import resolve_model_id
from reda import store as reda_store


def _pairs_from_jsonl(path: Path, hyp_path: Path | None, split: str | None = None) -> list[tuple[str, str]]:
    hyp_by_id: dict[str, str] = {}
    if hyp_path is not None:
        for line in hyp_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = str(row.get("utterance_id") or row.get("id") or "")
            hyp_by_id[key] = str(row.get("hyp") or row.get("text") or "")
    pairs: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if split and split != "all" and str(row.get("split") or "train") != split:
            continue
        ref = str(row.get("text") or "").strip()
        if not ref:
            continue
        uid = str(row.get("utterance_id") or row.get("id") or "")
        hyp = str(row.get("hyp") or hyp_by_id.get(uid) or "").strip()
        if not hyp:
            continue
        pairs.append((hyp, ref))
    return pairs


def _pairs_from_corrections() -> list[tuple[str, str]]:
    conn = reda_store._connect()
    try:
        rows = conn.execute(
            """
            SELECT before_text, after_text
            FROM corrections
            WHERE source = 'HUMAN'
              AND TRIM(COALESCE(after_text, '')) != ''
              AND TRIM(COALESCE(before_text, '')) != ''
            ORDER BY created_at
            """
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    pairs: list[tuple[str, str]] = []
    for row in rows:
        hyp = str(row["before_text"] or "").strip()
        ref = str(row["after_text"] or "").strip()
        if hyp and ref:
            pairs.append((hyp, ref))
    return pairs


def _pairs_from_gold_model(path: Path, model_id: str, split: str | None = None) -> list[tuple[str, str]]:
    from faster_whisper import WhisperModel
    from media_transcribe import repair_radio_text

    resolved = resolve_model_id(model_id)
    model = WhisperModel(resolved, device="cpu", compute_type="int8")
    pairs: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if split and split != "all" and str(row.get("split") or "train") != split:
            continue
        ref = str(row.get("text") or "").strip()
        audio = row.get("audio")
        if not ref or not audio:
            continue
        wav = (path.parent / audio).resolve()
        if not wav.is_file():
            continue
        segments, _info = model.transcribe(str(wav), language="en", beam_size=1, vad_filter=False)
        hyp = repair_radio_text(" ".join(str(seg.text or "") for seg in segments).strip())
        if hyp:
            pairs.append((hyp, ref))
    return pairs


def format_report(stats: dict) -> str:
    lines = [
        f"n={stats.get('n')}",
        f"WER={stats.get('wer')}",
        f"CER={stats.get('cer')}",
        "entity_accuracy:",
    ]
    for field, val in (stats.get("entity_accuracy") or {}).items():
        lines.append(f"  {field}: {val}")
    lines.append("taxonomy:")
    for kind, count in sorted((stats.get("taxonomy") or {}).items(), key=lambda x: -x[1]):
        lines.append(f"  {kind}: {count}")
    examples = stats.get("examples") or {}
    if examples:
        lines.append("examples:")
        for kind, rows in examples.items():
            lines.append(f"  [{kind}]")
            for row in rows[:3]:
                lines.append(f"    hyp: {row.get('hyp')}")
                lines.append(f"    ref: {row.get('ref')}")
    return "\n".join(lines)


def collect_pairs(
    *,
    gold: Path | None = None,
    hyp: Path | None = None,
    from_corrections: bool = False,
    split: str | None = None,
    model: str | None = None,
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if from_corrections or (gold is None and hyp is None and not model):
        pairs.extend(_pairs_from_corrections())
    gold_path = gold or (manifest_path() if manifest_path().is_file() else None)
    if model and gold_path is not None and gold_path.is_file():
        pairs.extend(_pairs_from_gold_model(gold_path, model, split))
        return pairs
    if gold_path is not None and gold_path.is_file():
        pairs.extend(_pairs_from_jsonl(gold_path, hyp, split))
    return pairs


def eval_payload(
    *,
    gold: Path | None = None,
    hyp: Path | None = None,
    from_corrections: bool = True,
    split: str | None = None,
    model: str | None = None,
    mix: bool = False,
) -> dict:
    target = gold
    if mix:
        from_corrections = False
        if target is None:
            target = mix_manifest_path() if mix_manifest_path().is_file() else None
            split = split or "test"
    pairs = collect_pairs(
        gold=target,
        hyp=hyp,
        from_corrections=from_corrections,
        split=split,
        model=model,
    )
    stats = summarize_pairs(pairs)
    stats["ok"] = True
    stats["n"] = int(stats.get("n") or 0)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Baseline ATC ASR eval: HUMAN vs ASR, entity metrics, error taxonomy."
    )
    parser.add_argument("--gold", type=Path, default=None, help="Gold JSONL (ref in 'text').")
    parser.add_argument("--hyp", type=Path, default=None, help="Hypothesis JSONL keyed by utterance_id.")
    parser.add_argument(
        "--from-corrections",
        action="store_true",
        help="Dung bang corrections (before=ASR, after=HUMAN).",
    )
    parser.add_argument("--split", default=None, help="Chi lay split gold (train/dev/test).")
    parser.add_argument("--model", default=None, help="CT2 path hoac alias turbo/tclin; transcribe wav gold.")
    parser.add_argument("--mix", action="store_true", help="Eval held-out ATCO2-1h (split=test).")
    parser.add_argument("--json", action="store_true", help="In JSON thay vi bang text.")
    args = parser.parse_args()
    stats = eval_payload(
        gold=args.gold,
        hyp=args.hyp,
        from_corrections=args.from_corrections or (args.gold is None and args.hyp is None and not args.model and not args.mix),
        split=args.split,
        model=args.model,
        mix=args.mix,
    )
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        print(format_report(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
