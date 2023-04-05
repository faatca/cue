import os

from faat import userdb
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

auth_db = None
listeners = {}


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
async def post_cue(request):
    names = [request.path_params["id"]]
    content = await request.json()
    return await push_cue(names, content)


@requires("authenticated")
async def post_cues(request):
    names = set(v for k, v in request.query_params.multi_items() if k == "name")
    content = await request.json()
    return await push_cue(names, content)


async def push_cue(names, content):
    listener_count = 0
    for ws, topics in listeners.items():
        matches = topics & names
        if matches:
            listener_count += 1
            await ws.send_json({"names": sorted(matches), "content": content})
    return JSONResponse({"success": True, "listeners": listener_count})


@requires("authenticated")
def connections(request):
    ids = sorted(set(id for ws, ws_ids in listeners.items() for id in ws_ids))
    return JSONResponse(ids)


@requires("authenticated")
async def get_listen(websocket):
    names = set(v for k, v in websocket.query_params.multi_items() if k == "name")
    if not names:
        return JSONResponse({"message": "No cue names requested"}, 400)
    elif len(names) > 128:
        return JSONResponse({"message": "Too many cue names requested"}, 400)

    await websocket.accept()

    listeners[websocket] = names
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        listeners.pop(websocket)


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
    Route("/", homepage, methods=["GET"]),
    Route("/auth", post_auth, methods=["POST"]),
    Route("/cues/{id}", post_cue, methods=["POST"]),
    Route("/cues/", post_cues, methods=["POST"]),
    Route("/connections/", connections),
    WebSocketRoute("/listen", get_listen),
]


middleware = [Middleware(AuthenticationMiddleware, backend=TokenAuthBackend())]
app = Starlette(
    routes=routes,
    middleware=middleware,
    on_startup=[startup],
    on_shutdown=[shutdown],
    debug=True,
)
