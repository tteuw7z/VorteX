"""Local media inspection, timecoded frame sampling and delivery checks."""

from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory

from .evidence import file_sha256
from .process_env import tool_environment
from .private_io import restrict_file

# Playlist and script demuxers are deliberately absent. Local paths alone do
# not prevent an input playlist from dereferencing other files.
_INPUT_OPTIONS = (
    "-protocol_whitelist", "file",
    "-format_whitelist", "mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,avi,mpeg,"
    "mpegts,flv,mxf,wav,mp3,aac,flac,ogg,asf,amr,aiff",
)


def _local_file(path: Path | str) -> Path:
    file = Path(path).resolve(strict=True)
    if not file.is_file():
        raise ValueError(f"Expected a local file: {path}")
    return file


def _destination(path: Path | str) -> Path:
    target = Path(path)
    if target.exists() or target.is_symlink():
        raise ValueError(f"Output already exists: {target}")
    destination = target.absolute()
    if not destination.parent.is_dir():
        raise ValueError(f"Output directory does not exist: {destination.parent}")
    return destination


def _run_tool(name: str, args, operation: str, *, cwd=None, timeout=300) -> subprocess.CompletedProcess:
    executable = shutil.which(name)
    if executable is None:
        raise FileNotFoundError(f"{name} is required for {operation}")
    try:
        result = subprocess.run([executable, *args], cwd=cwd, stdin=subprocess.DEVNULL, env=tool_environment(),
                                capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"{name} timed out during {operation}") from exc
    if result.returncode:
        # Tool logs can include embedded metadata or unrelated absolute paths.
        raise ValueError(f"{name} could not complete {operation} (exit {result.returncode})")
    return result


def _publish_directory(stage: Path, target: Path) -> None:
    # Reserve the destination exclusively and clean up only paths that we wrote.
    target.mkdir(mode=0o700)
    written = []
    try:
        for source in sorted(stage.iterdir()):
            output = target / source.name
            restrict_file(source)
            os.link(source, output)
            written.append(output)
    except BaseException:
        for output in written:
            output.unlink(missing_ok=True)
        try:
            target.rmdir()
        except OSError:
            pass
        raise


def _decimal(value, *, positive=False) -> Decimal:
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Expected a finite number") from exc
    if not number.is_finite() or (positive and number <= 0):
        raise ValueError("Expected a positive finite number" if positive else "Expected a finite number")
    return number


def _seconds(value) -> float | None:
    if value in (None, "N/A"):
        return None
    return float(_decimal(value))


def _fraction(value) -> Fraction | None:
    if value in (None, "", "N/A", "0/0"):
        return None
    return Fraction(str(value))


def _media_info(file: Path) -> dict:
    result = _run_tool("ffprobe", [
        "-v", "error", *_INPUT_OPTIONS, "-show_format", "-show_streams", "-of", "json", str(file),
    ], "media inspection")
    return json.loads(result.stdout)


def _primary_tracks(info: dict):
    streams = info.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"
                  and not stream.get("disposition", {}).get("attached_pic")), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    return video, audio


def _timeline(info: dict, stream: dict) -> tuple[Decimal, Decimal | None]:
    container = info.get("format", {})
    start = stream.get("start_time")
    if start in (None, "N/A"):
        start = container.get("start_time")
    origin = _decimal(0 if start in (None, "N/A") else start)
    duration = stream.get("duration")
    if duration not in (None, "N/A"):
        return origin, _decimal(duration, positive=True)
    duration = container.get("duration")
    if duration in (None, "N/A"):
        return origin, None
    container_start = container.get("start_time")
    relative = origin - _decimal(0 if container_start in (None, "N/A") else container_start)
    return origin, max(Decimal(0), _decimal(duration, positive=True) - relative)


def _dimensions(stream: dict) -> tuple[int, int]:
    rotation = next((item["rotation"] for item in stream.get("side_data_list", [])
                     if "rotation" in item), 0)
    width, height = int(stream["width"]), int(stream["height"])
    return (height, width) if rotation % 180 == 90 else (width, height)


