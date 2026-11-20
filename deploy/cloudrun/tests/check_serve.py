"""Self-check for serve.py: the nginx.conf routing, the SPA fallback, the rate limits, the body-size limits, the security
headers, the live market stream and the trace WebSocket.

Run it with the backend's Python from the repo root:  backend/.venv/Scripts/python deploy/cloudrun/tests/check_serve.py
It changes no demo state: the limited requests carry empty bodies (422) or are refused logins until the limit answers 429,
and the market event it streams is published straight onto the event bus.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]  # deploy/cloudrun, where serve.py is
tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # removed when the script exits
static = Path(tmp.name)
(static / "assets").mkdir()
(static / "index.html").write_text("<!doctype html><title>spa shell</title>", encoding="utf-8")
(static / "assets" / "app.js").write_text("export {};", encoding="utf-8")
(static / "download").mkdir()
(static / "download" / "KrishiNexus.apk").write_bytes(b"PK test package")
os.environ["KNX_STATIC_DIR"] = str(static)
sys.path[:0] = [str(HERE), str(HERE.parent.parent / "backend")]  # serve.py, then main.py in the repo layout

from starlette.testclient import TestClient  # noqa: E402

import serve  # noqa: E402  (first: it sets the host's environment defaults before the backend reads its config)
import marketplace  # noqa: E402,I001

with TestClient(serve.app) as client:
    for route in ("/", "/os/field", "/docs"):  # client routes; /docs is the whitepaper, not FastAPI's docs
        page = client.get(route)
        assert page.status_code == 200 and "spa shell" in page.text, route
        assert page.headers["cache-control"] == "no-cache", route
    assert client.get("/assets/app.js").headers["cache-control"].startswith("public")
    assert client.get("/assets/gone.js").status_code == 404
    assert "swagger-ui" in client.get("/api/docs").text
    assert client.get("/openapi.json").json()["info"]["title"]
    assert client.get("/health").json()["status"] == "ok"
    assert client.post("/os").status_code == 405

    visitor = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}  # the client wrote 1.2.3.4; the edge proxy appended 5.6.7.8
    for _ in range(serve.WRITES_PER_MINUTE):
        assert client.post("/market/bids/lock", json={}, headers=visitor).status_code == 422
    # The same visitor stays limited: through /api/, whatever the client writes first, and behind an internal hop.
    assert client.post("/api/market/bids/lock", json={}, headers={"X-Forwarded-For": "9.9.9.9, 5.6.7.8"}).status_code == 429
    assert client.delete("/mcp/anomalies", headers={"X-Forwarded-For": "5.6.7.8, 169.254.1.1"}).status_code == 429
    assert client.post("/market/bids/lock", json={}, headers={"X-Forwarded-For": "5.6.7.9"}).status_code == 422
    assert client.get("/mcp/anomalies", headers=visitor).status_code == 200  # reads stay open

    # Logins and the heavy AI calls have their own buckets; the MCP calls the pages poll are never limited.
    other = {"X-Forwarded-For": "7.7.7.7"}
    assert client.post("/auth/login", json={"user_id": "ADMIN-01"}, headers=other).status_code == 401  # admin needs the host password
    for _ in range(19):
        client.post("/auth/login", json={}, headers=other)
    assert client.post("/auth/login", json={}, headers=other).status_code == 429
    assert client.post("/edge/grade-crop", json={}, headers=other).status_code == 422  # a separate bucket
    for _ in range(40):
        assert client.post("/mcp/call", json={}, headers=other).status_code != 429

    page = client.get("/")
    assert page.headers["x-frame-options"] == "DENY" and page.headers["x-content-type-options"] == "nosniff"
    assert client.get("/health").headers["strict-transport-security"].startswith("max-age=")
    assert page.headers["permissions-policy"] == "camera=(self), microphone=(self), geolocation=(self)"

    # A driver's location reports have their own bucket: the visitor whose writes are used up can still send them.
    assert client.post("/market/deliveries/LOT-SEED06/location", json={}, headers={"X-Forwarded-For": "5.6.7.8"}).status_code == 401
    # IPv6 visitors count per /64; anything unparseable is still a visitor of its own.
    v6 = [serve.visitor({"headers": [(b"x-forwarded-for", f"2a00:1450:4001:81{x}::{y}".encode())]}) for x, y in ("a1", "a2", "b1")]
    assert v6[0] == v6[1] == "2a00:1450:4001:81a::/64" != v6[2]
    assert serve.visitor({"headers": [(b"x-forwarded-for", b"1.2.3.4:5678")]}) == "1.2.3.4:5678"

    # Request bodies: 413 over 512 KB (8 MB for a crop photo), by Content-Length or counted when streamed without one.
    big, kb = {"Content-Type": "application/json", "X-Forwarded-For": "8.8.4.4"}, 1024
    assert client.post("/market/bids/lock", content=b" " * (512 * kb + 1), headers=big).status_code == 413
    assert client.post("/market/bids/lock", content=b"{}" + b" " * (512 * kb - 2), headers=big).status_code == 422  # at the limit
    assert client.post("/edge/grade-crop", content=b"{}" + b" " * (2 * kb * kb), headers=big).status_code == 422  # a photo fits
    assert client.post("/api/edge/grade-crop", content=b" " * (8 * kb * kb + 1), headers=big).status_code == 413
    assert client.post("/edge/verify-certificate", content=b" " * (600 * kb), headers=big).status_code == 413
    chunked = client.post("/auth/login", content=(part for part in [b" " * (300 * kb)] * 2), headers=big)
    assert chunked.status_code == 413 and "content-length" not in chunked.request.headers
    small = client.post("/auth/login", content=(part for part in [b'{"user_id": ', b'"NOPE-01"}']), headers=big)
    assert small.status_code == 403  # a small streamed body reaches the API whole
    assert client.post("/os", content=b" " * (600 * kb), headers=big).status_code == 413  # site paths too

    # Polled JSON is gzipped; a server-sent event stream is not.
    assert client.get("/automation/truck-pools", headers={"Accept-Encoding": "gzip"}).headers.get("content-encoding") == "gzip"
    stream = client.post("/mcp/servers/dam-market-mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                         headers={"Accept": "text/event-stream", "Accept-Encoding": "gzip"})
    assert stream.headers["content-type"].startswith("text/event-stream") and "content-encoding" not in stream.headers

    # The live market stream passes through unbuffered and uncompressed, also for a visitor whose writes are used up.
    for path in ("/market/stream", "/api/market/stream"):
        with client.stream("GET", path, headers={"Accept-Encoding": "gzip", "X-Forwarded-For": "5.6.7.8"}) as sse:
            assert sse.status_code == 200 and "content-encoding" not in sse.headers, sse.headers
            assert sse.headers["content-type"].startswith("text/event-stream") and sse.headers["x-accel-buffering"] == "no"
            assert sse.headers["x-frame-options"] == "DENY"
            lines = sse.iter_lines()
            assert next(lines) == "retry: 5000" and next(lines) == ""
            marketplace.EVENTS.publish("market_reset")
            assert next(lines) == f"id: {marketplace.EVENTS.seq}" and next(lines) == "event: market"
            assert json.loads(next(lines).removeprefix("data: "))["kind"] == "market_reset"
    assert client.get("/market/events", headers={"X-Forwarded-For": "5.6.7.8"}).json()["seq"] == marketplace.EVENTS.seq

    with client.websocket_connect("/ws/agent-trace") as ws:
        assert ws.receive_json()["type"] == "hello"

    # The Android app is downloaded from the site itself: typed as a package (nosniff is on) and saved as a file.
    apk = client.get("/download/KrishiNexus.apk")
    assert apk.status_code == 200 and apk.content.startswith(b"PK"), apk.status_code
    assert apk.headers["content-type"] == "application/vnd.android.package-archive", apk.headers["content-type"]
    assert apk.headers["content-disposition"] == 'attachment; filename="KrishiNexus.apk"'
    assert "content-disposition" not in client.get("/").headers

print("serve.py: all checks passed")
