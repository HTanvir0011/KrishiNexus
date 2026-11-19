"""Motion graphics drawn over the demo's footage, one clear idea per beat, in the site's colours, with an exponential
ease-out: cards that slide in and out, diagrams that build (the middlemen chain, the agents lighting in sequence, a
truck on a route, the escrow flow, a credit gauge, break-even bars and the pilot timeline), highlight boxes that draw
on around what the narrator names, a grade stamp, a redaction sweep, section wipes and title reveals.

Every effect is `fx(img, t, life, **kw)`: t = seconds since the effect began, life = how long it stays.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFont

from look import (AMBER, AMBER_D, EMERALD, EMERALD_D, H, INK, LINE, ROSE, SLATE, W, WHITE, count_text, font, pe,
                  shadow, sprite)

SKY = (3, 105, 161)
WIN = (160, 156, 1760, 1056)  # the browser window's content area in the frame (x0, y0, x1, y1)


def life_alpha(t: float, life: float, din: float = 0.45, dout: float = 0.3) -> tuple[float, float]:
    """(opacity, entrance progress) for something that eases in and fades out at the end of its life."""
    k = pe(t, 0, din)
    out = 1 - pe(t, life - dout, life)
    return min(k, out), k


def layer(size):
    return Image.new("RGBA", size, (0, 0, 0, 0))


def put(img: Image.Image, lay: Image.Image, xy, alpha: float = 1.0):
    if alpha <= 0.01:
        return
    if alpha < 0.999:
        lay = lay.copy()
        lay.putalpha(lay.getchannel("A").point(lambda v: int(v * alpha)))
    img.paste(lay, (int(xy[0]), int(xy[1])), lay)


def card(w: int, h: int, fill=WHITE) -> Image.Image:
    sh = shadow((w, h), 22, blur=18, opacity=60)
    m = (sh.width - w) // 2
    lay = layer((w + 2 * m, h + 2 * m))
    lay.paste(sh, (0, 8), sh)
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle((m, m, m + w - 1, m + h - 1), 22, fill=(*fill, 245), outline=(*LINE, 255), width=2)
    lay.info["m"] = m
    return lay


def text(d: ImageDraw.ImageDraw, xy, s, size, weight, col, anchor="la"):
    d.text(xy, s, font=font(size, weight), fill=(*col, 255), anchor=anchor)


def top_card(img, t, life, w, h, draw_fn, y=None):
    """A white card that slides down into the top of the window and fades out; draw_fn(d, lay, m, w, h) fills it."""
    a, k = life_alpha(t, life)
    if a <= 0.01:
        return
    lay = card(w, h)
    m = lay.info["m"]
    draw_fn(ImageDraw.Draw(lay), lay, m, w, h)
    x = (WIN[0] + WIN[2]) / 2 - w / 2 - m
    y0 = (WIN[1] + 26 if y is None else y) - m
    put(img, lay, (x, y0 - 40 * (1 - k)), a)


# -- diagrams -------------------------------------------------------------------------------------------------------

def chain(img, t, life, nodes, note=""):
    """Farmer -> middlemen -> buyer: nodes appear one by one along a line, each markup popping above its link."""
    w, h = 1440, 268
    n = len(nodes)

    def draw(d, lay, m, w, h):
        x0, x1, y = m + 90, m + w - 90, m + 168
        step = (x1 - x0) / (n - 1)
        for i, (name, value) in enumerate(nodes):
            p = pe(t, 0.15 + 0.32 * i, 0.55 + 0.32 * i)
            if p <= 0:
                break
            cx = x0 + step * i
            if i > 0:  # the link draws on from the previous node
                d.line((cx - step + 24, y, cx - step + 24 + (step - 48) * p, y), fill=(*SLATE, 255), width=4)
            r = 22 * (0.4 + 0.6 * p)
            first, last = i == 0, i == n - 1
            col = EMERALD if first else (INK if last else ROSE)
            d.ellipse((cx - r, y - r, cx + r, y + r), fill=(*col, 255))
            text(d, (cx, y + 38), name, 26, 600, INK, "ma")
            vcol = EMERALD_D if first else (INK if last else ROSE)
            text(d, (cx, y - 78 + 16 * (1 - p)), value, 32 if (first or last) else 28, 700, vcol, "ma")
        if note:
            text(d, (m + w / 2, m + 12), note, 26, 500, SLATE, "ma")
    top_card(img, t, life, w, h, draw)


def nodes_lit(img, t, life, names, times, title=""):
    """A pipeline whose nodes light up in sequence (times: seconds since the start, one per node)."""
    n = len(names)
    w = min(1460, 170 * n + 120)
    h = 200 if title else 170

    def draw(d, lay, m, w, h):
        y = m + (120 if title else 86)
        x0, x1 = m + 90, m + w - 90
        step = (x1 - x0) / max(1, n - 1)
        if title:
            text(d, (m + w / 2, m + 18), title, 28, 600, INK, "ma")
        d.line((x0, y, x1, y), fill=(*LINE, 255), width=6)
        for i, nm in enumerate(names):
            p = pe(t, times[i], times[i] + 0.45)
            cx = x0 + step * i
            if p > 0 and i > 0:
                d.line((cx - step, y, cx - step + step * min(1, p * 1.5), y), fill=(*EMERALD, 255), width=6)
            r = 20 + 6 * p
            d.ellipse((cx - r, y - r, cx + r, y + r), fill=(*(EMERALD if p > 0.5 else (226, 232, 228)), 255),
                      outline=(*EMERALD, 255), width=3)
            if p > 0.5:  # a soft ring on the node that just lit
                q = pe(t, times[i], times[i] + 0.9)
                rr = r + 16 * q
                d.ellipse((cx - rr, y - rr, cx + rr, y + rr), outline=(*EMERALD, int(150 * (1 - q))), width=3)
            text(d, (cx, y + 36), nm, 24, 600 if p > 0.5 else 500, INK if p > 0.5 else SLATE, "ma")
    top_card(img, t, life, w, h, draw)


def truck_icon(d, x, y, s=1.0, col=EMERALD):
    d.rounded_rectangle((x - 28 * s, y - 16 * s, x + 6 * s, y + 8 * s), 4, fill=(*col, 255))
    d.rounded_rectangle((x + 6 * s, y - 8 * s, x + 26 * s, y + 8 * s), 4, fill=(*col, 255))
    for wx in (-18, 16):
        d.ellipse((x + (wx - 6) * s, y + 4 * s, x + (wx + 6) * s, y + 16 * s), fill=(*INK, 255))


def route(img, t, life, a_name, b_name, info="", tags=(), reroute_at=None, pulse=False):
    """A route line drawing on between two places, a truck driving along it; tags = [(t, text)] popping above the
    truck; reroute_at: a flood mark blocks the line and a detour draws round it."""
    w, h = 1180, 280

    def draw(d, lay, m, w, h):
        x0, x1, y = m + 120, m + w - 120, m + 150
        k = pe(t, 0.1, 0.9)
        d.line((x0, y, x0 + (x1 - x0) * k, y), fill=(*SLATE, 255), width=5)
        for x, nm in ((x0, a_name), (x1, b_name)):
            d.ellipse((x - 12, y - 12, x + 12, y + 12), fill=(*EMERALD_D, 255))
            text(d, (x, y + 26), nm, 26, 600, INK, "ma")
        if info:
            text(d, (m + w / 2, m + 16), info, 26, 500, SLATE, "ma")
        if reroute_at is None:
            u = min(1.0, max(0.0, (t - 0.6) / max(0.5, life - 1.2)))
            tx = x0 + (x1 - x0) * (1 - (1 - u) ** 2)
            ty = y
        else:
            fx = (x0 + x1) / 2
            r = reroute_at
            fk = pe(t, r, r + 0.5)
            if fk > 0:  # the flood: a blue wave on the line
                for j in range(3):
                    yy = y - 6 + 9 * j
                    pts = [(fx - 40 + q, yy + 5 * math.sin(q / 7 + t * 4)) for q in range(0, 81, 4)]
                    d.line(pts, fill=(*SKY, int(255 * fk)), width=4)
                text(d, (fx, y - 64), "Flood alert", 28, 700, SKY, "ma")
            dk = pe(t, r + 0.5, r + 1.4)
            detour = [(x0 + (fx - 40 - x0) * 0.6, y), (fx - 60, y + 58), (fx + 60, y + 58),
                      (x1 - (x1 - fx - 40) * 0.6, y)]
            if dk > 0:
                pts = [(x0 + (fx - 40 - x0) * 0.6, y)]
                segs = list(zip(detour, detour[1:]))
                total = dk * len(segs)
                for si, (pa, pb) in enumerate(segs):
                    f = min(1.0, total - si)
                    if f <= 0:
                        break
                    pts.append((pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f))
                d.line(pts, fill=(*EMERALD, 255), width=6, joint="curve")
                text(d, (fx, y + 64), "rerouted", 24, 600, EMERALD_D, "ma")
            # the truck: drives to the flood, then takes the detour
            u = min(1.0, max(0.0, (t - 0.6) / max(0.4, r - 0.6)))
            tx, ty = x0 + (detour[0][0] - x0) * u, y
            if dk > 0:
                v = pe(t, r + 1.0, life - 0.4)
                path = [detour[0]] + detour[1:] + [(x1, y)]
                seg = min(len(path) - 2, int(v * (len(path) - 1)))
                f = v * (len(path) - 1) - seg
                pa, pb = path[seg], path[seg + 1]
                tx, ty = pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f
        if pulse:  # live position: a pulsing dot
            q = (t * 1.2) % 1.0
            rr = 10 + 22 * q
            d.ellipse((tx - rr, ty - 34 - rr, tx + rr, ty - 34 + rr), outline=(*EMERALD, int(200 * (1 - q))), width=3)
            d.ellipse((tx - 9, ty - 43, tx + 9, ty - 25), fill=(*EMERALD, 255))
        truck_icon(d, tx, ty - 4)
        for i, (tt, s) in enumerate(tags):
            p = pe(t, tt, tt + 0.4)
            if p > 0:
                fw = font(28, 700).getlength(s) + 36
                bx, by = tx - fw / 2, ty - 92 - 14 * (1 - p) - 52 * i
                d.rounded_rectangle((bx, by, bx + fw, by + 44), 12, fill=(*AMBER, int(255 * p)))
                d.text((tx, by + 22), s, font=font(28, 700), fill=(*INK, int(255 * p)), anchor="mm")
    top_card(img, t, life, w, h, draw)


def escrow(img, t, life, release_at=None, amount=""):
    """Buyer -> escrow -> farmer: the payment travels to escrow and is held; on release it travels on to the farmer."""
    w, h = 1120, 220

    def draw(d, lay, m, w, h):
        y = m + 112
        xs = [m + 150, m + w / 2, m + w - 150]
        labels = [("Buyer", INK), ("Escrow", AMBER_D), ("Farmer", EMERALD_D)]
        for (nm, col), x in zip(labels, xs):
            fill = (254, 243, 199) if nm == "Escrow" else (241, 245, 243)
            d.rounded_rectangle((x - 92, y - 40, x + 92, y + 40), 16, fill=(*fill, 255), outline=(*col, 255), width=3)
            text(d, (x, y), nm, 30, 700, col, "mm")
        k1 = pe(t, 0.3, 1.2)
        ax0, ax1 = xs[0] + 96, xs[1] - 96
        d.line((ax0, y, ax0 + (ax1 - ax0) * k1, y), fill=(*AMBER, 255), width=6)
        if k1 > 0.95:
            d.polygon([(ax1 + 2, y), (ax1 - 16, y - 11), (ax1 - 16, y + 11)], fill=(*AMBER, 255))
        coin_x = ax0 + (ax1 - ax0) * k1
        held = release_at is None or t < release_at
        if held:
            d.ellipse((coin_x - 15, y - 58, coin_x + 15, y - 28), fill=(*AMBER, 255))
            if k1 >= 1:
                text(d, (xs[1], y + 56), "payment held" + (f" · {amount}" if amount else ""), 26, 600, AMBER_D, "ma")
        else:
            k2 = pe(t, release_at, release_at + 0.9)
            bx0, bx1 = xs[1] + 96, xs[2] - 96
            d.line((bx0, y, bx0 + (bx1 - bx0) * k2, y), fill=(*EMERALD, 255), width=6)
            if k2 > 0.95:
                d.polygon([(bx1 + 2, y), (bx1 - 16, y - 11), (bx1 - 16, y + 11)], fill=(*EMERALD, 255))
            cx = bx0 + (bx1 - bx0) * k2
            d.ellipse((cx - 15, y - 58, cx + 15, y - 28), fill=(*EMERALD, 255))
            if k2 >= 0.9:
                text(d, (xs[2], y + 56), "released on delivery", 26, 600, EMERALD_D, "ma")
    top_card(img, t, life, w, h, draw)


def gauge(img, t, life, lo=300, hi=850, value=775, sub="", side="right"):
    """A credit-score dial: the arc draws, the needle sweeps to the score, the number counts up."""
    w, h = 520, 330

    def draw(d, lay, m, w, h):
        cx, cy, r = m + w / 2, m + 230, 150
        k = pe(t, 0.2, 1.4)
        d.arc((cx - r, cy - r, cx + r, cy + r), 180, 360, fill=(*LINE, 255), width=22)
        frac = (value - lo) / (hi - lo) * k
        d.arc((cx - r, cy - r, cx + r, cy + r), 180, 180 + 180 * frac, fill=(*EMERALD, 255), width=22)
        ang = math.pi * (1 - frac)
        nx, ny = cx + (r - 34) * math.cos(ang), cy - (r - 34) * math.sin(ang)
        d.line((cx, cy, nx, ny), fill=(*INK, 255), width=6)
        d.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=(*INK, 255))
        text(d, (cx - r, cy + 22), str(lo), 22, 500, SLATE, "ma")
        text(d, (cx + r, cy + 22), str(hi), 22, 500, SLATE, "ma")
        text(d, (cx, cy - 64), str(int(round(lo + (value - lo) * k))), 64, 700, INK, "ms")
        if sub:
            text(d, (cx, m + 22), sub, 26, 600, EMERALD_D, "ma")

    a, kk = life_alpha(t, life)
    if a <= 0.01:
        return
    lay = card(w, h)
    m = lay.info["m"]
    draw(ImageDraw.Draw(lay), lay, m, w, h)
    x = WIN[2] - 40 - w - m + 60 * (1 - kk) if side == "right" else WIN[0] + 40 - m - 60 * (1 - kk)
    put(img, lay, (x, WIN[1] + 40 - m), a)


def bars(img, t, life, n=16, label="trucks a month to break even"):
    """Break-even: monthly truck bars rise one by one until the line is reached at n; the count rises with them."""
    w, h = 1120, 300

    def draw(d, lay, m, w, h):
        x0, y0, bw, gap = m + 50, m + 260, 30, 10
        shown = pe(t, 0.2, 1.8) * n
        for i in range(n):
            p = min(1.0, max(0.0, shown - i))
            if p <= 0:
                break
            hh = 30 + 9 * i
            d.rounded_rectangle((x0 + i * (bw + gap), y0 - hh * p, x0 + i * (bw + gap) + bw, y0), 6,
                                fill=(*(EMERALD if i == n - 1 else (167, 207, 187)), 255))
        ly = y0 - (30 + 9 * (n - 1)) - 8
        d.line((x0 - 10, ly, x0 + n * (bw + gap), ly), fill=(*AMBER_D, 255), width=3)
        text(d, (x0 - 6, ly - 34), "break-even", 22, 600, AMBER_D, "la")
        text(d, (m + w - 40, m + 30), str(int(min(n, shown + 0.999))), 80, 700, EMERALD_D, "ra")
        text(d, (m + w - 40, m + 120), label, 24, 500, SLATE, "ra")
    a, k = life_alpha(t, life)
    if a <= 0.01:
        return
    lay = card(w, h)
    m = lay.info["m"]
    draw(ImageDraw.Draw(lay), lay, m, w, h)
    put(img, lay, (WIN[2] - 40 - w - m + 60 * (1 - k), WIN[1] + 40 - m), a)


def timeline(img, t, life, items):
    """A timeline that draws on, each milestone popping as the line reaches it. items = [(date, text)]."""
    w, h = 1100, 200

    def draw(d, lay, m, w, h):
        x0, x1, y = m + 120, m + w - 120, m + 92
        k = pe(t, 0.1, 1.3)
        d.line((x0, y, x0 + (x1 - x0) * k, y), fill=(*EMERALD, 255), width=6)
        for i, (date, s) in enumerate(items):
            x = x0 + (x1 - x0) * i / max(1, len(items) - 1)
            p = pe(t, 0.1 + 1.2 * i / max(1, len(items) - 1), 0.5 + 1.2 * i / max(1, len(items) - 1))
            if p <= 0:
                continue
            r = 16 * (0.5 + 0.5 * p)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(*AMBER, 255), outline=(*AMBER_D, 255), width=2)
            text(d, (x, y - 62 + 10 * (1 - p)), date, 32, 700, INK, "ma")
            text(d, (x, y + 30), s, 26, 500, EMERALD_D, "ma")
    top_card(img, t, life, w, h, draw)


def truckpool(img, t, life, lots=8, cap="5,000 kg"):
    """Small lots slide into one shared truck; its load bar fills to the 5-ton line."""
    w, h = 1000, 220

    def draw(d, lay, m, w, h):
        y = m + 120
        tx = m + w - 300
        d.rounded_rectangle((tx, y - 50, tx + 200, y + 34), 10, outline=(*EMERALD_D, 255), width=4)
        d.rounded_rectangle((tx + 200, y - 22, tx + 254, y + 34), 8, outline=(*EMERALD_D, 255), width=4)
        for wx in (tx + 40, tx + 160, tx + 226):
            d.ellipse((wx - 15, y + 26, wx + 15, y + 56), fill=(*INK, 255))
        filled = 0
        for i in range(lots):
            p = pe(t, 0.2 + 0.22 * i, 0.6 + 0.22 * i)
            sx = m + 60 + (i % 4) * 92
            sy = y - 52 + (i // 4) * 62
            if p < 1:
                x = sx + (tx + 20 - sx) * p
                yy = sy + (y - 40 - sy) * p
                d.rounded_rectangle((x, yy, x + 70, yy + 46), 8, fill=(*AMBER, int(255 * (1 - 0.6 * p))))
            else:
                filled += 1
        frac = filled / lots
        d.rounded_rectangle((tx + 8, y - 42 + 68 * (1 - frac), tx + 192, y + 26), 6, fill=(*EMERALD, 255))
        text(d, (tx + 100, y - 98), cap, 32, 700, EMERALD_D, "ma")
        text(d, (m + 40, m + 16), "small lots, one shared 5-ton truck", 26, 500, SLATE)
    top_card(img, t, life, w, h, draw)


def versus(img, t, life, low=("Middleman's offer", "Tk 4,800"), high=("Pooled truck", "Tk 19,980"), note=""):
    """The circuit breaker: the below-cost offer is struck through, the better route counts up beside it."""
    w, h = 1000, 250

    def draw(d, lay, m, w, h):
        xa, xb, y = m + 260, m + w - 260, m + 70
        text(d, (xa, y - 46), low[0], 28, 600, SLATE, "ma")
        text(d, (xa, y), low[1], 56, 700, ROSE, "ma")
        k = pe(t, 0.5, 1.0)
        fw = font(56, 700).getlength(low[1])
        if k > 0:
            d.line((xa - fw / 2 - 6, y + 52, xa - fw / 2 - 6 + (fw + 12) * k, y + 52), fill=(*ROSE, 255), width=6)
        text(d, (xb, y - 46), high[0], 28, 600, SLATE, "ma")
        text(d, (xb, y), count_text(high[1], pe(t, 0.8, 1.8)), 56, 700, EMERALD_D, "ma")
        if note:  # the Greek letters come from Segoe UI (Anek has none), the rest in Anek
            f1, f2 = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 27), font(26, 600)
            g = "ΔΠ "
            wtot = f1.getlength(g) + f2.getlength(note)
            x = m + w / 2 - wtot / 2
            d.text((x, m + h - 52), g, font=f1, fill=(*ROSE, 255))
            d.text((x + f1.getlength(g), m + h - 52), note, font=f2, fill=(*ROSE, 255))
    top_card(img, t, life, w, h, draw)


def redact(img, t, life, before="Phone: 01X XXXX XXXX", after="<BD_PHONE_REDACTED>", title=""):
    """PII removal: a bar sweeps over the phone number and the token replaces it."""
    w, h = 900, 190

    def draw(d, lay, m, w, h):
        y = m + 104
        if title:
            text(d, (m + w / 2, m + 18), title, 26, 500, SLATE, "ma")
        k = pe(t, 0.5, 1.3)
        f = font(40, 600)
        x = m + w / 2 - f.getlength(before) / 2
        if k < 1:
            d.text((x, y), before, font=f, fill=(*INK, 255), anchor="lm")
            d.rectangle((x - 8, y - 28, x - 8 + (f.getlength(before) + 16) * k, y + 28), fill=(*INK, 255))
        else:
            q = pe(t, 1.3, 1.8)
            d.text((m + w / 2, y), after, font=f, fill=(*EMERALD_D, int(255 * q)), anchor="mm")
    top_card(img, t, life, w, h, draw)


def ring(img, t, life, value="24 h", sub="the most a farmer's details are kept"):
    """A ring that draws its full circle as the number lands (data kept for 24 hours)."""
    w, h = 460, 300

    def draw(d, lay, m, w, h):
        cx, cy, r = m + w / 2, m + 140, 100
        k = pe(t, 0.2, 1.4)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(*LINE, 255), width=18)
        d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * k, fill=(*EMERALD, 255), width=18)
        text(d, (cx, cy), value, 54, 700, INK, "mm")
        text(d, (cx, m + h - 40), sub, 22, 500, SLATE, "ma")
    a, kk = life_alpha(t, life)
    if a <= 0.01:
        return
    lay = card(w, h)
    m = lay.info["m"]
    draw(ImageDraw.Draw(lay), lay, m, w, h)
    put(img, lay, (WIN[2] - 40 - w - m + 60 * (1 - kk), WIN[1] + 40 - m), a)


def stamp(img, t, life, x, y, letter="A", label="GRADE"):
    """The grade stamp lands on the certificate: drops in large and rotated, settles with an exponential ease."""
    a, _ = life_alpha(t, life, din=0.12)
    if a <= 0.01:
        return
    k = pe(t, 0, 0.45)
    s = 1.9 - 0.9 * k
    size = 230
    lay = layer((size, size))
    d = ImageDraw.Draw(lay)
    d.ellipse((6, 6, size - 6, size - 6), outline=(*AMBER_D, 255), width=10)
    d.ellipse((24, 24, size - 24, size - 24), outline=(*AMBER_D, 200), width=3)
    d.text((size / 2, size / 2 - 12), letter, font=font(110, 700), fill=(*AMBER_D, 255), anchor="mm")
    d.text((size / 2, size / 2 + 62), label, font=font(26, 700), fill=(*AMBER_D, 255), anchor="mm")
    lay = lay.rotate(-14 + 6 * k, resample=Image.BICUBIC, expand=False)
    sz = int(size * s)
    lay = lay.resize((sz, sz), Image.BICUBIC)
    put(img, lay, (x - sz / 2, y - sz / 2), a * min(1.0, 0.3 + k))


def box(img, t, life, rect, color=AMBER, label=""):
    """A highlight box drawing on around a region (frame coordinates), clockwise from the top left."""
    a, _ = life_alpha(t, life, din=0.05)
    if a <= 0.01:
        return
    x0, y0, x1, y1 = rect
    k = pe(t, 0, 0.6)
    per = 2 * ((x1 - x0) + (y1 - y0))
    L = per * k
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    lay = layer((W, H))
    d = ImageDraw.Draw(lay)
    acc = 0.0
    for pa, pb in zip(pts, pts[1:]):
        seg = math.dist(pa, pb)
        if acc + seg <= L:
            d.line((pa, pb), fill=(*color, 255), width=6)
        elif acc < L:
            f = (L - acc) / seg
            d.line((pa, (pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f)), fill=(*color, 255), width=6)
        acc += seg
    if label and k > 0.6:
        f = font(26, 700)
        lw = f.getlength(label) + 28
        d.rounded_rectangle((x0, y0 - 46, x0 + lw, y0 - 6), 10, fill=(*color, 255))
        d.text((x0 + 14, y0 - 26), label, font=f, fill=(*INK, 255), anchor="lm")
    put(img, lay, (0, 0), a)


# -- transitions and titles -----------------------------------------------------------------------------------------

def wipe(old: Image.Image, new: Image.Image, p: float) -> Image.Image:
    """Section change: an emerald panel with an amber leading edge sweeps across (covering the old picture), then
    sweeps on (revealing the new one). p: 0..1 over the whole move; each half eases out exponentially."""
    if p <= 0:
        return old
    if p >= 1:
        return new
    out = (old if p < 0.5 else new).copy()
    d = ImageDraw.Draw(out)
    if p < 0.5:
        k = pe(p, 0, 0.5)
        x = W * k
        d.rectangle((0, 0, x, H), fill=EMERALD)
        d.rectangle((x - 18, 0, x, H), fill=AMBER)
    else:
        k = pe(p, 0.5, 1.0)
        x = W * k
        d.rectangle((x, 0, W, H), fill=EMERALD)
        if x > 0:
            d.rectangle((x, 0, min(W, x + 18), H), fill=AMBER)
    return out


def title_reveal(img: Image.Image, title: str, t: float, x: float, y: float, size: int = 44):
    """A section title revealed by a mask moving left to right, after an amber bar drops in beside it."""
    bar = pe(t, 0.0, 0.35)
    d = ImageDraw.Draw(img)
    if bar > 0:
        d.rounded_rectangle((x, y + 4 + 36 * (1 - bar), x + 7, y + 4 + 36), 3, fill=AMBER)
    k = pe(t, 0.12, 0.7)
    if k <= 0:
        return
    spr = sprite(title, size, 600, INK)
    cw = max(1, int(spr.width * k))
    part = spr.crop((0, 0, cw, spr.height))
    img.paste(part, (int(x + 26 - 10), int(y - 10)), part)
