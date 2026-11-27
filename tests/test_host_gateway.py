"""Real Python gateway operations and defensive regressions."""
import hashlib
import json
import subprocess
import sys
import unittest

from vortex.host_gateway import MAX_BYTES, handle


def request(operation, arguments):
    return json.dumps({"schema": 1, "operation": operation,
                       "arguments": arguments}).encode()


class HostGatewayTests(unittest.TestCase):
    def test_discovery_does_not_authorize_delivery(self):
        result = handle(request("capabilities", {}))
        self.assertEqual(result["status"], "ok")
        self.assertIn("design.audit", result["result"]["operations"])
        self.assertFalse(result["execution"])
        self.assertFalse(result["delivery_authorized"])

    def test_actual_design_audit_with_evidence(self):
        raw = request("design.audit", {"document": {
            "colors": {"fg": "#000", "bg": "#fff"},
            "contrast_pairs": [{"foreground": "fg", "background": "bg"}]}})
        result = handle(raw)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["execution"])
        self.assertFalse(result["delivery_authorized"])
        self.assertEqual(result["result"]["contrast"][0]["ratio"], 21)
        self.assertEqual(result["result"]["status"], "PASS")
        canonical = json.dumps(result["result"], sort_keys=True, ensure_ascii=True,
                               separators=(",", ":"), allow_nan=False).encode("ascii")
        self.assertEqual(result["evidence"]["result_sha256"],
                         hashlib.sha256(canonical).hexdigest())
        self.assertEqual(result, handle(raw))

    def test_real_planner_is_not_task_execution(self):
        result = handle(request("plan", {"task": "compile APK Android", "agent_limit": 2}))
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["execution"])
        self.assertFalse(result["delivery_authorized"])

    def test_fail_closed(self):
        bad = [
            b'{"schema":1,"schema":1,"operation":"capabilities","arguments":{}}',
            b'{"schema":true,"operation":"capabilities","arguments":{}}',
            b'{"schema":1,"operation":"design.audit","arguments":{"document":NaN}}',
            b'\xff', b' ' * (MAX_BYTES + 1),
            request("shell", {"command": "ignored"}),
            request("capabilities", {"path": "/tmp"}),
            request("plan", {"task": "x", "agent_limit": True}),
            request("design.audit", {"document": {"colors": {"bad": "invalid"}}}),
            b'[' * 5000 + b']' * 5000,
        ]
        for raw in bad:
            with self.subTest(length=len(raw)):
                result = handle(raw)
                self.assertEqual(result["status"], "blocked")
                self.assertFalse(result["execution"])
                self.assertFalse(result["delivery_authorized"])
                self.assertNotIn("result", result)

    def test_stdio_integration(self):
        proc = subprocess.run([sys.executable, "-m", "vortex.host_gateway"],
                              input=request("capabilities", {}), capture_output=True,
                              timeout=15, check=True)
        self.assertEqual(json.loads(proc.stdout)["status"], "ok")
        self.assertEqual(proc.stderr, b"")
