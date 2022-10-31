import asyncio
import json
import os
from starlette.applications import Starlette
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
    requires,
)
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from .routing import RouteHelper

from faat import userdb

auth_db = None
listeners = {}

routes = RouteHelper()


@routes.get("/")
def homepage(request):
    return JSONResponse({"message": "This is the cue api"})


@routes.post("/auth")
async def post_auth(request):
    content = await request.json()
    username = str(content["username"])
    password = str(content["password"])

    try:
        user_id = auth_db.authenticate(username, password)
    except userdb.AuthenticationError:
        return JSONResponse({"success": False, "message": "Invalid credentials"}, 401)

    token = auth_db.create_apikey(user_id)

    return JSONResponse({"success": True, "message": "Authenticated", "token": token})


@routes.post("/cues/{id}")
@requires("authenticated")
async def post_cue(request):
    names = [request.path_params["id"]]
    content = await request.json()
    return push_cue(names, content)


@routes.post("/cues/")
@requires("authenticated")
async def post_cues(request):
    names = set(v for k, v in request.query_params.multi_items() if k == "name")
    content = await request.json()
    return push_cue(names, content)


def push_cue(names, content):
    listener_count = 0
    for q, topics in listeners.items():
        matches = topics & names
        if matches:
            listener_count += 1
            q.put_nowait({"names": sorted(matches), "content": content})
    return JSONResponse({"success": True, "listeners": listener_count})


@routes.get("/connections/")
@requires("authenticated")
def connections(request):
    ids = sorted(set(id for ws, ws_ids in listeners.items() for id in ws_ids))
    return JSONResponse(ids)


@routes.get("/listen")
@requires("authenticated")
async def get_listen(request):
    names = set(v for k, v in request.query_params.multi_items() if k == "name")
    if not names:
        return JSONResponse({"message": "No cue names requested"}, 400)
    elif len(names) > 128:
        return JSONResponse({"message": "Too many cue names requested"}, 400)

    async def event_publisher():
        q = asyncio.Queue()
        listeners[q] = names
        try:
            while True:
                message = await q.get()
                yield json.dumps(message)
        finally:
            listeners.pop(q)

    return EventSourceResponse(event_publisher())


def startup():
    global auth_db
    path = os.environ.get("CUE_USER_DB") or "users.db"
    auth_db = userdb.connect(path)


def shutdown():
    global auth_db
    auth_db.close()
    auth_db = None


class TokenAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if "Authorization" not in conn.headers:
            return

        auth = conn.headers["Authorization"]
        try:
            scheme, credentials = auth.split()
            if scheme.lower() != "bearer":
                return
        except ValueError:
            raise AuthenticationError("Invalid credentials")

        token = credentials
        try:
            user_id = auth_db.authenticate_apikey(token)
        except userdb.AuthenticationError:
            raise AuthenticationError("Invalid credentials")

        return AuthCredentials(["authenticated"]), SimpleUser(user_id)


middleware = [Middleware(AuthenticationMiddleware, backend=TokenAuthBackend())]
app = Starlette(
    routes=routes.routes,
    middleware=middleware,
    on_startup=[startup],
    on_shutdown=[shutdown],
    debug=True,
)
