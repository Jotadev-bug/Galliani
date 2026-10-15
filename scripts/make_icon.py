"""Derive the app icons from the logo tile in assets/logo.png.

    python -m scripts.make_icon      # -> assets/galliani.{ico,icns,png}, app/web/logo.png and packaging/msix/Assets/
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SOURCE = ASSETS / "logo.png"
WEB_LOGO = ROOT / "app" / "web" / "logo.png"  # favicon and in-app logo, served at /logo.png
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

# Microsoft Store tiles (spec 016 R21): base name -> (width, height) at scale 100, and the scales the manifest declares.
MSIX_ASSETS_DIR = ROOT / "packaging" / "msix" / "Assets"
MSIX_TILE_COLOR = (0x12, 0x13, 0x18, 255)  # #121318, the logo tile's color (Decision 0025)
MSIX_SCALES = (100, 125, 150, 200, 400)
MSIX_ASSETS = {
    "Square44x44Logo": (44, 44),
    "Square150x150Logo": (150, 150),
    "Wide310x150Logo": (310, 150),
    "StoreLogo": (50, 50),
}


def _tile() -> Image.Image:
    """The logo tile cropped to its visible pixels and centered on a transparent square."""
    art = Image.open(SOURCE).convert("RGBA")
    art = art.crop(art.getchannel("A").getbbox())
    side = max(art.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(art, ((side - art.width) // 2, (side - art.height) // 2))
    return square


def msix_asset(tile: Image.Image, width: int, height: int) -> Image.Image:
    """The logo tile scaled to fit, on a square canvas as is, or centered on the tile color for a wide one."""
    if width == height:
        return tile.resize((width, height), Image.LANCZOS)
    canvas = Image.new("RGBA", (width, height), MSIX_TILE_COLOR)
    side = round(height * 0.8)
    canvas.paste(tile.resize((side, side), Image.LANCZOS), ((width - side) // 2, (height - side) // 2),
                 tile.resize((side, side), Image.LANCZOS))
    return canvas


def write_msix_assets(tile: Image.Image, out_dir: Path = MSIX_ASSETS_DIR) -> list[Path]:
    """`<Name>.scale-<N>.png` for every tile and scale, plus `<Name>.png` (the 200% tile), which the manifest names."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, (width, height) in MSIX_ASSETS.items():
        for scale in MSIX_SCALES:
            path = out_dir / f"{name}.scale-{scale}.png"
            msix_asset(tile, round(width * scale / 100), round(height * scale / 100)).save(path, optimize=True)
            written.append(path)
        # `makeappx` checks the file names the manifest declares, so the unscaled name must exist too. It is the 200% tile.
        base = out_dir / f"{name}.png"
        msix_asset(tile, width * 2, height * 2).save(base, optimize=True)
        written.append(base)
    return written


def main() -> None:
    tile = _tile()
    tile.resize((256, 256), Image.LANCZOS).save(ASSETS / "galliani.png")
    tile.resize((128, 128), Image.LANCZOS).save(WEB_LOGO, optimize=True)
    tile.save(ASSETS / "galliani.ico", sizes=[(s, s) for s in ICO_SIZES])
    tile.resize((1024, 1024), Image.LANCZOS).save(ASSETS / "galliani.icns")
    write_msix_assets(tile)
    print(f"Wrote galliani.ico, galliani.icns and galliani.png in {ASSETS}, {WEB_LOGO} and the Store tiles in {MSIX_ASSETS_DIR}")


if __name__ == "__main__":
    main()
