import asyncio
import datetime
import logging
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
async def get_keyrequest(request):
    k = request.path_params["key"]

    is_valid_request = await apikey_db.is_valid_key_request(k)
    if not is_valid_request:
        return RedirectResponse("/", 303)

    name = f"{datetime.datetime.utcnow()}Z"
    return templates.TemplateResponse("keyrequest.html", locals())


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
        Route("/keyrequest/{key}", get_keyrequest),
        Route("/keyrequest/{key}/accept", post_keyrequest_confirmation, methods=["POST"]),
        Mount("/auth", routes=auth.routes),
        Mount("/static", StaticFiles(directory="static"), name="static"),
        Mount("/api", routes=api.routes),
    ],
    on_startup=[db_startup_task],
    on_shutdown=[db_shutdown_task],
)
