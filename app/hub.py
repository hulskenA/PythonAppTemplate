"""Widgets on Hub, the server's home page: what this app shows on the board of the people who
can open it.

Hub asks the app on 127.0.0.1 with the viewer's own sign-in headers, so each widget is built for
the person asking, with the same rights as on the app's pages. The format is in ObjimoHub's
WIDGETS.md; this file answers its three requests:

    GET  /hub                                  what the app offers
    GET  /hub/widgets/<id>?size=…&<setting>=…   one widget's content
    POST /hub/widgets/<id>/actions/<action>    a button pressed in a widget

Describe the widgets in app/routes.py (`widgets`). No widgets: leave its list empty, and Hub shows
the app's tile only.
"""
import inspect
import re

from starlette.requests import Request

from .auth import require_user
from .http import HttpError, read_json

SIZES = ("small", "wide", "tall")
ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,40}")


def _settings_list(widget: dict) -> list:
    """A widget's settings: a list, or a function returning one when the options change."""
    settings = widget.get("settings") or []
    return (settings() if callable(settings) else settings) or []


def _allowed(widget: dict, me: dict) -> bool:
    """`groups` on a widget keeps it for those groups, like require_group."""
    return not widget.get("groups") or any(g in me["groups"] for g in widget["groups"])


def _settings_of(widget: dict, values) -> dict:
    """The settings asked for, each one of its options (the first when missing or unknown)."""
    out = {}
    for s in _settings_list(widget):
        v = values.get(s["id"])
        out[s["id"]] = v if v in s["options"] else s["options"][0]
    return out


def _widget_of(definition: dict, wid: str, me: dict) -> dict:
    widget = definition["widgets"].get(wid) if ID.fullmatch(wid) else None
    if not widget:
        raise HttpError(404, "No such widget.")
    if not _allowed(widget, me):
        raise HttpError(403, "This widget is for another group.")
    return widget


async def _maybe_await(value):
    return await value if inspect.isawaitable(value) else value


def hub_routes(definition: dict) -> list:
    """The routes for app/routes.py: `*hub_routes(widgets)`.

    `definition` is {name, icon, summary, widgets: {<id>: {title, description, sizes, settings
    (a list, or a function returning one), groups, content(me, size, settings),
    actions: {<id>: function(me, arg, size, settings)}}}}.
    """
    for wid, w in definition["widgets"].items():
        if not ID.fullmatch(wid):
            raise ValueError(f'widget id "{wid}": lower case letters, digits, - and _ only')
        if not w.get("sizes") or any(s not in SIZES for s in w["sizes"]):
            raise ValueError(f"widget {wid}: sizes are small, wide or tall")
        if not callable(w.get("content")):
            raise ValueError(f"widget {wid}: content(me, size, settings) is missing")

    def offer(request: Request):
        me = require_user(request)
        return {
            "hub": 1, "name": definition.get("name"), "icon": definition.get("icon"), "summary": definition.get("summary"),
            "widgets": [
                {"id": wid, "title": w["title"], "description": w.get("description", ""), "sizes": list(w["sizes"]),
                 "settings": [{"id": s["id"], "label": s["label"], "options": list(s["options"])} for s in _settings_list(w)]}
                for wid, w in definition["widgets"].items() if _allowed(w, me)
            ],
        }

    async def content(request: Request):
        me = require_user(request)
        w = _widget_of(definition, request.path_params["id"], me)
        size = request.query_params.get("size")
        size = size if size in w["sizes"] else w["sizes"][0]
        return await _maybe_await(w["content"](me, size, _settings_of(w, request.query_params)))

    async def action(request: Request):
        me = require_user(request)
        w = _widget_of(definition, request.path_params["id"], me)
        run = (w.get("actions") or {}).get(request.path_params["action"])
        if not run:
            raise HttpError(404, "No such action.")
        body = await read_json(request, 4096)
        settings = body.get("settings") if isinstance(body.get("settings"), dict) else {}
        arg = body.get("arg") if isinstance(body.get("arg"), str) else None
        size = body.get("size") if body.get("size") in w["sizes"] else w["sizes"][0]
        result = await _maybe_await(run(me, arg, size, _settings_of(w, {k: str(v) for k, v in settings.items()})))
        return {"ok": True, "message": (result or {}).get("message") or "Done."}

    return [
        ("GET", "/hub", offer),
        ("GET", "/hub/widgets/{id}", content),
        ("POST", "/hub/widgets/{id}/actions/{action}", action),
    ]
