"""Builds the silent, captioned draft of the KrishiNexus demo video from the recorded frames.

Design: the animated team intro (intro.py), then each scene as a screen recording inside a styled browser window with
the page's real tanvir.health address, on the Heat Wave navy with a soft glow and a dot grid. Each scene opens with its
title, then the window rises in; key figures slide in as yellow callout cards; captions sit in a branded bar; a thin
yellow line along the bottom shows progress. A clip longer than its slot is sped up evenly, a shorter one holds its
last frame. Frames are piped as MJPEG into Playwright's bundled ffmpeg (VP8/WebM; the final cut with the voice needs a
full ffmpeg for H.264 and audio).

Usage: python assemble.py <output.webm>
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import textwrap
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from intro import ASSETS, NAVY, SOFT, WHITE, YELLOW, font, intro_frames, phase  # noqa: E402

HERE = Path(__file__).resolve().parent
FRAMES = HERE / "frames"
FPS = 30
W, H = 1920, 1080
FFMPEG = Path(os.environ["LOCALAPPDATA"]) / "ms-playwright" / "ffmpeg-1011" / "ffmpeg-win64.exe"
INK = (12, 17, 36)

# Window geometry: the 1920x1080 recording at 0.9 scale under a 46 px title bar.
WX, WY, BAR = 96, 28, 46
CW, CH = 1728, 972
WIN_W, WIN_H = CW, CH + BAR
RADIUS = 18

PATHS = {"S01": "/", "S02": "/login", "S03": "/os/field", "S04": "/os/field", "S05a": "/", "S05b": "/docs",
         "S06a": "/os/coop", "S06b": "/os/himagar", "S07a": "/os/trade", "S07b": "/os/trade", "S07c": "/os/driver",
         "S08": "/os/market", "S09": "/docs", "S10": "/docs"}

# (clips, slot s, title, narration, callouts [(start fraction, big, small)]). Narration: docs/VIDEO_PLAN.md.
SEGMENTS = [
    (["S01"], 16, "The problem", "In Bangladesh, a potato farmer often sells below cost, while five tiers of middlemen mark produce up by as much as 116%. Traders hold 77% of cold-storage space, and one flash flood can wipe out a season.",
     [(0.18, "Up to 116%", "middleman markup (green chili)"), (0.62, "77.32%", "of cold storage held by traders and owners")]),
    (["S02"], 13, "One OS, every role", "KrishiNexus OS is one AI operating system for everyone in that chain: the farmer, the co-op, the cold store, the buyer, the truck driver and the bank. Each logs in to their own workspace.",
     [(0.35, "8 roles", "one operating system")]),
    (["S03"], 20, "The farmer asks", "Rahim, a potato farmer in Rangpur, just asks in his own dialect. After his consent, four AI agents grade his crop, compare today's market with cold storage and a shared truck, and check flood risk. A circuit breaker stops him selling below his cost, and shows the working.",
     [(0.2, "Rangpuri Bangla", "typed or spoken"), (0.66, "Tk 20,004", "pooled truck, vs Tk 5,223 cold storage")]),
    (["S04"], 12, "Photo grading", "He can photograph his potatoes. A trained vision model finds every tuber and its defects, and signs a quality certificate that buyers and banks can verify.",
     [(0.62, "Grade A", "HMAC-signed quality certificate")]),
    (["S05a", "S05b"], 16, "Agents, tools, offline", "Behind every answer, you can watch the agents work: retrieval from Bangladeshi farm data, live tool calls through three MCP servers, and every step traced. It even runs offline, on a fine-tuned Bangla model at a village kiosk.",
     [(0.15, "Below-cost sale blocked", "the ΔΠ circuit breaker"), (0.55, "13 MCP tools", "on 3 live servers")]),
    (["S06a", "S06b"], 14, "Co-op and cold storage", "Co-ops pool small harvests into full five-ton trucks. The cold store sees live chamber sensors in a 3D twin, and when a flood or heat alert hits, the trucks are rerouted.",
     [(0.18, "5-ton truck pools", "small lots, one shared truck"), (0.66, "Flood alert", "Sentinel-1 radar, 72 h ahead")]),
    (["S07a", "S07b", "S07c"], 23, "Direct market and delivery", "Rahim can also sell directly. He lists his lot, traders bid in the open, and he accepts the best bid. The payment is held in escrow. A driver takes the job, reports the load temperature on the road, our shelf-life model checks it will arrive safe, and on delivery the payment is released to Rahim.",
     [(0.12, "Tk 18.75/kg", "open bid, raised live"), (0.4, "Payment held", "signed escrow (simulated)"), (0.78, "Payment released", "on delivery")]),
    (["S08"], 12, "Credit for the farmer", "Banks see a credit score from 300 to 850, backed by satellite flood checks and signed certificates, so a farmer without collateral can still get credit.",
     [(0.45, "775", "credit score · Tk 12,000 loan")]),
    (["S09"], 17, "Honest AI, safe data", "We trained five models and publish every score, including the ones that missed their targets. The app asks for consent, removes names and phone numbers, keeps data for 24 hours only, and always leaves the final decision to the farmer.",
     [(0.2, "100/100", "regression cases, run live"), (0.62, "24 hours", "the most a farmer's details are kept")]),
    (["S10"], 15, "Growth", "One pooled truck covers its costs, and a district breaks even at sixteen trucks a month. We start a field test this December and a potato pilot in January.",
     [(0.25, "16 trucks a month", "district break-even"), (0.62, "Dec 2026", "field test, then a potato pilot")]),
]
END_S = 5
MAX_SPEED = 1.7
TITLE_IN = 1.0  # seconds of the chapter-title move at the start of each scene

F_CAP, F_URL, F_BAR = font(38, "SemiBold"), font(24, "Regular"), font(22, "SemiBold")
F_BIG, F_SMALL = font(54, "Bold"), font(26, "SemiLight")
F_CH, F_CH_TAG = font(112, "Bold"), font(34, "SemiBold")


# -- static layers ------------------------------------------------------------

@lru_cache(maxsize=1)
def background() -> Image.Image:
    """Navy with two soft glows, a faint dot grid and the window's shadow."""
    bg = Image.new("RGB", (W, H), NAVY)
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse((-300, -400, 900, 600), fill=(46, 58, 110))
    g.ellipse((1200, 500, 2300, 1400), fill=(70, 60, 30))
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    bg = Image.blend(bg, glow, 0.45)
    d = ImageDraw.Draw(bg)
    for y in range(20, H, 36):
        for x in range(20, W, 36):
            d.point((x, y), fill=(44, 54, 92))
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle((WX + 10, WY + 24, WX + WIN_W + 10, WY + WIN_H + 24), RADIUS, fill=150)
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    bg.paste(Image.new("RGB", (W, H), (5, 8, 18)), mask=shadow)
    return bg


