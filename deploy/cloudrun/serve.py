"""KrishiNexus OS public demo server: the built frontend and the API on one origin, in one process.

It serves what frontend/nginx.conf serves in the compose stack, for a host that runs one container on one port
(Cloud Run and Render send requests to $PORT):
- the API prefixes and /ws go to the FastAPI app in main.py;
- /api/* goes to it with the prefix stripped, so the API docs are at /api/docs;
- every other path is the built SPA, with index.html for the client routes (/, /os/*, /docs).
Per visitor, four things are rate-limited: writes that change what every visitor sees (escrows, lots, truck pools, n8n
jobs, injected anomalies), drivers' truck locations (their own bucket, so a phone reporting often never blocks the room's
bids), logins, sign-ups and account changes, and the CPU-heavy AI calls (a free instance has a fraction of a CPU). The
MCP tool calls the pages poll every few seconds and the live market stream are not. Request bodies are capped (8 MB for
a crop photo, 512 KB otherwise). Every response carries the usual security headers, and admin accounts need
KNX_ADMIN_PASSWORD (a per-boot random value unless the host sets one, so never quick login).
Responses are gzipped, which keeps a free host's bandwidth allowance (Render: 5 GB a month) far from its limit.

Run from the folder that holds main.py:  uvicorn serve:app --port 8080
(The image also sets FORWARDED_ALLOW_IPS=* so uvicorn trusts the host's proxy headers.)
"""

from __future__ import annotations

import ipaddress
import mimetypes
import os
import re
import secrets
import time
from collections import deque
from pathlib import Path

# A public host: config.py then refuses the public development signing key.
os.environ.setdefault("KNX_ENV", "production")
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
from starlette.types import ASGIApp, Message, Receive, Scope, Send  # noqa: E402

from main import app as api  # noqa: E402

STATIC_DIR = Path(os.getenv("KNX_STATIC_DIR", Path(__file__).with_name("static")))
# The API location of frontend/nginx.conf plus /ws; keep the two lists in step.
API_PATH = re.compile(r"/(mcp|rag|edge|agents|automation|guardrails|optimization|prompts|evals|market|health|auth|feedback|openapi\.json|ws)(/|$)")
# (name, "METHOD /path" pattern, requests a minute per visitor); the first match counts. A judging room behind one
# address shares each bucket.
LIMITS = [
    ("locations", re.compile(r"POST /market/deliveries/[^/]+/location$"), 60),
    ("writes", re.compile(r"POST /market/|POST /automation/|POST /mcp/simulate-anomaly|DELETE /mcp/anomalies|POST /feedback"), 30),
    ("accounts", re.compile(r"(POST|PATCH|DELETE) /auth/"), 20),
    ("ai", re.compile(r"POST /(edge|agents|rag|evals|optimization|guardrails)/"), 20),
]
WRITES_PER_MINUTE = LIMITS[1][2]
BODY_LIMIT = 512 * 1024
PHOTO_BODY_LIMIT = 8 * 1024 * 1024  # POST /edge/grade-crop carries a base64 photo
SECURITY_HEADERS = [
    (b"strict-transport-security", b"max-age=31536000"),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"content-security-policy", b"frame-ancestors 'none'"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(self), microphone=(self), geolocation=(self)"),
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
        if scope["path"].startswith("/download/") and response.status_code in (200, 206):
            response.headers["Content-Disposition"] = f'attachment; filename="{Path(scope["path"]).name}"'
        return response


# The Android app is served from /download/ (the repository is private, so a GitHub release can't host it). Android
# installs only a file typed as a package, and nosniff is on, so the type is registered here, not guessed.
mimetypes.add_type("application/vnd.android.package-archive", ".apk")
_site = Starlette(routes=[Mount("/", _Spa(directory=STATIC_DIR, html=True))])


def visitor(scope: Scope) -> str:
    """The rightmost public address in X-Forwarded-For, which the host's edge proxy saw. Internal hops after it (private
    or link-local, as a host's own proxies add) are skipped; anything unparseable counts as public. The entries before it
    are the client's to forge, so they are never read. An IPv6 visitor counts per /64, the block one phone or home gets,
    so picking new addresses inside it doesn't reset the limits."""
    forwarded = dict(scope["headers"]).get(b"x-forwarded-for", b"").decode("latin-1")
    addresses = [address.strip() for address in forwarded.split(",") if address.strip()]
    for address in reversed(addresses):
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return address
        if ip.is_global:
            return str(ipaddress.ip_network(f"{ip}/64", strict=False)) if ip.version == 6 else address
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
# Server-sent events (MCP streaming, GET /market/stream) pass through uncompressed and unbuffered: Starlette's
# GZipMiddleware skips text/event-stream (check_serve.py checks it still does).
_gzipped = GZipMiddleware(route, minimum_size=1_000, compresslevel=6)


async def limit_body(scope: Scope, receive: Receive, send: Send, call: ASGIApp) -> None:
    """413 for a body over its limit: by Content-Length before reading, or, for a body streamed without one, counted
    here (at most the limit is held in memory) and handed on whole."""
    path = scope["path"].removeprefix("/api")
    limit = PHOTO_BODY_LIMIT if (scope["method"], path) == ("POST", "/edge/grade-crop") else BODY_LIMIT
    too_large = JSONResponse({"detail": f"Request body over the {limit // 1024:,} KB limit."}, status_code=413)
    length = dict(scope["headers"]).get(b"content-length")
    if length is not None:
        if not length.isdigit() or int(length) > limit:
            return await too_large(scope, receive, send)
        return await call(scope, receive, send)
    chunks, size, message = [], 0, {"more_body": True}
    while message.get("more_body"):
        message = await receive()
        if message["type"] != "http.request":  # the client went away
            return
        chunks.append(message.get("body", b""))
        size += len(chunks[-1])
        if size > limit:
            return await too_large(scope, receive, send)
    pending: list[Message] = [{"type": "http.request", "body": b"".join(chunks), "more_body": False}]

    async def replay() -> Message:
        return pending.pop() if pending else await receive()

    await call(scope, replay, send)


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "http":
        return await _gzipped(scope, receive, send)

    async def with_headers(message: dict) -> None:
        if message["type"] == "http.response.start":
            message = {**message, "headers": [*message.get("headers", []), *SECURITY_HEADERS]}
        await send(message)

    await limit_body(scope, receive, with_headers, _gzipped)
