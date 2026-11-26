"""Bind declarative workflows to the vetted local command registry."""
from argparse import ArgumentError, ArgumentParser
from pathlib import Path

from .automation import execute_manifest


# Names are operations on local data, never executable paths or shell commands.
_OPERATIONS = {
    ("archive", "videos"): "engineering",
    ("archive", "extract"): "engineering",
    ("archive", "repack"): "engineering",
    ("media", "probe"): "media",
    ("media", "frames"): "media",
    ("media", "edit"): "media",
    ("media", "qa"): "media",
    ("design", "audit"): "design",
    ("design", "preview"): "design",
    ("research", "synthesize"): "research",
    ("engineering", "inspect"): "engineering",
    ("engineering", "rebuild"): "engineering",
}


class _ManifestParser(ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.update(add_help=False, allow_abbrev=False, exit_on_error=False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        raise ValueError(f"Invalid automation arguments: {message}")


def add_commands(subparsers, technical_registrars):
    automation = subparsers.add_parser("automation", help="Plan or run approved local workflows")
    commands = automation.add_subparsers(dest="operation", required=True)
    parser = _ManifestParser(prog="vortex automation")
    nested = parser.add_subparsers(dest="command", required=True, parser_class=_ManifestParser)
    for register in technical_registrars:
        register(nested)

    def prepare(argv):
        capability = _OPERATIONS.get(argv[:2])
        if capability is None:
            raise ValueError(f"Operation is not enabled for automation: {' '.join(argv[:2])}")
        try:
            parsed = parser.parse_args(argv)
        except ArgumentError as exc:
            raise ValueError(f"Invalid automation arguments: {exc}") from exc
        return capability, lambda: parsed.technical_handler(parsed)

    def handle(args):
        simulate = args.operation == "plan"
        return execute_manifest(args.manifest, prepare, approvals=() if simulate else args.approve,
                                simulate=simulate)

    plan = commands.add_parser("plan", help="Validate a manifest without running tools")
    run = commands.add_parser("run", help="Execute stages whose approval labels were supplied")
    run.add_argument("--approve", action="append", default=[], metavar="LABEL")
    for command in (plan, run):
        command.add_argument("manifest", type=Path)
        command.set_defaults(technical_handler=handle)
