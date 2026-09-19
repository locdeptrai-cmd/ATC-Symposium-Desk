"""Merge LoRA into Whisper and convert to CTranslate2 for ATC Desk / reda-atc."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from asr_dataset.paths import repo_root


def merge_lora(base: str, adapter: Path, merged: Path) -> None:
    import torch
    from peft import PeftModel
    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    merged.mkdir(parents=True, exist_ok=True)
    model = WhisperForConditionalGeneration.from_pretrained(base)
    model = PeftModel.from_pretrained(model, str(adapter))
    model = model.merge_and_unload()
    model.save_pretrained(str(merged))
    processor = WhisperProcessor.from_pretrained(str(adapter) if (adapter / "tokenizer.json").is_file() else base)
    processor.save_pretrained(str(merged))
    (merged / "merge.json").write_text(
        json.dumps({"base": base, "adapter": str(adapter)}, indent=2),
        encoding="utf-8",
    )
    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def convert_ct2(merged: Path, dest: Path, quantization: str) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    cmd = [
        sys.executable,
        "-m",
        "ctranslate2.converters.transformers",
        "--model",
        str(merged),
        "--output_dir",
        str(dest),
        "--quantization",
        quantization,
        "--copy_files",
        "tokenizer.json",
        "preprocessor_config.json",
    ]
    alt = shutil.which("ct2-transformers-converter")
    if alt:
        cmd = [
            alt,
            "--model",
            str(merged),
            "--output_dir",
            str(dest),
            "--quantization",
            quantization,
            "--copy_files",
            "tokenizer.json",
        ]
    print(" ".join(cmd))
    proc = subprocess.run(cmd, check=False)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Export atc-vn-ct2 for faster-whisper.")
    parser.add_argument("--base", default="openai/whisper-small.en")
    parser.add_argument("--merge-from", type=Path, default=None, help="LoRA adapter dir.")
    parser.add_argument("--merged", type=Path, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "models" / "whisper" / "atc-vn-ct2",
    )
    parser.add_argument("--quantization", default="int8")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    plan = {
        "base": args.base,
        "adapter": str(args.merge_from) if args.merge_from else None,
        "output": str(args.output),
        "quantization": args.quantization,
        "next": "set ATC_WHISPER_MODEL to output dir; A/B with tools/asr_eval.py",
    }
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return 0
    merged = args.merged or (args.output.parent / "atc-vn-merged")
    if args.merge_from is not None:
        try:
            merge_lora(args.base, args.merge_from, merged)
        except ImportError as exc:
            print("Can transformers+peft de merge LoRA:", exc, file=sys.stderr)
            return 2
    elif not merged.is_dir():
        print("Can --merge-from LoRA hoac --merged HF dir.", file=sys.stderr)
        return 1
    code = convert_ct2(merged, args.output, args.quantization)
    if code == 0:
        print(f"CT2 model: {args.output}")
        print("A/B: python tools/asr_eval.py --from-corrections")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
