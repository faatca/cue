import argparse
import asyncio
import logging
from pathlib import Path
import random
import shlex
from subprocess import list2cmdline, run
import sys
from . import connect_async
from .keyprovisioning import authenticate

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Global flag notification app")

    subparsers = parser.add_subparsers(dest="command", help="the command to execute")
    subparsers.required = True

    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("-v", "--verbose", action="store_true", help="show debug messages")
    parent_parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".config/cue.json",
        help="path to settings file",
    )
    parent_parser.add_argument("-k", "--key", help="a name for the API key to use")

    auth_parser = subparsers.add_parser(
        "auth",
        description="Authenticates",
        help="authenticates",
        parents=[parent_parser],
    )
    auth_parser.add_argument("-p", "--pattern", help="limits access to cues of this glob pattern")
    auth_parser.add_argument("url", help="the server URL")
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
    post_parser.add_argument("--content", help="optional payload to include with the cue")
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

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.DEBUG if args.verbose else logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.DEBUG if args.verbose else logging.WARNING)

    try:
        result = asyncio.run(args.func(args))
    except Exception:
        log.exception("Unexpected error encountered")
        sys.exit(3)

    if result:
        sys.exit(int(result))


async def do_auth(args):
    try:
        await authenticate(args.config, args.url, args.key, args.pattern)
    except KeyboardInterrupt:
        pass


async def do_wait(args):
    try:
        async with connect_async(config_path=args.config, key_name=args.key) as client:
            async for event in client.listen(args.name):
                break
    except asyncio.CancelledError:
        return 4


async def do_post(args):
    async with connect_async(config_path=args.config, key_name=args.key) as client:
        await client.post(args.name, args.content)


async def do_on(args):
    command = list(args.command)
    if command[:1] == ["--"]:
        del command[0]
    cmd = (
        command[0]
        if len(command) == 1
        else list2cmdline(command)
        if sys.platform == "win32"
        else shlex.join(command)
    )
    flag_names = set(n.strip() for n in args.name.split(","))

    try:
        async with connect_async(config_path=args.config, key_name=args.key) as client:
            try:
                async for event in client.listen(flag_names):
                    log.debug(f"Recieved event: {event}")
                    log.debug(f"Running command: {cmd=}")
                    p = await asyncio.create_subprocess_shell(cmd)
                    await p.wait()
                    log.debug(f"Command finished: {p.returncode}")
            except KeyboardInterrupt:
                log.debug("Closed")
    except asyncio.CancelledError:
        return 4


async def do_run(args):
    if args.name:
        names = args.name
    else:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuv23456789"
        cue_name = "auto." + "".join(random.choices(alphabet, k=5))
        print(f"Using random cue name: {cue_name}")
        names = [cue_name]

    command = list(args.command)
    if command[:1] == ["--"]:
        del command[0]
    cmd = (
        command[0]
        if len(command) == 1
        else list2cmdline(command)
        if sys.platform == "win32"
        else shlex.join(command)
    )
    try:
        with connect_async(config_path=args.config, key_name=args.key) as client:
            log.info("Running command")
            p = await asyncio.create_subprocess_shell(command)
            await p.wait()

            log.info("Posting cue")
            await client.post(names)
    except asyncio.CancelledError:
        return 4


if __name__ == "__main__":
    main()
