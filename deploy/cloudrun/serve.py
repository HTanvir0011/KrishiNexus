"""KrishiNexus OS public demo server: the built frontend and the API on one origin, in one process.

It serves what frontend/nginx.conf serves in the compose stack, for a host that runs one container on one port
(Cloud Run sends requests to $PORT, 8080 by default):
- the API prefixes and /ws go to the FastAPI app in main.py;
- /api/* goes to it with the prefix stripped, so the API docs are at /api/docs;
- every other path is the built SPA, with index.html for the client routes (/, /os/*, /docs).
Writes that change what every visitor sees (escrows, truck pools, n8n jobs, injected anomalies) are limited per visitor.

Run from the folder that holds main.py:  uvicorn serve:app --port 8080
(The image also sets FORWARDED_ALLOW_IPS=* so uvicorn trusts the host's proxy headers.)
"""

from __future__ import annotations

import ipaddress
import os
import re
import secrets
import time
from collections import deque
from pathlib import Path

# Page and API share one origin, so no other site needs CORS; a host variable can still list origins.
os.environ.setdefault("KNX_CORS_ORIGINS", "")
# The default signing key is public on GitHub: sign receipts and certificates with a per-boot secret unless one is set.
os.environ.setdefault("KNX_RECEIPT_SIGNING_KEY", secrets.token_hex(32))

# Imported after the defaults above, because config reads the environment on import.
from starlette.applications import Starlette  # noqa: E402
from starlette.exceptions import HTTPException  # noqa: E402
from starlette.responses import JSONResponse, Response  # noqa: E402
from starlette.routing import Mount  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402
from starlette.types import Receive, Scope, Send  # noqa: E402

from main import app as api  # noqa: E402

STATIC_DIR = Path(os.getenv("KNX_STATIC_DIR", Path(__file__).with_name("static")))
# The API location of frontend/nginx.conf plus /ws; keep the two lists in step.
API_PATH = re.compile(r"/(mcp|rag|edge|agents|automation|guardrails|optimization|prompts|evals|market|health|auth|openapi\.json|ws)(/|$)")
WRITE = re.compile(r"POST /market/bids/lock|POST /automation/|POST /mcp/simulate-anomaly|DELETE /mcp/anomalies")
WRITES_PER_MINUTE = 30

# shortcut: counters live in this process, which is right while the demo runs one instance (its state is in memory too).
_writes: dict[str, deque[float]] = {}


class _Spa(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        asset = scope["path"].startswith("/assets/")
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or asset:
                raise
            response = await super().get_response("index.html", scope)  # a client route
        # Hashed assets never change; the shell is re-checked, so a redeploy can't leave it pointing at deleted assets.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable" if asset else "no-cache"
        return response


_site = Starlette(routes=[Mount("/", _Spa(directory=STATIC_DIR, html=True))])


def _internal(address: str) -> bool:
    """A private or link-local address, as a host's own proxies add; anything unparseable counts as public."""
    try:
        return not ipaddress.ip_address(address).is_global
    except ValueError:
        return False


def visitor(scope: Scope) -> str:
    """The rightmost public address in X-Forwarded-For, which the host's edge proxy saw. Internal hops after it are
    skipped; the entries before it are the client's to forge, so they are never read."""
    forwarded = dict(scope["headers"]).get(b"x-forwarded-for", b"").decode("latin-1")
    addresses = [address.strip() for address in forwarded.split(",") if address.strip()]
    for address in reversed(addresses):
        if not _internal(address):
            return address
    if addresses:
        return addresses[-1]
    return scope["client"][0] if scope.get("client") else ""


def over_write_limit(scope: Scope, now: float) -> bool:
    if not WRITE.match(f"{scope['method']} {scope['path']}"):
        return False
    recent = _writes.setdefault(visitor(scope), deque())
    while recent and recent[0] <= now - 60:
        recent.popleft()
    if len(recent) >= WRITES_PER_MINUTE:
        return True
    recent.append(now)
    return False


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] in ("http", "websocket"):
        if scope["path"].startswith("/api/"):
            scope = {**scope, "path": scope["path"][4:]}
        elif not API_PATH.match(scope["path"]):
            if scope["type"] == "http":
                return await _site(scope, receive, send)
        if scope["type"] == "http" and over_write_limit(scope, time.monotonic()):
            limited = JSONResponse({"detail": "Too many changes from this address; try again in a minute."},
                                   status_code=429, headers={"Retry-After": "60"})
            return await limited(scope, receive, send)
    await api(scope, receive, send)
