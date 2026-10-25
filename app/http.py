"""Small HTTP helpers: answers, JSON bodies, the same-origin check for changes, static files."""
import hashlib
import inspect
import json
import time
from collections import deque
from urllib.parse import unquote, urlsplit

from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from .config import ROOT

PUBLIC = ROOT / "public"
TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".ico": "image/x-icon",
    ".json": "application/json", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8",
}

# Sent with every answer. Fonts and their stylesheet come from Google Fonts; everything else
# from the app itself. Add a host here before loading anything from elsewhere.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'self'; style-src 'self' https://fonts.googleapis.com; style-src-attr 'unsafe-inline'; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
}

CHANGES = {"POST", "PUT", "PATCH", "DELETE"}


class HttpError(HTTPException):
    """An error the routes can raise: answered with its status and message."""

    def __init__(self, status: int, message: str):
        super().__init__(status_code=status, detail=message)


class SecurityHeaders:
    """Adds SECURITY_HEADERS to every answer."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_with_headers)


def text(body: str, status: int = 200, headers: dict | None = None) -> Response:
    return PlainTextResponse(body, status, headers=headers)


def error_answer(request: Request, status: int, message: str) -> Response:
    """An error as the pages expect it: JSON with ok and message for the API, text otherwise."""
    if request.url.path.startswith(("/api/", "/hub")):
        return JSONResponse({"ok": False, "message": message}, status, headers={"Cache-Control": "no-store", **SECURITY_HEADERS})
    return text(f"{message}\n", status, headers=SECURITY_HEADERS)


def rate_limit(limit: int, seconds: float):
    """At most `limit` calls per `seconds`, counted for the whole app.

    Behind nginx every request comes from 127.0.0.1, so there is no visitor to count by. Call
    the returned function in a route: past the limit it raises a 429. Meant for what anyone can
    do on a public app.
    """
    times: deque[float] = deque()

    def check() -> None:
        now = time.monotonic()
        while times and now - times[0] >= seconds:
            times.popleft()
        if len(times) >= limit:
            raise HttpError(429, "Too many requests for now. Try again in a minute.")
        times.append(now)

    return check


async def read_json(request: Request, limit: int = 64 * 1024) -> dict:
    """A JSON object from the request body, at most `limit` bytes."""
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > limit:
            raise HttpError(413, "The request is too large.")
    if not body:
        return {}
    try:
        value = json.loads(body)
    except ValueError:
        raise HttpError(400, "The request is not valid JSON.") from None
    return value if isinstance(value, dict) else {}


def same_origin(request: Request) -> bool:
    """Changes (POST, PUT, DELETE) must come from the app's own pages.

    They send the header X-Requested-By (public/common.js does), which another site cannot send
    without a CORS preflight this app never answers, and the Origin, when present, must be this
    host.
    """
    if not request.headers.get("x-requested-by"):
        return False
    origin = request.headers.get("origin")
    if not origin:
        return True
    try:
        return urlsplit(origin).netloc == request.headers.get("host")
    except ValueError:
        return False


def api(handler):
    """Turns a route of app/routes.py into what the server calls.

    The route gets the request and returns a value (sent as JSON) or raises HttpError. It may be
    a plain function or an `async def`.
    """

    async def endpoint(request: Request) -> Response:
        if request.method in CHANGES and not same_origin(request):
            raise HttpError(403, "Refused: this request did not come from the app itself.")
        result = handler(request)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, Response):
            return result
        return JSONResponse(result if result is not None else {"ok": True}, headers={"Cache-Control": "no-store"})

    return endpoint


def serve_static(request: Request, pathname: str) -> Response | None:
    """A file from public/, with an ETag so browsers check cheaply and never run stale scripts."""
    rel = unquote(pathname)
    if rel.endswith("/"):
        rel += "index.html"
    try:
        file = (PUBLIC / rel.lstrip("/")).resolve()
        if not file.is_relative_to(PUBLIC) or not file.is_file():
            return None
        data = file.read_bytes()
    except (OSError, ValueError):
        return None
    etag = f'"{hashlib.sha1(data).hexdigest()[:16]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-cache"})
    return Response(data, media_type=TYPES.get(file.suffix.lower(), "application/octet-stream"), headers={"Cache-Control": "no-cache", "ETag": etag})
