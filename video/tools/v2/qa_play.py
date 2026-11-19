"""Plays the delivered MP4s in headless Chromium through a <video> element with its captions <track>, the way the site
will: serves frontend/public/video over HTTP at /media/ (range requests, as a static host does) next to a test page
kept in video/out, waits for readyState >= 3, checks the duration, plays and checks time advances, seeks near the
end, and counts the parsed caption cues.

Usage: python -I qa_play.py [names...]   (system python with Playwright) -> prints JSON, writes video/out/qa_play.json
"""
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path("C:/ai-congress/KrishiNexus")
VIDEO = ROOT / "frontend/public/video"


OUT = ROOT / "video/out"


class Ranged(SimpleHTTPRequestHandler):
    """Static files with byte ranges (Chromium seeks media with Range requests); /media/* is frontend/public/video."""

    def translate_path(self, path):
        if path.startswith("/media/"):
            return str(VIDEO / path[len("/media/"):].split("?")[0])
        return str(OUT / path.lstrip("/").split("?")[0])

    def send_head(self):
        rng = self.headers.get("Range")
        path = Path(self.translate_path(self.path))
        if not rng or not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        a, _, b = rng.replace("bytes=", "").partition("-")
        start = int(a or 0)
        end = min(int(b) if b else size - 1, size - 1)
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._left = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        left = getattr(self, "_left", None)
        if left is None:
            return super().copyfile(source, outputfile)
        while left > 0:
            buf = source.read(min(65536, left))
            if not buf:
                break
            outputfile.write(buf)
            left -= len(buf)

    def log_message(self, *a):
        pass


PAGE = """<!doctype html><meta charset=utf-8><body>
<video id=v preload=auto muted playsinline src="/media/{src}" poster="/media/{poster}">
  <track kind=captions srclang=en label=English src="/media/{vtt}" default>
</video></body>"""


def main():
    names = sys.argv[1:] or ["krishinexus-demo", "problem-30s"]
    class Quiet(ThreadingHTTPServer):
        def handle_error(self, request, client_address):  # the browser drops range requests it no longer needs
            pass
    srv = Quiet(("127.0.0.1", 0), partial(Ranged, directory=str(OUT)))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}/"
    results = {}
    with sync_playwright() as p:
        for channel in (None, "msedge", "chrome"):
            try:
                b = p.chromium.launch(channel=channel) if channel else p.chromium.launch()
            except Exception:
                continue
            pg = b.new_page()
            pg.goto(base + "media/" + names[0] + ".jpg")
            can = pg.evaluate("document.createElement('video').canPlayType('video/mp4; codecs=\"avc1.640028, mp4a.40.2\"')")
            if not can:
                b.close()
                results.setdefault("skipped", []).append({"browser": channel or "chromium", "canPlayType": can})
                continue
            results["browser"] = {"channel": channel or "playwright chromium", "version": b.version, "canPlayType": can}
            for name in names:
                (OUT / "qa_page.html").write_text(PAGE.format(src=f"{name}.mp4", poster=f"{name}.jpg",
                                                              vtt=f"{name}.en.vtt"), encoding="utf-8")
                pg.goto(base + "qa_page.html")
                pg.wait_for_function("document.getElementById('v').readyState >= 3", timeout=60_000)
                info = pg.evaluate("""async () => {
                    const v = document.getElementById('v');
                    const t = v.textTracks[0]; t.mode = 'showing';
                    const r0 = v.readyState, d = v.duration;
                    await v.play(); await new Promise(r => setTimeout(r, 1500));
                    const ct = v.currentTime; v.pause();
                    v.currentTime = d - 2; await new Promise(r => v.addEventListener('seeked', r, {once: true}));
                    await new Promise(r => setTimeout(r, 300));
                    return {readyState: r0, duration: d, videoWidth: v.videoWidth, videoHeight: v.videoHeight,
                            playedTo: ct, seekedReadyState: v.readyState, error: v.error && v.error.code,
                            cues: t.cues ? t.cues.length : null,
                            firstCue: t.cues && t.cues.length ? [t.cues[0].startTime, t.cues[0].text] : null};
                }""")
                info["ok"] = bool(info["readyState"] >= 3 and info["playedTo"] > 0.5 and not info["error"])
                results[name] = info
            b.close()
            break
    (OUT / "qa_page.html").unlink(missing_ok=True)
    srv.shutdown()
    out = ROOT / "video/out/qa_play.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
