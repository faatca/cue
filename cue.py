import argparse
import asyncio
import getpass
import json
import logging
from pathlib import Path
import subprocess
import sys
import random
from cueclient import Client, authenticate

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
    run_parser.add_argument("--name", action="append", help="the cue name")
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

    authenticate(server, username, password)


def do_wait(args):
    client = Client()
    asyncio.run(client.wait(args.name))


def do_post(args):
    client = Client()
    client.post(args.name)


def do_on(args):
    client = Client()

    command = args.command
    if command[:1] == ["--"]:
        del command[0]

    flag_name = args.name

    async def hello():
        async for value in client.async_iter(flag_name):
            log.debug(f"Recieved flag: {value}")
            subprocess.run(command, shell=True)

    asyncio.run(hello())


def do_run(args):
    client = Client()

    if args.name:
        names = args.name
    else:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuv23456789"
        names = ["".join(random.choices(alphabet, k=5))]

    command = args.command
    if command[:1] == ["--"]:
        del command[0]

    print(f"Cue: {names}")

    log.info("Running command")
    subprocess.run(command, shell=True)

    log.info("Posting cue")
    client.post(names)


def do_list(args):
    for item in Client().list():
        print(item)


def load_config():
    config_path = Path.home() / ".config/cue.json"
    if not config_path.is_file():
        return None

    with config_path.open() as f:
        return json.load(f)


if __name__ == "__main__":
    main()
