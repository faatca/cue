import logging
from functools import wraps
from urllib.parse import quote_plus, urlencode

from authlib.integrations.starlette_client import OAuth
from starlette.datastructures import Secret
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from starlette.routing import Route

from .settings import config

log = logging.getLogger(__name__)


oauth = OAuth(config)

OAUTH_DOMAIN = config("OAUTH_DOMAIN")
OAUTH_CONF_URL = f"https://{OAUTH_DOMAIN}/.well-known/openid-configuration"
OAUTH_CLIENT_ID = config("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = config("OAUTH_CLIENT_SECRET", cast=Secret)

oauth.register(
    "auth0",
    client_id=OAUTH_CLIENT_ID,
    client_secret=str(OAUTH_CLIENT_SECRET),
    server_metadata_url=OAUTH_CONF_URL,
    client_kwargs={"scope": "openid profile"},
)


async def sign_in(request):
    auth0 = oauth.create_client("auth0")
    redirect_uri = str(request.url_for("authorize"))
    result = await auth0.authorize_redirect(request, redirect_uri)
    return result


async def authorize(request):
    auth0 = oauth.create_client("auth0")
    token = await auth0.authorize_access_token(request)
    userinfo = token["userinfo"]
    request.session["userinfo"] = userinfo
    return RedirectResponse("/")


async def sign_out(request):
    form = await request.form()
    if request.session.get("csrf") != form["csrf"]:
        request.session["flash"] = "Failed. Please try again."
        return RedirectResponse("/", 303)

    userinfo = request.session.pop("userinfo")
    if userinfo:
        param_values = {"client_id": OAUTH_CLIENT_ID, "returnTo": request.url_for("get_index")}
        params = urlencode(param_values, quote_via=quote_plus)
        logout_url = f"https://{OAUTH_DOMAIN}/v2/logout?{params}"
        return RedirectResponse(logout_url, 303)
    return RedirectResponse("/", 303)


def requires_auth(view):
    @wraps(view)
    async def wrapper(request, **kwargs):
        user = get_user(request)
        if not user:
            return RedirectResponse("/")
        request.state.user = user
        request.state.user_id = user["sub"]
        return await view(request, **kwargs)

    return wrapper


def get_user(request):
    return request.session.get("userinfo") or None


class UserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        user = get_user(request)
        request.state.user = user
        response = await call_next(request)
        return response


routes = [
    Route("/sign-in", sign_in),
    Route("/authorize", authorize, methods=["GET", "POST"]),
    Route("/sign-out", sign_out, methods=["GET", "POST"]),
]
