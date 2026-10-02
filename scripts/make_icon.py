"""Render the Galliani "G" mark (same geometry as the SVG logo in app/web/index.html) to icons.

    python -m scripts.make_icon      # -> assets/galliani.ico and assets/galliani.png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SIZE = 1024  # draw large, downsample for crisp small sizes
STOPS = [(0.0, (59, 130, 246)), (0.55, (109, 110, 247)), (1.0, (168, 85, 247))]  # #3b82f6 -> #6d6ef7 -> #a855f7


def _gradient(size: int) -> Image.Image:
    """Diagonal (top-left -> bottom-right) gradient matching the SVG's linearGradient."""
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
                if t <= t1:
                    k = (t - t0) / (t1 - t0)
                    px[x, y] = (*[round(a + (b - a) * k) for a, b in zip(c0, c1)], 255)
                    break
    return img


def _mask(size: int) -> Image.Image:
    """The SVG path `M35.3 12.7 A16 16 0 1 0 40 24 H26` (viewBox 48, stroke 8, round caps), scaled."""
    s = size / 48
    stroke = 8 * s
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    c, r = 24 * s, 16 * s
    box = (c - r - stroke / 2, c - r - stroke / 2, c + r + stroke / 2, c + r + stroke / 2)
    # PIL angles run clockwise from 3 o'clock: the G's arc spans 0 deg -> 315 deg.
    d.arc(box, start=0, end=315, fill=255, width=round(stroke))
    d.line([(26 * s, 24 * s), (40 * s, 24 * s)], fill=255, width=round(stroke))
    # Square corner where the arc meets the bar (the SVG's default miter join).
    d.rectangle((40 * s - stroke / 2, 24 * s - stroke / 2, 40 * s + stroke / 2, 24 * s + stroke / 2), fill=255)
    for x, y in [(35.3, 12.7), (26, 24)]:  # round caps
        d.ellipse((x * s - stroke / 2, y * s - stroke / 2, x * s + stroke / 2, y * s + stroke / 2), fill=255)
    return mask


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    art = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    art.paste(_gradient(SIZE), (0, 0), _mask(SIZE))
    art.resize((256, 256), Image.LANCZOS).save(ASSETS / "galliani.png")
    art.save(ASSETS / "galliani.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print(f"Wrote {ASSETS / 'galliani.ico'} and {ASSETS / 'galliani.png'}")


if __name__ == "__main__":
    main()
