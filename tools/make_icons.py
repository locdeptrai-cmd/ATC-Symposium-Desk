"""Build PWA PNG icons from web/icons/icon.jpg (run once, commit the PNGs)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "icons" / "icon.jpg"
OUT = ROOT / "web" / "icons"
BG = (7, 16, 24, 255)


def square(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return im.crop((left, top, left + side, top + side))


def resize(im: Image.Image, size: int) -> Image.Image:
    return im.resize((size, size), Image.Resampling.LANCZOS)


def maskable(im: Image.Image, size: int = 512) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), BG)
    inner = int(size * 0.72)
    icon = resize(im, inner)
    off = (size - inner) // 2
    canvas.paste(icon, (off, off), icon)
    return canvas


def main() -> None:
    if not SRC.exists():
        raise SystemExit("missing " + str(SRC))
    base = square(Image.open(SRC))
    OUT.mkdir(parents=True, exist_ok=True)
    resize(base, 180).convert("RGB").save(OUT / "icon-180.png", "PNG", optimize=True)
    resize(base, 192).convert("RGB").save(OUT / "icon-192.png", "PNG", optimize=True)
    resize(base, 512).convert("RGB").save(OUT / "icon-512.png", "PNG", optimize=True)
    maskable(base, 512).save(OUT / "icon-maskable-512.png", "PNG", optimize=True)
    print("wrote", OUT / "icon-180.png")
    print("wrote", OUT / "icon-192.png")
    print("wrote", OUT / "icon-512.png")
    print("wrote", OUT / "icon-maskable-512.png")


if __name__ == "__main__":
    main()
