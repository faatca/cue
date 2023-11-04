import asyncio
import datetime
import logging
import re
from pathlib import Path
from urllib.parse import quote_plus

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from . import api
from . import auth
from . import settings
from .csrf import CSRFMiddleware
from .db import apikey_db

log = logging.getLogger(__name__)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["quote_plus"] = quote_plus


async def get_index(request):
    if auth.get_user(request):
        return RedirectResponse("/home")
    return templates.TemplateResponse("index.html", {"request": request})


@auth.requires_auth
async def get_home(request):
    current_page = int(request.query_params.get("page", 1))
    term = request.query_params.get("q") or ""

    uid = request.state.user_id

    apikeys = await apikey_db.find_user_apikeys(uid)
    return templates.TemplateResponse("home.html", locals())


@auth.requires_auth
async def post_cue(request):
    async with request.form() as form:
        if request.session.get("csrf") != form["csrf"]:
            request.session["flash"] = "Failed. Please try again."
            return RedirectResponse("/home", 303)
        name = form["name"]

    uid = request.state.user_id
    await api.push_cue(uid, [name], "")
    return RedirectResponse("/home", 303)


@auth.requires_auth
async def get_keyrequest(request):
    k = request.path_params["key"]

    apikey_request = await apikey_db.find_key_request(k)
    if apikey_request is None:
        return RedirectResponse("/", 303)

    name = apikey_request["name"] or f"{datetime.datetime.utcnow()}Z"
    return templates.TemplateResponse("keyrequest.html", locals())


@auth.requires_auth
async def key_removal(request):
    key_id = request.path_params["key"]
    if not re.fullmatch(r"[0-9A-Fa-f-]+", key_id):
        request.session["flash"] = "Invalid key ID"
        return RedirectResponse("/home", 303)

    keys = [k for k in await apikey_db.find_user_apikeys(request.state.user_id) if k["id"] == key_id]
    if not keys:
        request.session["flash"] = "Key not found"
        return RedirectResponse("/home", 303)

    k = keys[0]

    if request.method == "POST":
        async with request.form() as form:
            if request.session.get("csrf") != form["csrf"]:
                request.session["flash"] = "Failed. Please try again."
                return RedirectResponse("/home", 303)
        await apikey_db.remove_key(key_id)
        return RedirectResponse("/home", 303)

    return templates.TemplateResponse("key-removal.html", locals())


@auth.requires_auth
async def post_keyrequest_confirmation(request):
    k = request.path_params["key"]

    async with request.form() as form:
        if request.session.get("csrf") != form["csrf"]:
            request.session["flash"] = "Failed. Please try again."
            return RedirectResponse("/", 303)
        name = form["name"] or f"{datetime.datetime.utcnow()}Z"

    try:
        await apikey_db.redeem_key_request(k, request.state.user_id, name)
    except ValueError:
        log.info("Invalid request")
    return RedirectResponse("/", 303)


listener_task = None


async def db_startup_task():
    global listener_task
    listener_task = asyncio.create_task(api.monitor_messages())


async def db_shutdown_task():
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        log.debug("monitor task is cancelled")


app = Starlette(
    debug=settings.DEBUG,
    middleware=[
        Middleware(
            SessionMiddleware,
            secret_key=str(settings.SESSION_SECRET_KEY),
            https_only=settings.SESSION_HTTPS_ONLY,
        ),
        Middleware(auth.UserMiddleware),
        Middleware(CSRFMiddleware),
    ],
    routes=[
        Route("/", get_index),
        Route("/home", get_home),
        Route("/home/cue", post_cue, methods=["POST"]),
        Route("/keyrequest/{key}", get_keyrequest),
        Route("/keyrequest/{key}/accept", post_keyrequest_confirmation, methods=["POST"]),
        Route("/key-removal/{key}", key_removal, methods=["GET", "POST"]),
        Mount("/auth", routes=auth.routes),
        Mount("/static", StaticFiles(directory="static"), name="static"),
        Mount("/api", routes=api.routes),
    ],
    on_startup=[db_startup_task],
    on_shutdown=[db_shutdown_task],
)
