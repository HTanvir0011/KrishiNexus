"""Shared look for the v2 videos, in the site's style: daylight canvas, emerald, amber, Anek Latin (the app's bundled
font files, copied to video/assets/fonts), a faint dot grid. Frames are 1920x1080; the web cut is scaled to 1280x720.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 30
ROOT = Path("C:/ai-congress/KrishiNexus")
FONTS = ROOT / "video/assets/fonts"

CANVAS = (246, 248, 245)      # #F6F8F5
EMERALD = (4, 120, 87)        # #047857
EMERALD_D = (6, 78, 59)       # #064E3B
EMERALD_T = (209, 250, 229)   # #D1FAE5
AMBER = (245, 158, 11)        # #F59E0B
AMBER_D = (180, 83, 9)        # #B45309, amber text on light
AMBER_T = (254, 243, 199)     # #FEF3C7
INK = (17, 24, 39)            # #111827
SLATE = (71, 85, 105)         # #475569
LINE = (226, 232, 240)        # #E2E8F0
WHITE = (255, 255, 255)
ROSE = (225, 29, 72)          # #E11D48
TEAL = (94, 154, 163)         # the logo's third block


@lru_cache(maxsize=64)
def font(size: int, weight: int = 600) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"AnekLatin-{weight}.ttf"), size)


@lru_cache(maxsize=8)
def bangla(size: int, serif: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / ("TiroBangla-400.ttf" if serif else "AnekBangla-600.ttf")), size,
                              layout_engine=ImageFont.Layout.RAQM if ImageFont.core.HAVE_RAQM else ImageFont.Layout.BASIC)


def ease(x: float) -> float:  # ease-out cubic
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def ease_exp(x: float) -> float:
    """Exponential ease-out, the motion curve for everything that enters or moves."""
    x = min(1.0, max(0.0, x))
    return 1.0 if x >= 1 else (1 - 2 ** (-10 * x)) / (1 - 2 ** -10)


def pe(t: float, a: float, b: float) -> float:
    """Exponential ease-out progress of t between a and b."""
    return ease_exp((t - a) / (b - a)) if b > a else float(t >= a)


def ease_io(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 3 * x * x - 2 * x * x * x


def phase(t: float, a: float, b: float) -> float:
    return ease((t - a) / (b - a)) if b > a else float(t >= a)


@lru_cache(maxsize=2)
def canvas_bg(w: int = W, h: int = H) -> Image.Image:
    """Daylight canvas with a faint dot grid and a soft emerald glow top-left, amber glow bottom-right."""
    bg = Image.new("RGB", (w, h), CANVAS)
    glow = Image.new("RGB", (w, h), CANVAS)
    g = ImageDraw.Draw(glow)
    g.ellipse((-500, -600, 900, 500), fill=(214, 236, 224))
    g.ellipse((w - 700, h - 450, w + 600, h + 650), fill=(250, 236, 205))
    glow = glow.filter(ImageFilter.GaussianBlur(200))
    bg = Image.blend(bg, glow, 0.55)
    d = ImageDraw.Draw(bg)
    for y in range(18, h, 32):
        for x in range(18, w, 32):
            d.point((x, y), fill=(218, 225, 220))
    return bg


def text_size(text: str, fnt) -> tuple[int, int]:
    l, t, r, b = fnt.getbbox(text)
    return r - l, b - t


@lru_cache(maxsize=512)
def sprite(text: str, size: int, weight: int, color: tuple, bangla_font: bool = False, tracking: int = 0) -> Image.Image:
    """Text rendered once as an RGBA sprite (cropped to the ink, with a little padding)."""
    fnt = bangla(size) if bangla_font else font(size, weight)
    if tracking:
        widths = [fnt.getlength(c) + tracking for c in text]
        wtot = int(sum(widths)) + 20
    else:
        wtot = int(fnt.getlength(text)) + 20
    asc, desc = fnt.getmetrics()
    img = Image.new("RGBA", (wtot, asc + desc + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if tracking:
        x = 10
        for c, wc in zip(text, widths):
            d.text((x, 10), c, font=fnt, fill=(*color, 255))
            x += wc
    else:
        d.text((10, 10), text, font=fnt, fill=(*color, 255))
    return img


def paste_sprite(img: Image.Image, spr: Image.Image, xy: tuple[float, float], alpha: float = 1.0,
                 anchor: str = "la") -> None:
    """Paste with opacity; anchor 'la' = left/top of the text box, 'ma' = centred horizontally, 'ra' = right."""
    if alpha <= 0.01:
        return
    x, y = xy
    if anchor[0] == "m":
        x -= spr.width / 2
    elif anchor[0] == "r":
        x -= spr.width
    s = spr
    if alpha < 0.999:
        s = spr.copy()
        s.putalpha(spr.getchannel("A").point(lambda v: int(v * alpha)))
    img.paste(s, (int(round(x - 10)), int(round(y - 10))), s)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return m


def shadow(size: tuple[int, int], radius: int, blur: int = 28, opacity: int = 70, spread: int = 0) -> Image.Image:
    """An RGBA soft shadow image, (size + 2*margin) big; paste at (x - margin, y - margin + offset)."""
    m = blur * 2 + spread
    s = Image.new("L", (size[0] + 2 * m, size[1] + 2 * m), 0)
    ImageDraw.Draw(s).rounded_rectangle((m - spread, m - spread, m + size[0] + spread, m + size[1] + spread), radius,
                                        fill=opacity)
    s = s.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", s.size, (16, 40, 32, 0))
    out.putalpha(s)
    return out


def logo(size: int) -> Image.Image:
    """The KrishiNexus mark: a tall emerald block with an amber and a teal square beside it."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = size / 32
    d.rounded_rectangle((2 * u, 2 * u, 15 * u, 30 * u), int(3 * u), fill=(*EMERALD, 255))
    d.rounded_rectangle((18 * u, 2 * u, 30 * u, 14 * u), int(3 * u), fill=(*AMBER, 255))
    d.rounded_rectangle((18 * u, 17 * u, 30 * u, 30 * u), int(3 * u), fill=(*TEAL, 255))
    return img


def count_text(big: str, k: float) -> str:
    """Kinetic numbers: '116%', '77.32%', 'Tk 19,980' count up from zero as k goes 0..1 (exponential ease-out)."""
    m = re.match(r"^(Tk |)(\d[\d,]*)(\.\d+)?(.*)$", big)
    if not m or k >= 1:
        return big
    val = float((m.group(2) + (m.group(3) or "")).replace(",", ""))
    v = val * ease_exp(k)
    dec = len(m.group(3)) - 1 if m.group(3) else 0
    s = f"{v:,.{dec}f}" if "," in m.group(2) else f"{v:.{dec}f}"
    return m.group(1) + s + m.group(4)
