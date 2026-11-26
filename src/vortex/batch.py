"""Apply proven media operations to each video candidate in a ZIP or directory."""
import json
import math
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from .archive import MAX_BYTES, MAX_ENTRIES, _publish, discover_videos, extract_archive
from .media import extract_frames, probe
from .transcription import transcribe


def _inspect(file, directory, *, interval, max_frames, model, language):
    try:
        metadata = probe(file)
        if metadata["video"] is None:
            raise ValueError("No video stream")
    except (ValueError, OSError) as exc:
        return {"status": "FAILED", "errors": {"probe": str(exc)}}

    directory.mkdir()
    row = {"status": "SUCCESS", "metadata": metadata, "errors": {},
           "transcript": {"status": "NOT_REQUESTED" if model is None else "NO_AUDIO"}}
    try:
        pictures = extract_frames(file, directory / "frames", interval=interval, max_frames=max_frames)
        if pictures["source_sha256"] != metadata["source_sha256"]:
            raise ValueError("Source changed during inspection")
        row["frames"] = {"manifest": f"{directory.name}/frames/frames.json",
                         "count": len(pictures["frames"]), "capped": pictures["capped"]}
    except (ValueError, OSError) as exc:
        row["errors"]["frames"] = str(exc)
    if model is not None and metadata["audio"] is not None:
        try:
            transcript = transcribe(file, directory / "transcript", model=model, language=language)
            if transcript["source_sha256"] != metadata["source_sha256"]:
                raise ValueError("Source changed during transcription")
            row["transcript"] = {"status": "TRANSCRIBED", "language": transcript["language"],
                                 "manual_reviewed": False,
                                 "manifest": f"{directory.name}/transcript/transcript.json"}
        except (ValueError, OSError) as exc:
            row["errors"]["transcription"] = str(exc)
            row["transcript"] = {"status": "FAILED"}
    if row["errors"] or row.get("frames", {}).get("capped"):
        row["status"] = "PARTIAL"
    return row


def inspect_batch(source: Path, output: Path, *, interval: float = 2, max_frames: int = 500,
                  model: Path | None = None, language: str = "auto",
                  max_entries: int = MAX_ENTRIES, max_bytes: int = MAX_BYTES) -> dict:
    if not math.isfinite(interval) or interval <= 0 or type(max_frames) is not int or not 1 <= max_frames <= 10000:
        raise ValueError("Use a positive interval and a frame limit between 1 and 10000")
    for tool in ("ffprobe", "ffmpeg"):
        if shutil.which(tool) is None:
            raise FileNotFoundError(f"{tool} is required for batch inspection")
    if model is not None:
        model = model.resolve(strict=True)
        if not model.is_file():
            raise ValueError("The ASR model must be a local file")
        if shutil.which("whisper-cli") is None:
            raise FileNotFoundError("whisper-cli is required when an ASR model is requested")
    source = source.resolve(strict=True)
    output = output.parent.resolve() / output.name
    if source.is_dir() and output.is_relative_to(source):
        raise ValueError("Choose an output directory outside the input tree")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output already exists: {output}")
    candidates = discover_videos(source, max_entries=max_entries, max_bytes=max_bytes)
    if not candidates:
        raise ValueError("No video candidates found in the source")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".vortex-batch-", dir=output.parent) as staging:
        root = source
        if not source.is_dir():
            root = Path(staging) / "source"
            extract_archive(source, root, max_entries=max_entries, max_bytes=max_bytes)
        prepared = Path(staging) / "result"
        prepared.mkdir()
        rows = []
        for index, candidate in enumerate(candidates, 1):
            relative = candidate["path"]
            row = _inspect(root / relative, prepared / f"video_{index:04}", interval=interval,
                           max_frames=max_frames, model=model, language=language)
            rows.append({"path": relative, **row})
        total_success = sum(row["status"] == "SUCCESS" for row in rows)
        report = {"status": ("SUCCESS" if total_success == len(rows) else
                             "FAILED" if all(row["status"] == "FAILED" for row in rows) else "PARTIAL"),
                  "candidates": len(rows), "complete": total_success, "videos": rows}
        manifest = prepared / "batch.json"
        with manifest.open("x", encoding="utf-8") as target:
            json.dump(report, target, ensure_ascii=False, indent=2)
            target.write("\n")
        _publish(prepared, output)
    return {**report, "manifest": str(output / "batch.json")}
