"""Dry-run the LoRA / CT2 recipes without GPU."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


def test_train_lora_dry_run(tmp_path: Path, monkeypatch):
    from asr_dataset.paths import gold_root

    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "split": "train",
                "text": "Viet Nam one two three",
                "audio": None,
                "t_start": 0,
                "t_end": 2,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("asr_dataset.train_lora.manifest_path", lambda: manifest)
    from asr_dataset.train_lora import dry_run

    stats = dry_run(manifest)
    assert stats["ok"] is True
    assert stats["counts"]["train"] == 1
    assert gold_root()


def test_export_ct2_dry_run(capsys):
    from asr_dataset.export_ct2 import main

    sys.argv = ["export_ct2.py", "--dry-run", "--output", "models/whisper/atc-vn-ct2"]
    assert main() == 0
    out = capsys.readouterr().out
    assert "atc-vn-ct2" in out