def _probe_result(file: Path, info: dict) -> dict:
    video, audio = _primary_tracks(info)
    container = info.get("format", {})
    video_data = None
    if video is not None:
        width, height = _dimensions(video)
        fps = _fraction(video.get("avg_frame_rate"))
        video_data = {"stream": video["index"], "codec": video.get("codec_name"),
                      "width": width, "height": height, "avg_fps": float(fps) if fps else None,
                      "duration_seconds": _seconds(video.get("duration")),
                      "start_seconds": _seconds(video.get("start_time"))}
    audio_data = None
    if audio is not None:
        audio_data = {"stream": audio["index"], "codec": audio.get("codec_name"),
                      "sample_rate": int(audio["sample_rate"]) if audio.get("sample_rate") else None,
                      "channels": audio.get("channels"),
                      "start_seconds": _seconds(audio.get("start_time"))}
    return {"source_sha256": file_sha256(file), "duration_seconds": _seconds(container.get("duration")),
            "container": container.get("format_name"), "video": video_data, "audio": audio_data}


def probe(path: Path | str) -> dict:
    file = _local_file(path)
    return _probe_result(file, _media_info(file))


def _cadence(file: Path, stream: dict, fps: int) -> tuple[int, bool | None]:
    result = _run_tool("ffprobe", [
        "-v", "error", *_INPUT_OPTIONS, "-select_streams", str(stream["index"]),
        "-show_frames", "-show_entries", "frame=best_effort_timestamp",
        "-of", "json", str(file),
    ], "frame cadence check")
    rows = json.loads(result.stdout).get("frames", [])
    if len(rows) < 2 or any("best_effort_timestamp" not in row for row in rows):
        return len(rows), None
    base = _fraction(stream.get("time_base"))
    if not base or base <= 0 or base > Fraction(1, fps):
        return len(rows), None
    timestamps = [int(row["best_effort_timestamp"]) for row in rows]
    start = timestamps[0]
    # Permit one tick of quantization introduced by the container time base.
    cadence = all(a < b for a, b in zip(timestamps, timestamps[1:])) and all(
        abs(Fraction(index, fps) - (timestamp - start) * base) < base
        for index, timestamp in enumerate(timestamps)
    )
    return len(rows), cadence


def check_media(path: Path | str, *, fps: int = 60, orientation: str = "any",
                require_audio: bool = True, subtitle: Path | str | None = None) -> dict:
    if fps not in (24, 25, 30, 48, 50, 60):
        raise ValueError("Unsupported QA frame rate")
    if orientation not in ("any", "vertical", "horizontal"):
        raise ValueError("Orientation must be any, vertical or horizontal")
    file = _local_file(path)
    info = _media_info(file)
    video, audio = _primary_tracks(info)
    report = _probe_result(file, info)
    errors = []
    frames, cadence = 0, None
    if video is None:
        errors.append("No video track")
    else:
        frames, cadence = _cadence(file, video, fps)
        if cadence is not True:
            errors.append("Frame cadence differs from the target" if cadence is False
                          else "Frame cadence could not be verified")
        expected = {"vertical": (1080, 1920), "horizontal": (1920, 1080)}
        if orientation in expected and _dimensions(video) != expected[orientation]:
            errors.append(f"Expected Full HD {orientation} dimensions")
    if require_audio and audio is None:
        errors.append("No audio track")
    if subtitle is not None:
        from .subtitles import read_srt

        try:
            cues = read_srt(_local_file(subtitle))
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if not cues:
                errors.append("No subtitle cues")
            if video is not None:
                _, duration = _timeline(info, video)
                if duration is not None and cues and cues[-1].end_ms > int(duration * 1000) + 1:
                    errors.append("Subtitle extends past the video")
    return {**report, "status": "FAILED" if errors else "SUCCESS", "errors": errors,
            "frames": frames, "frame_cadence_matches": cadence, "target_fps": fps,
            "scope": "stream structure, frame timestamps and optional SRT structure"}


