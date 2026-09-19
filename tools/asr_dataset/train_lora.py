"""LoRA fine-tune recipe for Whisper on gold VN VHF (GPU). CPU = --dry-run only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from asr_dataset.paths import gold_root, manifest_path


def load_split(manifest: Path, split: str) -> list[dict]:
    rows: list[dict] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if split != "all" and row.get("split") != split:
            continue
        audio = row.get("audio")
        text = (row.get("text") or "").strip()
        if not text:
            continue
        if audio:
            wav = (manifest.parent / audio).resolve()
            if not wav.is_file():
                continue
            row["audio_path"] = str(wav)
        else:
            continue
        rows.append(row)
    return rows


def dry_run(manifest: Path) -> dict:
    counts = {"train": 0, "dev": 0, "test": 0, "with_audio": 0}
    hours = 0.0
    if not manifest.is_file():
        return {"ok": False, "error": f"Missing {manifest}", "counts": counts}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        split = str(row.get("split") or "train")
        counts[split] = counts.get(split, 0) + 1
        if row.get("audio"):
            counts["with_audio"] += 1
        hours += max(0.0, float(row.get("t_end") or 0) - float(row.get("t_start") or 0))
    return {
        "ok": True,
        "manifest": str(manifest),
        "counts": counts,
        "hours": round(hours / 3600.0, 3),
        "note": "Train on CUDA with --train. Mix 70% this gold + 30% ATCO2/ATCoSIM.",
    }


def train(args: argparse.Namespace) -> int:
    try:
        import torch
        from datasets import Audio, Dataset
        from peft import LoraConfig, get_peft_model
        from transformers import (
            Seq2SeqTrainer,
            Seq2SeqTrainingArguments,
            WhisperForConditionalGeneration,
            WhisperProcessor,
        )
    except ImportError as exc:
        print("Can GPU stack: torch, transformers, peft, datasets, librosa.", file=sys.stderr)
        print(exc, file=sys.stderr)
        return 2
    if not torch.cuda.is_available():
        print("Khong co CUDA. Dung --dry-run tren CPU.", file=sys.stderr)
        return 2
    rows = load_split(Path(args.manifest), "train")
    if len(rows) < 8:
        print("Chua du utterance co WAV (toi thieu 8). Chay export_gold.py.", file=sys.stderr)
        return 1
    processor = WhisperProcessor.from_pretrained(args.base, language="en", task="transcribe")
    model = WhisperForConditionalGeneration.from_pretrained(args.base)
    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj", "k_proj", "out_proj", "fc1", "fc2"],
        lora_dropout=0.05,
        bias="none",
    )
    model = get_peft_model(model, lora)
    ds = Dataset.from_list(
        [{"audio": r["audio_path"], "sentence": r["text"]} for r in rows]
    )
    ds = ds.cast_column("audio", Audio(sampling_rate=16000))

    def prepare(batch: dict) -> dict:
        audio = batch["audio"]
        feats = processor.feature_extractor(
            audio["array"], sampling_rate=audio["sampling_rate"], return_tensors="np"
        )
        batch["input_features"] = feats.input_features[0]
        batch["labels"] = processor.tokenizer(batch["sentence"]).input_ids
        return batch

    ds = ds.map(prepare, remove_columns=ds.column_names)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    targs = Seq2SeqTrainingArguments(
        output_dir=str(out),
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=2,
        learning_rate=1e-4,
        warmup_steps=50,
        max_steps=args.steps,
        fp16=True,
        logging_steps=10,
        save_steps=max(50, args.steps // 4),
        predict_with_generate=False,
        report_to=[],
        remove_unused_columns=False,
    )
    trainer = Seq2SeqTrainer(model=model, args=targs, train_dataset=ds)
    trainer.train()
    model.save_pretrained(str(out / "lora"))
    processor.save_pretrained(str(out / "lora"))
    print(f"Saved LoRA adapter to {out / 'lora'}")
    print("Next: python tools/asr_dataset/export_ct2.py --merge-from", out / "lora")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Whisper LoRA on VN VHF gold (GPU).")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--base", default="openai/whisper-small.en")
    parser.add_argument("--output", default=str(gold_root().parent / "models" / "whisper" / "atc-vn-lora"))
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--train", action="store_true")
    args = parser.parse_args()
    manifest = args.manifest or manifest_path()
    if args.train and not args.dry_run:
        args.manifest = manifest
        return train(args)
    stats = dry_run(manifest)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
