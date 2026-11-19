import json, sys
from PIL import Image, ImageDraw
segs = sys.argv[2:]; out = sys.argv[1]; n = 4; W, H = 600, 338
sheet = Image.new("RGB", (W * n, H * len(segs)), "white")
for r, seg in enumerate(segs):
    d = json.load(open(f"frames/{seg}/frames.json")); fr = d["frames"]; end = d["end"]
    for i in range(n):
        t = end * (i + 0.6) / n
        f = [x for x in fr if x[1] <= t][-1][0]
        sheet.paste(Image.open(f"frames/{seg}/{f}").resize((W, H)), (W * i, H * r))
    ImageDraw.Draw(sheet).text((6, H * r + 4), seg, fill="red")
sheet.save(out, quality=85)
