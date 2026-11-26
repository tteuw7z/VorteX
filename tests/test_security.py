import hashlib
import hmac
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from vortex.security import audit, publish, _canonical, POLICY_VERSION
from vortex.learning import LearningEngine
from vortex.automation import execute_manifest
from vortex.workflow import Stage, Workflow


class DeliveryGateTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.output = self.root / "delivery"
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        self.key = b"fixture-verifier-key-not-a-real-key" * 2

    def write(self, name, data):
        path = self.candidate / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")

    def attest(self, report, **changes):
        now = int(time.time())
        for name in report["required_checks"]:
            (self.evidence / (name + ".log")).write_text("test-only evidence for " + name)
        from vortex.security import snapshot
        captured = snapshot(self.candidate)
        (self.evidence / "code_review.log").write_text(json.dumps({
            "artifact_sha256": captured.digest, "files": [
                {"path": name, "sha256": hashlib.sha256(data).hexdigest(),
                 "bytes_reviewed": len(data), "status": "PASS"} for name, data in captured.files]}))
        payload = {"policy_version": POLICY_VERSION, "kind": report["kind"], "artifact_sha256": report["artifact_sha256"],
                   "reviewer": "test fixture only", "issued_at": now - 1, "expires_at": now + 60,
                   "checks": {name: {"status": "PASS", "evidence_sha256": hashlib.sha256((self.evidence / (name + ".log")).read_bytes()).hexdigest()}
                              for name in report["required_checks"]}}
        payload.update(changes)
        return {"payload": payload, "signature": hmac.new(self.key, _canonical(payload),
                                                            hashlib.sha256).hexdigest()}

    def test_clean_static_scan_never_authorizes_delivery(self):
        self.write("main.py", "print('hello')\n")
        report = audit(self.candidate, "script")
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["findings"], [])
        self.assertEqual(publish(self.candidate, self.output, "script")["status"], "BLOCKED")
        self.assertFalse(self.output.exists())

    def test_valid_attestation_publishes_exact_bytes_and_no_overwrite(self):
        self.write("index.html", "<p>Hello</p>")
        report = audit(self.candidate, "website")
        attestation = self.attest(report)
        result = publish(self.candidate, self.output, "website", attestation=attestation, key=self.key, evidence_dir=self.evidence)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual((self.output / "index.html").read_bytes(),
                         (self.candidate / "index.html").read_bytes())
        self.assertEqual(audit(self.output, "website")["artifact_sha256"], report["artifact_sha256"])
        with self.assertRaises(FileExistsError):
            publish(self.candidate, self.output, "website", attestation=attestation, key=self.key, evidence_dir=self.evidence)

    def test_mutation_forgery_missing_check_and_expiry_block(self):
        self.write("main.py", "print('hello')")
        report = audit(self.candidate, "script")
        signed = self.attest(report)
        bad = [
            (signed, b"x" * 32),
            (self.attest(report, checks={}), self.key),
            (self.attest(report, issued_at=1, expires_at=2), self.key),
            (self.attest(report, kind="website"), self.key),
        ]
        for attestation, key in bad:
            self.assertEqual(publish(self.candidate, self.output, "script",
                                     attestation=attestation, key=key, evidence_dir=self.evidence)["status"], "BLOCKED")
        self.write("main.py", "print('changed')")
        self.assertEqual(publish(self.candidate, self.output, "script", attestation=signed,
                                 key=self.key, evidence_dir=self.evidence)["status"], "BLOCKED")
        self.assertFalse(self.output.exists())

    def test_findings_block_even_with_attestation_and_do_not_leak_values(self):
        token = "ghp_" + "Z" * 36
        self.write("main.py", "import subprocess as s\ns.run('echo unsafe', shell=True)\n")
        self.write("index.html", '<div onclick="bad()">Hello</div>')
        self.write(".env", "TOKEN=" + token)
        report = audit(self.candidate, "website")
        rules = {item["rule"] for item in report["findings"]}
        self.assertTrue({"PY_SHELL_EXECUTION", "WEB_INLINE_HANDLER", "PRIVATE_ENV_FILE",
                         "POSSIBLE_CREDENTIAL"} <= rules)
        self.assertNotIn(token, json.dumps(report))
        self.assertEqual(publish(self.candidate, self.output, "website",
                                 attestation=self.attest(report), key=self.key, evidence_dir=self.evidence)["status"], "BLOCKED")
        self.assertFalse(self.output.exists())

    def test_actual_evidence_required_and_integrity_checked(self):
        self.write("main.py", "print('hello')")
        report = audit(self.candidate, "script")
        attestation = self.attest(report)
        self.assertEqual(publish(self.candidate, self.output, "script",
                                 attestation=attestation, key=self.key)["status"], "BLOCKED")
        record = self.evidence / (report["required_checks"][0] + ".log")
        original = record.read_bytes()
        record.write_bytes(b"tampered evidence")
        self.assertEqual(publish(self.candidate, self.output, "script",
                                 attestation=attestation, key=self.key,
                                 evidence_dir=self.evidence)["status"], "BLOCKED")
        record.write_bytes(original)
        self.assertEqual(publish(self.candidate, self.output, "script",
                                 attestation=attestation, key=self.key,
                                 evidence_dir=self.evidence)["status"], "SUCCESS")
        self.assertEqual([p.name for p in self.output.iterdir()], ["main.py"])

    def test_publication_failure_never_creates_final_directory(self):
        self.write("main.py", "print('hello')")
        report = audit(self.candidate, "script")
        attestation = self.attest(report)
        with patch("vortex.security.Path.rename", side_effect=OSError("test interruption")):
            with self.assertRaises(OSError):
                publish(self.candidate, self.output, "script", attestation=attestation,
                        key=self.key, evidence_dir=self.evidence)
        self.assertFalse(self.output.exists())
        self.assertFalse(any(path.name.startswith(".vortex-") for path in self.root.iterdir()))

    def test_git_metadata_and_symlinks_are_rejected(self):
        self.write("main.py", "pass")
        (self.candidate / ".git").mkdir()
        with self.assertRaises(ValueError):
            audit(self.candidate, "script")
        (self.candidate / ".git").rmdir()
        try:
            (self.candidate / "link").symlink_to(self.root / "outside")
        except OSError:
            self.skipTest("Symlink creation unavailable")
        with self.assertRaises(ValueError):
            audit(self.candidate, "script")

    def test_unparsed_formats_require_attestation(self):
        (self.candidate / "app.apk").write_bytes(b"synthetic binary")
        report = audit(self.candidate, "application")
        self.assertEqual(report["limited_static_coverage"], ["app.apk"])
        self.assertEqual(report["status"], "BLOCKED")