_FRAME_LINES = re.compile(r"(?m)^\[Parsed_showinfo_[^\n]+?\] n:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:")
_FRAME_TIMEBASE = re.compile(r"(?m)^\[Parsed_showinfo_[^\n]+?\] config in time_base:\s*(\d+/\d+)")


def extract_frames(path: Path | str, output: Path | str, *, interval=2,
                   scene_threshold=0.30, max_frames=500, ocr_language: str | None = None) -> dict:
    file = _local_file(path)
    destination = _destination(output)
    step = _decimal(interval, positive=True)
    scene = _decimal(scene_threshold)
    if not 0 <= scene <= 1:
        raise ValueError("Scene threshold must be between 0 and 1")
    if not isinstance(max_frames, int) or not 1 <= max_frames <= 10000:
        raise ValueError("Maximum frame count must be between 1 and 10000")
    if ocr_language is not None:
        if not re.fullmatch(r"[a-z]{3}(?:_[a-zA-Z]+)?(?:\+[a-z]{3}(?:_[a-zA-Z]+)?)*", ocr_language):
            raise ValueError("Use installed Tesseract language codes joined by +")
        available = _run_tool("tesseract", ["--list-langs"], "OCR language discovery")
        if set(ocr_language.split("+")) - set(available.stdout.splitlines()):
            raise ValueError("Requested Tesseract language data is not installed")
    info = _media_info(file)
    video, _ = _primary_tracks(info)
    if video is None:
        raise ValueError("No video track")
    origin, _ = _timeline(info, video)
    selection = f"isnan(prev_selected_t)+gte(t-prev_selected_t,{step:f})+gt(scene,{scene:f})"
    filters = (f"setpts=PTS-({origin:f})/TB,select='{selection}',"
               "scale=768:768:force_original_aspect_ratio=decrease:force_divisible_by=2,showinfo")
    with TemporaryDirectory(prefix=".vortex-frames-", dir=destination.parent) as tmp:
        folder = Path(tmp)
        result = _run_tool("ffmpeg", [
            "-nostdin", "-hide_banner", "-loglevel", "info", *_INPUT_OPTIONS, "-copyts", "-i", str(file),
            "-map", f"0:{video['index']}", "-vf", filters, "-an", "-fps_mode", "vfr",
            "-frames:v", str(max_frames + 1), "-q:v", "3", str(folder / "frame_%06d.jpg"),
        ], "frame sampling", timeout=600)
        timebase = _FRAME_TIMEBASE.search(result.stderr)
        rows = [(int(i), int(pts)) for i, pts in _FRAME_LINES.findall(result.stderr)]
        files = sorted(folder.glob("frame_*.jpg"))
        if not timebase or not files or len(rows) != len(files):
            raise ValueError("Could not verify timestamps for sampled frames")
        if [index for index, _ in rows] != list(range(len(rows))):
            raise ValueError("Frame sampling produced inconsistent timestamps")
        base = Fraction(timebase[1])
        capped = len(files) > max_frames
        if capped:
            files.pop().unlink()
        frames = [{"file": img.name, "seconds": float(rows[i][1] * base)}
                  for i, img in enumerate(files)]
        report = {"source_sha256": file_sha256(file), "frames": frames, "capped": capped,
                  "interval_seconds": float(step), "scene_threshold": float(scene),
                  "timeline_origin": "primary video start", "source_origin_seconds": float(origin)}
        if ocr_language is not None:
            report["ocr"] = {"engine": "tesseract", "languages": ocr_language.split("+"),
                             "scope": "text on sampled frames", "manual_reviewed": False}
            for frame, image in zip(frames, files, strict=True):
                recognized = _run_tool("tesseract", [str(image), "stdout", "-l", ocr_language,
                                                      "--psm", "11"], "frame text recognition", timeout=30)
                frame["screen_text"] = recognized.stdout.strip()
        (folder / "frames.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _publish_directory(folder, destination)
    return {**report, "output": str(destination)}
