"""AVI → MP4: copy H.264 when possible, encode otherwise."""
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import media_transcode as m  # noqa: E402


def _ffmpeg() -> str:
    exe = m.find_ffmpeg()
    assert exe, "ffmpeg is required for this test"
    return exe


def _make(ffmpeg: str, dest: Path, vcodec: str, extra: list[str]) -> None:
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=2:size=320x240:rate=10",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=800:duration=2",
        "-c:v",
        vcodec,
        *extra,
        "-c:a",
        "pcm_s16le",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    assert proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 64, proc.stderr


def _is_mp4(path: Path) -> bool:
    data = path.read_bytes()[:64]
    return b"ftyp" in data


def main() -> None:
    ffmpeg = _ffmpeg()
    folder = Path(tempfile.mkdtemp(prefix="atc-tx-test-"))
    try:
        h264 = folder / "h264pcm.avi"
        mpeg4 = folder / "mpeg4.avi"
        _make(ffmpeg, h264, "libx264", ["-preset", "ultrafast", "-pix_fmt", "yuv420p"])
        _make(ffmpeg, mpeg4, "mpeg4", ["-q:v", "8"])

        r1 = m.transcode_file(h264, "h264pcm.avi")
        assert r1.ok and r1.path and _is_mp4(r1.path), r1.error
        assert m._LAST_STRATEGY == "copy_video", m._LAST_STRATEGY
        m.cleanup_result(r1)

        r2 = m.transcode_file(mpeg4, "mpeg4.avi")
        assert r2.ok and r2.path and _is_mp4(r2.path), r2.error
        assert str(m._LAST_STRATEGY).startswith("encode:"), m._LAST_STRATEGY
        info = m.probe_media(r2.path, ffmpeg)
        assert info["vcodec"] == "h264" and info["has_audio"], info
        assert abs(info["duration"] - 2) < 0.3, info
        m.cleanup_result(r2)

        # A silent child must still be stopped by the deadline.
        real_popen = subprocess.Popen
        child = real_popen([sys.executable, "-c", "import time; time.sleep(60)"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        started = time.monotonic()
        def spawn(cmd, **kwargs):
            return child if cmd[0] == ffmpeg else real_popen(cmd, **kwargs)

        with patch.object(m.subprocess, "Popen", side_effect=spawn):
            try:
                m._encode_progress(ffmpeg, [], 0, None, "test", timeout=0.2)
                raise AssertionError("Expected timeout")
            except subprocess.TimeoutExpired:
                pass
        assert child.poll() is not None
        assert time.monotonic() - started < 5

        with patch.object(m, "CONVERT_SECONDS", 0):
            expired = m.transcode_file(h264, "deadline.avi")
        assert not expired.ok and "5" in expired.error
        assert h264.is_file(), "Conversion must preserve the source"
    finally:
        for item in folder.glob("*"):
            try:
                item.unlink()
            except OSError:
                pass
        try:
            folder.rmdir()
        except OSError:
            pass
    print("media_transcode_test.py: copy_video + encode paths passed")


if __name__ == "__main__":
    main()
