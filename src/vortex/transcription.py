"""Run local whisper.cpp on a selected audio track and export aligned text."""

from dataclasses import asdict
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from .evidence import file_sha256
from .media import (_INPUT_OPTIONS, _destination, _local_file, _media_info, _dimensions,
                    _primary_tracks, _publish_directory, _run_tool, _timeline)
from .subtitles import Cue, Word, progressive_ass, srt_text


def _bounds(item: dict) -> tuple[int, int] | None:
    offsets = item.get("offsets")
    if not isinstance(offsets, dict):
        return None
    start, end = offsets.get("from"), offsets.get("to")
    if type(start) is not int or type(end) is not int or not 0 <= start <= end:
        return None
    return start, end


def _words(segment: dict, start_ms: int, end_ms: int) -> tuple[Word, ...]:
    pieces = []
    position = 0
    tokens = segment.get("tokens") or ()
    for token in tokens:
        value = token.get("text")
        if not isinstance(value, str) or (value.startswith("[_") and value.endswith("_]")):
            continue
        pieces.append((position, position + len(value), value, _bounds(token), token.get("p")))
        position += len(value)
    composed = "".join(piece[2] for piece in pieces)
    if composed.strip() != segment["text"].strip():
        return ()
    words = []
    for match in re.finditer(r"\S+", composed):
        matches = [p for p in pieces if p[0] < match.end() and p[1] > match.start()]
        if not matches or any(p[3] is None for p in matches):
            return ()
        prob = [p[4] for p in matches if type(p[4]) in (float, int) and 0 <= p[4] <= 1]
        start = min(end_ms, max(start_ms, min(p[3][0] for p in matches)))
        end = min(end_ms, max(start, max(p[3][1] for p in matches)))
        if words and start < words[-1].start_ms:
            return ()
        words.append(Word(start, end, match[0], min(prob) if prob else None))
    return tuple(words)


def _decode_result(backend_output: dict, duration_ms: int | None):
    segments = backend_output.get("transcription")
    if not isinstance(segments, list):
        raise ValueError("whisper-cli returned an invalid JSON transcript")
    cues = []
    adjusted = 0
    for segment in segments:
        value = segment.get("text")
        if not isinstance(value, str) or not value.strip():
            continue
        if value.strip() == "[BLANK_AUDIO]":
            continue
        bounds = _bounds(segment)
        if bounds is None:
            raise ValueError("whisper-cli returned an invalid segment time")
        lower, upper = bounds
        start = max(lower, cues[-1].end_ms if cues else 0)
        end = min(upper, duration_ms) if duration_ms is not None else upper
        if end <= start:
            # A backend may estimate both offsets beyond a very short real clip.
            # Retain any text in the preceding cue or report the unplaceable segment.
            if not cues:
                raise ValueError("Recognized text has no interval inside the source")
            last = cues.pop()
            cues.append(Cue(last.start_ms, last.end_ms, last.text + " " + value.strip()))
            adjusted += 1
            continue
        adjusted += (start, end) != bounds
        cues.append(Cue(start, end, value.strip().replace("\n\n", "\n"),
                        _words(segment, start, end)))
    language = backend_output.get("result", {}).get("language")
    return tuple(cues), language, adjusted


