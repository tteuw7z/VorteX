"""Export the real parser and planning catalog without executing commands."""
import argparse
from dataclasses import asdict
import json
import re
import sys

from .agents import AgentEngine
from .cli import build_parser
from .skills import SKILLS


def commands(parser, prefix=()):
    """Walk registered subcommands; no handler is invoked."""
    rows = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                path = (*prefix, name)
                rows.append({"path": list(path),
                             "arguments": [
                                 {"name": item.dest, "flags": item.option_strings,
                                  "required": bool(item.required)}
                                 for item in child._actions
                                 if not isinstance(item, (argparse._SubParsersAction, argparse._HelpAction))
                             ]})
                rows.extend(commands(child, path))
    return rows


def export(source_sha):
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("Expected immutable source commit")
    return {"schema": 1, "source_sha": source_sha,
            "skills": [asdict(skill) for skill in SKILLS],
            "agents": [asdict(agent) for agent in AgentEngine().catalog()],
            "commands": commands(build_parser()),
            "execution": "host_binding_required",
            "delivery_authorized": False}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m vortex.live_catalog SOURCE_SHA")
    print(json.dumps(export(sys.argv[1]), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
