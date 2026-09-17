"""PTT grouping and loop collapse for radio STT."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import media_transcribe as stt  # noqa: E402


def test_collapse() -> None:
    text = stt.collapse_loops("roger nine roger nine roger nine roger nine land")
    assert "roger nine" in text.lower()
    assert text.lower().count("roger nine") <= 2, text


def test_ptt_windows() -> None:
    sr = 16000
    x = np.zeros(sr * 4, dtype=np.float32)
    x[int(0.5 * sr) : int(1.2 * sr)] = 0.2
    x[int(1.4 * sr) : int(2.1 * sr)] = 0.2
    x[int(3.2 * sr) : int(3.7 * sr)] = 0.2
    wins = stt.ptt_windows(x, sr, min_dur=0.3, merge_gap=0.5, max_span=18)
    assert len(wins) == 2, wins
    assert wins[0][1] - wins[0][0] > 1.0
    assert wins[1][0] > 3.0


def main() -> None:
    test_collapse()
    test_ptt_windows()
    print("media_transcribe_ptt_test.py: ok")


if __name__ == "__main__":
    main()