class InternalSecurityTests(unittest.TestCase):
    def test_duplicate_approval_labels_rejected(self):
        with self.assertRaisesRegex(ValueError, "distinct approval"):
            Workflow([Stage("a", "engineering", "first", approval="shared"),
                      Stage("b", "engineering", "second", approval="shared")])

    def test_duplicate_manifest_keys_rejected_before_prepare(self):
        with TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text('{"version":1,"steps":[],"steps":[{"id":"x","argv":["a","b"]}]}')
            calls = []
            with self.assertRaises(ValueError):
                execute_manifest(manifest, lambda argv: calls.append(argv), simulate=True)
            self.assertEqual(calls, [])

    @unittest.skipUnless(os.name == "posix", "POSIX permissions required")
    def test_learning_database_private_permissions(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "knowledge.sqlite"
            engine = LearningEngine(path)
            engine.remember("engineering", "test", "fixture", "review")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "permissions must be private"):
                engine.recall()


class ProcessAndManifestSecurityTests(unittest.TestCase):
    def test_child_environment_does_not_inherit_secrets(self):
        from vortex.process_env import tool_environment
        from vortex.media import _run_tool
        from vortex.android import _run
        from subprocess import CompletedProcess
        secrets = {"OPENAI_API_KEY": "fixture-openai", "VORTEX_DELIVERY_KEY_HEX": "fixture-reviewer",
                   "GITHUB_TOKEN": "fixture-github", "UNRELATED_SECRET": "fixture-unrelated"}
        with patch.dict(os.environ, {"PATH": os.defpath, **secrets}, clear=True):
            self.assertFalse(set(secrets) & tool_environment().keys())
            with self.assertRaises(ValueError):
                tool_environment(extra=["VORTEX_DELIVERY_KEY_HEX"])
            with patch("vortex.media.shutil.which", return_value="/trusted/ffmpeg"), patch(
                    "vortex.media.subprocess.run", return_value=CompletedProcess([], 0, "", "")) as run:
                _run_tool("ffmpeg", [], "fixture")
                self.assertFalse(set(secrets) & run.call_args.kwargs["env"].keys())
            with patch("vortex.android.subprocess.run",
                       return_value=CompletedProcess([], 0, "", "")) as run:
                _run("/trusted/aapt2", [], step="fixture")
                self.assertFalse(set(secrets) & run.call_args.kwargs["env"].keys())

    def test_changed_manifest_cannot_reuse_approval(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "flow.json"
            def write(value):
                path.write_text(json.dumps({"version": 1, "steps": [
                    {"id": "review", "argv": ["archive", value]}]}))
            writes = []
            def prepare(argv):
                return "archive", lambda: writes.append(argv) or {"status": "SUCCESS"}
            write("original")
            plan = execute_manifest(path, prepare, simulate=True)
            self.assertEqual(plan["steps"][0]["argv"], ["archive", "original"])
            write("changed")
            result = execute_manifest(path, prepare, approvals=["review"],
                                      expected_sha256=plan["manifest_sha256"])
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(writes, [])
            current = execute_manifest(path, prepare, simulate=True)
            result = execute_manifest(path, prepare, approvals=["review"],
                                      expected_sha256=current["manifest_sha256"])
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(writes, [("archive", "changed")])


class PortableArtifactSecurityTests(unittest.TestCase):
    def test_script_urls_and_secret_in_filename_are_blocked(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "index.html").write_text('<a href="java&#115;cript:alert(1)">Unsafe</a>')
            report = audit(root, "website")
            self.assertIn("WEB_SCRIPT_URL", {item["rule"] for item in report["findings"]})
            (root / ("ghp_" + "Z" * 36 + ".txt")).touch()
            with self.assertRaisesRegex(ValueError, "possible credential"):
                audit(root, "website")

    @unittest.skipIf(os.name == "nt", "Windows itself rejects device paths")
    def test_reserved_windows_names_are_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "NUL.txt").touch()
            with self.assertRaisesRegex(ValueError, "reserved device"):
                audit(root, "script")


