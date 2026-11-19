"""Animated team intro for the demo: the title, then each Team Heat Wave member in spoken order (lead first, advisor
last), each in their own slot that starts on their spoken name: a large portrait revealed by a rising mask with an
amber block sliding in behind it, the name and role rising in, an amber underline drawing, and a slide-out into the
next member; then all six together in a grid that pops in one by one. Exponential ease-out throughout.

`frame(t, cues, grid_at, end)`: cues = [title_start, member_1_start, ..., member_6_start] (seconds, film time);
grid_at = when the grid takes over; end = when the next section starts. Portraits: frontend/public/team/<slug>.webp
(640x800); names and roles: frontend/src/data/team.json.
"""
from __future__ import annotations

import json
from functools import lru_cache

from PIL import Image, ImageDraw

from look import (AMBER, EMERALD, EMERALD_D, H, INK, ROOT, SLATE, W, canvas_bg, font, logo, paste_sprite, pe,
                  rounded_mask, shadow, sprite)

TEAM = json.loads((ROOT / "frontend/src/data/team.json").read_text(encoding="utf-8"))["members"]
PH, PR = 780, 30                 # portrait card height (72 % of the frame), corner radius
PW = PH * 640 // 800             # 624
PX, PY = 1140, (H - PH) // 2
TX = 150                         # text column


@lru_cache(maxsize=8)
def portrait(slug: str) -> Image.Image:
    return Image.open(ROOT / f"frontend/public/team/{slug}.webp").convert("RGB")


@lru_cache(maxsize=1)
def card_shadow():
    return shadow((PW, PH), PR, blur=34, opacity=70)


@lru_cache(maxsize=1)
def card_mask():
    return rounded_mask((PW, PH), PR)


def base(t: float) -> Image.Image:
    img = canvas_bg().copy()
    mark = sprite("HEAT WAVE", 400, 700, (238, 242, 239))  # a watermark drifting slowly through the intro
    paste_sprite(img, mark, (-160 - 38 * t, 620))
    return img


def title(img: Image.Image, t: float, t_out: float) -> None:
    out = 1 - pe(t, t_out - 0.4, t_out)
    if out <= 0:
        return
    a = pe(t, 0.0, 0.6)
    lg = logo(132)
    s = 0.7 + 0.3 * a
    lgs = lg.resize((int(132 * s), int(132 * s)), Image.LANCZOS)
    lgs.putalpha(lgs.getchannel("A").point(lambda v: int(v * a * out)))
    img.paste(lgs, (int(W / 2 - lgs.width / 2), int(262 - lgs.height / 2)), lgs)
    k = pe(t, 0.1, 0.8)
    paste_sprite(img, sprite("KrishiNexus OS", 150, 700, INK), (W / 2, 350 + 50 * (1 - k)), k * out, "ma")
    bar = 420 * pe(t, 0.45, 1.1) * out
    if bar > 8:
        ImageDraw.Draw(img).rounded_rectangle(((W - bar) / 2, 586, (W + bar) / 2, 595), 5, fill=AMBER)
    paste_sprite(img, sprite("One AI operating system for Bangladesh's farm-to-market chain", 46, 400, SLATE),
                 (W / 2, 628 + 24 * (1 - pe(t, 0.7, 1.3))), pe(t, 0.7, 1.3) * out, "ma")
    paste_sprite(img, sprite("Built by Team Heat Wave", 48, 600, EMERALD), (W / 2, 706 + 24 * (1 - pe(t, 1.1, 1.7))),
                 pe(t, 1.1, 1.7) * out, "ma")


def rising_text(img, spr, x, y, k, rise=46):
    """Text that rises into place through a mask (clipped at its own baseline box)."""
    if k <= 0.001:
        return
    h = spr.height
    dy = int(rise * (1 - k))
    crop = spr.crop((0, 0, spr.width, max(1, h - dy)))
    a = crop.getchannel("A").point(lambda v: int(v * min(1.0, 0.25 + k)))
    crop.putalpha(a)
    img.paste(crop, (int(x - 10), int(y - 10 + dy)), crop)


