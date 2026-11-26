"""CLI entry points for the media, speech and editor capabilities."""

from pathlib import Path

from .batch_cli import add_command as add_batch_command
from .editor import render
from .media import check_media, extract_frames, probe
from .transcription import transcribe

_FRAME_RATES = (24, 25, 30, 48, 50, 60)


def _edit(args):
    if args.cut and (args.start is not None or args.end is not None):
        raise ValueError("Use --cut or --start/--end")
    ranges = args.cut
    if args.start is not None or args.end is not None:
        ranges = [(args.start or "0", args.end)]
    return render(args.source, args.output, ranges=ranges, fps=args.fps,
                  captions=args.captions, full_hd=args.full_hd, monochrome=args.monochrome,
                  fade=args.fade, effects=args.effect, contrast=args.contrast)


def add_commands(subparsers):
    group = subparsers.add_parser("media", help="Inspect, transcribe and edit local media")
    operations = group.add_subparsers(dest="media_operation", required=True)
    add_batch_command(operations)

    inspect = operations.add_parser("probe", help="Inspect primary video and audio tracks")
    inspect.add_argument("source", type=Path)
    inspect.set_defaults(technical_handler=lambda args: probe(args.source))

    frames = operations.add_parser("frames", help="Sample frames with source timecodes")
    frames.add_argument("source", type=Path)
    frames.add_argument("output", type=Path)
    frames.add_argument("--interval", default="2")
    frames.add_argument("--scene-threshold", default="0.30")
    frames.add_argument("--max-frames", type=int, default=500)
    frames.add_argument("--ocr-language", help="Read on-screen text using installed Tesseract data")
    frames.set_defaults(technical_handler=lambda args: extract_frames(
        args.source, args.output, interval=args.interval, scene_threshold=args.scene_threshold,
        max_frames=args.max_frames, ocr_language=args.ocr_language,
    ))

    qa = operations.add_parser("qa", help="Check frame cadence, tracks and optional SRT")
    qa.add_argument("source", type=Path)
    qa.add_argument("--fps", type=int, choices=_FRAME_RATES, default=60)
    qa.add_argument("--orientation", choices=("any", "horizontal", "vertical"), default="any")
    qa.add_argument("--allow-no-audio", action="store_true")
    qa.add_argument("--subtitle", type=Path)
    qa.set_defaults(technical_handler=lambda args: check_media(
        args.source, fps=args.fps, orientation=args.orientation, require_audio=not args.allow_no_audio,
        subtitle=args.subtitle,
    ))

    speech = operations.add_parser("transcribe", help="Local whisper-cli speech recognition")
    speech.add_argument("source", type=Path)
    speech.add_argument("output", type=Path)
    speech.add_argument("--model", type=Path, required=True, help="Local whisper.cpp model file")
    speech.add_argument("--language", default="auto")
    speech.add_argument("--fps", type=int, choices=_FRAME_RATES, default=60)
    speech.add_argument("--threads", type=int, default=4)
    speech.set_defaults(technical_handler=lambda args: transcribe(
        args.source, args.output, model=args.model, language=args.language, fps=args.fps,
        threads=args.threads,
    ))

    edit = operations.add_parser("edit", help="Render cuts and optional progressive captions")
    edit.add_argument("source", type=Path)
    edit.add_argument("output", type=Path)
    edit.add_argument("--cut", nargs=2, metavar=("START", "END"), action="append",
                      help="Repeat for ordered source intervals in seconds")
    edit.add_argument("--start", help="Single source cut start in seconds")
    edit.add_argument("--end", help="Single source cut end in seconds")
    edit.add_argument("--fps", type=int, choices=_FRAME_RATES, default=60)
    edit.add_argument("--captions", type=Path, help="SRT or transcript JSON for the source")
    edit.add_argument("--full-hd", action="store_true", help="Fit to landscape or portrait Full HD")
    edit.add_argument("--monochrome", action="store_true")
    edit.add_argument("--fade", default="0", help="Audio and video fades in seconds")
    edit.add_argument("--effect", action="append", nargs=4, metavar=("KIND", "START", "END", "STRENGTH"),
                      help="Flash, shake or blur over output seconds, strength (0,1]; repeatable")
    edit.add_argument("--contrast", default="1", help="Contrast multiplier from 0.8 to 1.4")
    edit.set_defaults(technical_handler=_edit)
