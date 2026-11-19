"""Builds the v2 demo video from the recordings, the edited voice and the mix:

  intro (team, intro2.py) -> S01..S09 (the site in a browser window, warped so each recorded moment lands on the word
  that names it) -> the Android app in a drawn phone (cloned narration) -> S10 -> end card.

Picture: 1920x1080 at 30 fps, rendered in worker processes; encoded with PyAV/libx264 twice from the same frames:
  video/out/krishinexus-demo-1080p.mp4      (master: CRF 18, AAC 192 kbps)
  frontend/public/video/krishinexus-demo.mp4 (web: 1280x720, CRF 24, preset slow, AAC 128 kbps 48 kHz, faststart)
plus the poster (.jpg) and the captions (.en.vtt).

Usage: python build.py [preview t1 t2 ...]     (video/.venv-tts python; run mix.py demo first)
"""
from __future__ import annotations

import json
import re
import sys
import time
from fractions import Fraction
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import intro2  # noqa: E402
import motion as mo  # noqa: E402
import timeline  # noqa: E402
from look import (AMBER, EMERALD, EMERALD_D, EMERALD_T, FPS, H, INK, LINE, ROOT, ROSE, SLATE, W,  # noqa: E402
                  WHITE, canvas_bg, count_text, ease, ease_io, font, logo, paste_sprite, pe, phase, rounded_mask,
                  shadow, sprite)
from motion import SKY  # noqa: E402

WORK = ROOT / "video/work"
FR = WORK / "frames"
OUT_WEB = ROOT / "frontend/public/video"
OUT_MASTER = ROOT / "video/out"

# browser window: the 1920x1080 recording shown at 1600x900 under a 40 px bar
WX, WY, BAR, CW, CH = 160, 116, 40, 1600, 900
WIN_W, WIN_H, RAD = CW, CH + BAR, 16
WIPE_IN, WIPE_OUT = 0.48, 0.04  # the section wipe: starts 0.48 s before the first word, done 0.04 s after it


# -- recordings ------------------------------------------------------------------------------------------------------

@lru_cache(maxsize=40)
def shot(name: str) -> dict:
    d = json.loads((FR / name / "frames.json").read_text())
    mp = FR / name / "marks.json"
    m = json.loads(mp.read_text()) if mp.exists() else {"marks": []}
    return {"times": np.array([t for _, t in d["frames"]]), "files": [FR / name / f for f, _ in d["frames"]],
            "end": d["end"], "marks": {k: v for k, v in m["marks"]}}


@lru_cache(maxsize=12)
def load_img(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def frame_at(name: str, t: float) -> Path:
    s = shot(name)
    i = int(np.searchsorted(s["times"], t, side="right")) - 1
    return s["files"][max(0, min(i, len(s["files"]) - 1))]


def warp(a: float, b: float, name: str, anchors: dict) -> tuple[list, list]:
    """Section time -> recording time, piecewise linear through (word time, mark time) pairs, 1:1 outside them."""
    s = shot(name)
    # a mark name, or "@<seconds>" for a moment in the recording that has no mark (e.g. the start of a scroll)
    pts = sorted((t, float(m[1:]) if m.startswith("@") else s["marks"][m]) for m, t in anchors.items()
                 if m.startswith("@") or m in s["marks"])
    if not pts:
        pts = [(a, 0.0)]
    t0, r0 = pts[0]
    tn, rn = pts[-1]
    full = [(a, max(0.0, r0 - (t0 - a)))] + pts + [(b, min(s["end"] - 0.05, rn + (b - tn)))]
    ts, rs = [], []
    for t, r in full:
        if ts and t <= ts[-1]:
            continue
        ts.append(t)
        rs.append(max(r, rs[-1]) if rs else r)
    return ts, rs


# -- picture elements ------------------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def window_base() -> Image.Image:
    bg = canvas_bg().copy()
    sh = shadow((WIN_W, WIN_H), RAD, blur=26, opacity=55)
    m = (sh.width - WIN_W) // 2
    bg.paste(sh, (WX - m, WY - m + 14), sh)
    return bg


@lru_cache(maxsize=16)
def chrome(url: str) -> Image.Image:
    bar = Image.new("RGB", (WIN_W, BAR), WHITE)
    d = ImageDraw.Draw(bar)
    for i in range(3):
        d.ellipse((18 + 22 * i, 13, 32 + 22 * i, 27), fill=(214, 222, 218), outline=(196, 206, 201))
    f = font(21, 500)
    uw = f.getlength(url) + 64
    x0 = (WIN_W - uw) / 2
    d.rounded_rectangle((x0, 6, x0 + uw, 34), 14, fill=(241, 245, 243))
    d.rounded_rectangle((x0 + 18, 18, x0 + 29, 28), 2, fill=EMERALD)  # the lock
    d.arc((x0 + 19, 12, x0 + 28, 23), 180, 360, fill=EMERALD, width=2)
    d.text((x0 + 40, 7), url, font=f, fill=SLATE)
    d.line((0, BAR - 1, WIN_W, BAR - 1), fill=LINE)
    return bar


@lru_cache(maxsize=1)
def win_mask() -> Image.Image:
    return rounded_mask((WIN_W, WIN_H), RAD)


def content(name: str, rt: float, cam: tuple[float, float, float]) -> Image.Image:
    img = load_img(frame_at(name, rt))
    cx, cy, z = cam
    w, h = img.width / z, img.height / z
    x0 = min(max(cx - w / 2, 0), img.width - w)
    y0 = min(max(cy - h / 2, 0), img.height - h)
    return img.resize((CW, CH), Image.LANCZOS, box=(x0, y0, x0 + w, y0 + h))


def cam_at(keys: list, t: float) -> tuple[float, float, float]:
    """Camera keyframes [(t, (cx, cy, zoom))]: eased moves of 0.7 s into each key."""
    if not keys:
        return (960.0, 540.0, 1.0)
    cur = keys[0][1]
    for kt, kv in keys[1:]:
        if t >= kt:
            k = ease_io((t - kt) / 0.7)
            cur = tuple(c + (v - c) * k for c, v in zip(cur, kv))
    return cur


KINDS = {"emerald": (EMERALD, WHITE, EMERALD_T), "rose": (ROSE, WHITE, (255, 228, 230)),
         "amber": (AMBER, INK, (69, 26, 3))}


def callout(img: Image.Image, big: str, small: str, t: float, life: float, kind: str = "emerald", pos: str = "br"):
    a_in, a_out = pe(t, 0, 0.35), 1 - pe(t, life - 0.3, life)
    a = min(a_in, a_out)
    if a <= 0.01:
        return
    bg, fg, sub = KINDS[kind]
    text = count_text(big, t / 0.9)
    fb, fs = font(60, 700), font(28, 500)
    bw = int(max(fb.getlength(big), fs.getlength(small)) + 76)
    bh = 150
    card = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, bw - 1, bh - 1), 20, fill=(*bg, 255))
    d.rounded_rectangle((0, 22, 8, bh - 22), 4, fill=(*(AMBER if kind != "amber" else WHITE), 255))
    d.text((38, 14), text, font=fb, fill=(*fg, 255))
    d.text((38, 92), small, font=fs, fill=(*sub, 255))
    s = 0.88 + 0.12 * pe(t, 0, 0.4)
    if s < 0.999:
        card = card.resize((int(bw * s), int(bh * s)), Image.BICUBIC)
    card.putalpha(card.getchannel("A").point(lambda v: int(v * a)))
    if pos == "br":
        x, y = WX + WIN_W - 40 - card.width, WY + WIN_H - 40 - card.height
    elif pos == "bl":
        x, y = WX + 40, WY + WIN_H - 40 - card.height
    else:  # "tr"
        x, y = WX + WIN_W - 40 - card.width, WY + BAR + 90
    sh = shadow((card.width, card.height), 20, blur=18, opacity=int(70 * a))
    m = (sh.width - card.width) // 2
    img.paste(sh, (int(x - m), int(y - m + 8)), sh)
    img.paste(card, (int(x), int(y)), card)


