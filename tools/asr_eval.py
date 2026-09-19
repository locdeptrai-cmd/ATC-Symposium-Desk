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
from asr_dataset.paths import manifest_path
from reda import store as reda_store


def _pairs_from_jsonl(path: Path, hyp_path: Path | None) -> list[tuple[str, str]]:
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
    parser.add_argument("--json", action="store_true", help="In JSON thay vi bang text.")
    args = parser.parse_args()
    pairs: list[tuple[str, str]] = []
    if args.from_corrections or (args.gold is None and args.hyp is None):
        pairs.extend(_pairs_from_corrections())
    gold = args.gold or (manifest_path() if manifest_path().is_file() else None)
    if gold is not None and gold.is_file():
        pairs.extend(_pairs_from_jsonl(gold, args.hyp))
    stats = summarize_pairs(pairs)
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        print(format_report(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
