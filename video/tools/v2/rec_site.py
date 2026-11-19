"""Records the website shots for the v2 demo from https://tanvir.health, with ../rec.py's Shot (CDP screencast frames
plus their times) and named marks at the moments the narration points at, so build.py can line them up with the voice.

Usage:  python -I rec_site.py S01 S03 ...   (system python with Playwright; no arguments: all)
Output: video/work/frames/<shot>/<n>.jpg, frames.json (from Shot) and marks.json {"marks": [[name, s]], "boxes": {...}}
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rec  # noqa: E402  (../rec.py: Shot, token, card)

rec.FRAMES = Path("C:/ai-congress/KrishiNexus/video/work/frames")
BASE = rec.BASE
CHILI_Q = "মোর ৪০০ কেজি কার্ডিনাল আলু আছে, এলা বেচমু না হিমাগারত থুমু?"


class Shot(rec.Shot):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.marks: list = []
        self.boxes: dict = {}

    def start(self):
        self.t0 = time.monotonic()  # a frame can arrive while startScreencast is still being sent
        super().start()

    def mark(self, name: str):
        self.marks.append([name, round(time.monotonic() - self.t0, 3)])

    def box(self, name: str, locator):
        b = locator.bounding_box()
        if b:
            self.boxes[name] = [round(b["x"]), round(b["y"]), round(b["width"]), round(b["height"]),
                                round(time.monotonic() - self.t0, 3)]

    def online(self):
        """Wait until the header shows the live backend (the free plan sleeps; a cold page shows a cached demo)."""
        try:
            self.page.get_by_text("MCP servers online", exact=False).first.wait_for(timeout=90_000)
        except Exception:
            print(f"{self.dir.name}: backend status not online")

    def stop(self):
        super().stop()
        (self.dir / "marks.json").write_text(json.dumps({"marks": self.marks, "boxes": self.boxes}), encoding="utf-8")


def wake():
    for _ in range(20):
        try:
            h = json.load(urllib.request.urlopen(f"{BASE}/health", timeout=60))
            if h.get("mcp_servers") == 3:
                return
        except Exception:
            pass
        time.sleep(3)


def heading(page, name):
    return page.get_by_role("heading", name=name).first


# -- segments (timing comments: the narration word each mark is lined up with) -----------------------------------

def s01(b):  # The problem: the headline and the five-tier syndicate, then the whitepaper's sourced figures.
    s = Shot(b, "S01a")
    s.goto("/")
    s.online()
    s.start()
    s.mark("hero")                                        # "In Bangladesh, a potato farmer often sells below cost."
    s.hold(1200)
    s.move_to(s.page.get_by_text("Five hands, or one truck", exact=False).first, steps=30)
    s.hold(2000)
    s.scroll_to(heading(s.page, "The five-tier syndicate"), block="center", ms=1500)
    s.mark("syndicate")                                   # "Between the field and the buyer, five tiers..."
    s.move_to(s.page.get_by_text("producer-to-retail markup", exact=False).first, steps=30)
    s.hold(2400)
    s.stop()
    s = Shot(b, "S01b")
    s.goto("/docs")
    s.online()
    big = s.page.get_by_text("116%", exact=True).first
    s.scroll_to(big, block="center", ms=600)
    s.start()
    s.mark("markup")                                      # "...can mark the price up by as much as 116%."
    s.move_to(big, steps=24)
    s.box("116", big)
    s.hold(2600)
    cold = s.page.get_by_text("77.32%", exact=True).first
    s.move_to(cold, steps=24)
    s.box("77", cold)
    s.mark("cold")                                        # "Traders hold 77% of the cold storage space"
    s.hold(2600)
    flood = s.page.get_by_text("65%", exact=True).first
    s.move_to(flood, steps=24)
    s.box("65", flood)
    s.mark("flood")                                       # "and a single flash flood can wipe out an entire season."
    s.hold(3600)
    s.stop()


def s02(b):  # One OS, every role: the login page and its quick-login seats.
    s = Shot(b, "S02", zoom=1.1)
    s.goto("/login")
    s.online()
    s.start()
    s.mark("login")                                       # "KrishiNexus OS is one AI operating system"
    s.hold(2200)
    s.scroll_to(heading(s.page, "Quick login"), ms=1500)
    s.mark("roles")                                       # "for everyone in that chain:"
    for label, m in (("Farmer", "farmer"), ("Co-op / cold chain", "coop"), ("Himagar (cold storage)", "himagar"),
                     ("Buyer / trader", "buyer"), ("Truck driver", "driver"), ("Bank", "bank")):
        s.move_to(heading(s.page, label), steps=16)
        s.mark(m)
        s.hold(900)
    s.move_to(s.page.get_by_role("button", name="Rahim Mia FARM-RAN-001", exact=False), steps=18)
    s.mark("signin")                                      # "Each one signs in to their own workspace."
    s.hold(2200)
    s.stop()


def s03(b):  # The farmer asks in his dialect, gives consent, the agents decide; the circuit breaker on the landing.
    s = Shot(b, "S03a", zoom=1.5)
    s.goto("/login")
    s.online()
    s.scroll_to(heading(s.page, "Quick login"), ms=600)
    s.start()
    s.hold(500)
    s.click(s.page.get_by_role("button", name="Rahim Mia FARM-RAN-001", exact=False))
    s.mark("rahim")                                       # "Rahim is a potato farmer in Rangpur."
    s.page.wait_for_url("**/os/field", timeout=90_000)
    s.page.wait_for_load_state("networkidle")
    s.hold(700)
    box = s.page.get_by_placeholder("or type your question", exact=False)
    s.scroll_to(box, block="center", ms=900)
    s.mark("ask")                                         # "He simply asks in his own dialect."
    s.type(box, CHILI_Q, delay=38)
    s.hold(300)
    s.click(s.page.get_by_role("button", name="পাঠান"))
    agree = s.page.get_by_role("button", name="I agree", exact=False)
    agree.wait_for(timeout=90_000)
    s.scroll_to(agree, block="center", ms=900)
    s.hold(500)
    s.click(agree)
    s.mark("consent")                                     # "After he gives consent,"
    decision = s.page.get_by_text("Your decision", exact=False).first
    decision.wait_for(timeout=120_000)
    s.hold(600)
    s.scroll_to(decision, block="start", ms=1500)
    s.mark("decision")                                    # "four AI agents grade his crop, compare..."
    s.hold(2800)
    s.scroll_by(260, ms=1400)
    s.mark("cards")                                       # "...with cold storage and a shared truck"
    s.hold(2500)
    s.stop()
    s = Shot(b, "S03b")
    s.goto("/")
    s.online()
    run = s.page.get_by_role("button", name="Run live multi-agent orchestration")
    s.start()
    s.hold(400)
    s.click(run)
    s.mark("run")
    s.page.get_by_text("circuit breaker", exact=False).first.wait_for(timeout=150_000)
    s.mark("breaker")                                     # "A circuit breaker stops him from selling below his cost"
    s.box("breaker", s.page.get_by_text("circuit breaker", exact=False).first)
    s.hold(1200)
    s.move_to(s.page.get_by_text("Faria distress sale", exact=False).first, steps=24)
    s.mark("working")                                     # "and it shows its working."
    s.hold(3800)
    s.stop()


def s04(b):  # Grading the sample lot: the vision model and the signed certificate.
    s = Shot(b, "S04", user="FARM-RAN-001", zoom=1.5)
    s.goto("/os/field")
    s.online()
    scan = s.page.get_by_role("button", name="Scan sample lot")
    s.scroll_to(scan, block="center", ms=600)
    s.start()
    s.hold(500)
    s.click(scan)
    s.mark("scan")                                        # "He can also photograph his potatoes."
    cert = s.page.get_by_text("Digital quality certificate", exact=False).first
    cert.wait_for(timeout=150_000)
    s.mark("graded")                                      # "A trained vision model finds every tuber..."
    s.hold(1500)
    s.scroll_to(cert, block="center", ms=1500)
    s.mark("cert")                                        # "...then signs a quality certificate."
    s.hold(1500)
    verify = s.page.get_by_role("button", name="Verify", exact=False)
    if verify.count():
        s.click(verify.first)
        s.mark("verify")                                  # "Buyers and banks can verify that certificate"
    s.hold(3500)
    s.stop()


def s05(b):  # The agents at work, the MCP tools, every step traced, offline mode.
    s = Shot(b, "S05a")
    s.goto("/")
    s.online()
    s.start()
    s.hold(500)
    s.click(s.page.get_by_role("button", name="Run live multi-agent orchestration"))
    s.mark("run")                                         # "Behind every answer, you can watch the agents work."
    s.page.get_by_text("Four agents are working", exact=False).first.wait_for(timeout=60_000)
    s.hold(2200)
    s.scroll_to(heading(s.page, "One question, nine LangGraph nodes"), ms=1800)
    s.mark("nodes")                                       # "They retrieve Bangladeshi farm data"
    for n in ("3 CRAG", "4 Grade", "6 Cold chain"):
        s.click(s.page.get_by_role("button", name=n))
        s.hold(1100)
    s.stop()
    s = Shot(b, "S05b")
    s.goto("/docs")
    s.online()
    s.scroll_to(heading(s.page, "Interactive 13-tool MCP protocol inspector"), ms=500)
    s.start()
    s.hold(500)
    s.click(s.page.get_by_role("button", name="get_chamber_telemetry"))
    s.hold(400)
    s.click(s.page.get_by_role("button", name="Execute tool"))
    s.mark("mcp")                                         # "call live tools through three MCP servers"
    s.hold(1800)
    s.scroll_by(360, ms=1300)
    s.mark("traced")                                      # "and every step is traced."
    s.hold(1800)
    s.click(s.page.get_by_text("Offline edge", exact=True).first)
    s.mark("offline")                                     # "It even runs offline, on a fine-tuned Bangla model"
    s.hold(3600)
    s.stop()


def s06(b):  # Co-op truck pools; the cold store's live chambers and a flood alert.
    s = Shot(b, "S06a", user="COOP-BOG-01")
    s.goto("/os/coop")
    s.online()
    s.start()
    s.mark("coop")                                        # "Co-ops pool small harvests into full five-ton trucks."
    s.hold(1200)
    s.scroll_to(heading(s.page, "5-ton union truck pool"), ms=1500)
    s.hold(1800)
    s.stop()
    s = Shot(b, "S06b", user="HIMAGAR-BOG-05")
    s.goto("/os/himagar")
    s.online()
    s.scroll_to(heading(s.page, "Cold-storage chamber inspector"), block="start", ms=500)
    s.start()
    s.mark("himagar")                                     # "The cold store sees live chamber sensors in a 3D twin."
    s.hold(2600)
    s.scroll_to(heading(s.page, "Incident control"), block="start", ms=1200)
    s.click(s.page.get_by_role("button", name="Simulate haor flood"))
    s.mark("flood")                                       # "And when a flood or heat alert arrives,"
    s.hold(4200)
    s.stop()
    try:  # clear the injected flood again so other visitors see a calm site (not filmed)
        t = rec.token("HIMAGAR-BOG-05")
        urllib.request.urlopen(urllib.request.Request(f"{BASE}/mcp/anomalies", method="DELETE",
                                                      headers={"Authorization": f"Bearer {t}"}), timeout=60)
    except Exception as exc:
        print("S06 cleanup failed:", exc)


def s07(b):  # Direct market: the farmer's lots, a trader raises a bid, accept, escrow, the driver delivers.
    s = Shot(b, "S07a", user="FARM-RAN-001")
    s.goto("/os/trade")
    s.online()
    lot = rec.card(s.page, "LOT-SEED01")
    s.start()
    s.mark("lots")                                        # "Rahim can also sell directly. He lists his lot,"
    s.hold(1200)
    s.scroll_to(lot, block="center", ms=1300)
    s.hold(1200)
    s.stop()
    s = Shot(b, "S07b", user="BUY-BOG-02")
    s.goto("/os/trade")
    s.online()
    lot = rec.card(s.page, "LOT-SEED01")
    s.scroll_to(lot, block="center", ms=500)
    s.start()
    s.hold(500)
    s.click(lot.get_by_role("button", name="+0.50").first)
    s.hold(300)
    s.click(lot.get_by_role("button", name="Raise bid"))
    s.mark("bid")                                         # "traders bid in the open"
    s.hold(1800)
    s.stop()
    s = Shot(b, "S07c", user="FARM-RAN-001")
    s.goto("/os/trade")
    s.online()
    lot = rec.card(s.page, "LOT-SEED01")
    s.scroll_to(lot, block="center", ms=500)
    s.start()
    s.hold(500)
    s.click(lot.get_by_role("button", name="Accept").first)
    s.mark("accept")                                      # "and he accepts the best bid."
    s.hold(2000)
    s.scroll_to(rec.card(s.page, "LOT-SEED06"), block="center", ms=1300)
    s.mark("escrow")                                      # "The payment is held in escrow."
    s.hold(2000)
    s.stop()
    s = Shot(b, "S07d", user="DRIVER-BOG-01")
    s.goto("/os/driver")
    s.online()
    job = rec.card(s.page, "Green Chili")
    s.start()
    s.hold(600)
    s.click(job.get_by_role("button", name="Take this job"))
    s.mark("take")                                        # "A driver takes the job"
    s.hold(1500)
    job = rec.card(s.page, "Green Chili")
    s.click(job.get_by_role("button", name="Loaded: start the trip"))
    s.hold(1300)
    job = rec.card(s.page, "Green Chili")
    temp = job.locator("input[type=number]").first
    s.click(temp)
    s.page.keyboard.press("Control+A")
    s.page.keyboard.type("34", delay=140)
    s.click(job.get_by_role("button", name="Report"))
    s.mark("temp")                                        # "and reports the load temperature along the road."
    s.hold(2600)
    s.mark("shelf")                                       # "Our shelf-life model checks..."
    s.click(job.get_by_role("button", name="Delivered: release payment"))
    s.mark("delivered")                                   # "and on delivery the payment is released to Rahim."
    s.hold(3000)
    s.stop()


def s08(b):  # The bank: credit underwriting with the flood check and certificates.
    s = Shot(b, "S08", user="BANK-UCB-01")
    s.goto("/os/market")
    s.online()
    s.scroll_to(heading(s.page, "Agri-credit underwriting"), block="center", ms=500)
    s.start()
    s.hold(500)
    s.click(s.page.get_by_role("button", name="Underwrite FARM-BOG-104"))
    s.mark("underwrite")                                  # "Banks see a credit score from 300 to 850."
    s.page.wait_for_load_state("networkidle", timeout=120_000)
    s.hold(3200)
    s.mark("backed")                                      # "It is backed by satellite flood checks..."
    s.scroll_by(240, ms=1300)
    s.hold(4200)
    s.stop()


def s09(b):  # Honest evaluation, then the data-safety tables.
    s = Shot(b, "S09", zoom=1.35)
    s.goto("/docs")
    s.online()
    s.scroll_to(heading(s.page, "Measured RAGAS-style metrics"), ms=500)
    s.start()
    s.mark("scores")                                      # "We trained five models and we publish every score"
    s.hold(1200)
    s.click(s.page.get_by_role("button", name="Run live regression suite"))
    s.hold(2400)
    s.scroll_to(heading(s.page, "Blind holdout probe"), ms=1400)
    s.mark("missed")                                      # "including the ones that missed their targets."
    s.hold(1600)
    s.scroll_to(heading(s.page, "What the node keeps about a farmer"), ms=1600)
    s.mark("consent")                                     # "The app asks for consent."
    s.hold(3600)
    s.scroll_to(heading(s.page, "Safeguards built in"), ms=1500)
    s.mark("safeguards")                                  # "...always leaves the final decision to the farmer."
    s.hold(3600)
    s.stop()


def s10(b):  # Unit economics and the pilot plan.
    s = Shot(b, "S10")
    s.goto("/docs")
    s.online()
    s.scroll_to(heading(s.page, "One pooled truck, and when a district breaks even"), ms=500)
    s.start()
    s.mark("truck")                                       # "One pooled truck covers its costs."
    s.hold(4200)
    s.scroll_to(heading(s.page, "Pilot plan (proposed, not started)"), ms=1500)
    s.mark("pilot")                                       # "We start a field test this December..."
    s.hold(4500)
    s.stop()


def s07e(b):  # (continues S07d on the live state it left) the temperature report, shelf life, delivery, payment.
    s = Shot(b, "S07e", user="DRIVER-BOG-01")
    s.goto("/os/driver")
    s.online()
    job = rec.card(s.page, "Green Chili")
    s.scroll_to(job, block="center", ms=500)
    s.start()
    s.hold(400)
    temp = job.locator("input[type=number]").first
    s.click(temp)
    s.page.keyboard.press("Control+A")
    s.page.keyboard.type("34", delay=140)
    s.click(job.get_by_role("button", name="Report", exact=True))
    s.mark("temp")                                        # "reports the load temperature along the road."
    s.hold(2600)
    s.mark("shelf")                                       # "Our shelf-life model checks..."
    s.click(job.get_by_role("button", name="Delivered: release payment"))
    s.mark("delivered")                                   # "and on delivery the payment is released to Rahim."
    s.hold(3200)
    s.stop()


SEGMENTS = {"S01": s01, "S02": s02, "S03": s03, "S04": s04, "S05": s05, "S06": s06, "S07": s07, "S08": s08,
            "S09": s09, "S10": s10, "S07e": s07e}

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    wanted = sys.argv[1:] or list(SEGMENTS)
    wake()
    with rec.sync_playwright() as p:
        browser = p.chromium.launch()
        for key in wanted:
            try:
                SEGMENTS[key](browser)
            except Exception as exc:  # one broken shot shouldn't cost the others
                import traceback
                tb = [l for l in traceback.format_exc().splitlines() if "rec_site.py" in l or "rec.py" in l]
                print(f"{key} FAILED: {str(exc).splitlines()[0]} | {' / '.join(x.strip() for x in tb[-3:])}")
        browser.close()
