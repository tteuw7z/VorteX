"""Single CLI entry point."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from zipfile import BadZipFile

from . import __version__
from .agents import AgentEngine
from .android_cli import add_commands as add_android_commands
from .archive_cli import add_commands as add_archive_commands
from .automation_cli import add_commands as add_automation_commands
from .archive import inventory
from .config import Config
from .context import ContextEngine
from .core import plan
from .learning import LearningEngine
from .remote import add_commands as add_remote_commands
from .security_cli import add_commands as add_security_commands
from .media_cli import add_commands as add_media_commands
from .methods_cli import add_commands as add_methods_commands
from .skills import SkillEngine
from .workflow import Status, report_status


_TECHNICAL_COMMANDS = (add_android_commands, add_archive_commands,
                       add_media_commands, add_methods_commands)


def _learning(args, config):
    if config.learning_db is None:
        raise ValueError("Set learning_db in the explicit --config file")
    engine = LearningEngine(config.learning_db)
    match args.operation:
        case "add":
            return {"id": engine.remember(args.capability, args.technique, args.source, args.evidence)}
        case "list":
            return engine.recall(args.capability)
        case "remove":
            return {"removed": engine.forget(args.id)}


def _dispatch(args, config):
    if handler := getattr(args, "technical_handler", None):
        return handler(args)
    match args.command:
        case "plan" | "knowledge":
            limit = config.agent_limit if args.agent_limit is None else args.agent_limit
            result = plan(args.task, agent_limit=limit, skills=SkillEngine(enabled=config.skills))
            if args.command == "knowledge":
                result["profiles"] = [asdict(profile)
                                      for profile in AgentEngine().load(result["agents"])]
                if config.learning_db is not None:
                    learning = LearningEngine(config.learning_db)
                    result["learned"] = [entry for skill in result["skills"]
                                         for entry in learning.recall(skill["name"])]
            return result
        case "inventory":
            return inventory(args.path)
        case "context":
            data = json.loads(args.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.keys() != {"checkpoint", "observations"}:
                raise ValueError("Context JSON requires checkpoint and observations objects")
            return ContextEngine(threshold=config.context_threshold).compact(**data).summary()
        case "learn":
            return _learning(args, config)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="vortex")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", type=Path, help="Read settings from an explicit TOML file")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "knowledge"):
        route = commands.add_parser(name)
        route.add_argument("task")
        route.add_argument("--agent-limit", type=int)
    commands.add_parser("inventory").add_argument("path", type=Path)
    commands.add_parser("context").add_argument("path", type=Path)
    learn = commands.add_parser("learn").add_subparsers(dest="operation", required=True)
    add = learn.add_parser("add")
    for name in ("capability", "technique", "source", "evidence"):
        add.add_argument(name)
    learn.add_parser("list").add_argument("--capability")
    learn.add_parser("remove").add_argument("id", type=int)
    for register in _TECHNICAL_COMMANDS:
        register(commands)
    add_automation_commands(commands, _TECHNICAL_COMMANDS)
    add_remote_commands(commands)
    add_security_commands(commands)
    args = parser.parse_args(argv)
    try:
        config = Config.load(args.config) if args.config else Config()
        result = _dispatch(args, config)
    except (ValueError, OSError, BadZipFile, sqlite3.Error) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    if getattr(args, "technical_handler", None):
        if report_status(result) in (Status.FAILED, Status.BLOCKED):
            return 1
    return 0
