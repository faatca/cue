import asyncio
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
    name = (await request.json())["name"]
    request_id, apikey = await apikey_db.start_key_request(name)
    return JSONResponse({"id": request_id, "key": apikey})


async def get_hello(request):
    uid = await get_request_uid(request.headers)
    if not uid:
        return JSONResponse({"message": "Unauthorized"}, 401)
    return JSONResponse({"message": "Hello!"})


async def post_cues(request):
    uid = await get_request_uid(request.headers)
    if not uid:
        return JSONResponse({"message": "Unauthorized"}, 401)

    names = set(v for k, v in request.query_params.multi_items() if k == "name")
    content = await request.json()
    await push_cue(uid, names, content)
    return JSONResponse({"message": "posted"})


async def get_request_uid(headers):
    if "Authorization" not in headers:
        return

    auth = headers["Authorization"]
    try:
        scheme, key = auth.split()
        if scheme.lower() not in ("bearer", "apikey"):
            return
    except ValueError:
        return

    return await apikey_db.get_key_user(key)


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

                        listeners = user_listeners.get(payload["uid"])
                        if listeners:
                            targets = [
                                (ws, matches)
                                for ws, topics in listeners.items()
                                for matches in [set(topics) & set(payload["names"])]
                                if matches
                            ]
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
    uid = await get_request_uid(websocket.headers)
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
    listeners[websocket] = names
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
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
