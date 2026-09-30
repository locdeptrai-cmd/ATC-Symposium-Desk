import json
from unittest.mock import patch

import numpy as np

import media_transcribe as mt
from asr_dataset import ingest_finetune as ing
from asr_dataset.hotwords import hotwords_for
from asr_dataset.paths import manifest_path
from asr_dataset.vocabulary import excel_phrases, vocabulary_revision


def test_excel_import_updates_hints_and_semantic_revision(tmp_path, monkeypatch):
    monkeypatch.setenv("ATC_ASR_GOLD", str(tmp_path))
    revision = vocabulary_revision()
    from openpyxl import Workbook
    book = Workbook()
    sheet = book.active
    sheet.append(["speaker", "text", "t_start", "t_end"])
    sheet.append(["ATCO", "Vacate taxiway Zulu", 0, 3])
    file = tmp_path / "new.xlsx"
    book.save(file)
    ing.parse_excel_payload(file, file.name, "new.mp4")
    assert "Vacate taxiway Zulu" in excel_phrases("new.mp4")
    assert "Vacate taxiway Zulu" in hotwords_for("new.mp4")
    assert vocabulary_revision() != revision
    revision = vocabulary_revision()
    # An identical re-import must not cause another round of automatic ASR.
    ing.parse_excel_payload(file, file.name, "new.mp4")
    assert vocabulary_revision() == revision
    assert ing.corpus_stats()["excel_phrase_count"] == 1


def test_later_quiet_speech_is_not_masked_by_first_loud_call():
    sr = 16000
    audio = np.zeros(sr * 13, dtype=np.float32)
    audio[:sr * 2] = .3
    audio[sr * 5:sr * 9] = .02
    slices = mt._ready_ptt_slices(audio, sr, eof=True, emitted_until=3, origin=0)
    assert slices
    assert max(end for _, end, _, _ in slices) >= 9
    assert all(start >= 3 for start, _, _, _ in slices)


def test_eof_does_not_drop_tail_of_long_transmission():
    sr = 16000
    audio = np.ones(sr * 25, dtype=np.float32) * .05
    slices = mt._ready_ptt_slices(audio, sr, eof=True, emitted_until=0, origin=0)
    assert len(slices) >= 4
    assert slices[-1][1] == 25
    assert all(end - start <= mt.PTT_FORCE_SEC for start, end, _, _ in slices)


def test_failed_job_finishes_and_preserves_partial_text(tmp_path):
    src = tmp_path / "test.wav"
    src.write_bytes(b"audio")
    mt._JOBS["failure-test"] = {"id": "failure-test", "text": "first call"}
    try:
        with patch.object(mt, "transcribe_with_turns", side_effect=RuntimeError("decoder failed")):
            mt._run_job("failure-test", src)
        snap = mt.job_snapshot("failure-test")
        assert snap["done"] and "decoder failed" in snap["error"]
        assert snap["text"] == "first call"
        assert not src.exists()
    finally:
        mt._JOBS.pop("failure-test")


def test_active_job_cannot_be_swept(tmp_path):
    src = tmp_path / "still-decoding.wav"
    src.write_bytes(b"audio")
    mt._JOBS["active-test"] = {"id": "active-test", "created": 1, "done": False, "src": src}
    try:
        mt.sweep_jobs(max_age=1)
        assert "active-test" in mt._JOBS and src.exists()
    finally:
        mt._JOBS.pop("active-test")
