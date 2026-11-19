"""Contact sheet of recorded shots: one row per shot, a frame at each mark (or at even times without marks).
Usage: python sheet.py <out.jpg> S01a S01b ...
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

FR = Path("C:/ai-congress/KrishiNexus/video/work/frames")
out, shots = sys.argv[1], sys.argv[2:]
N, W, H = 5, 384, 216
sheet = Image.new("RGB", (W * N, (H + 18) * len(shots)), "white")
d = ImageDraw.Draw(sheet)
for r, shot in enumerate(shots):
    data = json.loads((FR / shot / "frames.json").read_text())
    fr, end = data["frames"], data["end"]
    mp = FR / shot / "marks.json"
    marks = json.loads(mp.read_text())["marks"] if mp.exists() else []
    times = [(m[0], m[1] + 0.6) for m in marks][: N - 1] + [("end", end - 0.4)]
    if len(times) < N:
        times = [(f"{end * (i + 0.5) / N:.1f}s", end * (i + 0.5) / N) for i in range(N)] if not marks else times
    for i, (name, t) in enumerate(times[:N]):
        f = [x for x in fr if x[1] <= t]
        f = (f[-1] if f else fr[0])[0]
        im = Image.open(FR / shot / f)
        im.thumbnail((W, H))
        sheet.paste(im, (W * i, (H + 18) * r + 18))
        d.text((W * i + 4, (H + 18) * r + 3), f"{shot} {name} {t:.1f}", fill="black")
sheet.save(out, quality=85)
print(out)
