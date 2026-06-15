# tools/make_icon.py
"""Generate app/ui/img/tv2mt5.ico — a placeholder using the tray-icon style.

Run: python tools/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "app" / "ui" / "img" / "tv2mt5.ico"


def build() -> None:
    size = 256
    img = Image.new("RGBA", (size, size), "#1f2430")
    d = ImageDraw.Draw(img)
    m = size // 4
    d.rounded_rectangle([m, m, size - m, size - m], radius=size // 12, fill="#2d6cdf")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
