# -*- mode: python ; coding: utf-8 -*-
"""One-file Windows build: ATC-Desk.exe with bundled web UI + library DB."""

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve()
WEB = ROOT / "web"

crypto_datas, crypto_binaries, crypto_hidden = collect_all("cryptography")


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


datas = crypto_datas + web_datas() + [
    (str(ROOT / "VERSION"), "."),
    (str(ROOT / "SIGNATURE.txt"), "."),
]
binaries = crypto_binaries
hiddenimports = list(crypto_hidden) + [
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
]
ICON = ROOT / "build" / "app.ico"

a = Analysis(
    [str(ROOT / "tools" / "serve.py")],
    pathex=[str(ROOT), str(ROOT / "tools")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
