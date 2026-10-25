"""The app's server: health check, API routes (app/routes.py), static pages (public/).

What Control Center expects of it: listen on 127.0.0.1 and the port it is given, answer 200 on
/health, write its log to stdout and stderr, and stop cleanly when PM2 restarts it. uvicorn does
the listening and the stopping; the start command in control-center.yml passes it the port.
"""
import logging
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.routing import Match, Route

from .auth import who
from .config import APP_NAME, DEV, SIGNIN
from .http import HttpError, SecurityHeaders, api, error_answer, serve_static, text
from .routes import routes

log = logging.getLogger("app")

api_routes = [Route(path, api(route), methods=[method]) for method, path, route in routes]


async def health(request: Request):
    """Control Center checks this every 30 s. Keep it cheap; add checks of what the app needs
    (a database, a disk) only if a failure there means the app is really down."""
    return text("ok\n", headers={"Cache-Control": "no-store"})


async def pages(request: Request):
    """Everything that is not a route above: the files of public/."""
    path = request.url.path
    if path.startswith("/api/") or path == "/hub" or path.startswith("/hub/"):
        known = any(route.matches(request.scope)[0] != Match.NONE for route in api_routes)
        raise HttpError(405, "Method not allowed.") if known else HttpError(404, "No such API route.")
    if request.method not in ("GET", "HEAD"):
        raise HttpError(405, "Method not allowed")
    # Behind the sign-in, every page needs an account: without one, the sign-in did not run.
    # A public app (access: public) has no sign-in in front: it must run with SIGNIN: none.
    if SIGNIN == "required" and not who(request):
        return text("Nobody is signed in. Open this app through its address, so the sign-in runs first.\nIf this app is public (access: public), set SIGNIN: none in its settings.\n", 401)
    answer = serve_static(request, path)
    if answer is None:
        raise HttpError(404, "Not found")
    return answer


async def on_error(request: Request, exc: HTTPException):
    return error_answer(request, exc.status_code, str(exc.detail))


async def on_crash(request: Request, exc: Exception):
    # One line saying what was asked and what broke; the server then writes where it happened.
    log.error("%s %s: %s: %s", request.method, request.url.path, type(exc).__name__, exc)
    return error_answer(request, 500, "Something went wrong on the server. Its log has the details.")


@asynccontextmanager
async def lifespan(app: Starlette):
    # Before the first request: open what the app needs (a database, a file) here.
    log.info("%s started%s", APP_NAME, " (public: no sign-in)" if SIGNIN == "none" else " (dev: signed in as a fake user)" if DEV else "")
    yield
    # PM2 asked the app to stop: requests under way are finished, then this runs. Close things here.
    log.info("%s stopping", APP_NAME)


app = Starlette(
    routes=[
        Route("/health", health),
        *api_routes,
        Route("/{path:path}", pages, methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"]),
    ],
    middleware=[Middleware(SecurityHeaders)],
    exception_handlers={HTTPException: on_error, Exception: on_crash},
    lifespan=lifespan,
)
