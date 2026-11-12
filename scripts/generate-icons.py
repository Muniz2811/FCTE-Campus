"""Regenerate installation icons: python -m pip install Pillow first (tooling only)."""
from pathlib import Path
from PIL import Image, ImageDraw

target = Path(__file__).resolve().parents[1] / "public" / "icons"
target.mkdir(parents=True, exist_ok=True)
scale = 4
size = 512 * scale
blue, yellow = "#003f7a", "#ffcc00"
image = Image.new("RGB", (size, size), blue)
draw = ImageDraw.Draw(image)
def box(values):
    return tuple(round(value * scale) for value in values)
draw.line(box((256, 102, 256, 410)), fill="#667e49", width=8*scale)
draw.line(box((102, 256, 410, 256)), fill="#667e49", width=8*scale)
draw.ellipse(box((153, 153, 359, 359)), outline=yellow, width=12*scale)
draw.polygon([box(point) for point in [(303, 164), (279, 279), (164, 347), (232, 232)]], fill=yellow)
draw.ellipse(box((235, 235, 277, 277)), fill=blue)
for name, pixels in [("icon-192.png", 192), ("icon-512.png", 512), ("maskable-512.png", 512), ("apple-touch-icon.png", 180)]:
    image.resize((pixels, pixels), Image.Resampling.LANCZOS).save(target / name, optimize=True)
print("4 icons generated")
