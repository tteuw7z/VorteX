"""Host-side tool contract for the local, read-only planner."""
import json

from .core import plan


def planner_tool(provider: str) -> dict:
    schema = {"type": "object", "properties": {"task": {"type": "string"},
              "agent_limit": {"type": "integer", "minimum": 1, "maximum": 4}},
              "required": ["task", "agent_limit"], "additionalProperties": False}
    description = "Plan a task with the installed VorteX capability catalog."
    if provider == "openai":
        return {"type": "function", "name": "vortex_plan", "description": description,
                "parameters": schema, "strict": True}
    if provider == "anthropic":
        return {"name": "vortex_plan", "description": description, "input_schema": schema}
    raise ValueError("Unknown planner host")


def answer_planner_call(provider: str, call: dict) -> dict:
    """Consume one decoded Responses or Messages tool call and return its result item."""
    if not isinstance(call, dict) or call.get("name") != "vortex_plan":
        raise ValueError("Expected a vortex_plan tool call")
    if provider == "openai" and call.get("type") == "function_call":
        identifier = call.get("call_id")
        raw = call.get("arguments")
        if not isinstance(raw, str) or len(raw) > 65536:
            raise ValueError("Invalid function arguments")
        args = json.loads(raw)
    elif provider == "anthropic" and call.get("type") == "tool_use":
        identifier = call.get("id")
        args = call.get("input")
    else:
        raise ValueError("Unexpected planner host or call type")
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("Missing tool call identifier")
    if not isinstance(args, dict) or args.keys() != {"task", "agent_limit"}:
        raise ValueError("Expected task and agent_limit")
    if not isinstance(args["task"], str) or len(args["task"]) > 8192:
        raise ValueError("Invalid planning task")
    output = json.dumps(plan(**args), ensure_ascii=False)
    if provider == "openai":
        return {"type": "function_call_output", "call_id": identifier, "output": output}
    return {"type": "tool_result", "tool_use_id": identifier, "content": output}
