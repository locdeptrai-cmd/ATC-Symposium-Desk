"""File STT must return English from a spoken ATC phrase, not from the microphone."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import media_transcribe as stt  # noqa: E402

WAV = Path.home() / "AppData" / "Local" / "Temp" / "atc-stt-test.wav"
PHRASE = "Cleared to land runway two five left. Squawk four five two zero. Go around."


def _make_wav() -> None:
    ps = r"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = -1
$synth.SetOutputToWaveFile('{path}')
$synth.Speak('{text}')
$synth.Dispose()
""".format(path=str(WAV).replace("'", "''"), text=PHRASE.replace("'", "''"))
    subprocess.check_call(["powershell", "-NoProfile", "-Command", ps])
    assert WAV.is_file() and WAV.stat().st_size > 1000, "SAPI did not write wav"


def main() -> None:
    _make_wav()
    text, err = stt.transcribe_file(WAV)
    assert not err, err
    fold = text.lower()
    assert "land" in fold or "runway" in fold or "squawk" in fold or "around" in fold, text
    print("media_transcribe_test.py: got %r" % text)


if __name__ == "__main__":
    main()
