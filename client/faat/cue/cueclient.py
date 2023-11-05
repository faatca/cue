import base64
import json
import logging
from pathlib import Path
from posixpath import join as urljoin
from urllib.parse import urlparse, urlencode
import time

import httpx
from websockets.sync.client import connect
from websockets import WebSocketException

log = logging.getLogger(__name__)


class CueClient:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = Path.home() / ".config/cue.json"
        self.config = load_config(config_path)
        self._session = None

    def listen(self, cue_names):
        while True:
            socket_url = (
                urlparse(urljoin(self.config.socket_url, "api/listen"))
                ._replace(query=urlencode({"name": cue_names}, doseq=True))
                .geturl()
            )

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
        url = urljoin(self.config.server_url, "api/cues")
        r = self._session.post(str(url), params={"name": cue_names}, content=content)
        r.raise_for_status()


def authenticate(config_path, server_url, key_name, cue_pattern):
    r = httpx.post(urljoin(server_url, "api/auth"), json={"name": key_name, "pattern": cue_pattern})
    r.raise_for_status()

    j = r.json()
    id = j["id"]
    key = j["key"]
    print("Authorize the new key here:", urljoin(server_url, "keyrequest", id))
    print("Waiting for authorization")
    while True:
        r = httpx.get(urljoin(server_url, "api/hello"), headers={"AUTHORIZATION": f"Bearer {key}"})
        if r.is_success:
            break
        time.sleep(10)

    print("Yes! We're in.")

    if not config_path.parent.is_dir():
        config_path.parent.mkdir()

    with config_path.open("w") as f:
        json.dump({"server": server_url, "key": key}, f)


def load_config(config_path):
    try:
        with config_path.open() as f:
            j = json.load(f)
    except FileNotFoundError:
        raise ConfigurationError("Authentication required")

    server_url = j["server"]
    parsed_server_url = urlparse(server_url)
    socket_scheme = SOCKET_URL_SCHEMES[parsed_server_url.scheme]

    socket_url = parsed_server_url._replace(scheme=socket_scheme).geturl()
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
