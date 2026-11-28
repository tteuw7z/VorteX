import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_git_history.py"
spec = importlib.util.spec_from_file_location("history_security", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@unittest.skipUnless(shutil.which("git"), "Git is needed for history security tests")
class HistoryAuditTests(unittest.TestCase):
    def git(self, root, *args):
        return subprocess.run(["git", "-C", str(root), "-c", "user.name=Fixture",
                               "-c", "user.email=fixture@example.invalid", *args],
                              capture_output=True, check=True)

    def test_removed_credential_still_blocks_without_printing_value(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.git(root, "init")
            file = root / "example.txt"
            secret = "ghp_" + "Z" * 36
            file.write_text(secret)
            self.git(root, "add", ".")
            self.git(root, "commit", "-m", "synthetic history fixture")
            file.write_text("removed")
            self.git(root, "add", ".")
            self.git(root, "commit", "-m", "remove synthetic value")
            report = module.audit_history(root)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertTrue(any(f["rule"] == "github_token" for f in report["findings"]))
            self.assertNotIn(secret, json.dumps(report))

    def test_clean_history_and_shallow_refusal(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            self.git(root, "init")
            (root / "file.txt").write_text("ordinary text")
            self.git(root, "add", ".")
            self.git(root, "commit", "-m", "clean fixture")
            report = module.audit_history(root)
            self.assertEqual(report["status"], "NO_KNOWN_PATTERN_MATCHES")
            self.assertGreaterEqual(report["objects_scanned"], 3)
            clone = Path(directory) / "shallow"
            self.git(root, "clone", "--depth", "1", root.as_uri(), str(clone))
            with self.assertRaisesRegex(ValueError, "shallow"):
                module.audit_history(clone)
