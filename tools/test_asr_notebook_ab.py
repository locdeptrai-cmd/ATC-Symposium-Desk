import numpy as np

from asr_notebook_ab import PROFILES, normalize_notebook_audio


def test_notebook_audio_normalization_preserves_window_and_is_finite():
    samples = np.linspace(-0.2, 0.2, 3200, dtype=np.float32)
    normalized = normalize_notebook_audio(samples)
    assert len(normalized) == len(samples)
    assert normalized.dtype == np.float32
    assert np.isfinite(normalized).all()
    assert np.max(np.abs(normalized)) <= 0.99
    assert np.sqrt(np.mean(normalized.astype(np.float64) ** 2)) == pytest.approx(0.1, abs=0.002)


def test_profiles_keep_runtime_and_notebook_experiments_separate():
    profiles = {profile[0]: profile for profile in PROFILES}
    assert profiles["production"][1] != profiles["notebook_filter"][1]
    assert profiles["production"][2] is None
    assert profiles["beam5"][2:4] == (5, 5)