def transcribe(path: Path | str, output: Path | str, *, model: Path | str,
               language: str = "auto", fps: int = 60, threads: int = 4) -> dict:
    if not re.fullmatch(r"(?:auto|[a-z]{2,3})", language):
        raise ValueError("Language must be auto or a short lowercase language code")
    if type(threads) is not int or not 1 <= threads <= 32:
        raise ValueError("Threads must be between 1 and 32")
    if fps not in (24, 25, 30, 48, 50, 60):
        raise ValueError("Unsupported caption frame rate")
    file, weights = _local_file(path), _local_file(model)
    destination = _destination(output)
    info = _media_info(file)
    video, audio = _primary_tracks(info)
    if audio is None:
        raise ValueError("No audio track")
    origin, duration = _timeline(info, video or audio)
    with TemporaryDirectory(prefix=".vortex-asr-", dir=destination.parent) as tmp:
        work = Path(tmp)
        wav = work / "speech.wav"
        args = ["-nostdin", "-v", "error", *_INPUT_OPTIONS, "-copyts", "-i", str(file),
                "-map", f"0:{audio['index']}", "-vn", "-af",
                f"asetpts=PTS-({origin:f})/TB,aresample=16000:async=1:first_pts=0",
                "-ac", "1", "-c:a", "pcm_s16le"]
        if duration is not None:
            args.extend(("-t", f"{duration:f}"))
        _run_tool("ffmpeg", [*args, str(wav)], "ASR audio extraction", timeout=600)
        native = work / "recognition"
        _run_tool("whisper-cli", [
            "-m", str(weights), "-f", str(wav), "-l", language, "-ng", "-ojf",
            "-sow", "-ml", "54", "-of", str(native), "-t", str(threads),
        ], "local speech recognition", timeout=3600)
        # BPE fragments in a full backend transcript may split a UTF-8 code point.
        # Segment text still comes from the joined sequence. Token groups with
        # replacement characters fail the exact-text check and keep valid cue text.
        backend = json.loads(native.with_suffix(".json").read_text(encoding="utf-8", errors="replace"))
        bound = int(duration * 1000) if duration is not None else None
        cues, detected, adjusted = _decode_result(backend, bound)
        width, height = _dimensions(video) if video else (1920, 1080)
        ass, frames = progressive_ass(cues, fps, width, height)
        report = {
            "engine": "whisper.cpp/whisper-cli", "language": detected,
            "source_sha256": file_sha256(file), "model_sha256": file_sha256(weights),
            "timeline_origin": "primary video start" if video else "primary audio start",
            "captions_fps": fps, "segments": [asdict(cue) for cue in cues],
            "adjusted_segments": adjusted,
            "manual_reviewed": False,
            "speech_recognized": bool(cues),
            "timing_scope": "provider segment and token times; grouped word and estimated grapheme times",
            "review_cues": [i for i, item in enumerate(cues, 1) if not item.words or any(
                word.confidence is None or word.confidence < .55 for word in item.words
            )],
        }
        stage = work / "delivery"
        stage.mkdir()
        (stage / "transcript.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)
                                              + "\n", encoding="utf-8")
        (stage / "transcript.txt").write_text("".join(cue.text + "\n" for cue in cues), encoding="utf-8")
        (stage / "captions.srt").write_text(srt_text(cues), encoding="utf-8")
        (stage / "captions.ass").write_text(ass, encoding="utf-8")
        (stage / "frames.json").write_text(json.dumps({"fps": fps, "intervals": frames},
                                                      ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
        _publish_directory(stage, destination)
    return {**report, "output": str(destination),
            "files": ["transcript.json", "transcript.txt", "captions.srt", "captions.ass", "frames.json"]}


def read_transcript(path: Path, source_sha256: str) -> tuple[Cue, ...]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict) or document.get("source_sha256") != source_sha256:
        raise ValueError("Transcript belongs to a different source")
    raw = document.get("segments")
    if not isinstance(raw, list):
        raise ValueError("Transcript is missing its segments")
    cues = []
    for item in raw:
        try:
            start, end, value = item["start_ms"], item["end_ms"], item["text"]
            words = tuple(Word(**word) for word in item.get("words", ()))
        except (TypeError, KeyError) as exc:
            raise ValueError("Malformed transcript segment") from exc
        if not (type(start) is type(end) is int and 0 <= start < end
                and isinstance(value, str) and value.strip()):
            raise ValueError("Invalid transcript cue")
        if cues and start < cues[-1].end_ms:
            raise ValueError("Overlapping transcript cues")
        if any(type(w.start_ms) is not int or type(w.end_ms) is not int
               or not start <= w.start_ms <= w.end_ms <= end or not isinstance(w.text, str)
               for w in words):
            raise ValueError("Invalid transcript word interval")
        cues.append(Cue(start, end, value.strip(), words))
    return tuple(cues)
