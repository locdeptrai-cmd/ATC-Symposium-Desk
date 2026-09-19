"""Unit tests for ATC ASR eval, taxonomy, hotwords, gold split, radio repairs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from asr_dataset.entities import extract_entities
from asr_dataset.export_gold import split_for_session
from asr_dataset.hotwords import hotwords_for, infer_unit
from asr_dataset.metrics import cer, classify_error, summarize_pairs, wer
from media_transcribe import repair_radio_text


def test_wer_identical():
    assert wer("climb flight level two zero zero", "climb flight level two zero zero") == 0.0


def test_wer_substitution():
    val = wer("flight level two zero zero", "flight level two two zero")
    assert 0.1 < val < 0.5


def test_cer_empty_ref():
    assert cer("", "hello") == 1.0
    assert cer("", "") == 0.0


def test_entities_atc_utterance():
    ents = extract_entities(
        "Viet Nam three seven two descend flight level one two zero "
        "turn left heading two seven zero squawk four five two one "
        "qnh one zero one three runway two five left"
    )
    assert ents["callsign"] == "HVN372"
    assert ents["level"] == "FL120"
    assert ents["heading"] == 270
    assert ents["squawk"] == "4521"
    assert ents["qnh"] == 1013
    assert ents["runway"] == "25L"


def test_taxonomy_telephony_and_runway():
    assert classify_error("charlie jet one two three", "Vietjet one two three") in {
        "telephony_vn",
        "callsign",
    }
    assert classify_error("runway two final", "runway two five") == "runway"
    assert classify_error("tree five zero", "three five zero") == "icao_number"
    loop = "the right to the right to the right to the right to the right"
    assert classify_error(loop, "Viet Nam one two three") == "hallucination"


def test_summarize_pairs_entity_accuracy():
    pairs = [
        (
            "Viet Nam one two three climb flight level two two zero",
            "Viet Nam one two three climb flight level two zero zero",
        )
    ]
    stats = summarize_pairs(pairs)
    assert stats["n"] == 1
    assert stats["entity_accuracy"]["callsign"] == 1.0
    assert stats["entity_accuracy"]["level"] == 0.0


def test_split_is_stable_per_session():
    a = split_for_session("sessA", 1_700_000_000.0)
    b = split_for_session("sessA", 1_700_000_000.0)
    assert a == b
    assert a in {"train", "dev", "test"}


def test_hotwords_unit_saigon_not_library_dump():
    text = hotwords_for(filename="TWR_SGN_118-7.wav", unit="sgn")
    assert "Vietjet" in text
    assert "Saigon Tower" in text or "saigon" in text.lower()
    assert len(text.split()) < 80


def test_infer_unit_from_filename():
    assert infer_unit("2026_VVTS_TWR.wav") == "sgn"
    assert infer_unit("noi_bai_app.wav") == "han"


def test_radio_fixes_each_rule():
    cases = [
        ("charlie jet one two", "Vietjet"),
        ("sion one two three", "Vietjet"),
        ("viet jet air", "Vietjet"),
        ("vietnam airlines one", "Viet Nam"),
        ("viet nam one", "Viet Nam"),
        ("qi nine nine", "Viet Nam"),
        ("sona tower", "Saigon Tower"),
        ("sai gon tower", "Saigon Tower"),
        ("tan son nhat", "Tan Son Nhat"),
        ("noy bai", "Noi Bai"),
        ("later to land", "cleared to land"),
        ("continue approach over to ukraine", "continue approach"),
        ("two fellay", "two five"),
        ("fellay", "five"),
        ("runway two final", "runway two five"),
        ("niner", "nine"),
        ("tree", "three"),
        ("fife", "five"),
        ("wun", "one"),
        ("one degree", "degrees"),
    ]
    for src, needle in cases:
        out = repair_radio_text(src)
        assert needle.lower() in out.lower(), (src, out)


def test_gold_record_roundtrip(tmp_path: Path):
    from asr_dataset.export_gold import build_record

    rec = build_record(
        utterance_id="u1",
        session_id="s1",
        text="Vietjet one two three cleared to land runway two five right",
        speaker="ATCO",
        t_start=1.0,
        t_end=3.5,
        filename="sgn.wav",
        started_at=1_700_000_000.0,
        audio_rel="wav/u1.wav",
        unit="sgn",
    )
    line = json.dumps(rec)
    loaded = json.loads(line)
    assert loaded["source"] == "HUMAN"
    assert loaded["callsign"] == "VJC123"
    assert loaded["entities"]["runway"] == "25R"
    dest = tmp_path / "m.jsonl"
    dest.write_text(line + "\n", encoding="utf-8")
    assert dest.read_text(encoding="utf-8").startswith("{")


if __name__ == "__main__":
    import tempfile

    test_wer_identical()
    test_wer_substitution()
    test_cer_empty_ref()
    test_entities_atc_utterance()
    test_taxonomy_telephony_and_runway()
    test_summarize_pairs_entity_accuracy()
    test_split_is_stable_per_session()
    test_hotwords_unit_saigon_not_library_dump()
    test_infer_unit_from_filename()
    test_radio_fixes_each_rule()
    with tempfile.TemporaryDirectory() as folder:
        test_gold_record_roundtrip(Path(folder))
    print("asr_dataset tests ok")
