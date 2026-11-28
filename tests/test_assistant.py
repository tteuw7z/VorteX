import json
import unittest

from vortex.assistant import answer_planner_call, planner_tool


class PlannerHostTests(unittest.TestCase):
    def test_hosts_return_same_plan_and_echo_call_id(self):
        args = {"task": "Legendar vídeos do ZIP", "agent_limit": 2}
        calls = [
            ("openai", {"type": "function_call", "name": "vortex_plan", "call_id": "A",
                        "arguments": json.dumps(args)}, "parameters", "call_id", "output"),
            ("anthropic", {"type": "tool_use", "name": "vortex_plan", "id": "B",
                           "input": args}, "input_schema", "tool_use_id", "content"),
        ]
        plans = []
        for host, call, schema, identifier, content in calls:
            self.assertFalse(planner_tool(host)[schema]["additionalProperties"])
            result = answer_planner_call(host, call)
            self.assertEqual(result[identifier], call.get("call_id") or call["id"])
            plans.append(json.loads(result[content]))
        self.assertEqual(plans[0], plans[1])
        self.assertEqual(plans[0]["status"], "PLAN_ONLY")

    def test_unicode_length_matches_across_hosts(self):
        args = {"task": "vídeo " + "🎥" * 6000, "agent_limit": 2}
        anthropic = answer_planner_call("anthropic", {"type": "tool_use", "id": "A",
                                         "name": "vortex_plan", "input": args})
        for escaped in (False, True):
            openai = answer_planner_call("openai", {"type": "function_call", "call_id": "B",
                                          "name": "vortex_plan",
                                          "arguments": json.dumps(args, ensure_ascii=escaped)})
            self.assertEqual(openai["output"], anthropic["content"])

    def test_host_cannot_request_execution(self):
        for name, extra in (("vortex_plan", {"approved": True}), ("apk_build", {})):
            with self.assertRaises(ValueError):
                answer_planner_call("anthropic", {"type": "tool_use", "id": "A", "name": name,
                                    "input": {"task": "build APK", "agent_limit": 1, **extra}})

    def test_duplicate_json_keys_are_rejected(self):
        for raw in ('{"task":"APK","task":"finance","agent_limit":1}',
                    '{"task":"APK","agent_limit":1,"agent_limit":2}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                answer_planner_call("openai", {"type": "function_call", "name": "vortex_plan",
                                    "call_id": "A", "arguments": raw})

    def test_invalid_limits_and_empty_tasks_are_rejected_by_both_hosts(self):
        for args in ({"task": "APK", "agent_limit": True}, {"task": "APK", "agent_limit": 0},
                     {"task": "APK", "agent_limit": 5}, {"task": " ", "agent_limit": 1}):
            for provider, call in (
                ("openai", {"type": "function_call", "call_id": "A", "arguments": json.dumps(args)}),
                ("anthropic", {"type": "tool_use", "id": "A", "input": args}),
            ):
                with self.subTest(args=args, provider=provider), self.assertRaises(ValueError):
                    answer_planner_call(provider, {"name": "vortex_plan", **call})
