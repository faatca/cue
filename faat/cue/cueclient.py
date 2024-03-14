import asyncio
import base64
import json
import logging
from posixpath import join as urljoin
from urllib.parse import urlparse, urlencode
import time

import httpx
import websockets.sync.client
import websockets.client
from websockets import WebSocketException

log = logging.getLogger(__name__)


class CueClient:
    def __init__(self, url, key):
        self.url = url
        self.key = key
        self._session = httpx.Client(base_url=url, headers={"AUTHORIZATION": f"Bearer {key}"})

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self._session.close()

    def listen(self, cue_names):
        socket_url = get_socket_url(self.url, cue_names)
        headers = {"AUTHORIZATION": f"Bearer {self.key}"}

        while True:
            log.debug(f"Connecting: {socket_url}")
            try:
                with websockets.sync.client.connect(
                    str(socket_url), additional_headers=headers
                ) as ws:
                    log.debug("Waiting for cue")
                    while True:
                        value = json.loads(ws.recv())
                        if value["content"]:
                            value["content"] = base64.b64decode(value["content"])
                        yield value
            except (ConnectionError, TimeoutError, WebSocketException, FileNotFoundError):
                log.info("Connection error. Waiting to reconnect.")
                time.sleep(3)

    def post(self, cue_names, content=None):
        if isinstance(content, str):
            content = content.encode("utf-8")
        r = self._session.post("api/cues", params={"name": cue_names}, content=content)
        r.raise_for_status()


class AsyncCueClient:
    def __init__(self, url, key):
        self.url = url
        self.key = key
        self._session = httpx.AsyncClient(base_url=url, headers={"AUTHORIZATION": f"Bearer {key}"})

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def close(self):
        await self._session.aclose()

    async def listen(self, cue_names):
        socket_url = get_socket_url(self.url, cue_names)
        headers = {"AUTHORIZATION": f"Bearer {self.key}"}

        while True:
            log.debug(f"Connecting: {socket_url}")
            try:
                async with websockets.client.connect(str(socket_url), extra_headers=headers) as ws:
                    log.debug("Waiting for cue")
                    while True:
                        value = json.loads(await ws.recv())
                        if value["content"]:
                            value["content"] = base64.b64decode(value["content"])
                        yield value
            except (ConnectionError, TimeoutError, WebSocketException, FileNotFoundError):
                log.info("Connection error. Waiting to reconnect.")
                await asyncio.sleep(3)

    async def post(self, cue_names, content=None):
        if isinstance(content, str):
            content = content.encode("utf-8")
        r = await self._session.post("api/cues", params={"name": cue_names}, content=content)
        r.raise_for_status()


def get_socket_url(url, cue_names):
    u = urlparse(url)
    socket_scheme = SOCKET_URL_SCHEMES[u.scheme]
    return (
        u._replace(scheme=socket_scheme)
        ._replace(query=urlencode({"name": cue_names}, doseq=True))
        ._replace(path=urljoin(u.path, "/api/listen"))
        .geturl()
    )


SOCKET_URL_SCHEMES = {"https": "wss", "http": "ws"}
