import asyncio
import logging
import getpass
from posixpath import join as urljoin
import socket

import httpx

from .keydb import KeyDB

log = logging.getLogger(__name__)


async def authenticate(config_path, url, key_name, cue_pattern):
    if key_name is None:
        user = getpass.getuser()
        host = socket.gethostname()
        requested_name = f"{user}@{host} - default"
    else:
        requested_name = key_name

    async with httpx.AsyncClient(base_url=url) as session:
        r = await session.post("api/auth", json={"name": requested_name, "pattern": cue_pattern})
        r.raise_for_status()
        j = r.json()

        id = j["id"]
        key = j["key"]

        print("Authorize the new key here:", urljoin(url, "keyrequest", id))
        print("Waiting for authorization")

        while True:
            r = await session.get("api/hello", headers={"AUTHORIZATION": f"Bearer {key}"})
            if r.is_success:
                break
            await asyncio.sleep(10)

        print("Yes! We're in.")
        if not config_path.parent.is_dir():
            config_path.parent.mkdir()

        KeyDB(config_path).add(key_name or "default", url, key)
