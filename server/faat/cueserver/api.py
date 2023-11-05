import asyncio
from fnmatch import fnmatch
import json
import logging
import uuid

from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocketDisconnect
from .db import apikey_db, redis_db

log = logging.getLogger(__name__)

user_listeners = {}


def homepage(request):
    return JSONResponse({"message": "This is the cue api"})


async def post_auth(request):
    j = await request.json()
    name = j["name"]
    pattern = j.get("pattern")
    request_id, apikey = await apikey_db.start_key_request(name, pattern)
    return JSONResponse({"id": request_id, "key": apikey})


async def get_hello(request):
    uid = (await get_request_key(request.headers))["uid"]
    if not uid:
        return JSONResponse({"message": "Unauthorized"}, 401)
    return JSONResponse({"message": "Hello!"})


async def post_cues(request):
    key = await get_request_key(request.headers)
    uid = key["uid"]
    if not uid:
        return JSONResponse({"message": "Unauthorized"}, 401)

    names = set(v for k, v in request.query_params.multi_items() if k == "name")
    bad_names = [n for n in names if key["pattern"] and not fnmatch(n, key["pattern"])]
    if bad_names:
        return JSONResponse({"message": "Key has no access to cues", "names": bad_names}, 401)

    content = await request.json()
    await push_cue(uid, names, content)
    return JSONResponse({"message": "posted"})


async def get_request_key(headers):
    if "Authorization" not in headers:
        return

    auth = headers["Authorization"]
    try:
        scheme, key = auth.split()
        if scheme.lower() not in ("bearer", "apikey"):
            return
    except ValueError:
        return

    return await apikey_db.get_key(key)


async def monitor_messages():
    while True:
        try:
            async with redis_db.pubsub() as channel:
                await channel.subscribe("cues")
                while True:
                    message = await channel.get_message(ignore_subscribe_messages=True)
                    if message is None:
                        await asyncio.sleep(0.01)
                    else:
                        log.debug(f"(Reader) Message Received: {message}")
                        payload = json.loads(message["data"])

                        targets = []
                        listeners = user_listeners.get(payload["uid"])
                        if listeners:
                            for ws, listener_settings in listeners.items():
                                matches = [
                                    m
                                    for m in payload["names"]
                                    if (
                                        not listener_settings["keyPattern"]
                                        or fnmatch(m, listener_settings["keyPattern"])
                                    )
                                    and any(fnmatch(m, p) for p in listener_settings["names"])
                                ]

                                if matches:
                                    targets.append((ws, matches))

                        if targets:
                            async with asyncio.TaskGroup() as tasks:
                                for ws, matches in targets:
                                    tasks.create_task(
                                        ws.send_json(
                                            {
                                                "id": payload["id"],
                                                "names": sorted(matches),
                                                "content": payload["content"],
                                            }
                                        )
                                    )
        except Exception:
            log.exception("Error encountered while monitoring queue")
            await asyncio.sleep(1)


async def push_cue(uid, names, content):
    payload = {"id": str(uuid.uuid4()), "uid": uid, "names": sorted(names), "content": content}
    await redis_db.publish("cues", json.dumps(payload))


async def get_listen(websocket):
    key = await get_request_key(websocket.headers)
    uid = key["uid"]
    if uid is None:
        await websocket.close(code=1008)
        return

    names = set(v for k, v in websocket.query_params.multi_items() if k == "name")
    if not names:
        return JSONResponse({"message": "No cue names requested"}, 400)
    elif len(names) > 128:
        return JSONResponse({"message": "Too many cue names requested"}, 400)

    await websocket.accept()

    listeners = user_listeners.get(uid)
    if listeners is None:
        listeners = {}
        user_listeners[uid] = listeners

    listeners[websocket] = {"keyPattern": key["pattern"], "names": names}
    try:
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
    finally:
        listeners.pop(websocket)
        if not listeners:
            user_listeners.pop(uid)


routes = [
    Route("/", homepage),
    Route("/hello", get_hello),
    Route("/auth", post_auth, methods=["POST"]),
    Route("/cues", post_cues, methods=["POST"]),
    WebSocketRoute("/listen", get_listen),
]
