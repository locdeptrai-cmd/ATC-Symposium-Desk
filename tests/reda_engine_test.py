"""REDA concept-level compare — ported from reda-atc, no FastAPI."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from reda.engine import analyze, analyze_text  # noqa: E402
from reda.normalize_fn import (  # noqa: E402
    is_ack_only,
    normalize_callsign,
    normalize_freq,
    normalize_heading,
    normalize_level,
    normalize_qnh,
    normalize_squawk,
)


def test_normalize_examples():
    assert normalize_level("flight level two zero zero") == ("FL200", "FL")
    assert normalize_level("three thousand feet")[0] == "3000FT"
    assert normalize_heading("heading two seven zero") == 270
    assert normalize_squawk("squawk four five two one") == "4521"
    assert normalize_freq("one one eight decimal seven") == "118.700"
    assert normalize_qnh("qnh one zero one three") == (1013, "HPA")
    assert normalize_callsign("viet nam 123") == "VN123"
    assert normalize_callsign("vietnam one two three") == "VN123"
    assert is_ack_only("Roger Viet Nam 123")


def test_level_mismatch():
    out = analyze(
        [
            {"t_start": 0.2, "t_end": 3.2, "text": "Viet Nam 123 climb flight level two zero zero"},
            {"t_start": 4.0, "t_end": 7.5, "text": "climbing flight level two two zero Viet Nam 123"},
        ],
        filename="demo_level.wav",
    )
    types = {i["type"] for i in out["issues"]}
    assert "MISMATCH" in types
    mismatch = next(i for i in out["issues"] if i["type"] == "MISMATCH")
    assert mismatch["field"] == "level"
    assert mismatch["expected"] == "FL200"
    assert mismatch["got"] == "FL220"
    assert mismatch["severity"] == "RED"
    assert "FL200" in out["minutes_en"]
    assert "READBACK DEBRIEF MINUTES" in out["minutes_en"]


def test_roger_not_readback():
    out = analyze(
        [
            {"t_start": 0.2, "t_end": 3.0, "text": "Viet Nam 123 climb flight level two zero zero"},
            {"t_start": 3.6, "t_end": 5.2, "text": "Roger Viet Nam 123"},
        ]
    )
    assert any(i["rule_id"] == "R_ROGER_NOT_RB" for i in out["issues"])
    assert out["summary"]["amber"] >= 1


def test_squawk_mismatch_from_plain_text():
    out = analyze_text(
        "Viet Nam 123 squawk four five two one. squawk four five two two Viet Nam 123",
        filename="paste.txt",
    )
    mismatch = next((i for i in out["issues"] if i["type"] == "MISMATCH"), None)
    assert mismatch is not None
    assert mismatch["expected"] == "4521"
    assert mismatch["got"] == "4522"


def test_clean_readback():
    out = analyze(
        [
            {"t_start": 0.2, "t_end": 3.2, "text": "Viet Nam 123 climb flight level two zero zero"},
            {"t_start": 4.0, "t_end": 7.5, "text": "climbing flight level two zero zero Viet Nam 123"},
        ]
    )
    assert out["issues"] == []
    assert out["summary"]["ok_pairs"] == 1
    assert "No concept-level readback error" in out["minutes_en"]


if __name__ == "__main__":
    test_normalize_examples()
    test_level_mismatch()
    test_roger_not_readback()
    test_squawk_mismatch_from_plain_text()
    test_clean_readback()
    print("reda_engine_test.py: ok")
