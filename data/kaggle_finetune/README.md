# Kaggle fine-tune pack — ATC VHF (VN)

Upload this folder as a **Kaggle Dataset**, then attach it to a Notebook.

## Layout

```
kaggle_finetune/
  train.csv              # full metadata (ASR)
  dev.csv
  test.csv
  train_whisper.csv      # minimal: file_name, transcription, split
  dev_whisper.csv
  test_whisper.csv
  all.csv                # all splits combined
  manifest.jsonl         # same rows as Desk gold export style
  chat_sft.csv           # instruction/input/output (LLM / repair LoRA)
  chat_sft.jsonl
  blank_template.csv     # empty rows to fill gold labels
  blank_template.xlsx
  README.md              # this file
  audio/                 # PUT your .wav here (utt_*.wav or keep paths in CSV)
  notebook_snippet.py    # copy into Kaggle notebook
```

## Required columns for Whisper fine-tune

| column | meaning |
|--------|---------|
| `audio` / `file_name` | relative path under dataset root, e.g. `audio/utt_vjc1225_01.wav` |
| `text` / `transcription` | **gold** transcript (ICAO phraseology) |
| `split` | `train` / `dev` / `test` |

Optional: `speaker` (ATCO|PILOT), `callsign`, `freq_mhz`, `t_start`, `t_end`.

## How to fill gold labels

1. Listen to each clip (or full tape with `t_start`/`t_end`).
2. Write exact phraseology in `text` — do **not** invent unheard clearances.
3. Set `speaker` = ATCO or PILOT.
4. When WAV is present under `audio/`, set `has_audio` = 1.
5. Keep `split` balanced (~70% train / 20% dev / 10% test) or leave auto hashes.

## Kaggle notebook (Whisper + PEFT)

See `notebook_snippet.py`. Typical base: `openai/whisper-small` or `openai/whisper-large-v3`.

```python
import pandas as pd
from pathlib import Path
DATA = Path('/kaggle/input/your-dataset-slug')  # change slug
train = pd.read_csv(DATA / 'train_whisper.csv')
# map file_name -> full path
train['audio'] = train['file_name'].apply(lambda x: str(DATA / x))
```

## chat_sft.csv tasks

- `asr_text` — audio metadata → gold text (needs audio later)
- `asr_repair` — noisy ASR → gold (text-only, works immediately on Kaggle)
- `phraseology` — normalize standard phrases (text-only)

## Compatibility with ATC Symposium Desk

Desk gold export uses JSONL fields: `id`, `audio`, `text`, `speaker`, `t_start`, `t_end`, `split`, …
`manifest.jsonl` here matches that shape so you can round-trip on-prem ↔ Kaggle.