def member(img: Image.Image, i: int, t: float, dur: float) -> None:
    m = TEAM[i]
    exit_k = pe(t, dur - 0.28, dur)  # slide out to the left into the next member
    ex = -260 * exit_k
    fade = 1 - exit_k
    # amber block slides in from the right behind the card
    kb = pe(t, 0.0, 0.5)
    bx = PX + 34 + 160 * (1 - kb) + ex
    d = ImageDraw.Draw(img)
    if kb > 0.01 and fade > 0.02:
        col = tuple(int(c * fade + 246 * (1 - fade)) for c in AMBER)
        d.rounded_rectangle((bx, PY + 34, bx + PW, PY + 34 + PH), PR, fill=col)
    # the portrait: a rounded mask rising from the bottom, the photo settling from a slight zoom
    reveal = pe(t, 0.05, 0.62)
    shown = int(PH * reveal)
    if shown > 2 and fade > 0.02:
        z = 1.08 - 0.08 * pe(t, 0.08, 1.4)
        src = portrait(m["slug"])
        zw, zh = int(PW * z), int(PH * z)
        pic = src.resize((zw, zh), Image.LANCZOS).crop(((zw - PW) // 2, (zh - PH) // 3,
                                                         (zw - PW) // 2 + PW, (zh - PH) // 3 + PH))
        x0 = int(PX + ex)
        sh = card_shadow()
        mg = (sh.width - PW) // 2
        if reveal > 0.98:
            s2 = sh.copy()
            s2.putalpha(sh.getchannel("A").point(lambda v: int(v * fade)))
            img.paste(s2, (x0 - mg, PY - mg + 14), s2)
        mask = card_mask().crop((0, PH - shown, PW, PH)).point(lambda v: int(v * fade))
        img.paste(pic.crop((0, PH - shown, PW, PH)), (x0, PY + PH - shown), mask)
    # name rising, underline drawing, role rising
    name = m["name"]["en"]
    size, lines = 112, [name]
    if font(size, 700).getlength(name) > 900:  # a long name goes on two lines at full size, not one small line
        lines = name.rsplit(" ", 1)
    while max(font(size, 700).getlength(l) for l in lines) > 900 and size > 64:
        size -= 4
    lh = int(size * 1.08)
    dy = (len(lines) - 1) * lh / 2  # the block stays centred on the portrait
    for j, line in enumerate(lines):
        rising_text(img, sprite(line, size, 700, INK), TX + ex, 360 - dy + j * lh + (112 - size) * 0.8,
                    pe(t, 0.18 + 0.08 * j, 0.72 + 0.08 * j) * fade)
    bar = 210 * pe(t, 0.42, 0.92) * fade
    if bar > 1:
        d.rounded_rectangle((TX + ex, 528 + dy, TX + ex + bar, 538 + dy), 5, fill=AMBER)
    rising_text(img, sprite(m["role"]["en"], 52, 500, EMERALD_D), TX + ex, 570 + dy, pe(t, 0.5, 1.05) * fade)
    if i == len(TEAM) - 1:
        rising_text(img, sprite("Joins the team online", 40, 400, SLATE), TX + ex, 646 + dy, pe(t, 0.9, 1.4) * fade)


@lru_cache(maxsize=8)
def grid_avatar(slug: str, w: int = 236) -> Image.Image:
    h = w * 5 // 4
    im = portrait(slug).resize((w, h), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(im, (0, 0), rounded_mask((w, h), 20))
    return out


def grid(img: Image.Image, t: float) -> None:
    """All six together: a heading, then each portrait pops in, one by one, with its name."""
    k = pe(t, 0.0, 0.5)
    paste_sprite(img, sprite("Team Heat Wave", 84, 700, INK), (W / 2, 120 + 30 * (1 - k)), k, "ma")
    bar = 260 * pe(t, 0.2, 0.7)
    if bar > 1:
        ImageDraw.Draw(img).rounded_rectangle(((W - bar) / 2, 248, (W + bar) / 2, 256), 4, fill=AMBER)
    w, gap = 236, 52
    x0 = (W - (6 * w + 5 * gap)) / 2
    y0 = 330
    for i, m in enumerate(TEAM):
        p = pe(t, 0.2 + 0.1 * i, 0.65 + 0.1 * i)
        if p <= 0.001:
            continue
        av = grid_avatar(m["slug"], w)
        s = 0.6 + 0.4 * p
        a2 = av.resize((max(1, int(av.width * s)), max(1, int(av.height * s))), Image.LANCZOS)
        a2.putalpha(a2.getchannel("A").point(lambda v: int(v * min(1, p * 1.4))))
        cx = x0 + i * (w + gap) + w / 2
        cy = y0 + av.height / 2
        img.paste(a2, (int(cx - a2.width / 2), int(cy - a2.height / 2)), a2)
        nm = m["name"]["en"].replace("Mohammed ", "Mohammed\n")
        lines = nm.split("\n")
        for j, line in enumerate(lines):
            paste_sprite(img, sprite(line, 26, 600, INK), (cx, y0 + av.height + 22 + 32 * j), p, "ma")
        role = m["role"]["en"].split(" · ")[0]
        paste_sprite(img, sprite(role, 22, 500, EMERALD_D), (cx, y0 + av.height + 24 + 32 * len(lines)), p, "ma")


def frame(t: float, cues: list[float], grid_at: float, end: float) -> Image.Image:
    img = base(t)
    if t < cues[1]:
        title(img, t - cues[0], cues[1] - cues[0])
    elif t < grid_at:
        k = max(i for i in range(1, len(cues)) if cues[i] <= t)
        t1 = cues[k + 1] if k + 1 < len(cues) else grid_at
        member(img, k - 1, t - cues[k], t1 - cues[k])
    else:
        grid(img, t - grid_at)
    return img


if __name__ == "__main__":  # a frame every second through a sample timing
    cues = [0.0, 3.43, 5.36, 8.69, 11.53, 14.46, 18.39]
    picks = [x + 0.5 for x in range(0, 23)]
    sheet = Image.new("RGB", (384 * 6, 216 * 4), "white")
    for n, tt in enumerate(picks):
        sheet.paste(frame(tt, cues, 20.6, 22.7).resize((384, 216), Image.LANCZOS), (384 * (n % 6), 216 * (n // 6)))
    out = ROOT / "video/work/intro2_sheet.jpg"
    sheet.save(out, quality=86)
    print(out)
