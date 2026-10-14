"""Who is asking.

The sign-in (Authelia) checks every request before nginx passes it on, then nginx adds the
account in Remote-User, its groups in Remote-Groups, its name and email. The app only listens on
127.0.0.1, so nothing reaches it without going through nginx.
"""
import re

from starlette.requests import Request

from .config import DEV, DEV_GROUPS, DEV_USER, SIGNIN, SIGNIN_URL
from .http import HttpError


def who(request: Request) -> dict | None:
    """{user, name, email, groups}, or None when nobody is signed in."""
    if SIGNIN == "none":
        return None
    if DEV:
        return {"user": DEV_USER, "name": DEV_USER.capitalize(), "email": f"{DEV_USER}@example.com", "groups": DEV_GROUPS}
    user = request.headers.get("remote-user")
    if not user:
        return None
    return {
        "user": user,
        "name": request.headers.get("remote-name") or user,
        "email": request.headers.get("remote-email") or "",
        "groups": [g.strip() for g in (request.headers.get("remote-groups") or "").split(",") if g.strip()],
    }


def require_user(request: Request) -> dict:
    """The signed-in person, or a 401 when the app expects the sign-in and there is none."""
    me = who(request)
    if not me:
        raise HttpError(401, "This app has no sign-in." if SIGNIN == "none" else "Nobody is signed in. Open the app through its address, so the sign-in runs first.")
    return me


def require_group(request: Request, *groups: str) -> dict:
    """The signed-in person, if they are in one of these groups; a 403 otherwise."""
    me = require_user(request)
    if not any(g in me["groups"] for g in groups):
        raise HttpError(403, f"This needs the group {' or '.join(groups)}.")
    return me


def sign_out_url(request: Request) -> str | None:
    """The sign-in's sign-out address, for the page's link."""
    if DEV or SIGNIN == "none":
        return None
    if SIGNIN_URL:
        return f"{SIGNIN_URL.rstrip('/')}/logout"
    host = (request.headers.get("host") or "").split(":")[0]
    parts = host.split(".")
    if re.fullmatch(r"[\d.]+", host) or len(parts) < 3:
        return None
    return f"https://auth.{'.'.join(parts[1:])}/logout"
