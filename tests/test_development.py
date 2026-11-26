import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vortex.development import coordinate_development
from vortex.security import snapshot


class DevelopmentCoordinatorTests(unittest.TestCase):
    def adapters(self, trace, *, fail=None, mutate=None):
        def build(task, prepared, root):
            trace.append("build")
            self.assertEqual(prepared["stages"][0]["id"], "economy")
            self.assertTrue(prepared["economy"]["mandatory_review_roles_preserved"])
            (root / "main.py").write_text("print('hello')\n")
            return b"fixture build completed"
        def review(root, digest):
            trace.append("review")
            files = [{"path": name, "sha256": hashlib.sha256(data).hexdigest(),
                      "bytes_reviewed": len(data), "status": "PASS"}
                     for name, data in snapshot(root).files]
            return json.dumps({"artifact_sha256": digest,
                               "files": [] if fail == "review" else files}).encode()
        def test(name):
            def run(root, digest):
                trace.append(name)
                if mutate == name:
                    (root / "main.py").write_text("print('modified')")
                return {"artifact_sha256": digest, "passed": 1,
                        "failed": int(fail == name), "skipped": 0, "log": b"fixture test result"}
            return run
        def logic(task, prepared):
            trace.append("logic")
            from vortex.spectors import LogicSpector
            return {field: ["fixture requirement"] for field in LogicSpector.FIELDS}
        return dict(logic_plan=logic, build=build, code_review=review,
                    functional_tests=test("functional"), integration_tests=test("integration"),
                    regression_tests=test("regression"), performance_tests=test("performance"),
                    security_tests=test("security"))

    def test_order_and_no_self_authorized_delivery(self):
        with TemporaryDirectory() as directory:
            trace = []
            root = Path(directory) / "candidate"
            result = coordinate_development("Build Python script", root, approved=True,
                                            **self.adapters(trace))
            self.assertEqual(trace, ["logic", "build", "review", "functional", "integration", "regression", "performance", "security"])
            self.assertEqual(result["status"], "REVIEW_REQUIRED")
            self.assertFalse(result["delivery_authorized"])
            self.assertEqual(result["artifact_sha256"], snapshot(root).digest)

    def test_failure_or_mutation_stops_later_stages(self):
        for failure, mutation, expected in (
            ("review", None, ["logic", "build", "review"]),
            ("functional", None, ["logic", "build", "review", "functional"]),
            (None, "functional", ["logic", "build", "review", "functional"]),
            ("regression", None, ["logic", "build", "review", "functional", "integration", "regression"]),
            ("performance", None, ["logic", "build", "review", "functional", "integration", "regression", "performance"]),
        ):
            with self.subTest(failure=failure, mutation=mutation), TemporaryDirectory() as directory:
                trace = []
                result = coordinate_development("Python", Path(directory) / "candidate", approved=True,
                                                **self.adapters(trace, fail=failure, mutate=mutation))
                self.assertEqual(trace, expected)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(result["delivery_authorized"])

    def test_missing_approval_or_adapter_has_no_side_effects(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "candidate"
            trace = []
            for kwargs in (self.adapters(trace), {"approved": True}):
                report = coordinate_development("Python", root, **kwargs)
                self.assertEqual(report["status"], "BLOCKED")
                self.assertEqual(report["stages"][0]["stage"], "economy")
                self.assertFalse(root.exists())
            self.assertEqual(trace, [])

    def test_incomplete_plan_blocks_before_build(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "candidate"
            trace = []
            adapters = self.adapters(trace)
            adapters["logic_plan"] = lambda *_: {}
            report = coordinate_development("Python", root, approved=True, **adapters)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertFalse(root.exists())
            self.assertEqual(trace, [])