@lru_cache(maxsize=1)
def window_mask() -> Image.Image:
    m = Image.new("L", (WIN_W, WIN_H), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, WIN_W - 1, WIN_H - 1), RADIUS, fill=255)
    return m


@lru_cache(maxsize=16)
def chrome(path: str, title: str) -> Image.Image:
    """The browser window's title bar: three dots, the scene title, and the address pill with a lock."""
    bar = Image.new("RGB", (WIN_W, BAR), INK)
    d = ImageDraw.Draw(bar)
    for i, c in enumerate(((237, 106, 94), (245, 191, 79), (98, 197, 84))):
        d.ellipse((20 + 24 * i, 16, 34 + 24 * i, 30), fill=c)
    d.text((112, 11), title, font=F_BAR, fill=SOFT)
    url = f"tanvir.health{'' if path == '/' else path}"
    uw = d.textlength(url, font=F_URL) + 70
    x0 = (WIN_W - uw) / 2
    d.rounded_rectangle((x0, 8, x0 + uw, 38), 15, fill=(30, 38, 70))
    d.rounded_rectangle((x0 + 18, 19, x0 + 30, 30), 2, fill=(98, 197, 84))  # lock body
    d.arc((x0 + 19, 12, x0 + 29, 24), 180, 360, fill=(98, 197, 84), width=2)
    d.text((x0 + 44, 10), url, font=F_URL, fill=WHITE)
    return bar


@lru_cache(maxsize=240)
def content(src: Path) -> Image.Image:
    return Image.open(src).convert("RGB").resize((CW, CH), Image.LANCZOS)


# -- per-frame layers ---------------------------------------------------------

