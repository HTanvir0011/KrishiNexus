"""Records the Android app's screens from its Flutter web build (mobile/build/web, served on 127.0.0.1:8790) in a
412x915 phone viewport at 2x, as CDP screencast frames with times and named marks (like rec_site.py).

The build talks to http://localhost:8020 (its API_BASE). Those calls are answered from https://tanvir.health through
Playwright routing (with CORS headers), so the app shows the same live data as the website and no local backend is
touched. CanvasKit is served from the build's own copy. Nothing is rebuilt. A touch ring marks every tap.

Usage: python -I rec_app.py M0 M1 ...   (system python with Playwright; serve the build first:
       python -m http.server 8790 --bind 127.0.0.1 --directory mobile/build/web)
"""
from __future__ import annotations

import base64
import json
import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = "http://127.0.0.1:8790/"
LIVE = "https://tanvir.health"
CK = Path("C:/ai-congress/KrishiNexus/mobile/build/web/canvaskit")
FRAMES = Path("C:/ai-congress/KrishiNexus/video/work/frames")
VW, VH, DSF = 412, 915, 2

TOUCH_JS = """
(() => {
  const add = () => {
    if (document.getElementById('knx-touch')) return;
    const r = document.createElement('div');
    r.id = 'knx-touch';
    r.style.cssText = 'position:fixed;left:-99px;top:-99px;width:54px;height:54px;margin:-27px 0 0 -27px;border-radius:50%;' +
      'background:rgba(4,120,87,.20);border:2px solid rgba(4,120,87,.55);opacity:0;z-index:2147483647;pointer-events:none;transform:scale(.5)';
    document.documentElement.append(r);
    addEventListener('pointerdown', e => {
      r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
      r.style.transition = 'none'; r.style.opacity = '1'; r.style.transform = 'scale(.55)';
      requestAnimationFrame(() => requestAnimationFrame(() => {
        r.style.transition = 'opacity .55s ease-out, transform .55s ease-out'; r.style.opacity = '0'; r.style.transform = 'scale(1.35)'; }));
    }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', add); else add();
})();
"""


def proxy(route):
    req = route.request
    url = req.url.replace("http://localhost:8020", LIVE)
    cors = {"access-control-allow-origin": req.headers.get("origin", "*"),
            "access-control-allow-headers": "authorization,content-type",
            "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS"}
    if req.method == "OPTIONS":
        return route.fulfill(status=204, headers=cors)
    try:
        r = route.fetch(url=url, timeout=180_000)
        h = {k: v for k, v in r.headers.items() if k.lower() not in
             ("content-security-policy", "x-frame-options", "content-encoding", "content-length", "transfer-encoding")}
        h.update(cors)
        route.fulfill(status=r.status, headers=h, body=r.body())
    except Exception:
        route.abort()


def canvaskit(route):
    name = route.request.url.rsplit("/", 1)[-1]  # the chromium variant -> the build's full CanvasKit (same engine)
    path = CK / name
    if path.exists():
        return route.fulfill(path=str(path), headers={"content-type": "application/wasm" if name.endswith(".wasm")
                                                      else "text/javascript", "access-control-allow-origin": "*"})
    route.continue_()


class App:
    def __init__(self, browser, name: str):
        self.dir = FRAMES / name
        shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True)
        self.ctx = browser.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=DSF, locale="en-US")
        self.ctx.route("http://localhost:8020/**", proxy)
        self.ctx.route("https://www.gstatic.com/flutter-canvaskit/**", canvaskit)
        self.ctx.add_init_script(TOUCH_JS)
        self.page = self.ctx.new_page()
        self.frames, self.marks, self.t0, self.cdp = [], [], None, None
        self.page.goto(APP, wait_until="load", timeout=180_000)
        self.page.wait_for_function("document.querySelector('flt-semantics-placeholder') !== null", timeout=180_000)
        self.page.wait_for_timeout(2500)
        self.page.evaluate("document.querySelector('flt-semantics-placeholder')?.click()")
        self.page.wait_for_timeout(800)

    # -- semantics ----------------------------------------------------------
    def nodes(self):
        return self.page.evaluate(r"""[...document.querySelectorAll('flt-semantics')].map(e => {
            const r = e.getBoundingClientRect(); const l = (e.getAttribute('aria-label') || e.innerText || '').trim().replace(/\s+/g, ' ');
            return [e.getAttribute('role') || '', l, r.x, r.y, r.width, r.height]; }).filter(x => x[1] && x[4] > 0 && !(x[4] >= 412 && x[5] >= 915))""")

    def find(self, label: str, timeout: int = 60_000, exact_first: bool = True):
        t = 0
        while True:
            items = [n for n in self.nodes() if label in n[1]]
            exact = [n for n in items if n[1] == label]
            btn = [n for n in items if n[0] in ("button", "tab", "checkbox", "link", "radio", "switch", "slider")]
            pick = (exact if exact_first else []) or btn or items
            vis = [n for n in pick if 0 <= n[3] + n[5] / 2 <= VH]
            if vis:
                return vis[0]
            if t >= timeout:
                raise TimeoutError(f"{self.dir.name}: '{label}' not on screen")
            self.page.wait_for_timeout(400)
            t += 400

    def tap(self, label: str, pause: int = 250, **k):
        r, l, x, y, w, h = self.find(label, **k)
        self.page.wait_for_timeout(pause)
        self.page.mouse.click(x + w / 2, y + h / 2)
        return (x, y, w, h)

    def wait_for(self, label: str, timeout: int = 120_000):
        self.find(label, timeout=timeout, exact_first=False)

    def scroll(self, dy: int, steps: int = 14, x: float = 206, y: float = 520):
        self.page.mouse.move(x, y)
        for _ in range(steps):
            self.page.mouse.wheel(0, dy / steps)
            self.page.wait_for_timeout(28)

    # -- capture ------------------------------------------------------------
    def start(self):
        self.cdp = self.ctx.new_cdp_session(self.page)
        self.cdp.on("Page.screencastFrame", self._frame)
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": VW * DSF,
                                               "maxHeight": VH * DSF, "everyNthFrame": 1})
        self.t0 = time.monotonic()
        self.page.wait_for_timeout(120)
        # Flutter paints only on change: nudge one repaint so the first frame exists
        self.page.mouse.move(VW - 2, 4)

    def _frame(self, event):
        name = f"{len(self.frames):05d}.jpg"
        (self.dir / name).write_bytes(base64.b64decode(event["data"]))
        self.frames.append([name, round(time.monotonic() - self.t0, 3)])
        try:
            self.cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})
        except Exception:
            pass

    def mark(self, name: str):
        self.marks.append([name, round(time.monotonic() - self.t0, 3)])

    def hold(self, ms: int):
        self.page.wait_for_timeout(ms)

    def stop(self):
        self.hold(300)
        end = round(time.monotonic() - self.t0, 3)
        try:
            self.cdp.send("Page.stopScreencast")
        except Exception:
            pass
        (self.dir / "frames.json").write_text(json.dumps({"frames": self.frames, "end": end}), encoding="utf-8")
        (self.dir / "marks.json").write_text(json.dumps({"marks": self.marks, "boxes": {}}), encoding="utf-8")
        self.ctx.close()
        print(f"{self.dir.name}: {len(self.frames)} frames, {end:.1f} s, marks {self.marks}")


