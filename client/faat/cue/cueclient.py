import base64
import json
import logging
from pathlib import Path
import time

import httpx
from websockets.sync.client import connect
from websockets import WebSocketException
from yarl import URL

log = logging.getLogger(__name__)


class CueClient:
    def __init__(self):
        self.config = load_config()
        self._session = None

    def listen(self, cue_names):
        while True:
            query_parameters = [("name", cue_name) for cue_name in cue_names]
            socket_url = (self.config.socket_url / "api/listen").with_query(query_parameters)

            headers = {"AUTHORIZATION": f"Bearer {self.config.key}"}
            log.debug(f"Connecting: {socket_url}")
            try:
                with connect(str(socket_url), additional_headers=headers) as ws:
                    log.debug("Waiting for cue")
                    while True:
                        value = json.loads(ws.recv())
                        if value["content"]:
                            value["content"] = base64.b64decode(value["content"])
                        yield value
            except (ConnectionError, TimeoutError, WebSocketException):
                log.info("Connection error. Waiting to reconnect.")
                time.sleep(3)

    def post(self, cue_names, content=None):
        if self._session is None:
            headers = {"AUTHORIZATION": f"Bearer {self.config.key}"}
            self._session = httpx.Client(headers=headers)
        if isinstance(content, str):
            content = content.encode("utf-8")
        url = self.config.server_url / "api/cues"
        r = self._session.post(str(url), params={"name": cue_names}, content=content)
        r.raise_for_status()


def authenticate(server_url, key_name, cue_pattern):
    url = URL(server_url)
    r = httpx.post(str(url / "api/auth"), json={"name": key_name, "pattern": cue_pattern})
    r.raise_for_status()

    j = r.json()
    id = j["id"]
    key = j["key"]
    print("Authorize the new key:", url / "keyrequest" / id)
    print("Waiting for authorization")
    while True:
        r = httpx.get(str(url / "api/hello"), headers={"AUTHORIZATION": f"Bearer {key}"})
        if r.is_success:
            break
        time.sleep(10)

    print("Yes! We're in.")

    config_path = Path.home() / ".config/cue.json"
    if not config_path.parent.is_dir():
        config_path.parent.mkdir()

    with config_path.open("w") as f:
        json.dump({"server": server_url, "key": key}, f)


def load_config():
    config_path = Path.home() / ".config/cue.json"
    if not config_path.is_file():
        raise ConfigurationError("Authentication required")

    with config_path.open() as f:
        j = json.load(f)

    server_url = URL(j["server"])
    socket_scheme = SOCKET_URL_SCHEMES[server_url.scheme]
    socket_url = server_url.with_scheme(socket_scheme)
    return Config(server_url, socket_url, j["key"])


class Config:
    def __init__(self, server_url, socket_url, key):
        self.server_url = server_url
        self.socket_url = socket_url
        self.key = key


class Error(Exception):
    pass


class ConfigurationError(Error):
    pass


SOCKET_URL_SCHEMES = {"https": "wss", "http": "ws"}