def draw_alpha(img: Image.Image, draw_fn, alpha: float):
    """Run draw_fn(ImageDraw) on a transparent layer and composite it at `alpha`."""
    if alpha <= 0.01:
        return img
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    if alpha < 1:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def caption(img: Image.Image, lines: list[str], alpha: float) -> Image.Image:
    def fn(d):
        widths = [d.textlength(l, font=F_CAP) for l in lines]
        bw, bh = max(widths) + 84, 54 * len(lines) + 30
        x0, y0 = (W - bw) / 2, WY + WIN_H - bh - 34
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 16, fill=(*INK, 228))
        d.rectangle((x0, y0 + 14, x0 + 6, y0 + bh - 14), fill=(*YELLOW, 255))
        for i, l in enumerate(lines):
            d.text(((W - widths[i]) / 2 + 3, y0 + 13 + 54 * i), l, font=F_CAP, fill=(*WHITE, 255))
    return draw_alpha(img, fn, alpha)


def callout(img: Image.Image, big: str, small: str, t: float, life: float) -> Image.Image:
    """A yellow card that slides in at the window's top right, holds, then fades."""
    a_in, a_out = phase(t, 0, 0.35), 1 - phase(t, life - 0.35, life)
    alpha = min(a_in, a_out)
    if alpha <= 0:
        return img
    shift = int(70 * (1 - a_in))

    def fn(d):
        bw = max(d.textlength(big, font=F_BIG), d.textlength(small, font=F_SMALL)) + 64
        x1 = WX + WIN_W - 36 + shift
        x0, y0 = x1 - bw, WY + BAR + 110  # below the site's own header buttons
        d.rounded_rectangle((x0 + 6, y0 + 8, x1 + 6, y0 + 128), 18, fill=(0, 0, 0, 90))
        d.rounded_rectangle((x0, y0, x1, y0 + 120), 18, fill=(*YELLOW, 255))
        d.text((x0 + 32, y0 + 14), big, font=F_BIG, fill=(*INK, 255))
        d.text((x0 + 32, y0 + 78), small, font=F_SMALL, fill=(*INK, 255))
    return draw_alpha(img, fn, alpha)


def chapter_title(img: Image.Image, title: str, t: float) -> Image.Image:
    a = phase(t, 0, 0.25) * (1 - phase(t, 0.55, 0.9))
    rise = int(30 * (1 - phase(t, 0, 0.35)))

    def fn(d):
        tw = d.textlength(title, font=F_CH)
        d.text(((W - d.textlength("KrishiNexus OS", font=F_CH_TAG)) / 2, 400 + rise), "KrishiNexus OS",
               font=F_CH_TAG, fill=(*YELLOW, 255))
        d.text(((W - tw) / 2, 450 + rise), title, font=F_CH, fill=(*WHITE, 255))
        bar = 260 * phase(t, 0.1, 0.45)
        d.rectangle(((W - bar) / 2, 600 + rise, (W + bar) / 2, 608 + rise), fill=(*YELLOW, 255))
    return draw_alpha(img, fn, a)


