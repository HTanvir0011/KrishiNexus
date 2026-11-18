"""KrishiNexus OS public demo server: the built frontend and the API on one origin, in one process.

It serves what frontend/nginx.conf serves in the compose stack, for a host that runs one container on one port
(Cloud Run and Render send requests to $PORT):
- the API prefixes and /ws go to the FastAPI app in main.py;
- /api/* goes to it with the prefix stripped, so the API docs are at /api/docs;
- every other path is the built SPA, with index.html for the client routes (/, /os/*, /docs).
Per visitor, three things are rate-limited: writes that change what every visitor sees (escrows, lots, truck pools, n8n
jobs, injected anomalies), logins and account changes, and the CPU-heavy AI calls (a free instance has a fraction of a
CPU). The MCP tool calls the pages poll every few seconds are not. Every response carries the usual security headers,
and admin accounts need KNX_ADMIN_PASSWORD (a per-boot random value unless the host sets one, so never quick login).
Responses are gzipped, which keeps a free host's bandwidth allowance (Render: 5 GB a month) far from its limit.

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
# Admin accounts open only with this password here (auth.py); unset, nobody can log in as admin until the host sets it.
os.environ.setdefault("KNX_ADMIN_PASSWORD", secrets.token_urlsafe(24))

# Imported after the defaults above, because config reads the environment on import.
from starlette.applications import Starlette  # noqa: E402
from starlette.exceptions import HTTPException  # noqa: E402
from starlette.middleware.gzip import GZipMiddleware  # noqa: E402
from starlette.responses import JSONResponse, Response  # noqa: E402
from starlette.routing import Mount  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402
from starlette.types import Receive, Scope, Send  # noqa: E402

from main import app as api  # noqa: E402

STATIC_DIR = Path(os.getenv("KNX_STATIC_DIR", Path(__file__).with_name("static")))
# The API location of frontend/nginx.conf plus /ws; keep the two lists in step.
API_PATH = re.compile(r"/(mcp|rag|edge|agents|automation|guardrails|optimization|prompts|evals|market|health|auth|feedback|openapi\.json|ws)(/|$)")
# (name, "METHOD /path" pattern, requests a minute per visitor). A judging room behind one address shares each bucket.
LIMITS = [
    ("writes", re.compile(r"POST /market/|POST /automation/|POST /mcp/simulate-anomaly|DELETE /mcp/anomalies|POST /feedback"), 30),
    ("accounts", re.compile(r"(POST|PATCH|DELETE) /auth/"), 20),
    ("ai", re.compile(r"POST /(edge|agents|rag|evals|optimization|guardrails)/"), 20),
]
WRITES_PER_MINUTE = LIMITS[0][2]
SECURITY_HEADERS = [
    (b"strict-transport-security", b"max-age=31536000"),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"content-security-policy", b"frame-ancestors 'none'"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(self), microphone=(self), geolocation=()"),
]

# shortcut: counters live in this process, which is right while the demo runs one instance (its state is in memory too).
_recent: dict[tuple[str, str], deque[float]] = {}


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


def over_limit(scope: Scope, now: float) -> bool:
    request = f"{scope['method']} {scope['path']}"
    for name, pattern, per_minute in LIMITS:
        if pattern.match(request):
            recent = _recent.setdefault((name, visitor(scope)), deque())
            while recent and recent[0] <= now - 60:
                recent.popleft()
            if len(recent) >= per_minute:
                return True
            recent.append(now)
            return False
    return False


async def route(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] in ("http", "websocket"):
        if scope["path"].startswith("/api/"):
            scope = {**scope, "path": scope["path"][4:]}
        elif not API_PATH.match(scope["path"]):
            if scope["type"] == "http":
                return await _site(scope, receive, send)
        if scope["type"] == "http" and over_limit(scope, time.monotonic()):
            limited = JSONResponse({"detail": "Too many requests from this address; try again in a minute."},
                                   status_code=429, headers={"Retry-After": "60"})
            return await limited(scope, receive, send)
    await api(scope, receive, send)


# An open /os tab polls pools and telemetry every few seconds: about 5.8 MB an hour raw, 1.1 MB gzipped.
# Server-sent events (MCP streaming) are left uncompressed by the middleware.
_gzipped = GZipMiddleware(route, minimum_size=1_000, compresslevel=6)


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "http":
        return await _gzipped(scope, receive, send)

    async def with_headers(message: dict) -> None:
        if message["type"] == "http.response.start":
            message = {**message, "headers": [*message.get("headers", []), *SECURITY_HEADERS]}
        await send(message)

    await _gzipped(scope, receive, with_headers)
