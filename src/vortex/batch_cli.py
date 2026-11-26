"""CLI for batch video indexing, sampling and optional transcription."""
from pathlib import Path

from .archive import MAX_BYTES, MAX_ENTRIES
from .batch import inspect_batch


def _execute(args):
    return inspect_batch(args.source, args.output, interval=args.interval, max_frames=args.max_frames,
                         model=args.model, language=args.language,
                         max_entries=args.max_entries, max_bytes=args.max_bytes)


def add_command(media_commands):
    batch = media_commands.add_parser("batch", help="Inspect every video candidate in a folder or ZIP")
    batch.add_argument("source", type=Path)
    batch.add_argument("output", type=Path)
    batch.add_argument("--interval", type=float, default=2.0)
    batch.add_argument("--max-frames", type=int, default=500)
    batch.add_argument("--model", type=Path, help="Transcribe audio using the selected local Whisper model")
    batch.add_argument("--language", default="auto")
    batch.add_argument("--max-entries", type=int, default=MAX_ENTRIES)
    batch.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    batch.set_defaults(technical_handler=_execute)
