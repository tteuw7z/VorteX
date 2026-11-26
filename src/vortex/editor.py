"""Render an ordered set of local cuts with frame-aligned progressive captions."""

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from .media import (_INPUT_OPTIONS, _cadence, _decimal, _destination, _dimensions,
                    _local_file, _media_info, _primary_tracks, _run_tool, _sha256, _timeline)
from .subtitles import Cue, Word, progressive_ass, read_srt
from .transcription import read_transcript


@dataclass(frozen=True, slots=True)
class Cut:
    start_ms: int
    end_ms: int
    frames: int


def _cuts(ranges, duration: Decimal, fps: int) -> tuple[Cut, ...]:
    maximum = int(duration * 1000)
    if ranges is None:
        ranges = ((0, Decimal(maximum) / 1000),)
    else:
        ranges = tuple(ranges)
    if not 1 <= len(ranges) <= 32:
        raise ValueError("Provide between 1 and 32 cuts")
    cuts = []
    for start, end in ranges:
        start_ms = round(_decimal(start) * 1000)
        end_ms = maximum if end is None else round(_decimal(end) * 1000)
        if not 0 <= start_ms < end_ms <= maximum:
            raise ValueError("Each cut must be a positive interval inside the source video")
        frames = round(Fraction((end_ms - start_ms) * fps, 1000))
        if frames < 1:
            raise ValueError("A cut is shorter than one output frame")
        cuts.append(Cut(start_ms, end_ms, frames))
    return tuple(cuts)


def _remap(cues: tuple[Cue, ...], cuts: tuple[Cut, ...], fps: int) -> tuple[Cue, ...]:
    offset = 0
    normalized = []
    for cut in cuts:
        def translate(source_ms: int) -> int:
            return round(Fraction(offset * 1000, fps) + min(
                Fraction(cut.frames * 1000, fps), source_ms - cut.start_ms))

        for cue in cues:
            start, end = max(cut.start_ms, cue.start_ms), min(cut.end_ms, cue.end_ms)
            if end <= start:
                continue
            words = cue.words
            # For timed words, a cut can omit the words outside the source interval.
            # SRT-only cues keep their text because their word positions are unknown.
            if words and len(words) == len(cue.text.split()) and [w.text for w in words] == cue.text.split():
                words = tuple(w for w in words if w.start_ms < end and w.end_ms >= start)
                if not words:
                    continue
                value = " ".join(w.text for w in words)
                words = tuple(Word(translate(max(start, w.start_ms)), translate(min(end, w.end_ms)),
                                   w.text, w.confidence) for w in words)
            else:
                value = cue.text
                words = ()
            beginning, finish = translate(start), translate(end)
            if finish > beginning:
                normalized.append(Cue(beginning, finish, value, words))
        offset += cut.frames
    return tuple(normalized)


def _seconds_text(milliseconds: int) -> str:
    return f"{Decimal(milliseconds) / 1000:f}"


def _filter_graph(cuts: tuple[Cut, ...], fps: int, origin: Decimal, video: dict,
                  audio: dict | None, width: int, height: int,
                  captions: bool, monochrome: bool, fade_seconds: Decimal) -> str:
    count = len(cuts)
    graph = []
    video_in = (f"[0:{video['index']}]setpts=PTS-({origin:f})/TB,"
                f"fps={fps}:start_time=0")
    if count > 1:
        video_in += f",split={count}"
    graph.append(video_in + "".join(f"[vsrc{i}]" for i in range(count)))
    if audio is not None:
        audio_in = (f"[0:{audio['index']}]asetpts=PTS-({origin:f})/TB,"
                    "aresample=48000:async=1:first_pts=0,apad")
        if count > 1:
            audio_in += f",asplit={count}"
        graph.append(audio_in + "".join(f"[asrc{i}]" for i in range(count)))
    streams = []
    for i, cut in enumerate(cuts):
        start, end = _seconds_text(cut.start_ms), _seconds_text(cut.end_ms)
        duration = Decimal(cut.frames) / fps
        # Select the frame that covers the cut start on the output sampling grid.
        first_frame = cut.start_ms * fps // 1000
        graph.append(
            f"[vsrc{i}]trim=start_frame={first_frame}:end_frame={first_frame + cut.frames},"
            "setpts=PTS-STARTPTS,"
            f"tpad=stop_mode=clone:stop_duration={duration:.9f},trim=end_frame={cut.frames}[cutv{i}]"
        )
        streams.append(f"[cutv{i}]")
        if audio is not None:
            graph.append(f"[asrc{i}]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,"
                         f"apad,atrim=duration={duration:.9f}[cuta{i}]")
            streams.append(f"[cuta{i}]")
    joined_video = "cutv0"
    joined_audio = "cuta0"
    if count > 1:
        outputs = "[joinedv][joineda]" if audio is not None else "[joinedv]"
        graph.append(f"{''.join(streams)}concat=n={count}:v=1:a={int(audio is not None)}{outputs}")
        joined_video = "joinedv"
        joined_audio = "joineda"

    # Concat uses a microsecond time base. Rebuild a uniform output grid to
    # avoid rounding inconsistencies at cut boundaries.
    filters = [
        f"settb=1/{fps}", "setpts=N",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2", "setsar=1",
    ]
    if monochrome:
        filters.append("hue=s=0")
    total = Decimal(sum(cut.frames for cut in cuts)) / fps
    if fade_seconds:
        tail = total - fade_seconds
        filters.extend((f"fade=t=in:st=0:d={fade_seconds:f}",
                        f"fade=t=out:st={tail:.9f}:d={fade_seconds:f}"))
    if captions:
        filters.append("ass=captions.ass")
    graph.append(f"[{joined_video}]{','.join(filters)}[outv]")
    if audio is not None and fade_seconds:
        graph.append(f"[{joined_audio}]afade=t=in:st=0:d={fade_seconds:f},"
                     f"afade=t=out:st={tail:.9f}:d={fade_seconds:f}[outa]")
    elif audio is not None:
        graph.append(f"[{joined_audio}]anull[outa]")
    return ";".join(graph)


