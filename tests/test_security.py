import hashlib
import hmac
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

from vortex.security import audit, publish, _canonical
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
        self.key = b"fixture-verifier-key-not-a-real-key" * 2

    def write(self, name, data):
        path = self.candidate / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")

    def attest(self, report, **changes):
        now = int(time.time())
        payload = {"policy_version": 1, "kind": report["kind"], "artifact_sha256": report["artifact_sha256"],
                   "reviewer": "test fixture only", "issued_at": now - 1, "expires_at": now + 60,
                   "checks": {name: {"status": "PASS", "evidence_sha256": "a" * 64}
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
        result = publish(self.candidate, self.output, "website", attestation=attestation, key=self.key)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual((self.output / "index.html").read_bytes(),
                         (self.candidate / "index.html").read_bytes())
        self.assertEqual(audit(self.output, "website")["artifact_sha256"], report["artifact_sha256"])
        with self.assertRaises(FileExistsError):
            publish(self.candidate, self.output, "website", attestation=attestation, key=self.key)

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
                                     attestation=attestation, key=key)["status"], "BLOCKED")
        self.write("main.py", "print('changed')")
        self.assertEqual(publish(self.candidate, self.output, "script", attestation=signed,
                                 key=self.key)["status"], "BLOCKED")
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
                                 attestation=self.attest(report), key=self.key)["status"], "BLOCKED")
        self.assertFalse(self.output.exists())

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
                execute_manifest(manifest, lambda argv: calls.append(argv))
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
