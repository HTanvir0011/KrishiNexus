"""Scripted recorder for the KrishiNexus demo video: drives https://tanvir.health and saves each segment as JPEG frames
with timestamps (Chrome's screencast), so the assembly step can hold every frame for exactly as long as it was shown.

Usage:  python -I rec.py S01 S02 ...   (no arguments: all segments)
Output: frames/<segment>/<n>.jpg and frames/<segment>/frames.json  [[file, seconds since segment start], ...]
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = "https://tanvir.health"
HERE = Path(__file__).resolve().parent
FRAMES = HERE / "frames"
VIEW = {"width": 1920, "height": 1080}
ZOOM = 1.35  # CSS zoom on <body>: the UI reads larger and the frames stay sharp at 1920x1080

# A visible cursor (headless Chrome draws none) with a ring that pulses on each click.
CURSOR_JS = """
(() => {
  const add = () => {
    if (document.getElementById('knx-cursor')) return;
    const c = document.createElement('div');
    c.id = 'knx-cursor';
    c.style.cssText = 'position:fixed;left:-50px;top:-50px;width:22px;height:22px;z-index:2147483647;pointer-events:none;' +
      'transition:transform .12s ease;';
    c.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M4 2l16 9-7 2-3 7z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    const r = document.createElement('div');
    r.id = 'knx-ring';
    r.style.cssText = 'position:fixed;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;border:3px solid #0f766e;' +
      'opacity:0;z-index:2147483646;pointer-events:none;transition:opacity .35s, transform .35s;transform:scale(.4)';
    document.documentElement.append(c, r);
    addEventListener('mousemove', e => { c.style.left = e.clientX - 3 + 'px'; c.style.top = e.clientY - 2 + 'px'; }, true);
    addEventListener('mousedown', e => {
      r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
      r.style.transition = 'none'; r.style.opacity = '1'; r.style.transform = 'scale(.4)';
      requestAnimationFrame(() => { r.style.transition = 'opacity .45s, transform .45s'; r.style.opacity = '0'; r.style.transform = 'scale(1.6)'; });
    }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', add); else add();
})();
"""


def token(user_id: str) -> str:
    req = urllib.request.Request(f"{BASE}/auth/login", data=json.dumps({"user_id": user_id}).encode(),
                                 headers={"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))["token"]


class Shot:
    """One recorded clip: a browser context (optionally logged in) whose screencast frames go to frames/<name>/."""

    def __init__(self, browser, name: str, user: str | None = None, zoom: float = ZOOM):
        self.dir = FRAMES / name
        shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True)
        self.ctx = browser.new_context(viewport=VIEW, device_scale_factor=1, locale="en-US")
        self.ctx.add_init_script(f"addEventListener('DOMContentLoaded', () => {{ document.body.style.zoom = '{zoom}'; }});")
        self.ctx.add_init_script("try{localStorage.setItem('knx.lang','en')}catch(e){}")
        if user:
            self.ctx.add_init_script(f"localStorage.setItem('knx.session', {json.dumps(token(user))});")
        self.ctx.add_init_script(CURSOR_JS)
        self.page: Page = self.ctx.new_page()
        self.frames: list[list] = []
        self.t0: float | None = None
        self.cdp = None
        self.mouse = (960, 540)

    # -- capture -----------------------------------------------------------
    def start(self):
        self.cdp = self.ctx.new_cdp_session(self.page)
        self.cdp.on("Page.screencastFrame", self._frame)
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": 1920, "maxHeight": 1080,
                                               "everyNthFrame": 1})
        self.t0 = time.monotonic()
        self.page.mouse.move(*self.mouse)

    def _frame(self, event):
        import base64
        n = len(self.frames)
        name = f"{n:05d}.jpg"
        (self.dir / name).write_bytes(base64.b64decode(event["data"]))
        self.frames.append([name, round(time.monotonic() - self.t0, 3)])
        try:
            self.cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})
        except Exception:
            pass

    def stop(self):
        self.hold(300)
        end = round(time.monotonic() - self.t0, 3)
        try:
            self.cdp.send("Page.stopScreencast")
        except Exception:
            pass
        (self.dir / "frames.json").write_text(json.dumps({"frames": self.frames, "end": end}), encoding="utf-8")
        self.ctx.close()
        print(f"{self.dir.name}: {len(self.frames)} frames, {end:.1f} s")

    # -- actions -----------------------------------------------------------
    def goto(self, path: str, wait: str = "networkidle"):
        self.page.goto(BASE + path, wait_until=wait, timeout=120_000)
        self.page.wait_for_timeout(800)

    def hold(self, ms: int):
        self.page.wait_for_timeout(ms)

    def move_to(self, locator, steps: int = 25):
        locator.wait_for(state="visible", timeout=60_000)
        box = locator.bounding_box()
        if box["y"] < 130 or box["y"] + box["height"] > VIEW["height"] - 60:  # off screen or under the sticky header
            locator.evaluate("e => e.scrollIntoView({behavior: 'smooth', block: 'center'})")
            self.hold(900)
            box = locator.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.page.mouse.move(x, y, steps=steps)
        self.mouse = (x, y)

    def click(self, locator, pause: int = 350):
        self.move_to(locator)
        self.hold(pause)
        locator.click(timeout=30_000)  # checks the target is really under the pointer (not a sticky header)

    def type(self, locator, text: str, delay: int = 70):
        self.click(locator)
        self.page.keyboard.type(text, delay=delay)

    def scroll_to(self, locator, block: str = "start", ms: int = 1400):
        locator.evaluate(f"e => e.scrollIntoView({{behavior: 'smooth', block: '{block}'}})")
        self.hold(ms)

    def scroll_by(self, dy: int, ms: int = 1200):
        self.page.evaluate(f"window.scrollBy({{top: {dy}, behavior: 'smooth'}})")
        self.hold(ms)


# -- segments ----------------------------------------------------------------

def s01(b):  # The problem: the landing page and its three leaks.
    s = Shot(b, "S01")
    s.goto("/")
    s.start()
    s.hold(4000)
    s.scroll_to(s.page.get_by_role("heading", name="Where the money and the harvest leak"), ms=2500)
    s.hold(4500)
    s.scroll_by(520, ms=2000)
    s.hold(4000)
    s.stop()


def s02(b):  # One OS, a workspace per role: the login page.
    s = Shot(b, "S02")
    s.goto("/login")
    s.start()
    s.hold(3000)
    s.scroll_to(s.page.get_by_role("heading", name="Quick login"), ms=2200)
    for label in ("Farmer", "Himagar (cold storage)", "Buyer / trader", "Truck driver", "Bank"):
        s.move_to(s.page.get_by_role("heading", name=label, exact=True), steps=18)
        s.hold(1300)
    s.hold(1500)
    s.stop()


def s03(b):  # The farmer asks in his dialect; consent; the agents' decision with the circuit breaker.
    s = Shot(b, "S03", zoom=1.9)
    s.goto("/login")
    s.scroll_to(s.page.get_by_role("heading", name="Quick login"), ms=600)
    s.start()
    s.hold(800)
    s.click(s.page.get_by_role("button", name="Rahim Mia FARM-RAN-001"))
    s.page.wait_for_url("**/os/field", timeout=60_000)
    s.page.wait_for_load_state("networkidle")
    s.hold(1200)
    box = s.page.get_by_placeholder("or type your question", exact=False)
    s.scroll_to(box, block="center", ms=1000)
    s.type(box, "মোর ৪০০ কেজি কার্ডিনাল আলু আছে, এলা বেচমু না হিমাগারত থুমু?", delay=55)
    s.hold(500)
    s.click(s.page.get_by_role("button", name="পাঠান"))
    s.hold(1200)
    s.click(s.page.get_by_role("button", name="I agree"))
    decision = s.page.get_by_text("Your decision", exact=False).first
    decision.wait_for(timeout=120_000)
    s.hold(800)
    s.scroll_to(decision, block="start", ms=2000)
    s.hold(3500)
    s.scroll_by(450, ms=1800)
    s.hold(3000)
    s.stop()


def s04(b):  # Grading a sample lot: the vision model and a signed certificate.
    s = Shot(b, "S04", user="FARM-RAN-001", zoom=1.9)
    s.goto("/os/field")
    scan = s.page.get_by_role("button", name="Scan sample lot")
    s.scroll_to(scan, block="center", ms=600)
    s.start()
    s.hold(900)
    s.click(scan)
    cert = s.page.get_by_text("Digital quality certificate", exact=False).first
    cert.wait_for(timeout=120_000)
    s.hold(1200)
    s.scroll_to(cert, block="center", ms=1800)
    s.hold(3500)
    s.stop()


def s05(b):  # The agents at work, the MCP tools, offline mode.
    s = Shot(b, "S05a")
    s.goto("/")
    s.start()
    s.hold(700)
    s.click(s.page.get_by_role("button", name="Run live multi-agent orchestration"))
    s.hold(2500)
    s.scroll_to(s.page.get_by_role("heading", name="One question, nine LangGraph nodes"), ms=2200)
    s.hold(3500)
    s.stop()
    s = Shot(b, "S05b")
    s.goto("/docs")
    s.scroll_to(s.page.get_by_role("heading", name="Interactive 13-tool MCP protocol inspector"), ms=500)
    s.start()
    s.hold(700)
    s.click(s.page.get_by_role("button", name="get_chamber_telemetry"))
    s.hold(500)
    s.click(s.page.get_by_role("button", name="Execute tool"))
    s.hold(1500)
    s.scroll_by(380, ms=1500)
    s.hold(2500)
    s.click(s.page.get_by_text("Offline edge", exact=True).first)
    s.hold(2500)
    s.stop()


def s06(b):  # Co-op truck pools; the cold store's 3D twin and a flood alert.
    s = Shot(b, "S06a", user="COOP-BOG-01")
    s.goto("/os/coop")
    s.start()
    s.hold(2500)
    s.scroll_to(s.page.get_by_role("heading", name="5-ton union truck pool", exact=False), ms=1800)
    s.hold(2500)
    s.stop()
    s = Shot(b, "S06b", user="HIMAGAR-BOG-05")
    s.goto("/os/himagar")
    s.start()
    s.hold(2000)
    s.click(s.page.get_by_role("button", name="Simulate haor flood"))
    s.hold(4500)
    s.stop()
    # Clear the injected flood again so other visitors see a calm site (not filmed).
    t = token("HIMAGAR-BOG-05")
    urllib.request.urlopen(urllib.request.Request(f"{BASE}/mcp/anomalies", method="DELETE",
                                                  headers={"Authorization": f"Bearer {t}"}), timeout=60)


def card(page, lot_id):
    return page.locator("article").filter(has_text=lot_id).first


def s07(b):  # Direct market: a trader raises a bid, the farmer accepts, the driver delivers, the payment is released.
    s = Shot(b, "S07a", user="BUY-BOG-02")
    s.goto("/os/trade")
    lot = card(s.page, "LOT-SEED01")
    s.scroll_to(lot, block="center", ms=500)
    s.start()
    s.hold(800)
    price = lot.locator("input[type=number]").first
    s.click(price)
    s.page.keyboard.press("Control+A")
    s.page.keyboard.type("18.75", delay=120)
    s.hold(300)
    s.click(lot.get_by_role("button", name="Raise bid"))
    s.hold(2200)
    s.stop()
    s = Shot(b, "S07b", user="FARM-RAN-001")
    s.goto("/os/trade")
    lot = card(s.page, "LOT-SEED01")
    s.scroll_to(lot, block="start", ms=500)
    s.start()
    s.hold(900)
    s.click(lot.get_by_role("button", name="Accept").first)
    s.hold(2200)
    s.scroll_to(card(s.page, "LOT-SEED06"), block="center", ms=1600)
    s.hold(2200)
    s.stop()
    s = Shot(b, "S07c", user="DRIVER-BOG-01")
    s.goto("/os/driver")
    job = card(s.page, "Green Chili")
    s.start()
    s.hold(900)
    s.click(job.get_by_role("button", name="Take this job"))
    s.hold(1800)
    job = s.page.locator("article").filter(has_text="Green Chili").first
    s.click(job.get_by_role("button", name="Loaded: start the trip"))
    s.hold(1600)
    job = s.page.locator("article").filter(has_text="Green Chili").first
    temp = job.locator("input[type=number]").first
    s.click(temp)
    s.page.keyboard.press("Control+A")
    s.page.keyboard.type("34", delay=150)
    s.click(job.get_by_role("button", name="Report"))
    s.hold(2200)
    s.click(job.get_by_role("button", name="Delivered: release payment"))
    s.hold(2600)
    s.stop()


def s08(b):  # The bank: credit underwriting.
    s = Shot(b, "S08", user="BANK-UCB-01")
    s.goto("/os/market")
    s.scroll_to(s.page.get_by_role("heading", name="Agri-credit underwriting"), block="center", ms=500)
    s.start()
    s.hold(900)
    s.click(s.page.get_by_role("button", name="Underwrite FARM-BOG-104"))
    s.page.wait_for_load_state("networkidle", timeout=120_000)
    s.hold(4500)
    s.stop()


def s09(b):  # Honest evaluation, and data safety.
    s = Shot(b, "S09")
    s.goto("/docs")
    s.scroll_to(s.page.get_by_role("heading", name="Measured RAGAS-style metrics"), ms=500)
    s.start()
    s.hold(1500)
    s.click(s.page.get_by_role("button", name="Run live regression suite"))
    s.hold(4000)
    s.scroll_to(s.page.get_by_role("heading", name="What the node keeps about a farmer"), ms=2200)
    s.hold(4000)
    s.scroll_to(s.page.get_by_role("heading", name="Safeguards built in"), ms=1800)
    s.hold(3000)
    s.stop()


def s10(b):  # Unit economics and the pilot plan.
    s = Shot(b, "S10")
    s.goto("/docs")
    s.scroll_to(s.page.get_by_role("heading", name="One pooled truck, and when a district breaks even"), ms=500)
    s.start()
    s.hold(4500)
    s.scroll_to(s.page.get_by_role("heading", name="Pilot plan (proposed, not started)"), ms=2000)
    s.hold(5000)
    s.stop()


SEGMENTS = {"S01": s01, "S02": s02, "S03": s03, "S04": s04, "S05": s05, "S06": s06, "S07": s07, "S08": s08,
            "S09": s09, "S10": s10}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(SEGMENTS)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for key in wanted:
            try:
                SEGMENTS[key](browser)
            except Exception as exc:  # one broken shot shouldn't cost the others
                print(f"{key} FAILED: {str(exc).splitlines()[0]}")
        browser.close()
