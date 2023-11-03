import time
import json
import logging
from pathlib import Path

import httpx
from websockets.sync.client import connect
from websockets import WebSocketException
from yarl import URL

log = logging.getLogger(__name__)


class CueClient:
    def __init__(self):
        self.config = load_config()
        self._session = None

    def listen(self, flag_names):
        while True:
            query_parameters = [("name", flag_name) for flag_name in flag_names]
            socket_url = (self.config.socket_url / "api/listen").with_query(query_parameters)

            headers = {"AUTHORIZATION": f"Bearer {self.config.token}"}
            log.debug(f"Connecting: {socket_url}")
            try:
                with connect(str(socket_url), additional_headers=headers) as ws:
                    log.debug("Waiting for flag")
                    while True:
                        value = ws.recv()
                        log.debug(f"Recieved flag: {value}")
                        yield value
            except (ConnectionError, TimeoutError, WebSocketException):
                log.info("Connection error. Waiting to reconnect.")
                time.sleep(3)

    def post(self, flag_names):
        if self._session is None:
            headers = {"AUTHORIZATION": f"Bearer {self.config.token}"}
            self._session = httpx.Client(headers=headers)
        url = self.config.server_url / "api/cues"
        r = self._session.post(str(url), params={"name": flag_names}, json={})
        r.raise_for_status()


def authenticate(server_url, name):
    url = URL(server_url)
    r = httpx.post(str(url / "api/auth"), json={"name": name})
    r.raise_for_status()

    j = r.json()
    id = j["id"]
    token = j["token"]
    print("Authorize the new key:", url / "keyrequest" / id)
    print("Waiting for authorization")
    while True:
        r = httpx.get(str(url / "api/hello"), headers={"AUTHORIZATION": f"Bearer {token}"})
        if r.is_success:
            break
        time.sleep(10)

    print("Yes! We're in.")

    config_path = Path.home() / ".config/cue.json"
    if not config_path.parent.is_dir():
        config_path.parent.mkdir()

    with config_path.open("w") as f:
        json.dump({"server": server_url, "token": token}, f)


def load_config():
    config_path = Path.home() / ".config/cue.json"
    if not config_path.is_file():
        raise ConfigurationError("Authentication required")

    with config_path.open() as f:
        j = json.load(f)

    server_url = URL(j["server"])
    socket_scheme = SOCKET_URL_SCHEMES[server_url.scheme]
    socket_url = server_url.with_scheme(socket_scheme)
    return Config(server_url, socket_url, j["token"])


class Config:
    def __init__(self, server_url, socket_url, token):
        self.server_url = server_url
        self.socket_url = socket_url
        self.token = token


class Error(Exception):
    pass


class ConfigurationError(Error):
    pass


SOCKET_URL_SCHEMES = {"https": "wss", "http": "ws"}
