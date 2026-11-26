"""CLI surface for local archive operations."""

from dataclasses import asdict
from pathlib import Path

from .archive import MAX_BYTES, MAX_ENTRIES, discover_videos, extract_archive, repack_archive


def _limits(args):
    return {"max_entries": args.max_entries, "max_bytes": args.max_bytes}


def _extract(args):
    return asdict(extract_archive(args.path, args.destination, **_limits(args)))


def _repack(args):
    replacements = {name: Path(file) for name, file in args.replace}
    if len(replacements) != len(args.replace):
        raise ValueError("Multiple replacements for the same ZIP member")
    report = asdict(repack_archive(args.path, args.output, replacements, **_limits(args)))
    report["replaced"] = list(report["replaced"])
    return report


def _videos(args):
    return discover_videos(args.path, **_limits(args))


def add_commands(subparsers):
    command = subparsers.add_parser("archive", help="Extract, rebuild and inspect ZIP archives")
    actions = command.add_subparsers(dest="archive_action", required=True)
    for name, handler in (("extract", _extract), ("repack", _repack), ("videos", _videos)):
        parser = actions.add_parser(name)
        parser.add_argument("path", type=Path)
        parser.add_argument("--max-entries", type=int, default=MAX_ENTRIES)
        parser.add_argument("--max-bytes", type=int, default=MAX_BYTES)
        parser.set_defaults(technical_handler=handler)
        if name == "extract":
            parser.add_argument("destination", type=Path)
        elif name == "repack":
            parser.add_argument("output", type=Path)
            parser.add_argument("--replace", nargs=2, action="append", metavar=("MEMBER", "FILE"),
                                required=True)
