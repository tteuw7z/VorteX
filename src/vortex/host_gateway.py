"""Bounded local host gateway. Only fixed, read-only operations; no shell or network.

The trusted host must install this package and invoke it locally. A catalog
entry alone is not a binding. Results never authorize delivery.
"""
import hashlib
import json
import sys
from .assistant import _unique_object
from .discipline import prepare_task
from .design import audit

MAX_BYTES = 65536
OPERATIONS = ("capabilities", "plan", "design.audit")


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _reject_constant(_):
    raise ValueError("Non-finite JSON number")


def _failure(reason):
    return {"schema": 1, "status": "blocked", "reason": reason,
            "execution": False, "delivery_authorized": False}


def handle(raw):
    """Return a structured response. Never echo invalid requests or exceptions."""
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        return _failure("invalid_size")
    try:
        request = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
        if not isinstance(request, dict) or set(request) != {"schema", "operation", "arguments"}:
            return _failure("invalid_request")
        if type(request["schema"]) is not int or request["schema"] != 1:
            return _failure("unsupported_schema")
        operation, args = request["operation"], request["arguments"]
        if not isinstance(operation, str) or operation not in OPERATIONS:
            return _failure("operation_not_bound")
        if not isinstance(args, dict):
            return _failure("invalid_arguments")
        if operation == "capabilities":
            if args:
                return _failure("invalid_arguments")
            output = {"operations": list(OPERATIONS), "scope": "local read-only",
                      "independent_agents": False}
            execution = False
        elif operation == "plan":
            if set(args) != {"task", "agent_limit"}:
                return _failure("invalid_arguments")
            task, limit = args["task"], args["agent_limit"]
            if (not isinstance(task, str) or not task.strip() or len(task) > 8192
                    or type(limit) is not int or not 1 <= limit <= 4):
                return _failure("invalid_arguments")
            output = prepare_task(task, agent_limit=limit)
            execution = False
        else:
            if set(args) != {"document"}:
                return _failure("invalid_arguments")
            output = audit(args["document"])
            execution = True
        if len(_canonical(output)) > MAX_BYTES:
            return _failure("output_limit")
        return {"schema": 1, "status": "ok", "operation": operation,
                "execution": execution, "delivery_authorized": False,
                "result": output,
                "evidence": {"request_sha256": _digest(request),
                             "result_sha256": _digest(output)}}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return _failure("invalid_input")
    except Exception:
        return _failure("internal_error")


def main():
    result = handle(sys.stdin.buffer.read(MAX_BYTES + 1))
    sys.stdout.buffer.write(_canonical(result) + b"\n")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
