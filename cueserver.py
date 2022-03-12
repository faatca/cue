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
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocketDisconnect

from faat import userdb

auth_db = None
listeners = []


def homepage(request):
    return JSONResponse({"message": "This is the cue api"})


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


@requires("authenticated")
async def post_message(request):
    async def send(websocket):
        try:
            await websocket.send_json({"id": websocket.path_params["id"], "content": content})
        except WebSocketDisconnect:
            listeners.remove((id, websocket))

    content = await request.json()
    tasks = [send(ws) for id, ws in list(listeners) if id == request.path_params["id"]]
    if tasks:
        await asyncio.wait(tasks)
    return JSONResponse({"success": True, "clients": len(tasks)})


@requires("authenticated")
def connections(request):
    request.headers.get("AUTHORIZATION")
    ids = [id for id, _ in listeners]
    return JSONResponse(ids)


@requires("authenticated")
async def websocket_endpoint(websocket):
    await websocket.accept()
    listeners.append((websocket.path_params["id"], websocket))
    while True:
        try:
            await websocket.receive_json()
        except WebSocketDisconnect:
            listeners.remove((websocket.path_params["id"], websocket))
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


routes = [
    Route("/", homepage),
    Route("/auth", post_auth, methods=["POST"]),
    Route("/connections", connections),
    Route("/p/{id}/post", post_message, methods=["POST"]),
    WebSocketRoute("/p/{id}/listen", websocket_endpoint),
]


middleware = [Middleware(AuthenticationMiddleware, backend=TokenAuthBackend())]
app = Starlette(
    routes=routes,
    middleware=middleware,
    on_startup=[startup],
    on_shutdown=[shutdown],
    debug=True,
)
