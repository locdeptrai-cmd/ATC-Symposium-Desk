"""Unit tests for ATC ASR eval, taxonomy, hotwords, gold split, radio repairs."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from unittest.mock import patch

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
    assert "TSN Tower" in text or "tsn" in text.lower() or "saigon" in text.lower()
    assert len(text.split()) < 80


def test_infer_unit_from_filename():
    assert infer_unit("2026_VVTS_TWR.wav") == "sgn"
    assert infer_unit("noi_bai_app.wav") == "han"


def test_radio_fixes_each_rule():
    cases = [
        ("charlie jet one two", "VJC12"),
        ("sion one two three", "VJC123"),
        ("viet jet air", "Vietjet"),
        ("vietnam airlines one", "HVN1"),
        ("viet nam one", "HVN1"),
        ("qi nine nine", "HVN"),
        ("Viet nam one two two five", "HVN1225"),
        ("runway two five right", "RWY 25R"),
        ("ils whiskey runway two five right", "ILSw RWY 25R"),
        ("continue of course runway two seven right", "continue approach RWY 25R"),
        ("rejet one two two five", "VJC1225"),
        ("sona tower", "TSN Tower"),
        ("sai gon tower", "TSN Tower"),
        ("tan son nhat", "Tan Son Nhat"),
        ("noy bai", "Noi Bai"),
        ("later to land", "cleared to land"),
        ("continue approach over to ukraine", "continue approach"),
        ("two fellay", "two five"),
        ("fellay", "five"),
        ("runway two final", "RWY 25"),
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


def test_parse_clock_excel_types():
    from asr_dataset.ingest_finetune import parse_clock

    assert parse_clock(timedelta(seconds=56)) == 56.0
    assert parse_clock(dt_time(0, 1, 3)) == 63.0
    assert parse_clock(datetime(1899, 12, 30, 0, 0, 56)) == 56.0
    assert parse_clock("00:00:56") == 56.0
    assert parse_clock("0:00:56") == 56.0


def test_parse_excel_time_cells_and_vietnamese_headers():
    from openpyxl import Workbook

    from asr_dataset.ingest_finetune import parse_excel

    tmp = Path(tempfile.mkdtemp()) / "vhf.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Bắt đầu", "Kết thúc", "Vai", "Nội dung"])
    ws.append([dt_time(0, 0, 56), dt_time(0, 1, 2), "PILOT", "TSN Tower VJC1225"])
    ws.append([timedelta(seconds=63), timedelta(seconds=67), "ATCO", "continue approach"])
    wb.save(tmp)
    rows = parse_excel(tmp)
    assert len(rows) == 2, rows
    assert rows[0]["t_start"] == 56.0
    assert rows[0]["speaker"] == "PILOT"
    assert "VJC1225" in rows[0]["text"]
    assert rows[1]["t_start"] == 63.0
    assert rows[1]["speaker"] == "ATCO"


def test_stem_key_pairs_vjc1225_excel_and_audio():
    from asr_dataset.ingest_finetune import stem_key

    assert stem_key("VJC1225 text.xlsx") == "vjc1225"
    assert stem_key("vjc1225.mp4") == "vjc1225"
    assert stem_key("VJC1225 text.xlsx") == stem_key("vjc1225.mp4")


def test_rebase_wallclock_excel_times():
    from asr_dataset.ingest_finetune import _rebase_times

    origin = 22 * 3600 + 20 * 60
    rows = [
        {"t_start": origin, "t_end": origin + 8, "text": "a", "speaker": "ATCO"},
        {"t_start": origin + 10, "t_end": origin + 16, "text": "b", "speaker": "PILOT"},
    ]
    out = _rebase_times(rows)
    assert out[0]["t_start"] == 0
    assert abs(out[1]["t_start"] - 10) < 0.01


def test_gold_turns_lookup_by_audio_stem(tmp_path):
    from asr_dataset import ingest_finetune as inf

    man = tmp_path / "manifest.jsonl"
    rows = [
        {"speaker": "PILOT", "text": "TSN Tower VJC1225", "t_start": 56, "t_end": 62, "asr": ""},
        {"speaker": "ATCO", "text": "continue approach RWY 25R", "t_start": 63, "t_end": 70, "asr": ""},
    ]
    with patch.object(inf, "manifest_path", return_value=man), patch.object(inf, "ensure_gold_dirs", return_value=tmp_path):
        inf.append_gold_rows(
            [{"speaker": "ATCO", "text": "template dummy", "t_start": 5, "t_end": 12, "asr": ""}],
            "VJC1225 text.xlsx",
            None,
            "ft-old",
        )
        inf.append_gold_rows(rows, "VJC1225 text.xlsx", None, "reda-vjc1225")
        turns = inf.gold_turns_for("vjc1225.mp4")
        payload = inf.gold_payload_for("vjc1225.mp4")
    assert len(turns) == 2
    assert turns[0]["t_start"] == 56
    assert "VJC1225" in turns[0]["text"]
    assert payload["count"] == 2
    assert "template dummy" not in payload["text"]


def test_parse_real_vjc1225_excel_if_present():
    src = Path(__file__).resolve().parents[2] / "VJC1225 text.xlsx"
    if not src.is_file():
        return
    from asr_dataset.ingest_finetune import parse_excel, stem_key, turns_from_rows

    rows = parse_excel(src)
    assert rows, "VJC1225 Excel phai parse duoc"
    turns = turns_from_rows(rows)
    assert turns
    assert stem_key(src.name) == "vjc1225"
    assert turns[0]["t_start"] >= 0
    assert any("VJC" in (t["text"] or "").upper() or "TOWER" in (t["text"] or "").upper() for t in turns)


def test_seed_glossary_phrases_from_sources(tmp_path):
    from asr_dataset import ingest_finetune as inf

    tsv = tmp_path / "doc4444-phraseology.tsv"
    tsv.write_text("domain\tabbr\ten\tvi\tnote\tsource\nphraseology\t\tREAD BACK\tDoc lai\t\ttest\n", encoding="utf-8")
    user = tmp_path / "user-phraseology.json"
    user.write_text(json.dumps({"entries": [{"en": "line up and wait", "vi": "vao duong CHC va cho"}]}), encoding="utf-8")
    out_path = tmp_path / "glossary_phrases.json"
    with patch.object(inf, "_phrase_sources", return_value=[tsv, user]), patch.object(
        inf, "glossary_phrases_path", return_value=out_path
    ):
        payload = inf.seed_glossary_phrases(limit=10)
        phrases = inf.load_glossary_phrases()
    assert payload["ok"] and payload["count"] >= 2
    assert "READ BACK" in phrases
    assert "line up and wait" in phrases


def test_hotwords_include_seeded_glossary_phrases(tmp_path):
    from asr_dataset import hotwords as hw

    seeded = tmp_path / "glossary_phrases.json"
    seeded.write_text(json.dumps({"phrases": ["READ BACK", "HOLD POSITION"]}), encoding="utf-8")
    with patch.object(hw, "gold_root", return_value=tmp_path):
        text = hw.hotwords_for(filename="twr_sgn.wav", unit="sgn")
    lower = text.lower()
    assert "read back" in lower
    assert "hold position" in lower


def test_multipart_uploads_excel_and_audio():
    from serve import parse_multipart_uploads

    boundary = "----BoundaryTest"
    excel = b"PK\x03\x04excel"
    audio = b"RIFFWAVEfmt "

    def part(name, filename, data, ctype):
        return (
            ("--" + boundary + "\r\n").encode()
            + ('Content-Disposition: form-data; name="%s"; filename="%s"\r\n' % (name, filename)).encode()
            + ("Content-Type: %s\r\n\r\n" % ctype).encode()
            + data
            + b"\r\n"
        )

    body = part(
        "excel",
        "VJC1225 text.xlsx",
        excel,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    body += part("audio", "vjc1225.mp4", audio, "video/mp4")
    body += ("--" + boundary + "--\r\n").encode()
    files = parse_multipart_uploads(body, "multipart/form-data; boundary=" + boundary)
    assert files["excel"][0] == "VJC1225 text.xlsx"
    assert files["excel"][1] == excel
    assert files["audio"][0] == "vjc1225.mp4"
    assert files["audio"][1] == audio


def test_mix_train_rows_keeps_gold_and_fills_30_percent():
    from asr_dataset.recipe import mix_train_rows

    gold = [{"id": i} for i in range(70)]
    extra = [{"id": f"x{i}"} for i in range(200)]
    mixed = mix_train_rows(gold, extra, 0.7)
    assert len(mixed) == 100
    assert mixed[0]["id"] == 0
    assert mixed[70]["id"] == "x0"


def test_resolve_model_alias_tclin():
    from asr_dataset.recipe import AB_DIRNAME, resolve_model_id

    path = resolve_model_id("tclin").replace("\\", "/")
    assert AB_DIRNAME in path


def test_write_mix_records_and_load_train(tmp_path, monkeypatch):
    import numpy as np

    from asr_dataset.prepare_mix import write_mix_records
    from asr_dataset import recipe as recipe_mod

    rows = []
    for i in range(5):
        rows.append(
            {
                "id": f"u{i}",
                "text": "cleared to land",
                "samples": np.zeros(1600, dtype=np.float32),
                "sr": 16000,
                "t_end": 0.1,
            }
        )
    result = write_mix_records(rows, tmp_path)
    assert result["count"] == 5
    monkeypatch.setattr(recipe_mod, "mix_manifest_path", lambda: tmp_path / "manifest.jsonl")
    train_rows = recipe_mod.load_mix_rows("train")
    test_rows = recipe_mod.load_mix_rows("test")
    assert len(train_rows) == 4
    assert len(test_rows) == 1


def test_eval_payload_from_gold_jsonl(tmp_path):
    from asr_eval import eval_payload

    gold = tmp_path / "manifest.jsonl"
    gold.write_text(
        json.dumps({"id": "1", "text": "cleared to land", "hyp": "cleared to land", "split": "test"})
        + "\n",
        encoding="utf-8",
    )
    stats = eval_payload(gold=gold, from_corrections=False, split="test")
    assert stats["ok"] is True
    assert stats["n"] == 1
    assert stats["wer"] == 0.0


def test_corpus_stats_includes_recipe():
    from asr_dataset.ingest_finetune import corpus_stats

    stats = corpus_stats()
    assert stats["recipe"]["train_base"] == "SingularityUS/ATC-whisper-turbo-v1"
    assert stats["recipe"]["ab_hf"].endswith("turbo-atcosim-finetune")


if __name__ == "__main__":
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
    test_parse_clock_excel_types()
    test_parse_excel_time_cells_and_vietnamese_headers()
    test_stem_key_pairs_vjc1225_excel_and_audio()
    test_rebase_wallclock_excel_times()
    test_parse_real_vjc1225_excel_if_present()
    test_multipart_uploads_excel_and_audio()
    test_mix_train_rows_keeps_gold_and_fills_30_percent()
    test_resolve_model_alias_tclin()
    test_corpus_stats_includes_recipe()
    with tempfile.TemporaryDirectory() as folder:
        test_gold_record_roundtrip(Path(folder))
    with tempfile.TemporaryDirectory() as folder:
        test_eval_payload_from_gold_jsonl(Path(folder))
    sample = (
        "Saigon Tower sin charo Vietjet one two two five or ils whiskey "
        "runway two five right Vietjet one two three five tower continue of course "
        "runway two seven right"
    )
    polished = repair_radio_text(sample)
    assert "TSN Tower" in polished, polished
    assert "VJC1225" in polished, polished
    assert "ILSw RWY 25R" in polished, polished
    assert "VJC1235" in polished, polished
    assert "continue approach RWY 25R" in polished, polished
    from asr_dataset.ingest_finetune import learn_from_pair, parse_excel, write_template

    tmp = Path(tempfile.mkdtemp())
    xlsx = write_template(tmp / "t.xlsx")
    rows = parse_excel(xlsx)
    assert len(rows) >= 3, rows
    assert rows[0]["speaker"] == "ATCO"
    assert "TSN Tower" in rows[0]["text"]
    assert "Saigon Tower" in (rows[0].get("asr") or "")
    bucket = {}
    learn_from_pair(rows[0]["asr"], rows[0]["text"], bucket)
    assert bucket, bucket
    print("asr_dataset tests ok")