def chapter(img: Image.Image, title: str, t: float):
    mo.title_reveal(img, title, t, WX, 30)


def to_frame(rect, cam):
    """A rectangle in recording pixels -> frame pixels, through the camera crop of the window."""
    cx, cy, z = cam
    w, h = 1920 / z, 1080 / z
    x0 = min(max(cx - w / 2, 0), 1920 - w)
    y0 = min(max(cy - h / 2, 0), 1080 - h)
    sc = CW / w
    return (WX + (rect[0] - x0) * sc, WY + BAR + (rect[1] - y0) * sc, WX + (rect[2] - x0) * sc,
            WY + BAR + (rect[3] - y0) * sc)


# -- scenes ----------------------------------------------------------------------------------------------------------

def scene_specs(tl: dict) -> dict:
    """Shots, anchors, camera and callouts per section, in section time, from the narration's word times."""
    S = {s["key"]: s for s in tl["sections"]}

    def W(key):
        sec = S[key]
        return lambda text, after=0.0, end=False: timeline.word_time(sec, text, after, end)

    specs = {}
    w = W("S01")
    specs["S01"] = dict(title="The problem", url="tanvir.health", shots=[
        dict(shot="S01a", until=w("can") - 0.2, anchors={"hero": 0.05, "syndicate": w("Between")},
             cam=[(0, (960, 540, 1.0)), (w("Between") + 0.5, (690, 560, 1.3))]),
        dict(shot="S01b", url="tanvir.health/docs", anchors={"markup": w("mark") - 0.1, "@2.95": w("Traders") - 0.75,
                                                             "cold": w("Traders"), "flood": w("single")},
             cam=[(0, (1470, 600, 1.75)), (w("Traders") - 0.2, (800, 600, 1.75)), (w("single") - 0.2, (1470, 600, 1.75))]),
    ], callouts=[dict(at=w("116") - 0.1, big="116%", small="producer-to-retail markup, CPD study"),
                 dict(at=w("77") - 0.1, big="77.32%", small="cold storage held by traders and plant owners"),
                 dict(at=w("flash"), big="65%", small="of Sunamganj's boro lost in the 2017 flood", kind="amber")],
        fx=[dict(at=w("Between") - 0.2, life=w("mark") - w("Between") + 0.1, fx="chain",
                 nodes=[("Farmer", "Tk 31.42"), ("Faria", "+3.78"), ("Bepari", "+8.52"), ("Aratdar", "+6.60"),
                        ("Paiker", "+5.50"), ("Retailer", "+10.21"), ("Dhaka shopper", "Tk 66.03")],
                 note="Rahim's potato, taka per kilo, field to Dhaka"),
            dict(at=w("116") - 0.1, life=w("Traders") - w("116") - 0.6, fx="box", shot="S01b",
                 src=(1158, 503, 1300, 574)),
            dict(at=w("77"), life=w("single") - w("77") - 0.4, fx="box", shot="S01b", src=(490, 503, 662, 574)),
            dict(at=w("flash"), life=3.0, fx="box", shot="S01b", src=(1160, 503, 1274, 574), color=SKY)])
    w = W("S02")
    specs["S02"] = dict(title="One OS, every role", url="tanvir.health/login", shots=[
        dict(shot="S02", anchors={"login": 0.05, "roles": w("everyone"), "farmer": w("farmer"), "coop": w("co"),
                                  "himagar": w("cold"), "buyer": w("buyer"), "driver": w("truck"),
                                  "bank": w("bank"), "signin": w("Each")},
             cam=[(0, (960, 500, 1.45)), (w("everyone") - 0.3, (960, 540, 1.22))]),
    ], callouts=[dict(at=w("Each"), big="A workspace per role", small="one login each, one shared backend")],
        fx=[dict(at=w(key), life=w("Each") + 1.2 - w(key), fx="box", shot="S02", src=r, color=c)
            for key, r, c in (("farmer", (380, 152, 754, 500), EMERALD), ("co", (772, 152, 1144, 500), AMBER),
                              ("cold", (1166, 152, 1538, 500), SKY), ("buyer", (380, 524, 754, 804), AMBER),
                              ("truck", (1166, 524, 1538, 804), EMERALD), ("bank", (772, 524, 1144, 804), SKY))])
    w = W("S03")
    specs["S03"] = dict(title="The farmer asks", url="tanvir.health/os/field", shots=[
        dict(shot="S03a", until=w("circuit") - 0.45, anchors={"rahim": 0.2, "ask": w("He"), "consent": w("consent"),
                                                                "decision": w("four"), "cards": w("compare")},
             cam=[(0, (960, 600, 1.25)), (w("He") - 0.6, (960, 560, 1.4))]),
        dict(shot="S03b", url="tanvir.health", anchors={"breaker": w("circuit") - 0.1,
                                                        "working": w("and", after=w("cost"))},
             cam=[(0, (1465, 610, 1.6))]),
    ], callouts=[dict(at=w("dialect"), big="Rangpuri Bangla", small="his own words, typed or spoken")],
        fx=[dict(at=w("four") - 0.2, life=w("circuit") - w("four") - 0.2, fx="nodes_lit",
                 names=["Grade the crop", "Today's market", "Cold store + truck", "Flood risk"],
                 times=[w(k) - w("four") + 0.2 for k in ("grade", "compare", "cold", "flood")],
                 title="Four agents, one decision"),
            dict(at=w("circuit") - 0.1, life=w("working", end=True) - w("circuit") + 0.6, fx="versus",
                 low=("Middleman's offer", "Tk 4,800"), high=("Pooled truck", "Tk 19,980"),
                 note="circuit breaker: Tk 12/kg is below his Tk 15/kg cost")])
    w = W("S04")
    specs["S04"] = dict(title="Photo grading", url="tanvir.health/os/field", shots=[
        dict(shot="S04", anchors={"scan": w("photograph"), "graded": w("finds"), "cert": w("certificate")},
             cam=[(0, (960, 560, 1.4))]),
    ], callouts=[dict(at=w("verify") - 0.2, big="HMAC-signed", small="buyers and banks can verify it")],
        fx=[dict(at=w("finds") - 0.1, life=2.1, fx="box", shot="S04", src=(700, 504, 1220, 796), label="every tuber"),
            dict(at=w(("signs", "science")) - 0.05, life=w("verify") - w(("signs", "science")) + 2.2, fx="stamp", x=1150, y=742)])
    w = W("S05")
    specs["S05"] = dict(title="Agents, tools, offline", url="tanvir.health", shots=[
        dict(shot="S05a", until=w("call") - 0.2, anchors={"run": 0.1, "nodes": w("They")},
             cam=[(0, (1465, 560, 1.45)), (1.0, (960, 540, 1.0))]),
        dict(shot="S05b", url="tanvir.health/docs", anchors={"mcp": w("call"), "traced": w("every", w("servers")),
                                                             "offline": w("offline")},
             cam=[(0, (960, 540, 1.0))]),
    ], fx=[dict(at=w("They") - 0.2, life=w("offline") - w("They") - 0.2, fx="nodes_lit",
                names=["PII", "Compress", "CRAG", "Grade", "Bypass", "Cold chain", "Climate", "Review", "Voice"],
                times=[0.3 + 0.62 * i for i in range(9)], title="One question, nine LangGraph nodes, every step traced")],
        callouts=[dict(at=w("call") + 0.2, big="13 MCP tools", small="on 3 live servers, every call traced"),
                 dict(at=w("offline"), big="Offline edge", small="fine-tuned Bangla model at a village kiosk",
                      kind="amber")])
    w = W("S06")
    specs["S06"] = dict(title="Co-op and cold storage", url="tanvir.health/os/coop", shots=[
        dict(shot="S06a", until=w("The") - 0.2, anchors={"coop": 0.1}, cam=[(0, (960, 540, 1.0))]),
        dict(shot="S06b", url="tanvir.health/os/himagar", anchors={"himagar": w("The") + 0.1, "flood": w("flood")},
             cam=[(0, (960, 540, 1.0))]),
    ], callouts=[dict(at=w("sees") - 0.1, big="Live chambers", small="sensor readings in a 3D twin")],
        fx=[dict(at=0.15, life=w("The") - 0.3, fx="truckpool"),
            dict(at=w("And") - 0.2, life=w("rerouted", end=True) - w("And") + 0.8, fx="route", a_name="Cold store",
                 b_name="Market", info="a flood alert reroutes the truck", reroute_at=w("flood") - w("And") + 0.2)])
    w = W("S07")
    specs["S07"] = dict(title="Direct market and delivery", url="tanvir.health/os/trade", shots=[
        dict(shot="S07a", until=w("traders") - 0.2, anchors={"lots": 0.1}, cam=[(0, (960, 540, 1.0))]),
        dict(shot="S07b", until=w("and", after=w("open")) - 0.1, anchors={"bid": w("bid")},
             cam=[(0, (960, 540, 1.0))]),
        dict(shot="S07c", until=w("A", after=w("Escrow")) - 0.2, anchors={"accept": w("accepts"), "escrow": w("payment")},
             cam=[(0, (960, 540, 1.0))]),
        dict(shot="S07d", url="tanvir.health/os/driver", until=w("Our") - 0.2,
             anchors={"take": w("takes"), "loaded": w("reports") - 0.5, "temp": w("temperature")},
             cam=[(0, (960, 540, 1.0))]),
        dict(shot="S07e", url="tanvir.health/os/driver", anchors={"temp": w("Our"), "shelf": w("arrive"),
                                                                  "delivered": w("delivery")},
             cam=[(0, (1240, 560, 1.25))]),
    ], callouts=[dict(at=w("bid"), big="Open bids", small="traders raise them live")],
        fx=[dict(at=w("payment") - 0.1, life=w("A", after=w("Escrow")) - w("payment") + 0.1, fx="escrow"),
            dict(at=w("takes") - 0.2, life=w("delivery") - w("takes") - 0.3, fx="route", a_name="Shibganj",
                 b_name="Bogura", info="26.2 km, the load logged on the road",
                 tags=[(w("temperature") - w("takes") + 0.2, "34 °C"),
                       (w("arrive") - w("takes"), "22 h shelf life: safe")]),
            dict(at=w("delivery") - 0.3, life=3.0, fx="escrow", release_at=0.2)])
    w = W("S08")
    specs["S08"] = dict(title="Credit for the farmer", url="tanvir.health/os/market", shots=[
        dict(shot="S08", anchors={"underwrite": 0.15, "backed": w("backed")},
             cam=[(0, (960, 540, 1.0)), (w("see"), (1500, 560, 1.55))]),
    ], callouts=[dict(at=w("collateral") - 0.3, big="Tk 12,000", small="working capital, no collateral")],
        fx=[dict(at=w("score") - 0.2, life=w("collateral") - w("score") - 0.3, fx="gauge", sub="credit score", side="left")])
    w = W("S09")
    specs["S09"] = dict(title="Honest AI, safe data", url="tanvir.health/docs", shots=[
        dict(shot="S09", anchors={"scores": 0.1, "missed": w("including"), "consent": w("app"),
                                  "safeguards": w("always")}, cam=[(0, (960, 540, 1.0))]),
    ], callouts=[dict(at=w("models"), big="5 trained models", small="every score published, misses included")],
        fx=[dict(at=w("removes") - 0.1, life=w("keeps") - w("removes") + 0.1, fx="redact",
                 title="names and phone numbers never reach the agents"),
            dict(at=w("24") - 0.2, life=w("farmer", end=True) - w("24") + 0.6, fx="ring")])
    w = W("S10")
    specs["S10"] = dict(title="The road ahead", url="tanvir.health/docs", end_card=w("This", after=w("January")) - 0.3, shots=[
        dict(shot="S10", anchors={"truck": 0.1, "pilot": w("We")}, cam=[(0, (960, 540, 1.0))]),
    ], callouts=[dict(at=w("covers") - 0.1, big="1 pooled truck", small="covers its own costs")],
        fx=[dict(at=w("district") - 0.2, life=w("We") - w("district"), fx="bars", n=16),
            dict(at=w("We") - 0.1, life=w("This", after=w("January")) - w("We") - 0.2, fx="timeline",
                 items=[("Dec 2026", "field test"), ("Jan 2027", "potato pilot")])])
    for key, sp in specs.items():  # slot bounds and callout lifetimes
        sec = S[key]
        dur = sec["end"] - sec["start"]
        end = sp.get("end_card", dur + 0.5)
        t0 = 0.0
        for k, sh in enumerate(sp["shots"]):
            sh["from"] = t0
            sh["to"] = sh.get("until", end) if k < len(sp["shots"]) - 1 else end
            sh["warp"] = warp(sh["from"], sh["to"], sh["shot"], sh["anchors"])
            t0 = sh["to"]
        cs = sorted(sp["callouts"], key=lambda c: c["at"])
        sp["callouts"] = cs
        for i, c in enumerate(cs):
            nxt = cs[i + 1]["at"] - 0.2 if i + 1 < len(cs) else end - 0.25
            c["life"] = max(0.8, min(c.get("max_life", 3.2), nxt - c["at"]))
    return specs


