"""
One-off helper: generates simple placeholder background images for every
location in data/locations.py. The finished bot ships with these already
generated, so most owners never need to run this -- it's here for anyone
who adds new locations later and wants matching placeholder art.

Usage: pip install pillow, then: python scripts/generate_placeholder_backgrounds.py

Owners should eventually replace these with real art -- see
backgrounds/README.md for the exact filenames the bot expects.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.locations import LOCATIONS, BACKGROUNDS_DIR

WIDTH, HEIGHT = 1024, 576

# Muted gradient (top -> bottom) per category, so the pool has some visual variety.
PALETTES = {
    "urban": ("#2b2f36", "#4a5568"),
    "nature": ("#1f3b2c", "#3f7d54"),
    "fantasy": ("#2e1f3d", "#6b46a1"),
    "scifi": ("#0f2a3d", "#1b6ea8"),
    "mystery": ("#1a1a1a", "#3a3a3a"),
    "historical": ("#3d2f1f", "#8a6a3f"),
    "everyday": ("#3d2f2f", "#b3714f"),
    "transit": ("#1f3438", "#2f7d84"),
}

# Optional nicer fonts if available in this environment; falls back to
# Pillow's built-in font when not (e.g. on a bare deploy machine).
_FONT_CANDIDATES_TITLE = [
    "/mnt/skills/examples/canvas-design/canvas-fonts/BigShoulders-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_FONT_CANDIDATES_CAPTION = [
    "/mnt/skills/examples/canvas-design/canvas-fonts/IBMPlexMono-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(candidates, size):
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _hex_to_rgb(hex_color: str):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def _draw_vertical_gradient(draw: ImageDraw.ImageDraw, top_hex: str, bottom_hex: str):
    top_rgb = _hex_to_rgb(top_hex)
    bottom_rgb = _hex_to_rgb(bottom_hex)
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(top_rgb[0] + (bottom_rgb[0] - top_rgb[0]) * t)
        g = int(top_rgb[1] + (bottom_rgb[1] - top_rgb[1]) * t)
        b = int(top_rgb[2] + (bottom_rgb[2] - top_rgb[2]) * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))


def _centered_text(draw, y_offset, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (WIDTH - text_w) / 2
    y = (HEIGHT - text_h) / 2 + y_offset
    draw.text((x, y), text, font=font, fill=fill)


def generate_one(location: dict, title_font, caption_font) -> Image.Image:
    top_color, bottom_color = PALETTES.get(location["category"], PALETTES["urban"])
    img = Image.new("RGB", (WIDTH, HEIGHT), top_color)
    draw = ImageDraw.Draw(img)
    _draw_vertical_gradient(draw, top_color, bottom_color)

    # subtle vignette for a bit of depth
    overlay = Image.new("L", (WIDTH, HEIGHT), 0)
    odraw = ImageDraw.Draw(overlay)
    odraw.ellipse((-WIDTH * 0.3, -HEIGHT * 0.3, WIDTH * 1.3, HEIGHT * 1.3), fill=40)
    img = Image.composite(Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0)), img, overlay.point(lambda p: 255 - p))
    draw = ImageDraw.Draw(img)

    _centered_text(draw, -24, location["display_name"], title_font, "white")
    _centered_text(draw, 210, "placeholder -- replace in backgrounds/", caption_font, "#dddddd")
    return img


def generate():
    BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)
    title_font = _font(_FONT_CANDIDATES_TITLE, 52)
    caption_font = _font(_FONT_CANDIDATES_CAPTION, 20)

    for location in LOCATIONS:
        img = generate_one(location, title_font, caption_font)
        img.save(BACKGROUNDS_DIR / f"{location['key']}.png")

    # Neutral fallback used when an owner-provided free-text theme doesn't
    # match any location key (see episode_engine.run_episode_1).
    default_loc = {"display_name": "A New Story", "category": "urban"}
    img = generate_one(default_loc, title_font, caption_font)
    img.save(BACKGROUNDS_DIR / "default.png")

    print(f"Generated {len(LOCATIONS) + 1} placeholder images in {BACKGROUNDS_DIR}")


if __name__ == "__main__":
    generate()
