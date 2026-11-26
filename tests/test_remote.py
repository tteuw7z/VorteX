"""Local protocol and transport tests; no live credentials or external API calls."""
from contextlib import redirect_stdout
import io
import json
import unittest
from unittest.mock import patch, Mock

from vortex.cli import main
from vortex.remote import _post, RemotePlannerError, run_remote_planner
from vortex.workflow import Status


class RemotePlannerTests(unittest.TestCase):
    def test_explicit_approval_and_key_required(self):
        send = Mock()
        for flags in ({}, {"approved": "yes", "api_key": "test-key"}, {"approved": True}):
            result = run_remote_planner("openai", "model", "Android", transport=send, **flags)
            self.assertEqual(result["status"], Status.BLOCKED)
        send.assert_not_called()
        out = io.StringIO()
        with redirect_stdout(out), patch.dict("os.environ", {}, clear=True):
            self.assertEqual(main(["host", "anthropic", "model", "Android"]), 1)
        self.assertEqual(json.loads(out.getvalue())["status"], Status.BLOCKED)

    def test_openai_read_only_loop_replays_items_and_reports_usage(self):
        reasoning = {"type": "reasoning", "id": "r", "encrypted_content": "fixture"}
        call = {"type": "function_call", "name": "vortex_plan", "call_id": "c1",
                "arguments": json.dumps({"task": "Android", "agent_limit": 1})}
        requests = []
        def send(provider, key, payload, timeout):
            self.assertEqual((provider, key, timeout), ("openai", "test-key", 30))
            self.assertFalse(payload["store"])
            self.assertIn("reasoning.encrypted_content", payload["include"])
            self.assertNotIn("previous_response_id", payload)
            requests.append(payload)
            if len(requests) == 1:
                return {"status": "completed", "output": [reasoning, call],
                        "usage": {"input_tokens": 40, "output_tokens": 8, "total_tokens": 48}}
            history = payload["input"]
            self.assertEqual(history[1:3], [reasoning, call])
            self.assertEqual(history[-1]["call_id"], "c1")
            self.assertEqual(json.loads(history[-1]["output"])["status"], "PLAN_ONLY")
            return {"status": "completed", "output": [{"type": "message",
                        "content": [{"type": "output_text", "text": "Planned Android build"}]}],
                    "usage": {"input_tokens": 60, "output_tokens": 10, "total_tokens": 70}}
        result = run_remote_planner("openai", "model", "Android", api_key="test-key",
                                    approved=True, transport=send)
        self.assertEqual(result["status"], Status.SUCCESS)
        self.assertEqual((result["planner_calls"], result["received_responses"]), (1, 2))
        self.assertEqual(result["usage_source"], "injected_test")
        self.assertTrue(result["usage_complete"])
        self.assertEqual([u["total_tokens"] for u in result["usage_by_response"]], [48, 70])
        self.assertNotIn("test-key", json.dumps(result))

    def test_anthropic_loop_preserves_assistant_and_tool_result(self):
        call = {"type": "tool_use", "name": "vortex_plan", "id": "t1",
                "input": {"task": "ZIP", "agent_limit": 1}}
        requests = []
        def send(provider, key, payload, timeout):
            requests.append(payload)
            if len(requests) == 1:
                return {"stop_reason": "tool_use", "content": [call],
                        "usage": {"input_tokens": 25, "output_tokens": 9}}
            history = payload["messages"]
            self.assertEqual(history[-2], {"role": "assistant", "content": [call]})
            output = history[-1]["content"][0]
            self.assertEqual((history[-1]["role"], output["tool_use_id"]), ("user", "t1"))
            self.assertEqual(json.loads(output["content"])["skills"][0]["name"], "archive")
            return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Archive plan"}],
                    "usage": {"input_tokens": 44, "output_tokens": 7, "cache_read_input_tokens": 10}}
        result = run_remote_planner("anthropic", "model", "ZIP", api_key="test-key",
                                    approved=True, transport=send)
        self.assertEqual(result["status"], Status.SUCCESS)
        self.assertEqual(result["usage_by_response"][1]["cache_read_input_tokens"], 10)

    def test_unknown_tool_fails_closed_and_round_limit_stops(self):
        call = {"type": "tool_use", "name": "apk_build", "id": "t",
                "input": {"task": "APK", "agent_limit": 1}}
        send = Mock(return_value={"stop_reason": "tool_use", "content": [call]})
        result = run_remote_planner("anthropic", "model", "APK", api_key="test-key",
                                    approved=True, transport=send)
        self.assertEqual(result["status"], Status.FAILED)
        self.assertFalse(result["usage_complete"])
        self.assertEqual(send.call_count, 1)
        call = dict(call, name="vortex_plan")
        send = Mock(side_effect=[
            {"stop_reason": "tool_use", "content": [call]},
            {"stop_reason": "tool_use", "content": [dict(call, id="t2")]},
        ])
        result = run_remote_planner("anthropic", "model", "APK", api_key="test-key",
                                    approved=True, transport=send, max_rounds=2)
        self.assertEqual((result["status"], result["planner_calls"], send.call_count),
                         (Status.BLOCKED, 1, 2))

    def test_transport_failure_sanitizes_and_does_not_retry(self):
        send = Mock(side_effect=RuntimeError("test-key"))
        result = run_remote_planner("openai", "model", "APK", api_key="test-key",
                                    approved=True, transport=send)
        self.assertEqual(result["status"], Status.FAILED)
        self.assertEqual(send.call_count, 1)
        self.assertNotIn("test-key", json.dumps(result))


class HTTPSBoundaryTests(unittest.TestCase):
    def test_fixed_endpoint_and_redirect_rejection(self):
        with patch("vortex.remote.http.client.HTTPSConnection") as factory:
            connection = factory.return_value
            response = connection.getresponse.return_value
            response.status = 302
            with self.assertRaisesRegex(RemotePlannerError, "HTTP 302"):
                _post("openai", "test-key", {"model": "fixture"}, 5)
            factory.assert_called_once_with("api.openai.com", timeout=5)
            self.assertEqual(connection.request.call_args.args, ("POST", "/v1/responses"))
            self.assertEqual(connection.request.call_args.kwargs["headers"]["Authorization"],
                             "Bearer test-key")
            connection.close.assert_called_once()
            response.read.assert_not_called()

    def test_anthropic_headers_and_response_json(self):
        with patch("vortex.remote.http.client.HTTPSConnection") as factory:
            connection = factory.return_value
            response = connection.getresponse.return_value
            response.status = 200
            response.read.return_value = b'{"ok":true}'
            self.assertEqual(_post("anthropic", "test-key", {}, 5), {"ok": True})
            factory.assert_called_once_with("api.anthropic.com", timeout=5)
            headers = connection.request.call_args.kwargs["headers"]
            self.assertEqual(headers["x-api-key"], "test-key")
            self.assertIn("anthropic-version", headers)
            self.assertNotIn("Authorization", headers)
            connection.close.assert_called_once()

    def test_duplicate_provider_json_rejected(self):
        with patch("vortex.remote.http.client.HTTPSConnection") as factory:
            connection = factory.return_value
            response = connection.getresponse.return_value
            response.status = 200
            response.read.return_value = b'{"ok":true,"ok":false}'
            with self.assertRaisesRegex(RemotePlannerError, "invalid JSON"):
                _post("openai", "test-key", {}, 5)
            connection.close.assert_called_once()
