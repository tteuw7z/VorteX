import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from vortex.editor import render
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
