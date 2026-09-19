"""Regression checks for incremental file transcription without auto analysis."""
from pathlib import Path
from unittest.mock import patch

import numpy as np

import media_transcribe as mt


def test_continuous_audio_publishes_bounded_turns_before_completion(tmp_path):
    src = tmp_path / "radio.wav"
    src.write_bytes(b"sample")
    updates = []
    spans = []

    def decode(model, wav, duration, hotwords, streaming=False):
        assert streaming
        spans.append(duration)
        return [{"t_start": 0, "t_end": duration, "text": "cleared to land"}]

    with patch.object(mt.tx, "find_ffmpeg", return_value="ffmpeg"), \
         patch.object(mt, "_extract_wav", return_value=(True, "")), \
         patch.object(mt, "load_model", return_value=object()), \
         patch.object(mt, "_read_wav_mono", return_value=(np.zeros(160000), 16000)), \
         patch.object(mt, "_write_wav_slice"), \
         patch.object(mt, "_decode_window", side_effect=decode):
        text, turns, error = mt.transcribe_with_turns(src, on_turns=lambda ts: updates.append(ts))
    assert not error and text
    assert len(updates) == 3
    assert [len(ts) for ts in updates] == [1, 2, 3]
    assert max(spans) <= 4.36
    assert updates[0][0]["t_end"] < 5
    assert all("speaker_role" not in t for t in turns)


def test_job_keeps_partial_turns_and_never_analyzes(tmp_path):
    src = tmp_path / "radio.wav"
    src.write_bytes(b"sample")
    job_id = "stream-test"
    mt._JOBS[job_id] = {"id": job_id, "done": False}
    turns = [{"t_start": 0, "t_end": 4, "text": "cleared to land"}]

    def transcribe(src, on_progress, on_turns):
        on_turns(turns)
        snap = mt.job_snapshot(job_id)
        assert snap["turns"] == turns and not snap["done"]
        return "cleared to land", turns, ""

    try:
        with patch.object(mt, "transcribe_with_turns", side_effect=transcribe), \
             patch.object(mt, "_analyze_turns") as analyze:
            mt._run_job(job_id, src)
            analyze.assert_not_called()
        snap = mt.job_snapshot(job_id)
        assert snap["done"] and snap["turns"] == turns
        assert snap["analysis"] is None
    finally:
        mt._JOBS.pop(job_id, None)
