# Paste into a Kaggle Notebook (GPU). Change DATASET_SLUG.
from pathlib import Path
import pandas as pd

DATASET_SLUG = "your-username/atc-vhf-finetune"  # <-- change
DATA = Path(f"/kaggle/input/{DATASET_SLUG.split('/')[-1]}")
if not DATA.exists():
    # fallback: first input dir
    DATA = next(Path("/kaggle/input").iterdir())

train = pd.read_csv(DATA / "train_whisper.csv")
dev = pd.read_csv(DATA / "dev_whisper.csv")

def resolve_audio(rel: str) -> str:
    p = DATA / rel
    return str(p) if p.is_file() else ""

train["path"] = train["file_name"].map(resolve_audio)
dev["path"] = dev["file_name"].map(resolve_audio)
train = train[train["path"] != ""].reset_index(drop=True)
dev = dev[dev["path"] != ""].reset_index(drop=True)
print("train with audio", len(train), "dev", len(dev))

# --- Text-only repair SFT (works without WAV) ---
chat = pd.read_csv(DATA / "chat_sft.csv")
repair = chat[chat["task"] == "asr_repair"].reset_index(drop=True)
print("repair pairs", len(repair))
print(repair[["input", "output"]].head())

# --- Optional: HuggingFace Dataset for Whisper ---
# !pip install -q transformers datasets peft accelerate evaluate jiwer librosa soundfile
"""
from datasets import Dataset, Audio, DatasetDict
from transformers import WhisperProcessor, WhisperForConditionalGeneration

def to_hf(df):
    ds = Dataset.from_pandas(df[["path", "transcription"]].rename(columns={"path": "audio"}))
    return ds.cast_column("audio", Audio(sampling_rate=16000))

if len(train) >= 8:
    dsd = DatasetDict(train=to_hf(train), validation=to_hf(dev) if len(dev) else to_hf(train.head(2)))
    processor = WhisperProcessor.from_pretrained("openai/whisper-small", language="en", task="transcribe")
    print(dsd)
else:
    print("Need >=8 WAV under audio/ matching file_name. Use repair task meanwhile.")
"""
