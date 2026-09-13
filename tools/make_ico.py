"""Write a Windows .ico (PNG payload) from web/icons/icon-192.png."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "icons" / "icon-192.png"
DEST = ROOT / "build" / "app.ico"


def png_to_ico(png: bytes, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack("<HHH", 0, 1, 1)
    # ICONDIRENTRY width/height are bytes; 192 fits. PNG payload carries the real image.
    entry = struct.pack("<BBBBHHII", 192, 192, 0, 0, 1, 32, len(png), 6 + 16)
    dest.write_bytes(header + entry + png)


def main() -> None:
    if not SRC.is_file():
        raise SystemExit("thieu " + str(SRC))
    png_to_ico(SRC.read_bytes(), DEST)
    print("wrote", DEST, "(%s bytes)" % DEST.stat().st_size)


if __name__ == "__main__":
    sys.exit(main())
