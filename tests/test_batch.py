import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from vortex.batch import inspect_batch


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Batch integration requires FFmpeg and FFprobe")
class BatchTests(unittest.TestCase):
    def test_zip_batch_isolates_a_bad_video(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "clip.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "color=red:size=64x64:rate=30:duration=0.4", "-c:v", "libx264",
                            str(fixture)], check=True, stdin=subprocess.DEVNULL)
            source = root / "media.zip"
            with ZipFile(source, "w") as archive:
                archive.write(fixture, "pastas/A.MP4")
                archive.writestr("pastas/B.mp4", "Invalid video")
                archive.write(fixture, "pastas/nova/C.mp4")
            destination = root / "result"
            result = inspect_batch(source, destination)
            self.assertEqual((result["status"], result["candidates"], result["complete"]),
                             ("PARTIAL", 3, 2))
            self.assertEqual([row["status"] for row in result["videos"]], ["SUCCESS", "FAILED", "SUCCESS"])
            report = json.loads((destination / "batch.json").read_text())
            for row in (report["videos"][0], report["videos"][2]):
                frames = json.loads((destination / row["frames"]["manifest"]).read_text())
                self.assertEqual(frames["frames"][0]["seconds"], 0.0)
                self.assertIsNotNone(row["metadata"]["video"])
                self.assertEqual(row["transcript"]["status"], "NOT_REQUESTED")

    def test_interrupted_batch_can_retry_same_destination(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "media.zip"
            with ZipFile(source, "w") as archive:
                archive.writestr("bad.mp4", b"invalid")
            dest = root / "result"
            with patch("vortex.batch._inspect", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
                inspect_batch(source, dest)
            self.assertFalse(dest.exists())
            self.assertEqual(inspect_batch(source, dest)["status"], "FAILED")
            self.assertTrue((dest / "batch.json").is_file())
