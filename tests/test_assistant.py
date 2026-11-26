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

    def test_host_cannot_request_execution(self):
        for name, extra in (("vortex_plan", {"approved": True}), ("apk_build", {})):
            with self.assertRaises(ValueError):
                answer_planner_call("anthropic", {"type": "tool_use", "id": "A", "name": name,
                                    "input": {"task": "build APK", "agent_limit": 1, **extra}})
