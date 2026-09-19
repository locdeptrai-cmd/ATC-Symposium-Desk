# -*- mode: python ; coding: utf-8 -*-
"""One-file Windows build: ATC-Desk.exe with bundled web UI + library DB."""

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve()
WEB = ROOT / "web"

crypto_datas, crypto_binaries, crypto_hidden = collect_all("cryptography")
fw_datas, fw_binaries, fw_hidden = collect_all("faster_whisper")
ct_datas, ct_binaries, ct_hidden = collect_all("ctranslate2")
np_datas, np_binaries, np_hidden = collect_all("numpy")
try:
    av_datas, av_binaries, av_hidden = collect_all("av")
except Exception:
    av_datas, av_binaries, av_hidden = [], [], []


def web_datas() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(WEB):
        dirnames[:] = [name for name in dirnames if name != "certs"]
        for name in filenames:
            full = Path(dirpath) / name
            rel_dir = Path("web") / Path(dirpath).relative_to(WEB)
            entries.append((str(full), str(rel_dir)))
    sqlite = WEB / "data" / "library.sqlite"
    if not sqlite.is_file() or sqlite.stat().st_size < 1000:
        raise SystemExit("ATC-Desk.spec: thieu web/data/library.sqlite")
    snapshot = WEB / "js" / "library-data.js"
    if not snapshot.is_file() or snapshot.stat().st_size < 1000:
        raise SystemExit("ATC-Desk.spec: thieu web/js/library-data.js")
    sig = ROOT / "SIGNATURE.txt"
    if not sig.is_file() or "created by" not in sig.read_text(encoding="utf-8"):
        raise SystemExit("ATC-Desk.spec: thieu SIGNATURE.txt")
    return entries


def stt_datas() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    turbo = ROOT / "models" / "whisper" / "atc-turbo-ct2"
    weights = turbo / "model.bin"
    if not weights.is_file() or weights.stat().st_size < 400_000_000:
        raise SystemExit("ATC-Desk.spec: thieu models/whisper/atc-turbo-ct2 (model.bin)")
    for item in turbo.iterdir():
        if item.is_file():
            entries.append((str(item), "models/whisper/atc-turbo-ct2"))
    for name in ("vn-airline-spoken.tsv", "vn-callsigns.tsv"):
        path = ROOT / "data" / name
        if path.is_file():
            entries.append((str(path), "data"))
    return entries


def ffmpeg_binaries() -> list[tuple[str, str]]:
    ff = ROOT / "tools" / "bin" / "ffmpeg.exe"
    if not ff.is_file() or ff.stat().st_size < 1_000_000:
        raise SystemExit("ATC-Desk.spec: thieu tools/bin/ffmpeg.exe — chay tools/dong-goi-windows.ps1")
    return [(str(ff.resolve()), "bin")]


datas = (
    crypto_datas
    + fw_datas
    + ct_datas
    + np_datas
    + av_datas
    + web_datas()
    + stt_datas()
    + [
        (str(ROOT / "VERSION"), "."),
        (str(ROOT / "SIGNATURE.txt"), "."),
    ]
)
binaries = crypto_binaries + fw_binaries + ct_binaries + np_binaries + av_binaries + ffmpeg_binaries()
hiddenimports = list(
    dict.fromkeys(
        list(crypto_hidden)
        + list(fw_hidden)
        + list(ct_hidden)
        + list(np_hidden)
        + list(av_hidden)
        + [
            "app_paths",
            "media_transcode",
            "media_transcribe",
            "reda",
            "reda.engine",
            "reda.compare",
            "reda.concept",
            "reda.lexicon",
            "reda.normalize",
            "reda.normalize_fn",
            "reda.pairing",
            "reda.parse",
            "reda.callsign",
            "reda.store",
            "reda.script_polish",
            "asr_dataset",
            "asr_dataset.entities",
            "asr_dataset.metrics",
            "asr_dataset.hotwords",
            "asr_dataset.paths",
            "asr_dataset.audio_io",
            "asr_dataset.export_gold",
            "asr_dataset.append_gold",
        ]
    )
)
ICON = ROOT / "build" / "app.ico"

a = Analysis(
    [str(ROOT / "tools" / "serve.py")],
    pathex=[str(ROOT), str(ROOT / "tools")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(ROOT / "tools" / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "torchvision",
        "torchaudio",
        "tensorboard",
        "tensorflow",
        "tensorflow_intel",
        "keras",
        "jax",
        "flax",
        "transformers",
        "tokenizers",
        "huggingface_hub",
        "safetensors",
        "tokenizers",
        "onnxruntime",
        "sklearn",
        "scipy",
        "pandas",
        "matplotlib",
        "PIL",
        "cv2",
        "notebook",
        "jupyter",
        "jupyter_client",
        "jupyter_core",
        "IPython",
        "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ATC-Desk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.is_file() else None,
)
