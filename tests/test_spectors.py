import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vortex.spectors import CodeSpector, TokenSpector, TestSpector
from vortex.security import snapshot, audit


class SpectorTests(unittest.TestCase):
    def test_lossless_task_and_nonbeneficial_fallback(self):
        catalog = [{"role": "one"}, {"role": "two"}]
        selected, report = TokenSpector.select("Preserve exactly: á", catalog, catalog[:1])
        self.assertEqual(selected, catalog[:1])
        self.assertGreater(report["estimated_saved_tokens"], 0)
        self.assertEqual(report["discarded_task_information"], [])
        selected, report = TokenSpector.select("task", catalog, catalog + catalog)
        self.assertEqual(selected, catalog)
        self.assertFalse(report["optimization_applied"])
        self.assertIsNone(report["actual_provider_tokens"])

    def test_code_inventory_and_syntax_without_execution(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = b"def f(x=[]):\n    try:\n        return x\n    except:\n        raise\n"
            (root / "valid.py").write_bytes(source)
            (root / "invalid.py").write_text("def broken(:\n")
            rows = {r["path"]: r for r in CodeSpector.inspect(snapshot(root))}
            valid = rows["valid.py"]
            self.assertEqual(valid["sha256"], hashlib.sha256(source).hexdigest())
            self.assertEqual(valid["syntax"], "COMPILED")
            self.assertEqual({a["rule"] for a in valid["advisories"]},
                             {"BARE_EXCEPT", "MUTABLE_DEFAULT"})
            self.assertEqual(rows["invalid.py"]["syntax"], "INVALID")
            self.assertEqual(valid["review_status"], "PENDING_INDEPENDENT_REVIEW")

    def test_required_delivery_checks_and_skipped_tests(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("print(1)")
            report = audit(root, "script")
            self.assertTrue({"integration_tests", "regression_tests", "performance_tests"}
                            <= set(report["required_checks"]))
            self.assertEqual(report["status"], "BLOCKED")
        receipt = {"artifact_sha256": "a", "passed": 1, "failed": 0, "skipped": 1, "log": b"test"}
        self.assertFalse(TestSpector.receipt(receipt, "a")[0])
        with self.assertRaises(ValueError):
            TestSpector.receipt(receipt, "b")
