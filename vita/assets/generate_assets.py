#!/usr/bin/env python3
"""Generate deterministic LiveArea artwork for the Vita VPK."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LIVEAREA = ROOT / "sce_sys" / "livearea" / "contents"

NAVY = (18, 24, 38, 255)
NAVY_LIGHT = (29, 39, 58, 255)
GREEN = (38, 190, 125, 255)
GREEN_LIGHT = (80, 225, 155, 255)
WHITE = (245, 248, 252, 255)
MUTED = (165, 178, 197, 255)


def draw_wifi(draw: ImageDraw.ImageDraw, center: tuple[int, int], scale: float) -> None:
    x, y = center
    widths = (54, 38, 22)
    for index, width in enumerate(widths):
        inset = index * 7 * scale
        box = (
            x - width * scale,
            y - width * scale + inset,
            x + width * scale,
            y + width * scale + inset,
        )
        draw.arc(box, 205, 335, fill=GREEN_LIGHT, width=max(2, int(5 * scale)))
    radius = max(2, int(5 * scale))
    draw.ellipse((x - radius, y + 31 * scale - radius, x + radius, y + 31 * scale + radius), fill=GREEN_LIGHT)


def draw_controller(
    draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], line_width: int
) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=(y1 - y0) // 3, outline=WHITE, width=line_width)
    height = y1 - y0
    cx_left = x0 + (x1 - x0) * 0.30
    cy = y0 + height * 0.50
    arm = height * 0.17
    draw.line((cx_left - arm, cy, cx_left + arm, cy), fill=WHITE, width=line_width)
    draw.line((cx_left, cy - arm, cx_left, cy + arm), fill=WHITE, width=line_width)
    cx_right = x0 + (x1 - x0) * 0.71
    radius = height * 0.055
    for dx, dy in ((0, -0.15), (0.15, 0), (0, 0.15), (-0.15, 0)):
        px, py = cx_right + height * dx, cy + height * dy
        draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=GREEN_LIGHT)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Vita's package promoter rejects RGB/RGBA LiveArea PNGs with 0x8010113D.
    # Quantize to an actual 8-bit indexed palette, including alpha entries.
    indexed = image.convert("RGBA").quantize(
        colors=256,
        method=Image.Quantize.FASTOCTREE,
        dither=Image.Dither.NONE,
    )
    indexed.save(path, "PNG", optimize=True, bits=8)


def make_icon() -> None:
    image = Image.new("RGBA", (128, 128), NAVY)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 4, 123, 123), radius=24, fill=NAVY_LIGHT, outline=GREEN, width=5)
    draw_controller(draw, (20, 35, 108, 90), 5)
    draw_wifi(draw, (64, 52), 0.36)
    save(image, ROOT / "sce_sys" / "icon0.png")


def make_background() -> None:
    image = Image.new("RGBA", (840, 500), NAVY)
    draw = ImageDraw.Draw(image)
    for index in range(7):
        x = 480 + index * 72
        draw.ellipse((x, -120 + index * 18, x + 330, 210 + index * 18), outline=(38, 190, 125, 25), width=4)
    draw.rounded_rectangle((54, 61, 786, 439), radius=42, fill=NAVY_LIGHT, outline=(38, 190, 125, 120), width=4)
    draw_controller(draw, (104, 160, 408, 350), 12)
    draw_wifi(draw, (256, 212), 1.15)
    draw.text((470, 184), "VITA", font=font(57), fill=WHITE)
    draw.text((470, 252), "GAMEPAD", font=font(42), fill=GREEN_LIGHT)
    draw.text((472, 322), "Wi-Fi controller", font=font(22), fill=MUTED)
    save(image, LIVEAREA / "bg.png")


def make_startup() -> None:
    image = Image.new("RGBA", (280, 158), NAVY_LIGHT)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((3, 3, 276, 154), radius=18, outline=GREEN, width=4)
    draw_controller(draw, (26, 47, 128, 111), 5)
    draw_wifi(draw, (77, 64), 0.39)
    draw.text((151, 50), "VITA", font=font(28), fill=WHITE)
    draw.text((151, 82), "GAMEPAD", font=font(19), fill=GREEN_LIGHT)
    save(image, LIVEAREA / "startup.png")


if __name__ == "__main__":
    make_icon()
    make_background()
    make_startup()