def scene_frame(src: Path, path: str, title: str, t: float) -> Image.Image:
    win = Image.new("RGB", (WIN_W, WIN_H), INK)
    win.paste(chrome(path, title), (0, 0))
    win.paste(content(src), (0, BAR))
    frame = background().copy()
    k = phase(t, 0.45, TITLE_IN)  # the window rises and settles after the title
    if k >= 1:
        frame.paste(win, (WX, WY), window_mask())
    else:
        if k > 0:
            s = 0.92 + 0.08 * k
            ww, wh = int(WIN_W * s), int(WIN_H * s)
            small = win.resize((ww, wh), Image.BILINEAR)
            m = window_mask().resize((ww, wh)).point(lambda v: int(v * k))
            frame.paste(small, (WX + (WIN_W - ww) // 2, WY + (WIN_H - wh) // 2 + int(40 * (1 - k))), m)
        frame = chapter_title(frame, title, t)
    return frame


def caption_chunks(text: str, slot: float) -> list[tuple[float, float, list[str]]]:
    """Two-line captions, timed by word count across the slot (after the chapter title)."""
    lines = textwrap.wrap(text, 64)
    groups = [lines[i:i + 2] for i in range(0, len(lines), 2)]
    total = len(text.split())
    t, out = TITLE_IN * 0.7, []
    span = slot - t
    for g in groups:
        d = span * len(" ".join(g).split()) / total
        out.append((t, t + d, g))
        t += d
    return out


def clip_frames(name: str) -> tuple[list[tuple[Path, float]], float]:
    data = json.loads((FRAMES / name / "frames.json").read_text(encoding="utf-8"))
    return [(FRAMES / name / f, t) for f, t in data["frames"]], data["end"]


def end_card(t: float) -> Image.Image:
    group = Image.open(ASSETS / "team_6.webp").convert("RGB")
    group = group.resize((W, int(group.height * W / group.width)), Image.LANCZOS).crop((0, 0, W, H))
    img = Image.blend(Image.new("RGB", (W, H), NAVY), group, 0.12)
    big, mid = font(150, "Bold"), font(42, "SemiLight")

    def fn(d):
        a = phase(t, 0, 0.5)
        tw = d.textlength("tanvir.health", font=big)
        d.text(((W - tw) / 2, 330 + 30 * (1 - a)), "tanvir.health", font=big, fill=(*WHITE, int(255 * a)))
        bar = 380 * phase(t, 0.3, 0.8)
        d.rectangle(((W - bar) / 2, 525, (W + bar) / 2, 535), fill=(*YELLOW, 255))
        for i, line in enumerate(("Try KrishiNexus OS live: quick login as JUDGE-01 opens every seat",
                                  "Team Heat Wave · github.com/HTanvir0011/KrishiNexus")):
            a2 = phase(t, 0.6 + 0.25 * i, 1.1 + 0.25 * i)
            lw = d.textlength(line, font=mid)
            d.text(((W - lw) / 2, 580 + 62 * i), line, font=mid, fill=(*(YELLOW if i else SOFT), int(255 * a2)))
    return draw_alpha(img, fn, 1)


def main(out: Path) -> None:
    proc = subprocess.Popen([str(FFMPEG), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
                             "-c:v", "mjpeg", "-i", "pipe:0", "-c:v", "libvpx", "-b:v", "6M", "-deadline", "realtime",
                             "-cpu-used", "6", "-threads", "8", "-f", "webm", "file:" + str(out)], stdin=subprocess.PIPE)
    written = 0

    def emit(img: Image.Image):
        nonlocal written
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        proc.stdin.write(buf.getvalue())
        written += 1

    for frame in intro_frames():  # title, the team one by one, the group photo (intro.py)
        emit(frame)
    print(f"intro: {written / FPS:.1f}s", flush=True)

    scenes_total = sum(s[1] for s in SEGMENTS)
    elapsed = 0.0
    for clips, slot, title, text, callouts in SEGMENTS:
        loaded = [clip_frames(c) for c in clips]
        raw = sum(end for _, end in loaded)
        speed = min(MAX_SPEED, max(1.0, raw / slot))
        chunks = caption_chunks(text, slot)
        offsets, acc = [], 0.0
        for _, end in loaded:
            offsets.append(acc)
            acc += end
        for k in range(round(slot * FPS)):
            t = k / FPS
            t_src = min(t * speed, raw - 1e-3)
            ci = max(i for i, o in enumerate(offsets) if o <= t_src)
            frames, _ = loaded[ci]
            local = t_src - offsets[ci]
            src = frames[0][0]
            for p, ft in frames:
                if ft <= local:
                    src = p
                else:
                    break
            frame = scene_frame(src, PATHS[clips[ci]], title, t)
            for i, (start, big, small) in enumerate(callouts):
                t0 = start * slot
                t1 = callouts[i + 1][0] * slot - 0.2 if i + 1 < len(callouts) else slot - 0.3
                if t0 <= t < t1:
                    frame = callout(frame, big, small, t - t0, t1 - t0)
            line = next((c for c in chunks if c[0] <= t < c[1]), None)
            if line:
                frame = caption(frame, line[2], phase(t, line[0], line[0] + 0.2))
            prog = (elapsed + t) / scenes_total
            ImageDraw.Draw(frame).rectangle((0, H - 6, int(W * prog), H), fill=YELLOW)
            emit(frame)
        elapsed += slot
        print(f"{title}: {raw:.1f}s recorded -> {slot}s at {speed:.2f}x", flush=True)

    for k in range(END_S * FPS):
        emit(end_card(k / FPS))
    proc.stdin.close()
    proc.wait()
    print(f"{out}: {written / FPS:.1f}s, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
