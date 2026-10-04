"""Regression checks for PTT-window file transcription without auto analysis."""
import os
import sys
from unittest.mock import MagicMock, patch

import numpy as np

import media_transcribe as mt


def _burst_track(sr=16000, duration=10.0, bursts=((0.4, 1.5), (4.0, 5.2), (7.4, 8.6))):
    samples = np.zeros(int(duration * sr), dtype=np.float32)
    for start, end in bursts:
        a = int(start * sr)
        b = int(end * sr)
        samples[a:b] = 0.25
    return samples, sr


def test_ptt_windows_separates_talkspurts():
    samples, sr = _burst_track()
    windows = mt.ptt_windows(samples, sr)
    assert len(windows) == 3
    assert windows[0][1] - windows[0][0] < 2.2
    assert windows[1][0] > 3.2


def test_stream_emits_each_closed_ptt_before_eof(tmp_path):
    src = tmp_path / "live-radio.webm"
    src.write_bytes(b"RIFF" + b"\x00" * 80)
    samples, sr = _burst_track()
    cursor = {"i": 0}
    read_n = int(sr * 0.25)

    def read_pcm(proc, n_samples):
        i = cursor["i"]
        take = min(n_samples, max(0, len(samples) - i))
        if take <= 0:
            return np.zeros(0, dtype=np.float32)
        chunk = samples[i : i + take]
        cursor["i"] = i + take
        return chunk

    updates = []
    decoded = []

    def decode(model, window, hotwords):
        decoded.append(len(window) / 16000.0)
        return "cleared to land"

    proc = MagicMock()
    proc.poll.return_value = None
    proc.stdout = object()

    with patch.object(mt.tx, "find_ffmpeg", return_value="ffmpeg"), \
         patch.object(mt, "_open_pcm_pipe", return_value=proc), \
         patch.object(mt, "_read_pcm", side_effect=read_pcm), \
         patch.object(mt, "load_model", return_value=object()), \
         patch.object(mt, "_decode_samples", side_effect=decode):
        text, turns, error = mt.transcribe_with_turns(
            src,
            on_turns=lambda ts: updates.append(list(ts)),
        )
    assert not error and text
    assert len(turns) == 3
    assert len(updates) == 3
    assert updates[0][0]["t_end"] < 3
    assert max(decoded) < 3.5
    assert all("speaker_role" not in t for t in turns)


def test_job_keeps_partial_turns_and_never_analyzes():
    src = MagicMock()
    src.name = "radio.wav"
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


def test_energy_slices_when_ptt_sees_silence():
    sr = 16000
    samples = np.zeros(int(12 * sr), dtype=np.float32)
    samples[int(8.0 * sr) : int(9.4 * sr)] = 0.03
    assert mt.ptt_windows(samples, sr) == []
    slices = mt._energy_slices(samples, sr)
    assert slices
    assert slices[0][0] < 9.0


def test_decode_retries_with_stronger_beam_for_low_quality():
    class Seg:
        def __init__(self, text):
            self.text = text

    calls = []

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            calls.append(kwargs.copy())
            if len(calls) == 1:
                return [Seg("uh uh")], None
            return [Seg("cleared to land runway two five right")], None

    audio = np.ones(16000, dtype=np.float32) * 0.01
    with patch.object(mt, "WHISPER_RETRY_BEAM", 2):
        text = mt._decode_samples(FakeModel(), audio, "Vietjet")
    assert "cleared to land" in text.lower()
    assert len(calls) == 2
    assert calls[1]["beam_size"] >= calls[0]["beam_size"]


def test_decode_skips_retry_when_first_pass_is_good():
    class Seg:
        def __init__(self, text):
            self.text = text

    calls = []

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            calls.append(kwargs.copy())
            return [Seg("TSN Tower Vietjet one two two five continue approach runway two five right")], None

    audio = np.ones(20000, dtype=np.float32) * 0.02
    text = mt._decode_samples(FakeModel(), audio, "Vietjet")
    assert "rwy 25r" in text.lower()
    assert len(calls) == 1


def test_decode_supports_notebook_beam_override():
    class Seg:
        text = "cleared to land runway two five right"

    calls = []

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            calls.append(kwargs.copy())
            return [Seg()], None

    audio = np.ones(20000, dtype=np.float32) * 0.02
    mt._decode_samples(FakeModel(), audio, "", beam_size=5, best_of=5)
    assert calls[0]["beam_size"] == 5
    assert calls[0]["best_of"] == 5


def test_friendly_model_error_explains_mkl_malloc(monkeypatch):
    monkeypatch.setattr(
        mt,
        "memory_status",
        lambda: {
            "ok": True,
            "pagefile_enabled": True,
            "ram_avail_mb": 4096,
            "ram_total_mb": 16384,
        },
    )
    msg = mt._friendly_model_error("mkl_malloc: failed to allocate memory")
    assert "mkl_malloc" in msg.lower()
    assert "RAM" in msg or "ram" in msg.lower()
    assert "đang bật" in msg.lower() or "pagefile" in msg.lower()
    assert "bật pagefile windows" not in msg.lower()
    assert mt._is_memory_error("mkl_malloc: failed to allocate memory")


