"""The app's own API: this is the file to grow.

Each route gets the request and returns a value (sent as JSON) or raises an HttpError. The
example below is a small message board, kept in memory so the template needs nothing else:
replace it.
"""
import time

from starlette.requests import Request

from .auth import require_group, require_user, sign_out_url, who
from .config import APP_NAME, SIGNIN
from .http import HttpError, rate_limit, read_json
from .hub import hub_routes

messages: list[dict] = []  # {id, text, by, at}: gone at each restart; use a database or a file for real data.
next_id = 1

# On a public app anyone may read and post, as "Anonymous". With no account to answer for it,
# posting is capped for the whole app so a script cannot flood the board.
PUBLIC = SIGNIN == "none"
post_limit = rate_limit(20, 60)


def me(request: Request):
    """Who is signed in, for the page's header."""
    return {"app": APP_NAME, "signin": SIGNIN, "me": who(request), "signOut": sign_out_url(request)}


def list_messages(request: Request):
    if not PUBLIC:
        require_user(request)
    return {"messages": messages[-50:][::-1]}


async def post_message(request: Request):
    global next_id
    author = {"name": "Anonymous"} if PUBLIC else require_user(request)
    if PUBLIC:
        post_limit()
    body = await read_json(request)
    text = str(body.get("text") or "").strip()
    if not text:
        raise HttpError(400, "Write something first.")
    if len(text) > 500:
        raise HttpError(400, "Keep it under 500 characters.")
    item = {"id": next_id, "text": text, "by": author["name"], "at": int(time.time() * 1000)}
    next_id += 1
    messages.append(item)
    if len(messages) > 500:
        messages.pop(0)
    return {"ok": True, "message": "Posted.", "item": item}


def delete_message(request: Request):
    """For the admins group only: require_group refuses everyone else with a 403 (with a 401 on
    a public app, where nobody is signed in)."""
    require_group(request, "admins")
    wanted = request.path_params["id"]
    for i, m in enumerate(messages):
        if m["id"] == wanted:
            del messages[i]
            return {"ok": True, "message": "Deleted."}
    raise HttpError(404, "No such message.")


# What the app shows on Hub, the server's home page (app/hub.py has the format): one widget, built
# for the person asking, with a button that does what the page's own button does. Replace it with
# your app's, or leave `widgets` empty for no widget. Hub only knows who is asking behind the
# sign-in: a public app (SIGNIN: none) offers no widget.
def latest_content(me: dict, size: str, settings: dict) -> dict:
    mine = settings["show"] == "Mine"
    shown = [m for m in reversed(messages) if not mine or m["by"] == me["name"]]
    return {
        "footer": f"{len(messages)} on the board",
        "refresh": 60,
        "blocks": [
            {"type": "list", "empty": "No message yet.", "items": [{"text": m["text"], "meta": m["by"]} for m in shown[: 8 if size == "tall" else 3]]},
            {"type": "buttons", "buttons": [{"label": "Say hello", "icon": "waving_hand", "action": {"id": "hello"}}]},
        ],
    }


def say_hello(me: dict, arg, size: str, settings: dict) -> dict:
    global next_id
    messages.append({"id": next_id, "text": "Hello from Hub", "by": me["name"], "at": int(time.time() * 1000)})
    next_id += 1
    if len(messages) > 500:
        messages.pop(0)
    return {"message": "Posted."}


widgets = {
    "name": APP_NAME,
    "icon": "forum",
    "summary": "An example message board.",
    "widgets": {
        "latest": {
            "title": "Latest messages",
            "description": "The newest messages on the board, and a button to say hello.",
            "sizes": ["small", "wide", "tall"],
            "settings": [{"id": "show", "label": "Show", "options": ["Everyone's", "Mine"]}],
            "content": latest_content,
            "actions": {"hello": say_hello},
        },
    },
}


# (method, path, route). A part of the path in braces becomes request.path_params: {id:int}, {name}.
routes = [
    ("GET", "/api/me", me),
    ("GET", "/api/messages", list_messages),
    ("POST", "/api/messages", post_message),
    ("DELETE", "/api/messages/{id:int}", delete_message),
    # Hub's three requests: /hub, /hub/widgets/<id>, /hub/widgets/<id>/actions/<action>.
    *([] if PUBLIC else hub_routes(widgets)),
]
