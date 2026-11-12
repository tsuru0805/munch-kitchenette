"""Command line: ``kitchenette serve`` (or ``python -m kitchenette``)."""
from __future__ import annotations

import argparse
import logging
import sys

from . import __version__, config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kitchenette", description="A small kitchen for an AI companion.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="run the HTTP server (REST under /api, MCP at /mcp)")
    serve.add_argument("--config", help="path to a TOML settings file (default: ./kitchenette.toml if present)")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    check = sub.add_parser("check", help="load the settings, print them the way the file is written, and exit")
    check.add_argument("--config")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for line in config.unknown_env():       # a misspelt variable is ignored, but not silently
        print(line, file=sys.stderr)
    try:
        if args.command == "check":
            print(config.dump(config.load(args.config)), end="")
            return 0
        if args.command in (None, "serve"):
            cfg = config.load(getattr(args, "config", None))
            if getattr(args, "host", None):
                config.override(server_host=args.host)
            if getattr(args, "port", None):
                config.override(server_port=args.port)
    except config.ConfigError as e:
        # a settings mistake is the user's to fix: say which one and what it takes, no traceback
        for line in e.lines():
            print(line, file=sys.stderr)
        return 2
    if args.command in (None, "serve"):
        import uvicorn

        from .api import create_app
        uvicorn.run(create_app(), host=cfg.server_host, port=cfg.server_port, log_level="info")
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
