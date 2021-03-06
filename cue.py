import argparse
import asyncio
import getpass
import json
import logging
from pathlib import Path
import subprocess
import sys
import websockets
import random
import requests
from yarl import URL

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Global flag notification app")

    subparsers = parser.add_subparsers(dest="command", help="the command to execute")
    subparsers.required = True

    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("-v", "--verbose", action="store_true", help="show debug messages")

    auth_parser = subparsers.add_parser(
        "auth",
        description="Authenticates",
        help="authenticates",
        parents=[parent_parser],
    )
    auth_parser.add_argument("-u", "--user", help="the username")
    auth_parser.add_argument("-s", "--server", help="the server URL")
    auth_parser.set_defaults(func=do_auth)

    wait_parser = subparsers.add_parser(
        "wait",
        description="Waits for the cue",
        help="waits for the cue",
        parents=[parent_parser],
    )
    wait_parser.add_argument("name", nargs="+", help="the cue name to wait for")
    wait_parser.set_defaults(func=do_wait)

    post_parser = subparsers.add_parser(
        "post",
        description="Posts the cue",
        help="posts the cue",
        parents=[parent_parser],
    )
    post_parser.add_argument("name", nargs="+", help="the cue name to post")
    post_parser.set_defaults(func=do_post)

    on_parser = subparsers.add_parser(
        "on",
        description="Runs a command in response to a cue",
        help="runs a command in response to a cue",
        parents=[parent_parser],
    )
    on_parser.add_argument("name", help="the cue name")
    on_parser.add_argument("command", nargs=argparse.REMAINDER)
    on_parser.set_defaults(func=do_on)

    run_parser = subparsers.add_parser(
        "run",
        description="Runs a command and posts completion",
        help="runs a command and posts completion",
        parents=[parent_parser],
    )
    run_parser.add_argument("--name", help="the cue name")
    run_parser.add_argument("command", nargs=argparse.REMAINDER)
    run_parser.set_defaults(func=do_run)

    list_parser = subparsers.add_parser(
        "list",
        description="Lists the cues that are being monitored",
        help="lists the cues that are being monitored",
        parents=[parent_parser],
    )
    list_parser.set_defaults(func=do_list)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    )

    try:
        result = args.func(args)
    except Exception:
        log.exception("Unexpected error encountered")
        sys.exit(3)

    if result:
        sys.exit(int(result))


def do_auth(args):
    server = args.server or input("server url> ")
    username = args.user or input("user> ")
    password = getpass.getpass("password> ")

    url = URL(server)
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
        json.dump({"server": server, "username": username, "token": token}, f)


def do_wait(args):
    j = load_config()
    if not j:
        log.error("Authentication required. Use auth command.")
        return 2

    url = URL(j["server"])
    if url.scheme == "https":
        url = url.with_scheme("wss")
    elif url.scheme == "http":
        url = url.with_scheme("ws")
    else:
        raise ValueError(f"Invalid URL: {url}")

    token = j["token"]

    async def hello(flag_names):
        socket_url = (url / "listen").with_query([("name", name) for name in flag_names])
        headers = {"AUTHORIZATION": f"Bearer {token}"}
        log.debug(f"Connecting: {socket_url}")
        async with websockets.connect(str(socket_url), extra_headers=headers) as ws:
            log.debug("Waiting for flag")
            value = await ws.recv()
            log.debug(f"Received flag: {value}")

    asyncio.run(hello(args.name))


def do_post(args):
    j = load_config()
    if not j:
        log.error("Authentication required. Use auth command.")
        return 2

    url = URL(j["server"])
    token = j["token"]

    for name in args.name:
        r = requests.post(
            url / "cues" / name,
            json={"name": "yo"},
            headers={"AUTHORIZATION": f"Bearer {token}"},
        )
        r.raise_for_status()
        client_count = r.json()["clients"]
        print(f"Notified {client_count} listeners for {name}")


def do_on(args):
    j = load_config()
    if not j:
        log.error("Authentication required. Use auth command.")
        return 2

    url = URL(j["server"])
    if url.scheme == "https":
        url = url.with_scheme("wss")
    elif url.scheme == "http":
        url = url.with_scheme("ws")
    else:
        raise ValueError(f"Invalid URL: {url}")

    token = j["token"]

    command = args.command
    if command[:1] == ["--"]:
        del command[0]

    flag_name = args.name

    async def hello():
        while True:
            socket_url = (url / "listen").with_query({"name": flag_name})
            headers = {"AUTHORIZATION": f"Bearer {token}"}
            log.debug(f"Connecting: {socket_url}")
            try:
                async with websockets.connect(str(socket_url), extra_headers=headers) as ws:
                    log.debug("Waiting for flag")
                    while True:
                        value = await ws.recv()
                        log.debug(f"Recieved flag: {value}")
                        subprocess.run(command, shell=True)
            except websockets.ConnectionClosedError:
                log.debug("Connection closed. Waiting to reconnect")
                asyncio.sleep(3)

    asyncio.run(hello())


def do_run(args):
    j = load_config()
    if not j:
        log.error("Authentication required. Use auth command.")
        return 2

    url = URL(j["server"])
    token = j["token"]

    if args.name:
        name = args.name
    else:
        alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijklmnopqrstuv23456789'
        name = "".join(random.choices(alphabet, k=5))

    command = args.command
    if command[:1] == ["--"]:
        del command[0]

    print(f"Cue: {name}")

    log.info("Running command")
    subprocess.run(command, shell=True)

    log.info("Posting cue")
    r = requests.post(
        url / "cues" / name,
        json={"name": "yo"},
        headers={"AUTHORIZATION": f"Bearer {token}"},
    )
    r.raise_for_status()
    client_count = r.json()["clients"]

    log.info(f"Notified {client_count} listeners for {name}")


def do_list(args):
    j = load_config()
    if not j:
        log.error("Authentication required. Use auth command.")
        return 2

    url = URL(j["server"])
    token = j["token"]

    r = requests.get(url / "cues/", headers={"AUTHORIZATION": f"Bearer {token}"})
    r.raise_for_status()
    for item in r.json():
        print(item)


def load_config():
    config_path = Path.home() / ".config/cue.json"
    if not config_path.is_file():
        return None

    with config_path.open() as f:
        return json.load(f)


if __name__ == "__main__":
    main()
