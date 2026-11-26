"""Local design, research, and engineering command parsers."""

import json
from pathlib import Path

from . import design, engineering, research, interface


def _document(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Manifest is not a regular file: {path}")
    with path.open("rb") as source:
        data = source.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("Manifest exceeds 2 MiB")
    return json.loads(data.decode("utf-8-sig"))


def _design_audit(args):
    return design.audit(_document(args.tokens))


def _design_preview(args):
    return design.preview(_document(args.tokens), args.output)


def _research_synthesize(args):
    return research.synthesize(_document(args.manifest), args.source_root or args.manifest.parent)


def _engineering_inspect(args):
    return engineering.inspect_project(args.project)


def _engineering_rebuild(args):
    supplemental = None
    if args.supplemental is not None:
        supplemental = _document(args.supplemental), args.supplemental.parent
    return engineering.rebuild(
        _document(args.spec), args.candidate, source_root=args.source_root or args.spec.parent,
        reference_source=args.reference_source, supplemental=supplemental,
    )


def add_commands(subparsers):
    """Attach handlers to the main parser without changing its dispatch contract."""
    commands = subparsers.add_parser("design", help="Validate design tokens and generate a preview")
    design_commands = commands.add_subparsers(dest="design_action", required=True)
    audit = design_commands.add_parser("audit", help="Check declared text contrast")
    audit.add_argument("tokens", type=Path)
    audit.set_defaults(technical_handler=_design_audit)
    preview = design_commands.add_parser("preview", help="Write a local HTML token sheet")
    preview.add_argument("tokens", type=Path)
    preview.add_argument("output", type=Path)
    preview.set_defaults(technical_handler=_design_preview)

    motion = design_commands.add_parser("motion", help="Generate an offline Motion UI candidate")
    motion.add_argument("output", type=Path)
    motion.add_argument("--mode", choices=("menu", "gallery"), default="menu")
    motion.add_argument("--locale", choices=("pt-BR", "en"), default="pt-BR")
    motion.add_argument("--still", action="store_true")
    motion.set_defaults(technical_handler=lambda args: interface.write_preview(
        args.output, mode=args.mode, locale=args.locale, still=args.still))

    commands = subparsers.add_parser("research", help="Organize local evidence and citations")
    research_commands = commands.add_subparsers(dest="research_action", required=True)
    synthesis = research_commands.add_parser("synthesize", help="Verify exact cited excerpts")
    synthesis.add_argument("manifest", type=Path)
    synthesis.add_argument("--source-root", type=Path)
    synthesis.set_defaults(technical_handler=_research_synthesize)

    commands = subparsers.add_parser("engineering", help="Inspect authorized Python source")
    engineering_commands = commands.add_subparsers(dest="engineering_action", required=True)
    inspect = engineering_commands.add_parser("inspect", help="Check Python source and imports")
    inspect.add_argument("project", type=Path)
    inspect.set_defaults(technical_handler=_engineering_inspect)
    rebuild = engineering_commands.add_parser("rebuild", help="Run Study, Build, and Check")
    rebuild.add_argument("spec", type=Path)
    rebuild.add_argument("candidate", type=Path)
    rebuild.add_argument("--source-root", type=Path)
    rebuild.add_argument("--reference-source", type=Path,
                         help="Optional reference project whose source you are authorized to inspect")
    rebuild.add_argument("--supplemental", type=Path,
                         help="Optional secondary evidence manifest for gaps from Study")
    rebuild.set_defaults(technical_handler=_engineering_rebuild)
