"""Timed text and deterministic, Unicode-aware progressive captions."""

from dataclasses import dataclass
from fractions import Fraction
from itertools import groupby
from math import ceil
from pathlib import Path
import re
from unicodedata import iter_graphemes


@dataclass(frozen=True, slots=True)
class Word:
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class Cue:
    start_ms: int
    end_ms: int
    text: str
    words: tuple[Word, ...] = ()


_CLOCK = re.compile(r"(\d{2,}):([0-5]\d):([0-5]\d)[,.](\d{3})")


def _read_clock(value: str) -> int:
    match = _CLOCK.fullmatch(value)
    if not match:
        raise ValueError("Invalid SRT timestamp")
    hour, minute, second, millisecond = map(int, match.groups())
    return ((hour * 60 + minute) * 60 + second) * 1000 + millisecond


def _stamp(value: int, digits: int) -> str:
    scale = 10**digits
    seconds, rest = divmod(value, scale)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    separator = "," if digits == 3 else "."
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{rest:0{digits}d}"


def read_srt(path: Path) -> tuple[Cue, ...]:
    source = path.read_text(encoding="utf-8-sig").strip()
    cues = []
    for position, block in enumerate(re.split(r"\n[ \t]*\n", source), 1):
        if not block:
            continue
        lines = block.splitlines()
        try:
            if len(lines) < 3 or not lines[0].strip().isdecimal():
                raise ValueError("Missing cue number or text")
            start, end = map(_read_clock, lines[1].strip().split(" --> "))
            text = "\n".join(lines[2:]).strip()
            if not text or end <= start or (cues and start < cues[-1].end_ms):
                raise ValueError("Cue is empty, non-positive or overlapping")
        except ValueError as exc:
            raise ValueError(f"Invalid SRT cue {position}: {exc}") from exc
        cues.append(Cue(start, end, text))
    return tuple(cues)


def srt_text(cues: tuple[Cue, ...]) -> str:
    blocks = [
        f"{number}\n{_stamp(cue.start_ms, 3)} --> {_stamp(cue.end_ms, 3)}\n{cue.text}\n"
        for number, cue in enumerate(cues, 1)
    ]
    return "\n".join(blocks)


def _ass_literal(text: str) -> str:
    # Prevent literal text from becoming an ASS escape or override block.
    return (text.replace("\\", "\\\u200b").replace("{", r"\{").replace("}", r"\}")
            .replace("\n", r"\N"))


def _states(cue: Cue, first: int, stop: int, fps: int):
    text = cue.text
    spans = list(re.finditer(r"\S+", text))
    matched = cue.words and [m[0] for m in spans] == [w.text for w in cue.words]
    windows = (
        [(word.start_ms, word.end_ms, span.end()) for word, span in zip(cue.words, spans)]
        if matched else [(cue.start_ms, cue.end_ms, len(text))]
    )
    ranges = [str(cluster) for cluster in iter_graphemes(text)]
    consumed = 0
    events = []
    previous = first
    index = 0
    for offset, (start, end, limit) in enumerate(windows):
        beginning = index
        while index < len(ranges) and consumed < limit:
            consumed += len(ranges[index])
            index += 1
        if index == beginning:
            continue
        low = min(stop - 1, max(previous, ceil(Fraction(start * fps, 1000))))
        next_start = windows[offset + 1][0] if offset + 1 < len(windows) else cue.end_ms
        high = min(stop, max(low + 1, ceil(Fraction(min(end, next_start) * fps, 1000))))
        count = index - beginning
        for z in range(count):
            previous = low + ((high - low) * z // count)
            events.append((previous, ranges[beginning + z]))
    shown = ""
    grouped = []
    for appearance, glyphs in groupby(events, key=lambda row: row[0]):
        shown += "".join(glyph for _, glyph in glyphs)
        grouped.append((appearance, shown))
    return [(at, grouped[i + 1][0] if i + 1 < len(grouped) else stop, visible)
            for i, (at, visible) in enumerate(grouped)]


_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline},0,2,{side},{side},{bottom},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def progressive_ass(cues: tuple[Cue, ...], fps: int, width: int, height: int
                    ) -> tuple[str, list[dict]]:
    if not 1 <= fps <= 100:
        raise ValueError("ASS progressive rendering requires 1–100 fps")
    lines = [_ASS_HEADER.format(width=width, height=height, size=max(10, round(height * 0.055)),
                                outline=max(1, round(height * 0.003)), side=max(2, round(width * .06)),
                                bottom=max(4, round(height * .09)))]
    timeline = []
    previous_stop = 0
    for index, cue in enumerate(cues):
        start = max(previous_stop, ceil(Fraction(cue.start_ms * fps, 1000)))
        stop = max(start + 1, ceil(Fraction(cue.end_ms * fps, 1000)))
        if index + 1 < len(cues):
            # Reserve the next cue's first frame if it is representable at this FPS.
            following = ceil(Fraction(cues[index + 1].start_ms * fps, 1000))
            stop = min(stop, max(start + 1, following))
        previous_stop = stop
        for at, until, shown in _states(cue, start, stop, fps):
            rest = cue.text[len(shown):]
            styled = _ass_literal(shown)
            if rest:
                styled += r"{\alpha&HFF&}" + _ass_literal(rest)
            # A frame index occupies at least one centisecond at the supported rates.
            begin = _stamp(at * 100 // fps, 2)
            end = _stamp(until * 100 // fps, 2)
            lines.append(f"Dialogue: 0,{begin},{end},Caption,,0,0,0,,{styled}\n")
            timeline.append({"start_frame": at, "end_frame_exclusive": until, "text": shown})
    return "".join(lines), timeline
