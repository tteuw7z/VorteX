"""Single CLI entry point."""
import argparse
import json
from pathlib import Path
from .core import plan
from .archive import inventory
from . import __version__

def main(argv=None):
    parser = argparse.ArgumentParser(prog="vortex")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    route = commands.add_parser("plan")
    route.add_argument("task")
    route.add_argument("--agent-limit", type=int, default=3)
    archive = commands.add_parser("inventory")
    archive.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        result = plan(args.task, agent_limit=args.agent_limit) if args.command == "plan" else inventory(args.path)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
