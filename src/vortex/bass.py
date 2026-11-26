"""Local, frame-grid bass onset detection; not a BPM or musical beat classifier."""
from array import array
from decimal import Decimal
from fractions import Fraction
from math import sqrt
from pathlib import Path
from statistics import median
import sys
from tempfile import TemporaryDirectory
import wave

from .evidence import file_sha256
from .media import (_INPUT_OPTIONS, _decimal, _local_file, _media_info, _primary_tracks,
                    _run_tool, _timeline)

_SAMPLE_RATE = 8000
_FRAME_RATES = (24, 25, 30, 48, 50, 60)


def _energies(path: Path, fps: int) -> list[float]:
    energies = []
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, _SAMPLE_RATE):
            raise ValueError("Unexpected bass analysis PCM format")
        if stream.getnframes() > 601 * _SAMPLE_RATE:
            raise ValueError("Bass analysis audio exceeded its sample limit")
        position = 0
        while position < stream.getnframes():
            next_position = round(Fraction((len(energies) + 1) * _SAMPLE_RATE, fps))
            samples = array("h")
            samples.frombytes(stream.readframes(next_position - position))
            if sys.byteorder != "little":
                samples.byteswap()
            if not samples:
                break
            energies.append(sqrt(sum(value * value for value in samples) / len(samples)) / 32768)
            position += len(samples)
    return energies


def _onsets(energies: list[float], fps: int, min_gap_frames: int) -> list[dict]:
    peak = max(energies, default=0.0)
    if peak < .005:
        return []
    history_frames = max(2, round(fps * .25))
    threshold = max(.005, peak * .12)
    scores = [max(0.0, value - median(energies[max(0, i - history_frames):i] or [0.0]))
              for i, value in enumerate(energies)]
    radius = max(1, round(fps * .035))
    candidates = []
    for i, score in enumerate(scores):
        if score < threshold:
            continue
        neighborhood = scores[max(0, i - radius):min(len(scores), i + radius + 1)]
        if score >= max(neighborhood):
            candidates.append(i)
    # Choose the strongest candidate in each minimum-gap interval.
    selected = []
    for i in sorted(candidates, key=lambda n: (-scores[n], n)):
        if all(abs(i - other) >= min_gap_frames for other in selected):
            selected.append(i)
            if len(selected) == 128:
                break
    return [{"frame": i, "seconds": i / fps, "band_rms": round(energies[i], 6),
             "onset_score": round(scores[i], 6)} for i in sorted(selected)]


def detect_bass(path: Path | str, *, fps: int = 60, max_seconds: int = 600,
                min_gap="0.35") -> dict:
    if type(fps) is not int or fps not in _FRAME_RATES:
        raise ValueError("Unsupported analysis frame rate")
    if type(max_seconds) is not int or not 1 <= max_seconds <= 600:
        raise ValueError("Bass analysis limit must be 1 to 600 seconds")
    gap = _decimal(min_gap)
    if not Decimal(1) / 3 <= gap <= Decimal(3):
        raise ValueError("Bass onset gap must be between one third and three seconds")
    file = _local_file(path)
    info = _media_info(file)
    video, audio = _primary_tracks(info)
    if audio is None:
        raise ValueError("Bass analysis requires an audio track")
    origin, duration = _timeline(info, video or audio)
    limit = min(duration, Decimal(max_seconds)) if duration is not None else Decimal(max_seconds)
    if limit <= 0:
        raise ValueError("No audio interval to analyze")
    with TemporaryDirectory(prefix="vortex-bass-") as directory:
        wav = Path(directory) / "bass.wav"
        _run_tool("ffmpeg", ["-nostdin", "-v", "error", *_INPUT_OPTIONS, "-copyts", "-i", str(file),
                            "-map", f"0:{audio['index']}", "-vn", "-af",
                            f"asetpts=PTS-({origin:f})/TB,aresample={_SAMPLE_RATE}:async=1:first_pts=0,"
                            "highpass=f=35,lowpass=f=160",
                            "-ac", "1", "-c:a", "pcm_s16le", "-t", f"{limit:f}", str(wav)],
                  "local bass analysis", timeout=600)
        energies = _energies(wav, fps)
    events = _onsets(energies, fps, max(1, -(-Fraction(gap) * fps // 1)))
    return {"source_sha256": file_sha256(file), "fps": fps, "analyzed_frames": len(energies),
            "analyzed_seconds": len(energies) / fps,
            "source_origin_seconds": float(origin), "analysis_limit_seconds": max_seconds,
            "truncated": duration > limit if duration is not None else None,
            "method": "35-160 Hz band RMS and local energy onsets",
            "events": events, "event_limit_reached": len(events) == 128,
            "scope": "heuristic low-frequency transients; not verified musical beats"}


def flash_intervals(events: list[dict], cuts, fps: int, strength) -> tuple[tuple, ...]:
    """Map source onsets through an ordered cut list to bounded output intervals."""
    amount = _decimal(strength)
    if not 0 < amount <= 1:
        raise ValueError("Bass flash strength must be greater than zero and at most one")
    length = max(3, round(fps * .25))
    offset = 0
    intervals = []
    for cut in cuts:
        lower = Fraction(cut.start_ms * fps, 1000)
        upper = Fraction(cut.end_ms * fps, 1000)
        for event in events:
            frame = event["frame"]
            if not lower <= frame < upper:
                continue
            mapped = offset + min(cut.frames - 1, max(0, round(frame - lower)))
            first = max(offset, mapped - length // 2)
            last = min(offset + cut.frames, first + length)
            if last - first < 3:
                continue
            if intervals and (first < intervals[-1][1] or 3 * (first - intervals[-1][0]) < fps):
                continue
            intervals.append((first, last))
            if len(intervals) == 32:
                break
        if len(intervals) == 32:
            break
        offset += cut.frames
    return tuple(("flash", Decimal(first) / fps, Decimal(last) / fps, amount)
                 for first, last in intervals)
