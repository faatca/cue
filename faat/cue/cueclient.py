import asyncio
import json
import logging
from pathlib import Path

import requests
import websockets
from yarl import URL

log = logging.getLogger(__name__)


class CueClient:
    def __init__(self):
        self.config = load_config()

    async def listen(self, flag_names):
        while True:
            query_parameters = [("name", flag_name) for flag_name in flag_names]
            socket_url = (self.config.socket_url / "listen").with_query(query_parameters)

            headers = {"AUTHORIZATION": f"Bearer {self.config.token}"}
            log.debug(f"Connecting: {socket_url}")
            try:
                async with websockets.connect(str(socket_url), extra_headers=headers) as ws:
                    log.debug("Waiting for flag")
                    while True:
                        value = await ws.recv()
                        log.debug(f"Recieved flag: {value}")
                        yield value
            except (ConnectionError, TimeoutError, websockets.WebSocketException):
                log.debug("Connection error. Waiting to reconnect.")
                await asyncio.sleep(3)

    def post(self, flag_names):
        url = self.config.server_url / "cues/"
        headers = {"AUTHORIZATION": f"Bearer {self.config.token}"}
        r = requests.post(url, headers=headers, params={"name": flag_names}, json={})
        r.raise_for_status()
        client_count = r.json()["listeners"]
        print(f"Notified {client_count} listeners for {flag_names}")

    def list(self):
        url = self.config.server_url / "connections/"
        headers = {"AUTHORIZATION": f"Bearer {self.config.token}"}
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        return list(r.json())


def authenticate(server_url, username, password):
    url = URL(server_url)
    r = requests.post(url / "auth", json={"username": username, "password": password})
    if r.status_code == 401:
        log.error("Authentication failed")
        return 2
    r.raise_for_status()

    token = r.json()["token"]

    config_path = Path.home() / ".config/cue.json"
    if not config_path.parent.is_dir():
        config_path.parent.mkdir()

    with config_path.open("w") as f:
        json.dump({"server": server_url, "username": username, "token": token}, f)


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