def scene_frame(sp: dict, t: float) -> Image.Image:
    img = window_base().copy()
    shots = sp["shots"]
    k = max(i for i, s in enumerate(shots) if s["from"] <= t or i == 0)
    sh = shots[k]
    rt = float(np.interp(t, *sh["warp"]))
    win = Image.new("RGB", (WIN_W, WIN_H), WHITE)
    win.paste(content(sh["shot"], rt, cam_at(sh["cam"], t)), (0, BAR))  # camera keys are in section time
    if k > 0 and t - sh["from"] < 0.12:  # a short dissolve from the previous shot's last frame
        pv = shots[k - 1]
        old = content(pv["shot"], float(np.interp(pv["to"], *pv["warp"])), cam_at(pv["cam"], pv["to"]))
        cur = win.crop((0, BAR, WIN_W, WIN_H))
        win.paste(Image.blend(old, cur, (t - sh["from"]) / 0.12), (0, BAR))
    win.paste(chrome(sh.get("url", sp["url"])), (0, 0))
    img.paste(win, (WX, WY), win_mask())
    chapter(img, sp["title"], t)
    cam = cam_at(sh["cam"], t)
    for f in sp.get("fx", []):
        if f["at"] <= t < f["at"] + f["life"]:
            kw = {k: v for k, v in f.items() if k not in ("at", "life", "fx", "src", "shot")}
            if f["fx"] == "box":
                if f.get("shot") and f["shot"] != sh["shot"]:
                    continue
                kw["rect"] = to_frame(f["src"], cam)
            getattr(mo, f["fx"])(img, t - f["at"], f["life"], **kw)
    for c in sp["callouts"]:
        if c["at"] <= t < c["at"] + c["life"]:
            callout(img, c["big"], c["small"], t - c["at"], c["life"], c.get("kind", "emerald"), c.get("pos", "br"))
    return img


