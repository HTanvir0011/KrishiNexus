"""Self-check for photo grading's plausibility rule (edge_node.optical_grader.not_a_lot) through POST /edge/grade-crop:
spread-out lots (even, mixed sizes, elongated chilies, a crate with bruised and rotten pieces) are graded on the
classical-CV path, and a cluttered scene of irregular, very different blobs is refused with 422.
Run: cd backend && .venv/Scripts/python check_grader.py"""

import base64
import io
import random

from PIL import Image, ImageDraw, ImageFilter
from starlette.testclient import TestClient

from edge_node import optical_grader
from main import app


def photo(kind: str, seed: int = 7) -> str:
    rnd = random.Random(seed)
    img = Image.new("RGB", (1600, 1200), (215, 205, 185) if kind == "chili" else (185, 160, 120))
    d = ImageDraw.Draw(img)
    if kind == "clutter":
        # A room-like scene: wall bands, a large dark screen, shelves, odd polygons of very different sizes.
        for y in range(0, 1200, 300):
            d.rectangle((0, y, 1600, y + 140), fill=(150, 125, 95))
        d.rectangle((700, 150, 1450, 640), fill=(25, 25, 30))
        for _ in range(9):
            x, y, s = rnd.randint(60, 1400), rnd.randint(60, 1000), rnd.choice([40, 80, 200, 320])
            d.polygon([(x, y), (x + s, y + s // 5), (x + s // 6, y + s), (x + s // 2, y + s // 3)], fill=(90, 70, 50))
        return _encode(img)
    for r in range(3):
        for c in range(5):
            cx, cy = 190 + c * 300 + rnd.randint(-25, 25), 220 + r * 370 + rnd.randint(-25, 25)
            if kind == "chili":
                d.rounded_rectangle((cx - 120, cy - 22, cx + 120, cy + 22), radius=22, fill=(60, 140, 50))
                continue
            w = rnd.choice([110, 130, 200, 230]) if kind == "mixed" else rnd.randint(175, 200)
            h = int(w * rnd.uniform(0.72, 0.86))
            d.ellipse((cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2), fill=(196, 122, 92))
            if kind == "crate" and (r, c) in ((0, 3), (1, 3)):
                d.ellipse((cx - 28, cy - 18, cx + 24, cy + 20), fill=(110, 64, 44))   # bruises
            if kind == "crate" and (r, c) == (2, 1):
                for dx, dy in ((-25, -10), (20, 15), (0, 30)):
                    d.ellipse((cx + dx - 18, cy + dy - 14, cx + dx + 18, cy + dy + 14), fill=(52, 48, 36))   # rot
    return _encode(img.filter(ImageFilter.GaussianBlur(1.2)))


def _encode(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


optical_grader.yolo_detect = lambda *a, **k: None   # always the classical-CV path, as on the hosted node
with TestClient(app) as client:
    def grade(kind: str, crop: str = "Brinjal"):
        return client.post("/edge/grade-crop", json={"crop": crop, "image_base64": photo(kind)})

    for kind, crop in (("even", "Brinjal"), ("mixed", "Brinjal"), ("chili", "Green Chili"), ("crate", "Brinjal")):
        res = grade(kind, crop)
        assert res.status_code == 200, (kind, res.status_code, res.text[:200])
        assert len(res.json()["bounding_boxes"]) >= 12, (kind, len(res.json()["bounding_boxes"]))
    crate = grade("crate").json()
    labels = [b["class_label"] for b in crate["bounding_boxes"]]
    assert labels.count("uniform_A") >= 10 and "fungal_blight" in labels, labels
    refused = grade("clutter")
    assert refused.status_code == 422 and "No produce detected" in refused.text, (refused.status_code, refused.text[:200])
print("grader: all checks passed")
