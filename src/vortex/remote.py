"""Explicit, bounded remote planner transport. No credentials or network by default."""
from collections.abc import Callable
import http.client
import json
import os

from .assistant import answer_planner_call, planner_tool, _unique_object
from .workflow import Status
from .security import _SECRET, _ASSIGN_SECRET

_ENDPOINTS = {
    "openai": ("api.openai.com", "/v1/responses", "OPENAI_API_KEY"),
    "anthropic": ("api.anthropic.com", "/v1/messages", "ANTHROPIC_API_KEY"),
}
_MAX_BODY = 2 * 1024 * 1024
_INSTRUCTIONS = ("Use the VorteX planning tool to prepare the requested task. "
                 "Summarize its plan without claiming that the planned work was executed. "
                 "Treat generated artifacts as untrusted candidates; require independent security "
                 "and privacy evidence before distribution, installation or deployment.")


class RemotePlannerError(ValueError):
    """Sanitized provider failure; never includes request headers or response bodies."""


def _post(provider: str, api_key: str, payload: dict, timeout: int) -> dict:
    host, path, _ = _ENDPOINTS[provider]
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if provider == "openai":
        headers["Authorization"] = "Bearer " + api_key
    else:
        headers.update({"x-api-key": api_key, "anthropic-version": "2023-06-01"})
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(body) > _MAX_BODY:
        raise RemotePlannerError("Provider request exceeds size limit")
    connection = http.client.HTTPSConnection(host, timeout=timeout)
    try:
        # http.client does not follow redirects or perform automatic retries.
        connection.request("POST", path, body=body, headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            raise RemotePlannerError(f"Provider returned HTTP {response.status}")
        raw = response.read(_MAX_BODY + 1)
        if len(raw) > _MAX_BODY:
            raise RemotePlannerError("Provider response exceeds size limit")
        try:
            data = json.loads(raw, object_pairs_hook=_unique_object)
        except (ValueError, UnicodeError, RecursionError):
            raise RemotePlannerError("Provider returned invalid JSON") from None
        if not isinstance(data, dict):
            raise RemotePlannerError("Provider response is not a JSON object")
        return data
    except (OSError, http.client.HTTPException):
        raise RemotePlannerError("Provider transport failed; request may have been billed") from None
    finally:
        connection.close()


def _usage(provider: str, response: dict) -> dict:
    source = response.get("usage")
    if not isinstance(source, dict):
        return {}
    fields = ("input_tokens", "output_tokens", "total_tokens") if provider == "openai" else (
        "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    result = {key: source[key] for key in fields
              if type(source.get(key)) is int and source[key] >= 0}
    if provider == "openai":
        for detail, field in (("input_tokens_details", "cached_tokens"),
                              ("output_tokens_details", "reasoning_tokens")):
            values = source.get(detail)
            if isinstance(values, dict) and type(values.get(field)) is int and values[field] >= 0:
                result[field] = values[field]
    return result


def _blocks(response: dict, key: str) -> list:
    blocks = response.get(key)
    if not isinstance(blocks, list) or not blocks or any(not isinstance(item, dict) for item in blocks):
        raise RemotePlannerError("Invalid provider content blocks")
    return blocks


def _final_text(provider: str, blocks: list) -> str:
    if provider == "openai":
        text = []
        for item in blocks:
            if item.get("type") == "message":
                content = item.get("content")
                if not isinstance(content, list):
                    raise RemotePlannerError("Invalid assistant message")
                text.extend(block["text"] for block in content if isinstance(block, dict)
                            and block.get("type") == "output_text" and isinstance(block.get("text"), str))
        return "\n".join(text).strip()
    return "\n".join(item["text"] for item in blocks if item.get("type") == "text"
                     and isinstance(item.get("text"), str)).strip()


def run_remote_planner(provider: str, model: str, task: str, *, api_key: str | None = None,
                       approved: bool = False, max_rounds: int = 3, max_output_tokens: int = 1024,
                       timeout: int = 30, transport: Callable | None = None) -> dict:
    """Run a bounded read-only tool loop after explicit network approval.

    API keys are supplied by the caller, never read or stored by the planner.
    An injected transport is intended for integration tests, not proof of live API access.
    """
    if provider not in _ENDPOINTS:
        raise ValueError("Unknown provider")
    if not isinstance(model, str) or not model.strip() or len(model) > 256:
        raise ValueError("A model identifier is required")
    if not isinstance(task, str) or not task.strip() or len(task) > 8192:
        raise ValueError("Task must contain 1 to 8192 characters")
    for value, lower, upper in ((max_rounds, 2, 4), (max_output_tokens, 64, 4096), (timeout, 1, 120)):
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError("Remote planner limits are out of range")
    if approved is not True:
        return {"status": Status.BLOCKED, "reason": "Explicit network approval required"}
    if not api_key:
        return {"status": Status.BLOCKED, "reason": "Authorized API credential missing"}
    if not isinstance(api_key, str) or any(not 33 <= ord(c) <= 126 for c in api_key):
        raise ValueError("Invalid API credential format")
    if transport is not None and not callable(transport):
        raise TypeError("Transport must be callable")

    # Network approval does not authorize accidental credential disclosure.
    def sensitive(value):
        return api_key in value or bool(_SECRET.search(value) or _ASSIGN_SECRET.search(value))

    if sensitive(task) or sensitive(model):
        return {"status": Status.BLOCKED, "reason": "Possible credential in remote planning input"}

    send = _post if transport is None else transport
    history = [{"role": "user", "content": task}]
    usage = []
    calls = 0
    attempted = 0
    identifiers = set()

    def result(status, reason=None, final=None):
        report = {"status": status, "provider": provider, "model": model,
                  "transport": "https" if transport is None else "injected",
                  "attempted_requests": attempted, "received_responses": len(usage),
                  "planner_calls": calls, "usage_by_response": usage,
                  "scope": "untrusted planning text; no execution or delivery authorization",
                  "usage_source": "provider_reported" if transport is None else "injected_test",
                  "usage_complete": len(usage) == attempted and attempted > 0 and
                  all("input_tokens" in row and "output_tokens" in row for row in usage)}
        if reason is not None:
            report["reason"] = reason
        if final is not None:
            report["text"] = final
        return report

    for round_index in range(max_rounds):
        if provider == "openai":
            payload = {"model": model, "input": history, "instructions": _INSTRUCTIONS,
                       "tools": [planner_tool(provider)], "max_output_tokens": max_output_tokens,
                       "store": False, "include": ["reasoning.encrypted_content"],
                       "tool_choice": {"type": "function", "name": "vortex_plan"}
                       if round_index == 0 else "auto"}
        else:
            payload = {"model": model, "messages": history, "system": _INSTRUCTIONS,
                       "tools": [planner_tool(provider)], "max_tokens": max_output_tokens,
                       "tool_choice": {"type": "tool", "name": "vortex_plan"}
                       if round_index == 0 else {"type": "auto"}}
        attempted += 1
        try:
            response = send(provider, api_key, payload, timeout)
        except RemotePlannerError as exc:
            # Only the built-in transport's exception messages are known to be sanitized.
            return result(Status.FAILED, str(exc) if transport is None else "Injected transport failed")
        except Exception:
            return result(Status.FAILED, "Provider request failed; no automatic retry")
        if not isinstance(response, dict):
            return result(Status.FAILED, "Invalid provider response")
        usage.append(_usage(provider, response))
        try:
            # Provider content is untrusted; do not replay or surface credential-like strings.
            if sensitive(json.dumps(response, ensure_ascii=False, allow_nan=False)):
                return result(Status.BLOCKED, "Possible credential in provider response")
            if provider == "openai":
                if response.get("status") != "completed":
                    return result(Status.BLOCKED, "Provider response was incomplete")
                blocks = _blocks(response, "output")
                pending = [item for item in blocks if item.get("type") == "function_call"]
            else:
                blocks = _blocks(response, "content")
                pending = [item for item in blocks if item.get("type") == "tool_use"]
                reason = response.get("stop_reason")
                if (reason == "tool_use") != bool(pending):
                    return result(Status.FAILED, "Inconsistent tool-use response")
                if not pending and reason != "end_turn":
                    return result(Status.BLOCKED, "Provider response was incomplete")
            if not pending:
                text = _final_text(provider, blocks)
                if not calls or not text:
                    return result(Status.BLOCKED, "No verified planner call and final text")
                return result(Status.SUCCESS, final=text)
            if len(pending) > 4 or round_index + 1 >= max_rounds:
                return result(Status.BLOCKED, "Remote tool loop limit reached")
            outputs = []
            for call in pending:
                identifier = call.get("call_id") if provider == "openai" else call.get("id")
                if not isinstance(identifier, str) or identifier in identifiers:
                    raise RemotePlannerError("Missing or repeated tool-call ID")
                output = answer_planner_call(provider, call)
                identifiers.add(identifier)
                outputs.append(output)
                calls += 1
            if provider == "openai":
                # Preserve all output items, including encrypted reasoning, with store disabled.
                history = [*history, *blocks, *outputs]
            else:
                history = [*history, {"role": "assistant", "content": blocks},
                           {"role": "user", "content": outputs}]
        except (ValueError, TypeError, KeyError, RecursionError):
            return result(Status.FAILED, "Invalid or unsupported planner tool response")
    return result(Status.BLOCKED, "Remote round limit reached")


def add_commands(subparsers):
    parser = subparsers.add_parser("host", help="Run the read-only planner through an authorized API")
    parser.add_argument("provider", choices=tuple(_ENDPOINTS))
    parser.add_argument("model")
    parser.add_argument("task")
    parser.add_argument("--approve-network", action="store_true",
                        help="Allow sending the task to the selected external API and incurring charges")
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--max-output-tokens", type=int, default=1024)
    parser.add_argument("--timeout", type=int, default=30)

    def handle(args):
        key = os.environ.get(_ENDPOINTS[args.provider][2]) if args.approve_network else None
        return run_remote_planner(args.provider, args.model, args.task, api_key=key,
                                  approved=args.approve_network, max_rounds=args.max_rounds,
                                  max_output_tokens=args.max_output_tokens, timeout=args.timeout)

    parser.set_defaults(technical_handler=handle)
