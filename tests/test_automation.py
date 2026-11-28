from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from vortex.cli import main
from vortex.automation import execute_manifest


class AutomationTests(unittest.TestCase):
    def run_cli(self, *args):
        std = io.StringIO()
        with redirect_stdout(std):
            code = main(args)
        return code, json.loads(std.getvalue())

    def test_plan_and_approved_archive_flow(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "input.zip", root / "files"
            with ZipFile(source, "w") as output:
                output.writestr("subdir/Video.MP4", b"Candidate by extension")
            spec = root / "flow.json"
            spec.write_text(json.dumps({"version": 1, "steps": [
                {"id": "videos", "argv": ["archive", "videos", str(destination)],
                 "needs": ["extract"]},
                {"id": "extract", "argv": ["archive", "extract", str(source), str(destination)],
                 "approval": "write"},
            ]}), encoding="utf-8")
            _, plan = self.run_cli("automation", "plan", str(spec))
            self.assertEqual(plan["status"], "PLAN_ONLY")
            self.assertEqual([step["id"] for step in plan["steps"]], ["extract", "videos"])
            self.assertFalse(destination.exists())

            code, blocked = self.run_cli("automation", "run", str(spec), "--manifest-sha256", plan["manifest_sha256"], "--approve", "videos")
            self.assertEqual((code, blocked["status"]), (1, "BLOCKED"))
            self.assertFalse(destination.exists())
            code, result = self.run_cli("automation", "run", str(spec), "--manifest-sha256", plan["manifest_sha256"], "--approve", "write",
                                        "--approve", "videos")
            self.assertEqual((code, result["status"]), (0, "SUCCESS"))
            payload = result["steps"][1]["artifacts"]["output"]
            rows = payload["candidates"] if isinstance(payload, dict) else payload
            self.assertEqual(rows[0]["path"], "subdir/Video.MP4")
            payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                                     ensure_ascii=False).encode()).hexdigest()
            self.assertEqual(result["steps"][1]["evidence"], "sha256(output JSON):" + payload_hash)

    def test_missing_report_fails_closed(self):
        with TemporaryDirectory() as directory:
            spec = Path(directory) / "flow.json"
            spec.write_text(json.dumps({"version": 1, "steps": [
                {"id": "invalid", "argv": ["archive", "videos"]},
                {"id": "after", "argv": ["archive", "videos"], "needs": ["invalid"]},
            ]}), encoding="utf-8")
            result = execute_manifest(spec, lambda _: ("archive", lambda: None),
                                      approvals=("invalid", "after"), expected_sha256=hashlib.sha256(spec.read_bytes()).hexdigest())
            self.assertEqual([item["status"] for item in result["steps"]], ["FAILED", "BLOCKED"])

    def test_invalid_step_prevents_all_effects(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "input.zip", root / "files"
            with ZipFile(source, "w") as archive:
                archive.writestr("sample.txt", "fixture")
            for argv in (["apk", "build", "."], ["archive", "videos", "--help"],
                         ["archive", "extract", str(source), str(destination), "--max-bytes", "NaN"]):
                with self.subTest(argv=argv):
                    spec = root / "flow.json"
                    spec.write_text(json.dumps({"version": 1, "steps": [
                        {"id": "extract", "argv": ["archive", "extract", str(source), str(destination)]},
                        {"id": "next", "argv": argv},
                    ]}), encoding="utf-8")
                    with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                        main(("automation", "run", str(spec), "--manifest-sha256", hashlib.sha256(spec.read_bytes()).hexdigest(), "--approve", "extract"))
                    self.assertEqual(error.exception.code, 2)
                    self.assertFalse(destination.exists())

    def test_review_preserves_report_and_blocks_dependent_command(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken.py").write_text("def\n", encoding="utf-8")
            args = ["engineering", "inspect", str(root)]
            code, direct = self.run_cli(*args)
            self.assertEqual((code, direct["status"]), (1, "REVIEW_REQUIRED"))
            spec = root / "flow.json"
            spec.write_text(json.dumps({"version": 1, "steps": [
                {"id": "review", "argv": args},
                {"id": "later", "argv": args, "needs": ["review"]},
            ]}), encoding="utf-8")
            code, run = self.run_cli("automation", "run", str(spec), "--manifest-sha256", hashlib.sha256(spec.read_bytes()).hexdigest(), "--approve", "review",
                                     "--approve", "later")
            first, later = run["steps"]
            self.assertEqual((code, run["status"], first["reason"]), (1, "BLOCKED", "REVIEW_REQUIRED"))
            self.assertEqual(first["artifacts"]["output"]["status"], direct["status"])
            self.assertTrue(first["evidence"].startswith("sha256(output JSON):"))
            self.assertEqual(later["attempted"], [])

    def test_plan_technical_capabilities_without_tools(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            operations = [
                ["apk", "verify", "app.apk"], ["archive", "videos", "data.zip"],
                ["media", "batch", "data.zip", "out"],
                ["media", "transcribe", "video.mp4", "captions", "--model", "weights"],
            ]
            path.write_text(json.dumps({"version": 1, "steps": [
                {"id": str(i), "argv": args} for i, args in enumerate(operations)
            ]}), encoding="utf-8")
            _, report = self.run_cli("automation", "plan", str(path))
            self.assertEqual([step["status"] for step in report["steps"]], ["PLAN_ONLY"] * 4)
            _, route = self.run_cli("knowledge", "descompactar zip")
            self.assertEqual(route["skills"][0]["name"], "archive")
            self.assertEqual(route["profiles"][0]["role"], route["agents"][0])