def m0(b):  # The app as it opens, in Bangla; Rahim picks himself; the Ask tab with the microphone.
    a = App(b, "M0")
    a.find("Rahim Mia")
    a.start()
    a.mark("home")
    a.hold(1500)
    a.tap("Rahim Mia")
    a.mark("rahim")
    a.wait_for("বাংলায় প্রশ্ন বলুন")
    a.mark("mic")
    a.hold(2200)
    a.stop()


def m1(b):  # English UI: a recorded Rangpuri question goes in, the decision cards come back.
    a = App(b, "M1")
    a.tap("EN")
    a.hold(600)
    a.tap("Rahim Mia")
    a.wait_for("Try a recorded question")
    a.hold(800)
    a.start()
    a.hold(700)
    a.tap("Rahim Mia · Rangpur potato", exact_first=False)
    a.mark("ask")
    a.wait_for("Your decision")
    a.mark("answer")
    a.hold(2600)
    a.scroll(260)
    a.mark("cards")
    a.hold(2000)
    a.stop()


def m2(b):  # Scan: a sample lot is graded; pieces outlined, the grade stamped, the signed certificate.
    a = App(b, "M2")
    a.tap("EN")
    a.hold(600)
    a.tap("Rahim Mia")
    a.wait_for("Try a recorded question")
    a.tap("Scan")
    a.wait_for("Sample lot")
    a.hold(600)
    a.start()
    a.hold(600)
    a.tap("Sample lot")
    a.mark("sheet")
    a.hold(700)
    a.tap("Mixed wholesale lot")
    a.mark("grading")
    a.wait_for("GRADE")
    a.mark("graded")
    a.hold(2800)
    a.scroll(640, steps=18)
    a.mark("cert")
    a.hold(2200)
    a.stop()


def m3(b):  # A buyer's market on the phone: open lots, the bids on a lot, a quick raise.
    a = App(b, "M3")
    a.tap("EN")
    a.hold(600)
    a.tap("Bogura Agro Traders")
    a.wait_for("Open lots")
    a.hold(800)
    a.start()
    a.mark("lots")
    a.hold(1300)
    a.tap("A GRADE Cardinal potato", exact_first=False)
    a.mark("lot")
    a.wait_for("Bids")
    a.hold(1300)
    a.tap("+0.50")
    a.mark("raise")
    a.hold(1800)
    a.stop()


def m4(b):  # A driver's job: the route line and status, and the "Share live location" switch turned on.
    a = App(b, "M4")
    a.ctx.grant_permissions(["geolocation"], origin=APP.rstrip("/"))
    a.ctx.set_geolocation({"latitude": 25.7439, "longitude": 89.2752})  # Rangpur, where this demo job starts
    a.tap("EN")
    a.hold(600)
    a.tap("Jalal Uddin")
    a.wait_for("My jobs on the road")
    a.hold(800)
    a.start()
    a.mark("jobs")
    a.hold(1000)
    job = next(n for n in a.nodes() if n[0] == "button" and " kg " in n[1] and "Delivered" not in n[1])
    a.page.mouse.click(job[2] + job[4] / 2, job[3] + job[5] / 2)
    a.mark("route")
    a.wait_for("Share live location")
    a.hold(1500)
    a.tap("Share live location", exact_first=False)
    a.mark("share")
    a.hold(2600)
    a.stop()


SHOTS = {"M0": m0, "M1": m1, "M2": m2, "M3": m3, "M4": m4}

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--enable-unsafe-swiftshader", "--use-angle=swiftshader",
                                          "--enable-webgl", "--ignore-gpu-blocklist"])
        for key in sys.argv[1:] or list(SHOTS):
            try:
                SHOTS[key](browser)
            except Exception as exc:
                print(f"{key} FAILED: {str(exc).splitlines()[0]}")
        browser.close()
