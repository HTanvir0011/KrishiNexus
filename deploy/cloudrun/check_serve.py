"""Self-check for serve.py: the nginx.conf routing, the SPA fallback, the write limit and the trace WebSocket.

Run it with the backend's Python from the repo root:  backend/.venv/Scripts/python deploy/cloudrun/check_serve.py
It changes no demo state: the limited requests carry empty bodies (422) until the limit answers 429.
"""

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # removed when the script exits
static = Path(tmp.name)
(static / "assets").mkdir()
(static / "index.html").write_text("<!doctype html><title>spa shell</title>", encoding="utf-8")
(static / "assets" / "app.js").write_text("export {};", encoding="utf-8")
os.environ["KNX_STATIC_DIR"] = str(static)
sys.path[:0] = [str(HERE), str(HERE.parent.parent / "backend")]  # serve.py, then main.py in the repo layout

from starlette.testclient import TestClient  # noqa: E402

import serve  # noqa: E402

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

    with client.websocket_connect("/ws/agent-trace") as ws:
        assert ws.receive_json()["type"] == "hello"

print("serve.py: all checks passed")
