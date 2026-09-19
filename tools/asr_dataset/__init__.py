"""ATC VHF ASR gold corpus, metrics, and training helpers."""

from __future__ import annotations

DATASET_VERSION = "dataset_v1"
ASR_VERSION = "asr_v1"
PROCESSING_VERSION = f"reda-1.5+{ASR_VERSION}+{DATASET_VERSION}"

GOLD_DIRNAME = "asr-gold"
MANIFEST_NAME = "manifest.jsonl"
ERROR_TAXONOMY = (
    "telephony_vn",
    "icao_number",
    "runway",
    "station",
    "hallucination",
    "callsign",
    "phraseology",
    "other",
)

__all__ = [
    "ASR_VERSION",
    "DATASET_VERSION",
    "ERROR_TAXONOMY",
    "GOLD_DIRNAME",
    "MANIFEST_NAME",
    "PROCESSING_VERSION",
]