def render(path: Path | str, output: Path | str, *, ranges=None, fps: int = 60,
           captions: Path | str | None = None, full_hd: bool = False,
           monochrome: bool = False, fade=0) -> dict:
    if fps not in (24, 25, 30, 48, 50, 60):
        raise ValueError("Unsupported render frame rate")
    file = _local_file(path)
    destination = _destination(output)
    if destination.suffix.lower() != ".mp4":
        raise ValueError("The render output must end in .mp4")
    info = _media_info(file)
    video, audio = _primary_tracks(info)
    if video is None:
        raise ValueError("No video track")
    origin, duration = _timeline(info, video)
    if not duration:
        raise ValueError("A known positive video duration is required")
    cuts = _cuts(ranges, duration, fps)
    frames = sum(cut.frames for cut in cuts)
    fade_seconds = _decimal(fade)
    if not 0 <= fade_seconds * 2 <= Decimal(frames) / fps:
        raise ValueError("Fade must be nonnegative and at most half the output duration")
    width, height = _dimensions(video)
    if full_hd:
        width, height = (1920, 1080) if width >= height else (1080, 1920)
    else:
        width += width % 2
        height += height % 2
    digest = _sha256(file)
    cues = ()
    if captions is not None:
        caption_path = _local_file(captions)
        if caption_path.suffix.lower() == ".json":
            cues = read_transcript(caption_path, digest)
        elif caption_path.suffix.lower() == ".srt":
            cues = read_srt(caption_path)
        else:
            raise ValueError("Use SRT or a matching Vortex transcript JSON for captions")
        cues = _remap(cues, cuts, fps)
    with TemporaryDirectory(prefix=".vortex-render-", dir=destination.parent) as tmp:
        work = Path(tmp)
        staged = work / "render.mp4"
        timeline = []
        if cues:
            ass, timeline = progressive_ass(cues, fps, width, height)
            (work / "captions.ass").write_text(ass, encoding="utf-8")
        filters = _filter_graph(cuts, fps, origin, video, audio, width, height, bool(cues),
                                monochrome, fade_seconds)
        args = ["-nostdin", "-hide_banner", "-v", "error", *_INPUT_OPTIONS, "-copyts",
                "-i", str(file), "-filter_complex", filters, "-map", "[outv]"]
        if audio is not None:
            args.extend(("-map", "[outa]", "-c:a", "aac", "-b:a", "192k"))
        _run_tool("ffmpeg", [
            *args, "-map_metadata", "-1", "-map_chapters", "-1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-r:v", str(fps), "-fps_mode", "cfr", "-movflags", "+faststart", str(staged),
        ], "video render", cwd=work, timeout=3600)
        rendered, rendered_audio = _primary_tracks(_media_info(staged))
        if rendered is None:
            raise ValueError("Rendered file has no video track")
        actual_frames, cadence = _cadence(staged, rendered, fps)
        if actual_frames != frames or (actual_frames > 1 and cadence is not True):
            raise ValueError(f"Rendered frame count or cadence did not match the edit ({actual_frames}/{frames})")
        if (audio is not None and rendered_audio is None) or _dimensions(rendered) != (width, height):
            raise ValueError("Rendered tracks or dimensions did not match the edit")
        sha = _sha256(staged)
        os.link(staged, destination)
    return {"output": str(destination), "sha256": sha, "source_sha256": digest,
            "fps": fps, "frames": frames, "dimensions": [width, height], "audio": audio is not None,
            "cuts": [{"start_ms": cut.start_ms, "end_ms": cut.end_ms, "frames": cut.frames}
                     for cut in cuts],
            "caption_cues": len(cues), "caption_intervals": len(timeline),
            "caption_timing": "estimated grapheme times" if timeline else None}