@unittest.skipUnless(os.name == "posix", "POSIX permissions required")
class PrivateOutputTests(unittest.TestCase):
    def test_private_creation_and_media_publication_under_permissive_umask(self):
        from vortex.private_io import private_open
        from vortex.media import _publish_directory
        with TemporaryDirectory() as directory:
            root = Path(directory)
            previous = os.umask(0)
            try:
                with private_open(root / "private.txt", text=True) as stream:
                    stream.write("private data")
                self.assertEqual((root / "private.txt").stat().st_mode & 0o777, 0o600)
                with self.assertRaises(FileExistsError):
                    private_open(root / "private.txt")
                source = root / "staging"
                source.mkdir()
                (source / "transcript.txt").write_text("private transcript")
                _publish_directory(source, root / "published")
                self.assertEqual((root / "published").stat().st_mode & 0o777, 0o700)
                self.assertEqual((root / "published" / "transcript.txt").stat().st_mode & 0o777, 0o600)
            finally:
                os.umask(previous)

    def test_extracted_files_private_under_permissive_umask(self):
        from zipfile import ZipFile
        from vortex.archive import extract_archive
        with TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "input.zip"
            with ZipFile(archive, "w") as stream:
                stream.writestr("nested/private.txt", "private data")
            previous = os.umask(0)
            try:
                extract_archive(archive, root / "output")
                self.assertEqual((root / "output").stat().st_mode & 0o777, 0o700)
                self.assertEqual((root / "output" / "nested").stat().st_mode & 0o777, 0o700)
                self.assertEqual((root / "output" / "nested/private.txt").stat().st_mode & 0o777, 0o600)
            finally:
                os.umask(previous)
