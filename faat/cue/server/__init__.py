import asyncio
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
from starlette.websockets import WebSocketDisconnect

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
    async def send(id, websocket):
        try:
            await websocket.send_json({"id": id, "content": content})
        except WebSocketDisconnect:
            listeners.pop(websocket, None)

    id = request.path_params["id"]
    content = await request.json()
    tasks = [send(id, ws) for ws, ws_ids in listeners.items() if id in ws_ids]
    if tasks:
        await asyncio.wait(tasks)
    return JSONResponse({"success": True, "clients": len(tasks)})


@routes.post("/cues/")
@requires("authenticated")
async def post_cues(request):
    async def send(ids, websocket):
        try:
            await websocket.send_json({"ids": ids, "content": content})
        except WebSocketDisconnect:
            listeners.pop(websocket, None)

    ids = set(v for k, v in request.query_params.multi_items() if k == "name")

    tasks = [
        send(sorted(matches), ws)
        for ws, ws_ids in listeners.items()
        for matches in [ws_ids & ids]
        if matches
    ]
    content = await request.json()
    if tasks:
        await asyncio.wait(tasks)
    return JSONResponse({"success": True, "clients": len(tasks)})


@routes.get("/connections/")
@requires("authenticated")
def connections(request):
    ids = sorted(set(id for ws, ws_ids in listeners.items() for id in ws_ids))
    return JSONResponse(ids)


@routes.websocket("/listen")
@requires("authenticated")
async def websocket_endpoint(websocket):
    await websocket.accept()

    ids = set(v for k, v in websocket.query_params.multi_items() if k == "name")

    if not ids or len(ids) > 128:
        websocket.close()
        return

    listeners[websocket] = ids
    while True:
        try:
            # We accept and discard messages to keep the connection alive through firewalls.
            await websocket.receive_json()
        except WebSocketDisconnect:
            listeners.pop(websocket)
            break


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