def test_friendly_model_error_asks_pagefile_when_missing(monkeypatch):
    monkeypatch.setattr(
        mt,
        "memory_status",
        lambda: {
            "ok": True,
            "pagefile_enabled": False,
            "ram_avail_mb": 800,
            "ram_total_mb": 8192,
        },
    )
    msg = mt._friendly_model_error("mkl_malloc: failed to allocate memory")
    assert "pagefile đang tắt" in msg.lower() or "virtual memory" in msg.lower()


def test_memory_status_reports_pagefile_on_windows():
    st = mt.memory_status()
    if os.name != "nt":
        return
    assert st.get("ram_total_mb")
    assert st.get("pagefile_enabled") is not None
    assert isinstance(st["pagefile_enabled"], bool)


def test_apply_low_mem_env_caps_thread_arenas():
    mt._apply_low_mem_env()
    assert os.environ.get("CT2_PACKED_GEMM") == "0"
    assert os.environ.get("MKL_NUM_THREADS")
    assert os.environ.get("OMP_NUM_THREADS")


def test_model_status_reports_loading_progress():
    saved_state = mt._MODEL_LOAD_STATE.copy()
    mt._MODEL = None
    mt._MODEL_ERROR = ""
    mt._MODEL_LOAD_STATE = {"phase": "loading", "progress": 42, "message": "Đang nạp bộ nhận dạng..."}
    try:
        st = mt.model_status()
        assert st["phase"] == "loading"
        assert 0 <= st["progress"] <= 100
        assert "nạp" in st["message"].lower()
    finally:
        mt._MODEL_LOAD_STATE = saved_state


def test_schedule_model_preload_starts_background_load():
    saved_model = mt._MODEL
    saved_error = mt._MODEL_ERROR
    saved_state = mt._MODEL_LOAD_STATE.copy()
    mt._MODEL = None
    mt._MODEL_ERROR = ""
    mt._MODEL_LOAD_STATE = {"phase": "idle", "progress": 0, "message": ""}
    try:
        with patch.object(mt, "load_model", return_value=object()) as load_mock:
            mt.schedule_model_preload()
            assert load_mock.called
    finally:
        mt._MODEL = saved_model
        mt._MODEL_ERROR = saved_error
        mt._MODEL_LOAD_STATE = saved_state


def test_load_model_reports_warmup_oom():
    class BoomModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            raise RuntimeError("mkl_malloc: failed to allocate memory")

    fake = MagicMock()
    fake.WhisperModel = BoomModel
    saved_model = mt._MODEL
    saved_error = mt._MODEL_ERROR
    saved_mod = sys.modules.get("faster_whisper")
    mt._MODEL = None
    mt._MODEL_ERROR = ""
    sys.modules["faster_whisper"] = fake
    try:
        with patch.object(mt, "_model_candidates", return_value=["dummy"]):
            assert mt.load_model() is None
        assert mt._MODEL_ERROR
        assert "RAM" in mt._MODEL_ERROR or "mkl_malloc" in mt._MODEL_ERROR.lower()
        assert mt.model_status()["ready"] is False
        assert mt.model_status()["error"]
    finally:
        mt._MODEL = saved_model
        mt._MODEL_ERROR = saved_error
        if saved_mod is None:
            sys.modules.pop("faster_whisper", None)
        else:
            sys.modules["faster_whisper"] = saved_mod


def test_start_job_fails_fast_when_model_error(tmp_path):
    src = tmp_path / "clip.wav"
    src.write_bytes(b"RIFF")
    saved_model = mt._MODEL
    saved_error = mt._MODEL_ERROR
    mt._MODEL = None
    mt._MODEL_ERROR = "Hết RAM khi nạp bộ nhận dạng (mkl_malloc)."
    job_id = ""
    try:
        job_id = mt.start_job(src, "clip.wav")
        snap = mt.job_snapshot(job_id)
        assert snap["done"]
        assert "RAM" in snap["error"] or "mkl" in snap["error"].lower()
    finally:
        if job_id:
            mt._JOBS.pop(job_id, None)
        mt._MODEL = saved_model
        mt._MODEL_ERROR = saved_error


def test_stream_returns_partial_text_on_decode_oom(tmp_path):
    src = tmp_path / "live-radio.webm"
    src.write_bytes(b"RIFF" + b"\x00" * 80)
    samples, sr = _burst_track()
    cursor = {"i": 0}
    decoded = {"n": 0}

    def read_pcm(proc, n_samples):
        i = cursor["i"]
        take = min(n_samples, max(0, len(samples) - i))
        if take <= 0:
            return np.zeros(0, dtype=np.float32)
        chunk = samples[i : i + take]
        cursor["i"] = i + take
        return chunk

    def decode(model, window, hotwords):
        decoded["n"] += 1
        if decoded["n"] > 1:
            raise RuntimeError("mkl_malloc: failed to allocate memory")
        return "cleared to land"

    proc = MagicMock()
    proc.poll.return_value = None
    proc.stdout = object()

    with patch.object(mt.tx, "find_ffmpeg", return_value="ffmpeg"), \
         patch.object(mt, "_open_pcm_pipe", return_value=proc), \
         patch.object(mt, "_read_pcm", side_effect=read_pcm), \
         patch.object(mt, "load_model", return_value=object()), \
         patch.object(mt, "_decode_samples", side_effect=decode):
        text, turns, error = mt.transcribe_with_turns(src)
    assert "cleared to land" in text.lower()
    assert turns
    assert error
    assert "RAM" in error or "mkl_malloc" in error.lower()
