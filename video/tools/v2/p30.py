"""The 30-second problem video: the S01 narration (pauses shortened, natural speed) over footage from the live site,
with kinetic typography of its numbers (below cost, five tiers of middlemen, up to 116 %, 77 % of cold storage, one
flash flood), then a closing line naming KrishiNexus OS and tanvir.health. Exactly 30 s (900 frames at 30 fps).

Usage: python p30.py [preview t ...]   (video/.venv-tts python; run `mix.py p30` first)
Output: frontend/public/video/problem-30s.mp4, .jpg, .en.vtt
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402
from look import (AMBER, AMBER_D, EMERALD, EMERALD_D, FPS, H, INK, ROOT, ROSE, SLATE, W,  # noqa: E402
                  canvas_bg, ease_exp, ease_io, font, logo, paste_sprite, pe, rounded_mask, shadow, sprite)

WORK = ROOT / "video/work"
TOTAL, VOICE_AT = 30.0, 1.10
# footage panel on the right; type on the left (big numbers reach over the panel's edge)
FX, FY, FW, FH, FR_ = 800, 96, 1030, 888, 26


@lru_cache(maxsize=1)
def words() -> list:
    t = json.loads((WORK / "voice30/timing.json").read_text(encoding="utf-8"))
    return t["segments"]["S01"]["words"]


def w(text: str, after: float = 0.0, end: bool = False) -> float:
    """Absolute time of a word in the 30 s cut."""
    for word, s, e in words():
        if VOICE_AT + s >= after - 1e-6 and word.strip().lower().startswith(text.lower()):
            return VOICE_AT + (e if end else s)
    raise KeyError(text)


def voice_items(chain):
    """For mix.py: the voice at VOICE_AT and the music cue (problem in B minor, resolving to D on the closing)."""
    a = chain(np.load(WORK / "voice30/S01.npy"))
    close = closing_at()
    # the problem in B minor, a IV-V cadence resolving to D as the closing card turns over; chimes as each number lands
    hits = [(w("below") + 0.1, "thump"), (w("five") + 0.1, "chime"), (w("116") + 0.1, "chime"),
            (w("77") + 0.1, "chime"), (w("flash") + 0.15, "chime"), (close + 1.45, "big")]
    cues = {"end": TOTAL, "resolve": close, "fade_in": 0.5, "fade_out": 2.4, "hits": hits, "swells": [(close, 1.4)],
            "sections": [{"start": 0.0, "end": close, "prog": ["Bm", "G", "D", "A"]},
                         {"start": close, "end": TOTAL, "lift": True}]}
    return [(VOICE_AT, a)], TOTAL, cues, None


def closing_at() -> float:
    return VOICE_AT + json.loads((WORK / "voice30/timing.json").read_text(encoding="utf-8"))["segments"]["S01"]["dur"] + 0.25


def beats() -> list:
    """(start, end, shot, rec-time start, camera (cx, cy, zoom)) for the footage, by the narration."""
    b = [w("Between") - 0.25, w("mark") - 0.15, w("Traders") - 0.25, w("and", after=w("space")) - 0.1]
    return [
        (0.0, b[0], "S03b", 4.0, (1460, 620, 1.55)),        # the blocked below-cost sale (landing decision card)
        (b[0], b[1], "S01a", 6.4, (640, 560, 1.15)),         # the five-tier syndicate, farm gate to Dhaka retail
        (b[1], b[2], "S01b", 0.6, (1440, 600, 1.6)),         # whitepaper: 116 % markup
        (b[2], b[3], "S01b", 4.9, (780, 600, 1.6)),          # 77.32 % of cold storage
        (b[3], closing_at() + 0.6, "S01b", 8.0, (1440, 600, 1.6)),  # 65 % of Sunamganj's boro lost in 2017
    ]


@lru_cache(maxsize=1)
def panel_mask():
    return rounded_mask((FW, FH), FR_)


def footage(T: float) -> Image.Image | None:
    for i, (a, b, shot, r0, cam) in enumerate(beats()):
        if a <= T < b:
            break
    else:
        return None
    t = T - a
    cx, cy, z = cam
    z = z * (1 + 0.035 * t / max(b - a, 0.1))  # a slow push-in
    img = build.load_img(build.frame_at(shot, r0 + 0.35 * t))
    aspect = FW / FH
    h = 1080 / z
    wdt = h * aspect
    x0 = min(max(cx - wdt / 2, 0), 1920 - wdt)
    y0 = min(max(cy - h / 2, 0), 1080 - h)
    pic = img.resize((FW, FH), Image.LANCZOS, box=(x0, y0, x0 + wdt, y0 + h))
    if i > 0 and t < 0.3:  # dissolve from the previous beat
        pa, pb, pshot, pr0, pcam = beats()[i - 1]
        prev = footage(pb - 1e-3)
        if prev is not None:
            pic = Image.blend(prev, pic, ease_io(t / 0.3))
    return pic


def big_number(img, text: str, x: float, y: float, size: int, color, a: float, k: float):
    """A large number that counts up (k: 0..1) with a soft canvas halo so it reads over the footage edge."""
    shown = build.count_text(text, k)
    spr = sprite(shown, size, 700, color)
    halo = sprite(shown, size, 700, (246, 248, 245))
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
        paste_sprite(img, halo, (x + dx, y + dy), a)
    paste_sprite(img, spr, (x, y), a)


def frame(T: float) -> Image.Image:
    img = canvas_bg().copy()
    close = closing_at()
    # the footage panel (slides out for the closing)
    out = pe(T, close, close + 0.6)
    pic = footage(T)
    if pic is not None and out < 1:
        a_in = pe(T, 0.0, 0.6)
        x = FX + 80 * (1 - a_in) + 500 * out
        sh = shadow((FW, FH), FR_, blur=28, opacity=int(60 * a_in * (1 - out)))
        m = (sh.width - FW) // 2
        img.paste(sh, (int(x - m), FY - m + 14), sh)
        mask = panel_mask().point(lambda v: int(v * a_in * (1 - out)))
        img.paste(pic, (int(x), FY), mask)
    d = ImageDraw.Draw(img)
    X = 110
    if T < close + 0.4:
        fade = 1 - pe(T, close - 0.1, close + 0.3)
        b = beats()
        if T < b[1][0]:  # sells below cost
            k = T - 0.2
            a = pe(k, 0.6, 1.0) * (1 - pe(T, b[1][0] - 0.3, b[1][0]))
            paste_sprite(img, sprite("A potato farmer often", 58, 600, INK), (X, 300 + 20 * (1 - a)), a)
            paste_sprite(img, sprite("sells", 58, 600, INK), (X, 370 + 20 * (1 - a)), a)
            a2 = pe(T, w("below") - 0.15, w("below") + 0.25) * (1 - pe(T, b[1][0] - 0.3, b[1][0]))
            s = 1.15 - 0.15 * ease_exp((T - w("below") + 0.15) / 0.35)
            spr = sprite("BELOW COST", int(132 * s), 700, ROSE)
            paste_sprite(img, spr, (X - 4, 400), a2)
            paste_sprite(img, sprite("Tk 12/kg offered · Tk 15/kg to grow", 36, 500, SLATE), (X, 610), a2)
        elif T < b[2][0]:  # five tiers of middlemen
            a = pe(T, b[1][0], b[1][0] + 0.4) * (1 - pe(T, b[2][0] - 0.3, b[2][0]))
            paste_sprite(img, sprite("Between the field and the buyer", 46, 500, SLATE), (X, 300), a)
            a2 = pe(T, w("five") - 0.1, w("five") + 0.3) * (1 - pe(T, b[2][0] - 0.3, b[2][0]))
            big_number(img, "5", X - 6, 300, 220, AMBER_D, a2, (T - w("five") + 0.1) / 0.4)
            paste_sprite(img, sprite("tiers of", 58, 600, INK), (X + 150, 440), a2)
            paste_sprite(img, sprite("middlemen", 58, 600, INK), (X + 150, 506), a2)
            names = ["Faria", "Bepari", "Aratdar", "Paiker", "Retailer"]
            cx = X
            for i, nm in enumerate(names):
                ai = pe(T, w("field") + 0.32 * i, w("field") + 0.32 * i + 0.3) * (1 - pe(T, b[2][0] - 0.3, b[2][0]))
                if ai <= 0:
                    break
                f = font(30, 600)
                tw = f.getlength(nm) + 34
                y = 640 if i < 3 else 704
                if i == 3:
                    cx = X
                chip = Image.new("RGBA", (int(tw), 48), (0, 0, 0, 0))
                cd = ImageDraw.Draw(chip)
                cd.rounded_rectangle((0, 0, tw - 1, 47), 24, fill=(254, 243, 199, 255), outline=(*AMBER, 255), width=2)
                cd.text((17, 5), nm, font=f, fill=(*INK, 255))
                chip.putalpha(chip.getchannel("A").point(lambda v: int(v * ai)))
                img.paste(chip, (int(cx), int(y + 10 * (1 - ai))), chip)
                cx += tw + 44
                if i not in (2, 4):  # a drawn chevron (the font has no arrow glyph)
                    ax, ay = cx - 30, y + 24
                    col = tuple(int(c * ai + 246 * (1 - ai)) for c in AMBER_D)
                    d.line((ax, ay - 8, ax + 9, ay, ax, ay + 8), fill=col, width=4, joint="curve")
        elif T < b[3][0]:  # up to 116 %
            a = pe(T, b[2][0], b[2][0] + 0.4) * (1 - pe(T, b[3][0] - 0.3, b[3][0]))
            paste_sprite(img, sprite("can mark the price up", 50, 600, INK), (X, 300), a)
            paste_sprite(img, sprite("by as much as", 50, 500, SLATE), (X, 364), a)
            a2 = pe(T, w("116") - 0.2, w("116") + 0.2) * (1 - pe(T, b[3][0] - 0.3, b[3][0]))
            big_number(img, "116%", X - 8, 330, 250, AMBER_D, a2, (T - w("116") + 0.2) / 0.7)
            paste_sprite(img, sprite("markup, field to Dhaka retail (CPD study)", 32, 500, SLATE), (X, 668), a2)
        elif T < b[4][0]:  # 77 % of cold storage
            a = pe(T, b[3][0], b[3][0] + 0.4) * (1 - pe(T, b[4][0] - 0.3, b[4][0]))
            paste_sprite(img, sprite("Traders hold", 56, 600, INK), (X, 300), a)
            a2 = pe(T, w("77") - 0.2, w("77") + 0.2) * (1 - pe(T, b[4][0] - 0.3, b[4][0]))
            big_number(img, "77%", X - 8, 300, 250, EMERALD, a2, (T - w("77") + 0.2) / 0.7)
            paste_sprite(img, sprite("of the cold-storage space", 48, 600, INK), (X, 628), a2)
            fill = 560 * 0.7732 * pe(T, w("77"), w("77") + 0.9)
            d.rounded_rectangle((X, 728, X + 560, 750), 11, fill=(226, 232, 228))
            if fill > 2:
                d.rounded_rectangle((X, 728, X + fill, 750), 11, fill=EMERALD)
            paste_sprite(img, sprite("77.32% held by traders and plant owners", 28, 500, SLATE), (X, 766), a2)
        else:  # one flash flood
            a = pe(T, b[4][0], b[4][0] + 0.4) * fade
            paste_sprite(img, sprite("and a single", 54, 600, INK), (X, 300), a)
            a2 = pe(T, w("flash") - 0.2, w("flash") + 0.2) * fade
            paste_sprite(img, sprite("flash flood", 110, 700, (3, 105, 161)), (X - 4, 364 + 16 * (1 - a2)), a2)
            a3 = pe(T, w("wipe") - 0.1, w("wipe") + 0.3) * fade
            paste_sprite(img, sprite("can wipe out a season", 54, 600, INK), (X, 520), a3)
            paste_sprite(img, sprite("2017: 65% of Sunamganj's boro lost", 32, 500, SLATE), (X, 596), a3)
            # water rising along the bottom
            lvl = 150 * ease_io((T - w("flash")) / 1.6) * fade
            if lvl > 1:
                water = Image.new("RGBA", (W, int(lvl) + 30), (0, 0, 0, 0))
                wd = ImageDraw.Draw(water)
                xs = np.arange(0, W + 20, 20)
                ys = 18 + 8 * np.sin(xs / 90 + T * 3.0)
                wd.polygon([(0, water.height)] + list(zip(xs.tolist(), ys.tolist())) + [(W, water.height)],
                           fill=(3, 105, 161, int(70 * fade)))
                img.paste(water, (0, H - water.height), water)
    # closing: the name and the address
    if T >= close:
        t = T - close
        lg = logo(110)
        a = pe(t, 0.2, 0.7)
        lg2 = lg.copy()
        lg2.putalpha(lg.getchannel("A").point(lambda v: int(v * a)))
        img.paste(lg2, (W // 2 - 55, 150), lg2)
        paste_sprite(img, sprite("KrishiNexus OS", 120, 700, INK), (W / 2, 238 + 24 * (1 - a)), a, "ma")
        a2 = pe(t, 0.7, 1.2)
        paste_sprite(img, sprite("Fair prices, open cold storage and flood alerts", 46, 500, SLATE), (W / 2, 432), a2, "ma")
        paste_sprite(img, sprite("for Bangladeshi farmers: one AI operating system", 46, 500, SLATE), (W / 2, 492), a2,
                     "ma")
        a3 = pe(t, 1.3, 1.8)
        paste_sprite(img, sprite("tanvir.health", 132, 700, EMERALD), (W / 2, 556 + 16 * (1 - a3)), a3, "ma")
        bar = 380 * pe(t, 1.6, 2.2)
        if bar > 1:
            d.rounded_rectangle(((W - bar) / 2, 772, (W + bar) / 2, 782), 5, fill=AMBER)
        paste_sprite(img, sprite("Built by Team Heat Wave", 36, 600, EMERALD_D), (W / 2, 810), pe(t, 2.0, 2.5), "ma")
    return img  # the closing holds to the last frame (players often rest on it)


class Film30:
    total = TOTAL
    n = int(round(TOTAL * FPS))

    def frame(self, T: float) -> Image.Image:
        return frame(T)


def captions():
    from captions import CUES, align, vtt
    stem = build.read_stem("p30")
    a = stem[int(VOICE_AT * 48000):]
    cues = [(VOICE_AT + s, VOICE_AT + e, text) for s, e, text in align(words(), a, 48000, CUES["S01"])]
    (build.OUT_WEB / "problem-30s.en.vtt").write_text(vtt(cues), encoding="utf-8")
    print(len(cues), "cues")


def poster():
    img = frame(w("116") + 1.2).resize((1280, 720), Image.LANCZOS)
    path = build.OUT_WEB / "problem-30s.jpg"
    for q in (86, 80, 74, 68):
        img.save(path, quality=q, optimize=True, progressive=True)
        if path.stat().st_size < 150_000:
            break
    print("poster", path.stat().st_size, "bytes")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        ts = [float(x) for x in sys.argv[2:]]
        sheet = Image.new("RGB", (640 * 3, 360 * ((len(ts) + 2) // 3)), "white")
        for i, T in enumerate(ts):
            sheet.paste(frame(T).resize((640, 360), Image.LANCZOS), (640 * (i % 3), 360 * (i // 3)))
        sheet.save(WORK / "preview30.jpg", quality=88)
        print(WORK / "preview30.jpg")
    else:
        build.OUT_WEB.mkdir(parents=True, exist_ok=True)
        captions()
        poster()
        build.encode(Film30(), "p30", [(build.OUT_WEB / "problem-30s.mp4", (1280, 720), 24, 128000)],
                     WORK / "mix/p30_mix.wav")
