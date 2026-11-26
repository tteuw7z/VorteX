import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from vortex.editor import render
from vortex.effects import prepare_effects
from vortex.media import check_media, extract_frames, probe
from vortex.media_cli import add_commands
from vortex.subtitles import Cue, Word, progressive_ass, read_srt
from vortex.transcription import _decode_result, transcribe


def ffmpeg(*options):
    return subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-v", "error", *options],
                          check=True, capture_output=True, timeout=40).stdout


_HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


class SubtitleTests(unittest.TestCase):
    def test_unicode_clusters_and_cadence(self):
        cue = Cue(100, 1400, "Ola\u0301 👩🏻‍💻!", (
            Word(100, 500, "Ola\u0301"), Word(700, 1100, "👩🏻‍💻!"),
        ))
        ass, states = progressive_ass((cue,), 60, 320, 180)
        texts = [state["text"] for state in states]
        self.assertIn("Ola\u0301", texts)
        self.assertIn("Ola\u0301 👩🏻‍💻", texts)
        self.assertNotIn("Ola", texts)
        self.assertNotIn("Ola\u0301 👩", texts)
        self.assertEqual(texts[-1], cue.text)
        self.assertEqual(states[0]["start_frame"], 6)
        self.assertTrue(all(state["end_frame_exclusive"] == next_state["start_frame"]
                            for state, next_state in zip(states, states[1:])))
        self.assertIn(r"{\alpha&HFF&}", ass)

    def test_missing_word_timings_never_drop_segment_text(self):
        cues, language, adjusted = _decode_result({
            "result": {"language": "pt"},
            "transcription": [{"text": "Olá, equipe.", "offsets": {"from": 0, "to": 2100},
                               "tokens": [{"text": "equ", "offsets": {"from": 0, "to": 100}}]}],
        }, 2000)
        self.assertEqual(cues, (Cue(0, 2000, "Olá, equipe."),))
        self.assertEqual((language, adjusted), ("pt", 1))

    def test_blank_audio_label_is_not_spoken_text(self):
        cues, language, adjusted = _decode_result({
            "result": {"language": "en"},
            "transcription": [
                {"text": " [BLANK_AUDIO]", "offsets": {"from": 0, "to": 1500}},
                {"text": " Hello.", "offsets": {"from": 1500, "to": 2000}},
            ],
        }, 2000)
        self.assertEqual(cues, (Cue(1500, 2000, "Hello."),))
        self.assertEqual((language, adjusted), ("en", 0))

    def test_reject_invalid_srt(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.srt"
            path.write_text("1\n00:00:00,500 --> 00:00:00,100\nBad\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid SRT cue 1"):
                read_srt(path)


@unittest.skipUnless(_HAS_FFMPEG, "FFmpeg and FFprobe required")
class MediaIntegrationTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / "source.mp4"

    def frames_for(self, filename):
        return ffmpeg("-i", str(filename), "-an", "-vf", "format=gray", "-f", "rawvideo",
                      "-c:v", "rawvideo", "-threads:v", "1", "-")

    def test_probe_frames_and_scene_change(self):
        ffmpeg("-f", "lavfi", "-i", "color=c=red:s=160x90:r=30:d=0.5",
               "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=30:d=0.5",
               "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0",
               "-c:v", "libx264", str(self.source))
        self.assertEqual(probe(self.source)["video"]["width"], 160)
        result = extract_frames(self.source, self.root / "frames")
        self.assertEqual([frame["seconds"] for frame in result["frames"]], [0.0, 0.5])
        self.assertTrue((Path(result["output"]) / "frame_000002.jpg").is_file())
        report = json.loads((Path(result["output"]) / "frames.json").read_text())
        self.assertEqual(report["frames"], result["frames"])
        capped = extract_frames(self.source, self.root / "limited", interval=".1", max_frames=1)
        self.assertTrue(capped["capped"])
        self.assertEqual(len(capped["frames"]), 1)

    def test_sample_times_relative_to_offset_video(self):
        ffmpeg("-f", "lavfi", "-i", "color=c=red:s=160x90:r=10:d=1",
               "-c:v", "libx264", "-output_ts_offset", "5", str(self.source))
        result = extract_frames(self.source, self.root / "frames", interval=".5")
        self.assertEqual(result["source_origin_seconds"], 5)
        self.assertEqual([f["seconds"] for f in result["frames"]], [0, 0.5])
        self.assertEqual(result["source_sha256"], probe(self.source)["source_sha256"])

    @unittest.skipUnless(shutil.which("tesseract"), "Tesseract is required for frame OCR")
    def test_on_screen_text_in_sampled_frames(self):
        ffmpeg("-f", "lavfi", "-i", "color=c=black:s=480x270:r=10:d=1",
               "-vf", "drawtext=text=VORTEX TEST:fontcolor=white:fontsize=54:x=20:y=75",
               "-c:v", "libx264", str(self.source))
        out = self.root / "ocr"
        result = extract_frames(self.source, out, interval=".5", ocr_language="eng")
        self.assertEqual(result["ocr"]["languages"], ["eng"])
        self.assertEqual([(frame["seconds"], frame["screen_text"]) for frame in result["frames"]],
                         [(0, "VORTEX TEST"), (0.5, "VORTEX TEST")])
        self.assertEqual(json.loads((out / "frames.json").read_text())["frames"], result["frames"])

    def test_edit_preserves_audio_and_reveals_on_expected_frame(self):
        ffmpeg("-f", "lavfi", "-i", "color=c=black:s=320x180:r=30:d=1.5",
               "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1.5",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(self.source))
        captions = self.root / "caption.srt"
        captions.write_text("1\n00:00:00,200 --> 00:00:00,900\nOi!\n", encoding="utf-8")
        output = self.root / "output.mp4"
        info = render(self.source, output, ranges=[("0", "1"), ("1", "1.5")],
                      captions=captions, fade=".05", monochrome=True)
        self.assertEqual((info["fps"], info["frames"], info["audio"]), (60, 90, True))
        self.assertEqual(info["caption_intervals"], 3)
        report = check_media(output, subtitle=captions)
        self.assertEqual(report["status"], "SUCCESS")
        self.assertTrue(report["frame_cadence_matches"])
        output_frames = self.frames_for(output)
        size = 320 * 180
        bounds = lambda n: output_frames[n * size:(n + 1) * size]
        self.assertLess(max(bounds(11)), 25)
        self.assertGreater(max(bounds(12)), 140)
        self.assertNotEqual(bounds(12), bounds(46))
        with self.assertRaisesRegex(ValueError, "already exists"):
            render(self.source, output)
        self.assertEqual(probe(output)["source_sha256"], info["sha256"])

    def test_frame_aligned_flash_shake_and_blur_render(self):
        ffmpeg("-f", "lavfi", "-i", "testsrc2=s=160x90:r=60:d=1.5",
               "-f", "lavfi", "-i", "sine=frequency=80:sample_rate=48000:duration=1.5",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(self.source))
        baseline = self.root / "baseline.mp4"
        output = self.root / "effects.mp4"
        render(self.source, baseline)
        report = render(self.source, output, effects=[
            ("flash", ".2", ".4", ".8"),
            ("shake", ".6", ".85", ".8"),
            ("blur", "1", "1.25", "1"),
        ])
        self.assertEqual([(e["kind"], e["start_frame"], e["end_frame_exclusive"])
                          for e in report["effects"]],
                         [("flash", 12, 24), ("shake", 36, 51), ("blur", 60, 75)])
        self.assertEqual(report["frames"], 90)
        self.assertEqual(check_media(output)["status"], "SUCCESS")
        base, edited = self.frames_for(baseline), self.frames_for(output)
        size = 160 * 90
        def frame(raw, n):
            return raw[n * size:(n + 1) * size]
        def difference(n):
            return sum(abs(a - b) for a, b in zip(frame(base, n), frame(edited, n))) / size
        # Compare actual decoded video, not just generated filter text.
        self.assertLess(difference(5), 5)
        self.assertGreater(sum(frame(edited, 18)) / size - sum(frame(base, 18)) / size, 20)
        self.assertGreater(max(difference(n) for n in range(38, 49)), 1.5)
        self.assertGreater(difference(65), 2)
        self.assertLess(difference(85), 5)

    def test_effect_validation_precedes_render(self):
        ffmpeg("-f", "lavfi", "-i", "color=c=black:s=160x90:r=30:d=1",
               "-c:v", "libx264", str(self.source))
        output = self.root / "effects.mp4"
        with self.assertRaises(ValueError):
            render(self.source, output, effects=[("flash", "0", "2", "1")])
        self.assertFalse(output.exists())

    def test_validation_detects_wrong_fps_and_silent_video(self):
        ffmpeg("-f", "lavfi", "-i", "color=c=black:s=160x90:r=30:d=0.4",
               "-c:v", "libx264", str(self.source))
        report = check_media(self.source)
        self.assertEqual(report["status"], "FAILED")
        self.assertFalse(report["frame_cadence_matches"])
        self.assertIn("No audio track", report["errors"])

    def test_reject_playlist_container(self):
        other = self.root / "playlist.m3u8"
        other.write_text("#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nmissing.ts\n")
        with self.assertRaisesRegex(ValueError, "media inspection"):
            probe(other)

    @unittest.skipUnless(os.getenv("VORTEX_WHISPER_MODEL") and shutil.which("whisper-cli"),
                         "Set VORTEX_WHISPER_MODEL and put whisper-cli on PATH for live ASR")
    def test_local_asr_exports_and_renders_real_utterance(self):
        filters = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True,
                                 check=True).stdout
        if " flite " not in filters:
            self.skipTest("FFmpeg flite filter is required for the synthetic utterance")
        ffmpeg("-f", "lavfi", "-i", "color=c=black:s=320x180:r=30:d=5",
               "-f", "lavfi", "-i",
               "flite=text='We are testing every word in a video. The violet spider walks slowly.':voice=slt",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
               str(self.source))
        output = self.root / "speech"
        report = transcribe(self.source, output, model=os.environ["VORTEX_WHISPER_MODEL"],
                            language="auto")
        self.assertEqual(report["language"], "en")
        transcript = (output / "transcript.txt").read_text(encoding="utf-8").casefold()
        self.assertIn("testing every word", transcript)
        self.assertTrue(any(item["words"] for item in report["segments"]))
        self.assertTrue(report["segments"] and not report["manual_reviewed"])
        self.assertTrue(read_srt(output / "captions.srt"))
        rendered = render(self.source, self.root / "asr.mp4", captions=output / "transcript.json")
        self.assertGreater(rendered["caption_intervals"], 10)
        self.assertTrue(check_media(rendered["output"])["frame_cadence_matches"])

    def test_media_cli_hook(self):
        ffmpeg("-f", "lavfi", "-i", "color=c=black:s=160x90:r=30:d=0.2",
               "-c:v", "libx264", str(self.source))
        parser = argparse.ArgumentParser()
        add_commands(parser.add_subparsers())
        args = parser.parse_args(["media", "probe", str(self.source)])
        self.assertEqual(args.technical_handler(args)["video"]["avg_fps"], 30)


class EffectsValidationTests(unittest.TestCase):
    def test_effects_reject_invalid_bounds_strength_and_injection(self):
        for effects in (
            [("flash", "0", ".01", "1")],
            [("flash", "0", "1", "NaN")],
            [("blur", "0", "1", "2")],
            [("rotate;evil", "0", "1", "1")],
            [("shake", "0", ".4", "1"), ("shake", ".2", ".5", "1")],
            [("flash", "0", ".1", "1"), ("flash", ".15", ".25", "1")],
        ):
            with self.subTest(effects=effects), self.assertRaises(ValueError):
                prepare_effects(effects, 60, 120)
    def test_same_kind_can_repeat_with_separation(self):
        effects = prepare_effects([("flash", ".5", ".7", ".5"),
                                   ("flash", "0", ".2", ".5")], 60, 60)
        self.assertEqual([(e.start_frame, e.end_frame_exclusive) for e in effects],
                         [(0, 12), (30, 42)])
