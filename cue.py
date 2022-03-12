import argparse
import asyncio
import getpass
import json
import logging
import subprocess
import sys
import websockets
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
        description="Waits for the flag to be posted",
        help="waits for the flag to be posted",
        parents=[parent_parser],
    )
    wait_parser.add_argument("name", help="the flag name to wait for")
    wait_parser.set_defaults(func=do_wait)

    post_parser = subparsers.add_parser(
        "post",
        description="Posts the flag",
        help="posts the flag",
        parents=[parent_parser],
    )
    post_parser.add_argument("name", help="the flag name to post for")
    post_parser.set_defaults(func=do_post)

    on_parser = subparsers.add_parser(
        "on",
        description="Runs a command in response to a flag",
        help="runs a command in response to a flag",
        parents=[parent_parser],
    )
    on_parser.add_argument("name", help="the flag name to on for")
    on_parser.add_argument("command", nargs=argparse.REMAINDER)
    on_parser.set_defaults(func=do_on)

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

    with open(".cue", "w") as f:
        json.dump({"server": server, "username": username, "token": token}, f)


def do_wait(args):
    with open(".cue") as f:
        j = json.load(f)

    url = URL(j["server"]).with_scheme("ws")
    token = j["token"]

    async def hello(flag_name):
        socket_url = str(url / "p" / flag_name / "listen")
        headers = {"AUTHORIZATION": f"Bearer {token}"}
        log.debug(f"Connecting: {socket_url}")
        async with websockets.connect(socket_url, extra_headers=headers) as ws:
            log.debug("Waiting for flag")
            value = await ws.recv()
            log.debug(f"Received flag: {value}")

    asyncio.run(hello(args.name))


def do_post(args):
    with open(".cue") as f:
        j = json.load(f)

    url = URL(j["server"])
    token = j["token"]

    r = requests.post(
        url / "p" / args.name / "post",
        json={"name": "yo"},
        headers={"AUTHORIZATION": f"Bearer {token}"},
    )
    r.raise_for_status()
    client_count = r.json()["clients"]
    print(f"Notified {client_count} clients")


def do_on(args):
    with open(".cue") as f:
        j = json.load(f)

    url = URL(j["server"]).with_scheme("ws")
    token = j["token"]

    command = args.command
    if command[:1] == ["--"]:
        del command[0]

    flag_name = args.name

    async def hello():
        socket_url = str(url / "p" / flag_name / "listen")
        headers = {"AUTHORIZATION": f"Bearer {token}"}
        log.debug(f"Connecting: {socket_url}")
        async with websockets.connect(socket_url, extra_headers=headers) as ws:
            log.debug("Waiting for flag")
            while True:
                value = await ws.recv()
                log.debug(f"Recieved flag: {value}")
                subprocess.run(command, shell=True)

    asyncio.run(hello())


if __name__ == "__main__":
    main()
