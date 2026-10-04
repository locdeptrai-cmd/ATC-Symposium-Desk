from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_TOOLS = _ROOT / "tools"
if _TOOLS.is_dir() and str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from reda.normalize import normalize_text  # noqa: E402
from reda.script_polish import polish_script_en  # noqa: E402


class ATCCleaner:
    """Normalize and polish ATC radio transcript text."""

    def clean(self, raw_text: str) -> str:
        normalized = normalize_text(raw_text or "")
        return polish_script_en(normalized)

    def clean_batch(self, transcripts: list[str]) -> list[str]:
        return [self.clean(text) for text in transcripts]