# -- the phone section -----------------------------------------------------------------------------------------------

PS = 1.05
SW, SHH = int(412 * PS), int(915 * PS)          # app screen 433x961
STATUS, BEZ = 28, 14
PW, PH = SW + 2 * BEZ, SHH + STATUS + 2 * BEZ
PX, PY = 330, (H - PH) // 2


@lru_cache(maxsize=1)
def phone_body() -> Image.Image:
    body = Image.new("RGBA", (PW + 8, PH), (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    d.rounded_rectangle((0, 0, PW - 1, PH - 1), 58, fill=(*INK, 255))
    d.rounded_rectangle((2, 2, PW - 3, PH - 3), 56, outline=(70, 80, 96, 255), width=2)
    d.rounded_rectangle((PW - 2, 190, PW + 5, 280), 3, fill=(40, 48, 64, 255))  # side buttons
    d.rounded_rectangle((PW - 2, 310, PW + 5, 350), 3, fill=(40, 48, 64, 255))
    return body


@lru_cache(maxsize=1)
def status_bar() -> Image.Image:
    bar = Image.new("RGB", (SW, STATUS), (246, 248, 245))
    d = ImageDraw.Draw(bar)
    d.text((26, 3), "10:30", font=font(18, 600), fill=INK)
    d.ellipse((SW / 2 - 8, 6, SW / 2 + 8, 22), fill=(17, 24, 39))  # punch-hole camera
    x = SW - 70
    for i, hgt in enumerate((5, 8, 11, 14)):  # signal
        d.rectangle((x + 5 * i, 20 - hgt, x + 5 * i + 3, 20), fill=INK)
    d.rounded_rectangle((SW - 42, 7, SW - 18, 19), 3, outline=INK, width=2)  # battery
    d.rectangle((SW - 39, 10, SW - 25, 16), fill=INK)
    return bar


@lru_cache(maxsize=1)
def screen_mask() -> Image.Image:
    return rounded_mask((SW, SHH + STATUS), 44)


def app_screen(name: str, rt: float) -> Image.Image:
    return load_img(frame_at(name, rt)).resize((SW, SHH), Image.LANCZOS)


def mob_specs(sec: dict) -> dict:
    def w(text, after=0.0):
        return timeline.word_time(sec, text, after)

    def exact(word):  # "He" must not match "here's"
        off = sec["voice_at"] - sec["start"]
        return next(s + off for t, s, e in sec["words"] if t.strip().strip(".,").lower() == word.lower())
    rahim = ("Rahim", "Raheem", "Rahem", "Rahman")
    shots = [
        dict(shot="M0", until=w(rahim) - 0.15, anchors={"home": 0.45, "rahim": w("Our"), "mic": w("speaks")}),
        dict(shot="M1", until=exact("He") - 0.15, anchors={"ask": w(rahim) + 0.15, "answer": w(("hears", "here"))}),
        dict(shot="M2", until=w("Buyers") - 0.15, anchors={"grading": w("photographs"), "graded": w("signed"),
                                                            "cert": w("seconds") + 0.3}),
        dict(shot="M3", until=w("drivers") - 0.15, anchors={"lot": w("bid"), "raise": w("phones")}),
        dict(shot="M4", anchors={"route": w("drivers") + 0.2, "share": w("location") - 0.2}),
    ]
    end = sec["end"] - sec["start"] + 0.5
    t0 = 0.0
    for k, s in enumerate(shots):
        s["from"], s["to"] = t0, (s["until"] if k < len(shots) - 1 else end)
        s["warp"] = warp(s["from"], s["to"], s["shot"], s["anchors"])
        t0 = s["to"]
    items = [(w("speaks") - 0.2, "Speaks Bangla", "ask out loud, hear the answer back"),
             (w("photographs") - 0.2, "A signed grade in seconds", "photograph the harvest"),
             (w("Buyers") - 0.2, "Buyers bid from their phones", "open lots, live bids"),
             (w("drivers") - 0.2, "Drivers share live location", "everyone follows the sale in real time")]
    return {"shots": shots, "items": items, "cta": w("everyone") - 0.3}


def mob_frame(ms: dict, t: float) -> Image.Image:
    img = canvas_bg().copy()
    shots = ms["shots"]
    k = max(i for i, s in enumerate(shots) if s["from"] <= t or i == 0)
    sh = shots[k]
    scr = app_screen(sh["shot"], float(np.interp(t, *sh["warp"])))
    if k > 0 and t - sh["from"] < 0.2:
        pv = shots[k - 1]
        old = app_screen(pv["shot"], float(np.interp(pv["to"], *pv["warp"])))
        scr = Image.blend(old, scr, (t - sh["from"]) / 0.2)
    rise = int(700 * (1 - pe(t, -0.05, 0.7)))
    py = PY + rise
    sh_img = shadow((PW, PH), 58, blur=34, opacity=70)
    m = (sh_img.width - PW) // 2
    img.paste(sh_img, (PX - m, py - m + 18), sh_img)
    body = phone_body()
    img.paste(body, (PX, py), body)
    screen = Image.new("RGB", (SW, SHH + STATUS), (246, 248, 245))
    screen.paste(status_bar(), (0, 0))
    screen.paste(scr, (0, STATUS))
    img.paste(screen, (PX + BEZ, py + BEZ), screen_mask())
    # the right column: what the app does, item by item, then the download line
    x = 960
    mo.title_reveal(img, "In the farmer's pocket", t - 0.25, x - 26, 170, size=76)
    ImageDraw.Draw(img).rounded_rectangle((x, 290, x + 170 * pe(t, 0.6, 1.2), 298), 4, fill=AMBER)
    y = 352
    for i, (ti, head, sub) in enumerate(ms["items"]):
        a = pe(t, ti, ti + 0.45)
        if a <= 0:
            break
        nxt = ms["items"][i + 1][0] if i + 1 < len(ms["items"]) else 1e9
        active = t < nxt
        col, subc = (EMERALD_D, SLATE) if active else ((120, 132, 128), (150, 160, 156))
        d = ImageDraw.Draw(img)
        r = 13
        d.ellipse((x, y + 16, x + 2 * r, y + 16 + 2 * r), fill=AMBER if active else (210, 218, 214))
        paste_sprite(img, sprite(head, 44, 600, col), (x + 44 + 30 * (1 - a), y), a)
        paste_sprite(img, sprite(sub, 30, 400, subc), (x + 44 + 30 * (1 - a), y + 56), a)
        if i == len(ms["items"]) - 1:  # live location: a short route with a pulsing dot moving along it
            rx0, rx1, ry = x + 44, x + 700, y + 112
            k = pe(t, ti + 0.2, ti + 0.8)
            d.line((rx0, ry, rx0 + (rx1 - rx0) * k, ry), fill=(*LINE,), width=6)
            if k > 0.5:
                u = min(1.0, max(0.0, (t - ti - 0.6) / 3.0))
                dx = rx0 + (rx1 - rx0) * u
                d.line((rx0, ry, dx, ry), fill=EMERALD, width=6)
                q = ((t - ti) * 1.3) % 1.0
                rr = 10 + 24 * q
                ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(ring).ellipse((dx - rr, ry - rr, dx + rr, ry + rr), outline=(*EMERALD, int(210 * (1 - q))),
                                             width=4)
                img.paste(ring, (0, 0), ring)
                d.ellipse((dx - 11, ry - 11, dx + 11, ry + 11), fill=EMERALD, outline=WHITE, width=3)
            for xx in (rx0, rx1):
                d.ellipse((xx - 7, ry - 7, xx + 7, ry + 7), fill=EMERALD_D)
        y += 118
    a = pe(t, ms["cta"], ms["cta"] + 0.5)
    if a > 0:
        cw, chh = 760, 136
        card = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        d.rounded_rectangle((0, 0, cw - 1, chh - 1), 24, fill=(*EMERALD, 255))
        cxp, cyp = 56, chh // 2  # download arrow
        d.line((cxp, cyp - 22, cxp, cyp + 12), fill=WHITE, width=6)
        d.polygon([(cxp - 15, cyp - 2), (cxp + 15, cyp - 2), (cxp, cyp + 16)], fill=WHITE)
        d.rounded_rectangle((cxp - 20, cyp + 22, cxp + 20, cyp + 27), 2, fill=WHITE)
        d.text((100, 20), "Get the Android app at", font=font(34, 500), fill=EMERALD_T)
        d.text((100, 60), "tanvir.health", font=font(50, 700), fill=WHITE)
        s = 0.94 + 0.06 * a
        card = card.resize((int(cw * s), int(chh * s)), Image.BICUBIC)
        card.putalpha(card.getchannel("A").point(lambda v: int(v * a)))
        shd = shadow(card.size, 24, blur=20, opacity=int(80 * a))
        mm = (shd.width - card.width) // 2
        cy_ = 880 + int(30 * (1 - a))
        img.paste(shd, (x - mm, cy_ - mm + 10), shd)
        img.paste(card, (x, cy_), card)
    return img


# -- end card --------------------------------------------------------------------------------------------------------

@lru_cache(maxsize=8)
def avatar(slug: str, d: int = 132) -> Image.Image:
    im = intro2.portrait(slug)
    side = im.width
    im = im.crop((0, int(im.height * 0.06), side, int(im.height * 0.06) + side)).resize((d, d), Image.LANCZOS)
    m = Image.new("L", (d, d), 0)
    ImageDraw.Draw(m).ellipse((0, 0, d - 1, d - 1), fill=255)
    out = Image.new("RGBA", (d, d))
    out.paste(im, (0, 0), m)
    return out


def end_frame(t: float) -> Image.Image:
    img = canvas_bg().copy()
    lg = logo(96)
    a = pe(t, 0.0, 0.45)
    lg2 = lg.copy()
    lg2.putalpha(lg.getchannel("A").point(lambda v: int(v * a)))
    img.paste(lg2, (W // 2 - 48, 150), lg2)
    paste_sprite(img, sprite("KrishiNexus OS", 104, 700, INK), (W / 2, 262 + 20 * (1 - a)), a, "ma")
    b = pe(t, 0.35, 0.8)
    paste_sprite(img, sprite("Try it now at", 46, 500, SLATE), (W / 2, 418), b, "ma")
    paste_sprite(img, sprite("tanvir.health", 120, 700, EMERALD), (W / 2, 466 + 16 * (1 - b)), b, "ma")
    bar = 360 * pe(t, 0.6, 1.1)
    if bar > 1:
        ImageDraw.Draw(img).rounded_rectangle(((W - bar) / 2, 646, (W + bar) / 2, 655), 5, fill=AMBER)
    team = intro2.TEAM
    d = 128
    gap = 124
    total = len(team) * d + (len(team) - 1) * gap
    x0 = (W - total) / 2
    for i, mbr in enumerate(team):
        ai = pe(t, 0.7 + 0.08 * i, 1.1 + 0.08 * i)
        if ai <= 0:
            continue
        av_ = avatar(mbr["slug"], d).copy()
        av_.putalpha(av_.getchannel("A").point(lambda v: int(v * ai)))
        x = int(x0 + i * (d + gap))
        img.paste(av_, (x, int(706 + 16 * (1 - ai))), av_)
        name = mbr["name"]["en"]
        paste_sprite(img, sprite(name, 21, 600, INK), (x + d / 2, 848), ai, "ma")
    paste_sprite(img, sprite("Team Heat Wave", 34, 600, EMERALD_D), (W / 2, 906), pe(t, 1.2, 1.6), "ma")
    paste_sprite(img, sprite("Quick login as JUDGE-01 opens every seat", 28, 400, SLATE), (W / 2, 958),
                 pe(t, 1.4, 1.8), "ma")
    return img


# -- the whole film --------------------------------------------------------------------------------------------------

class Film:
    def __init__(self):
        self.tl = timeline.load()
        self.secs = self.tl["sections"]
        self.specs = scene_specs(self.tl)
        self.mob = mob_specs(next(s for s in self.secs if s["key"] == "MOB"))
        s0 = self.secs[0]

        def w0(text, after=0.0):
            return s0["start"] + timeline.word_time(s0, text, after)
        # intro cut points: the title, then each member as their name is spoken
        # intro: each member's slot starts on their spoken name, found in spoken order (each search continues
        # after the last); if a name isn't heard, the speech is split evenly between the title and the end
        md = ("Mohammad", "Muhammad", "Mohammed", "Md")
        order = [("Tanvir",), md, md, md, md, md]
        onsets, after = [], 0.0
        try:
            for keys in order:
                t_ = timeline.word_time(s0, keys, after)
                onsets.append(s0["start"] + t_)
                after = t_ + 0.3
        except KeyError:
            a_, b_ = s0["start"] + 3.2, s0["end"] - 2.0
            onsets = [a_ + (b_ - a_) * i / 6 for i in range(6)]
        # the reveal lands as the name is heard; the lead's card starts a little earlier (the title has room) and the
        # advisor's runs 2.7 s, so every member is fully on screen for over 2 s
        leads = [0.65, 0.35, 0.35, 0.35, 0.35, 0.35]
        self.intro_cues = [0.0] + [o - ld for o, ld in zip(onsets, leads)]
        self.grid_at = self.intro_cues[-1] + 2.7
        self.total = self.tl["total"]
        self.n = int(round(self.total * FPS))

    def section_frame(self, i: int, T: float) -> Image.Image:
        sec = self.secs[i]
        t = T - sec["start"]
        key = sec["key"]
        if key == "S00":
            return intro2.frame(T, self.intro_cues, self.grid_at, self.secs[1]["start"])
        if key == "MOB":
            return mob_frame(self.mob, t)
        sp = self.specs[key]
        if "end_card" in sp and t >= sp["end_card"] - WIPE_IN:  # a wipe into the end card too
            te = t - sp["end_card"]
            if te < WIPE_OUT:
                p = (te + WIPE_IN) / (WIPE_IN + WIPE_OUT)
                if p < 0.5:
                    return mo.wipe(scene_frame(sp, t), None, p)
                return mo.wipe(None, end_frame(max(0.0, te)), p)
            return end_frame(te)
        return scene_frame(sp, max(0.0, t))

    def frame(self, T: float) -> Image.Image:
        """Section changes are wipes: covered by b - 0.22 s, revealed by b + 0.04 s (b: the first word)."""
        for k in range(1, len(self.secs)):
            b = self.secs[k]["start"]
            if b - WIPE_IN <= T < b + WIPE_OUT:
                p = (T - (b - WIPE_IN)) / (WIPE_IN + WIPE_OUT)
                if p < 0.5:
                    return mo.wipe(self.section_frame(k - 1, T), None, p)
                return mo.wipe(None, self.section_frame(k, T), p)
        i = max(k for k, s in enumerate(self.secs) if s["start"] <= T or k == 0)
        return self.section_frame(i, T)


def music_hits(film: "Film") -> list[tuple[float, str]]:
    """Film times of the picture's hit points, where mix.py puts the score's accents: the team grid complete, each
    count-up landing, the diagrams completing, the grade stamp, trucks arriving, the app's download card."""
    hits = [(film.grid_at + 0.85, "big")]
    for sec in film.secs:
        key, s0 = sec["key"], sec["start"]
        if key == "MOB":
            hits.append((s0 + film.mob["cta"] + 0.2, "big"))
        sp = film.specs.get(key, {})
        for c in sp.get("callouts", []):
            if re.match(r"(Tk )?\d", c["big"]):
                hits.append((s0 + c["at"] + 0.45, "chime"))
        for f in sp.get("fx", []):  # landing times follow each graphic's easing in motion.py
            at, life, kind = s0 + f["at"], f["life"], f["fx"]
            if kind == "chain":
                hits.append((at + 0.3 + 0.32 * (len(f["nodes"]) - 1), "chime"))
            elif kind == "versus":
                hits.append((at + 1.15, "chime"))
            elif kind == "stamp":
                hits.append((at + 0.15, "thump"))
            elif kind == "route":
                r = f.get("reroute_at")
                hits.append((at + (life - 0.6 if r is None else r + 1.0 + 0.45 * (life - 1.4 - r)), "arrive"))
            elif kind == "escrow" and f.get("release_at") is not None:
                hits.append((at + f["release_at"] + 0.35, "chime"))
            elif kind in ("gauge", "bars"):
                hits.append((at + 0.6, "chime"))
            elif kind == "nodes_lit":
                hits.append((at + f["times"][-1] + 0.15, "chime"))
    kept = []
    for t, k in sorted(hits):  # one accent at a time: drop any within 1.2 s of the last
        if not kept or t - kept[-1][0] >= 1.2:
            kept.append((round(t, 3), k))
    return kept


_FILMS: dict = {}


def _render(job) -> bytes:
    kind, n = job
    if kind not in _FILMS:
        if kind == "demo":
            _FILMS[kind] = Film()
        else:
            import p30
            _FILMS[kind] = p30.Film30()
    return _FILMS[kind].frame(n / FPS).tobytes()


def encode(film, kind: str, outputs: list, mix_path: Path, workers: int = 12):
    """Render `film` in worker processes and encode every output [(path, (w, h), crf, audio bitrate)] in one pass."""
    import av
    import wave
    from multiprocessing import Pool
    from av.video.reformatter import Colorspace, Interpolation
    with wave.open(str(mix_path)) as wv:
        audio = np.frombuffer(wv.readframes(wv.getnframes()), "<i2").reshape(-1, 2).T.astype(np.float32) / 32768
    outs = []
    for path, (w, h), crf, abr in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        c = av.open(str(path), "w", options={"movflags": "+faststart"})
        vs = c.add_stream("libx264", rate=FPS)
        vs.width, vs.height, vs.pix_fmt = w, h, "yuv420p"
        vs.options = {"crf": str(crf), "preset": "slow", "profile": "high",
                      "x264-params": "keyint=60:min-keyint=30:colorprim=bt709:transfer=bt709:colormatrix=bt709"}
        vs.codec_context.colorspace, vs.codec_context.color_primaries, vs.codec_context.color_trc = 1, 1, 1
        vs.codec_context.color_range = 1
        aus = c.add_stream("aac", rate=48000)
        aus.layout = "stereo"
        aus.bit_rate = abr
        outs.append((c, vs, aus, w, h))
    apos = 0
    t0 = time.time()
    def frames(pool, batch=120):  # bounded: results are 6 MB each, so render a window at a time
        for b0 in range(0, film.n, batch):
            yield from pool.imap(_render, [(kind, k) for k in range(b0, min(film.n, b0 + batch))], chunksize=2)

    with Pool(workers) as pool:
        for n, buf in enumerate(frames(pool)):
            img = av.VideoFrame.from_ndarray(np.frombuffer(buf, np.uint8).reshape(H, W, 3), format="rgb24")
            for c, vs, aus, w, h in outs:
                f = img.reformat(w, h, "yuv420p", dst_colorspace=Colorspace.ITU709,
                                 interpolation=Interpolation.LANCZOS)
                f.pts = n
                f.time_base = Fraction(1, FPS)
                for pkt in vs.encode(f):
                    c.mux(pkt)
            # audio up to the end of this frame, in whole 1024-sample AAC frames (the last partial frame, under
            # 21 ms of the fade-out, is dropped so the audio never runs past the picture)
            upto = min(audio.shape[1], int((n + 1) * 48000 / FPS))
            while apos + 1024 <= upto:
                chunk = audio[:, apos:apos + 1024]
                for c, vs, aus, w, h in outs:
                    af = av.AudioFrame.from_ndarray(np.ascontiguousarray(chunk), format="fltp", layout="stereo")
                    af.sample_rate, af.pts, af.time_base = 48000, apos, Fraction(1, 48000)
                    for pkt in aus.encode(af):
                        c.mux(pkt)
                apos += 1024
            if n % 300 == 0:
                print(f"{n}/{film.n} frames, {time.time() - t0:.0f} s", flush=True)
    for c, vs, aus, w, h in outs:
        for pkt in vs.encode(None):
            c.mux(pkt)
        for pkt in aus.encode(None):
            c.mux(pkt)
        c.close()
    print(f"encoded {film.n} frames in {time.time() - t0:.0f} s")


def read_stem(name: str) -> np.ndarray:
    """The mixed voice stem (mono, 48 kHz): captions are timed against the voice exactly as it is heard."""
    import wave
    with wave.open(str(WORK / f"mix/{name}_voice.wav")) as wv:
        x = np.frombuffer(wv.readframes(wv.getnframes()), "<i2").reshape(-1, wv.getnchannels()).T
    return x.astype(np.float32).mean(0) / 32768


def write_captions(film: Film):
    from captions import CUES, align, vtt
    import clone
    stem = read_stem("demo")
    allc = []
    for sec in film.secs:
        key = sec["key"]
        if key == "MOB":
            if not (WORK / "clone/mob.npy").exists():
                print("captions: no cloned lines yet, MOB left out")
                continue
            texts = [l[0] for l in clone.LINES]
            texts = [texts[0], "Our Android app speaks Bangla:", "Rahim asks out loud and hears the answer back.",
                     texts[2], "Buyers bid from their phones, drivers share their live location,",
                     "and everyone follows the sale in real time."]
        else:
            texts = CUES[key]
        a = stem[int(sec["voice_at"] * 48000):int((sec["voice_at"] + sec["voice_dur"]) * 48000)]
        for s, e, text in align(sec["words"], a, 48000, texts):
            allc.append((sec["voice_at"] + s, sec["voice_at"] + e, text))
    (OUT_WEB / "krishinexus-demo.en.vtt").write_text(vtt(allc), encoding="utf-8")
    (WORK / "demo_cues.json").write_text(json.dumps(allc, indent=1), encoding="utf-8")
    print(len(allc), "caption cues")


def poster(film: Film):
    img = film.frame(2.4).resize((1280, 720), Image.LANCZOS)
    for q in (86, 80, 74, 68):
        path = OUT_WEB / "krishinexus-demo.jpg"
        img.save(path, quality=q, optimize=True, progressive=True)
        if path.stat().st_size < 150_000:
            break
    print("poster", path.stat().st_size, "bytes")


if __name__ == "__main__":
    film = Film()
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        st = {s["key"]: s["start"] for s in film.secs}
        ts = [st[x.split("+")[0]] + float(x.split("+")[1]) if "+" in x else float(x) for x in sys.argv[2:]]
        sheet = Image.new("RGB", (640 * 3, 360 * ((len(ts) + 2) // 3)), "white")
        for i, T in enumerate(ts):
            sheet.paste(film.frame(T).resize((640, 360), Image.LANCZOS), (640 * (i % 3), 360 * (i // 3)))
        sheet.save(WORK / "preview.jpg", quality=88)
        print(WORK / "preview.jpg", "total", film.total)
    else:
        print("total", film.total, "s,", film.n, "frames")
        OUT_WEB.mkdir(parents=True, exist_ok=True)
        write_captions(film)
        poster(film)
        encode(film, "demo", [(OUT_MASTER / "krishinexus-demo-1080p.mp4", (1920, 1080), 18, 192000),
                              (OUT_WEB / "krishinexus-demo.mp4", (1280, 720), 24, 128000)], WORK / "mix/demo_mix.wav")
