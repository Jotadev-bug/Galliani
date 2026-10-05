"""Derive the app icons from the logo tile in assets/logo.png.

    python -m scripts.make_icon      # -> assets/galliani.{ico,icns,png} and app/web/logo.png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SOURCE = ASSETS / "logo.png"
WEB_LOGO = ROOT / "app" / "web" / "logo.png"  # favicon and in-app logo, served at /logo.png
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _tile() -> Image.Image:
    """The logo tile cropped to its visible pixels and centered on a transparent square."""
    art = Image.open(SOURCE).convert("RGBA")
    art = art.crop(art.getchannel("A").getbbox())
    side = max(art.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(art, ((side - art.width) // 2, (side - art.height) // 2))
    return square


def main() -> None:
    tile = _tile()
    tile.resize((256, 256), Image.LANCZOS).save(ASSETS / "galliani.png")
    tile.resize((128, 128), Image.LANCZOS).save(WEB_LOGO, optimize=True)
    tile.save(ASSETS / "galliani.ico", sizes=[(s, s) for s in ICO_SIZES])
    tile.resize((1024, 1024), Image.LANCZOS).save(ASSETS / "galliani.icns")
    print(f"Wrote galliani.ico, galliani.icns and galliani.png in {ASSETS}, and {WEB_LOGO}")


if __name__ == "__main__":
    main()
