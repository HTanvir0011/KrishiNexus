"""Where everything sits in the demo: the 11 narration segments (edited by narration.py), the mobile-app section with
the cloned lines (clone.py), the end card. Shared by mix.py (sound) and build.py (picture).

All times in seconds. Each section has: key, start (its first word, or its picture for the mobile section), end,
voice_at (where its voice file starts), words [[word, start, end], ...] relative to voice_at.
"""
from __future__ import annotations

import json
from pathlib import Path

WORK = Path("C:/ai-congress/KrishiNexus/video/work")
ORDER = ["S00", "S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "MOB", "S10"]
PRE = 0.30       # music and the title before the first word
GAP = 0.15       # added between segments (each voice file keeps 0.05 s of room at either end)
MOB_LEAD = 1.60  # the phone rises and shows the app opening (in Bangla) before the cloned voice starts
MOB_HOLD = 3.60  # the "Get the Android app" card holds after the last word
TAIL = 1.60      # the end card rings on after "tanvir.health"
INTRO_HOLD = 0.40  # the six-portrait grid holds after the last spoken word of the intro


def load(voice_dir: str = "voice") -> dict:
    v = json.loads((WORK / voice_dir / "timing.json").read_text(encoding="utf-8"))
    cpath = WORK / "clone/timing.json"
    if cpath.exists():
        clone = json.loads(cpath.read_text(encoding="utf-8"))
    else:  # before the cloned lines exist: words spread evenly over an estimated length (layout tests only)
        from clone import LINES
        toks = " ".join(l[0] for l in LINES).split()
        step = 21.5 / len(toks)
        clone = {"dur": 21.5, "placeholder": True,
                 "words": [[w, round(i * step, 3), round((i + 0.8) * step, 3)] for i, w in enumerate(toks)]}
    t = PRE
    sections = []
    for key in ORDER:
        if key == "MOB":
            dur = MOB_LEAD + clone["dur"] + MOB_HOLD
            sec = {"key": key, "start": t, "end": t + dur, "voice_at": t + MOB_LEAD, "voice_dur": clone["dur"],
                   "words": clone["words"]}
        else:
            seg = v["segments"][key]
            dur = seg["dur"] + {"S10": TAIL, "S00": INTRO_HOLD}.get(key, 0.0)
            sec = {"key": key, "start": t, "end": t + dur, "voice_at": t, "voice_dur": seg["dur"],
                   "words": seg["words"]}
        sections.append(sec)
        t = sec["end"] + GAP
    return {"sections": sections, "total": round(sections[-1]["end"], 3), "tempo": v["tempo"],
            "clone_placeholder": bool(clone.get("placeholder"))}


def word_time(sec: dict, text, after: float = 0.0, end: bool = False) -> float:
    """Section-relative time of the first recognised word starting with `text` (case-insensitive) after `after`;
    `text` may be a tuple of spellings (the recogniser hears "Rahim" as "Raheem" too)."""
    off = sec["voice_at"] - sec["start"]
    keys = [k.lower() for k in ((text,) if isinstance(text, str) else text)]
    for w, s, e in sec["words"]:
        ww = w.strip().lower().lstrip("-")
        if s + off >= after - 1e-6 and any(ww.startswith(k) for k in keys):
            return (e if end else s) + off
    raise KeyError(f"{sec['key']}: no word {text} after {after}")


if __name__ == "__main__":
    tl = load()
    for s in tl["sections"]:
        print(f"{s['key']:4s} {s['start']:7.2f} -> {s['end']:7.2f}  ({s['end'] - s['start']:5.2f} s)")
    print("total", tl["total"], "s", "(clone placeholder)" if tl["clone_placeholder"] else "")
