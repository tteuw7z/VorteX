"""Execute declarative local jobs with the existing workflow engine."""
from collections.abc import Callable, Collection
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from zipfile import BadZipFile

from .core import Engine
from .assistant import _unique_object
from .workflow import Stage, Status, Workflow, report_status


def _strings(value, name):
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip()
                                          or "\0" in item for item in value):
        raise ValueError(f"{name} must be a list of nonempty strings")
    return tuple(value)


def execute_manifest(path: Path, prepare: Callable, *, approvals: Collection[str] = (),
                     simulate: bool = False, expected_sha256: str | None = None) -> dict:
    """Prepare all tool invocations, then execute only approved stages."""
    with path.open("rb") as stream:
        raw = stream.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Automation manifest exceeds size limit")
    digest = hashlib.sha256(raw).hexdigest()
    if not simulate and expected_sha256 != digest:
        return {"status": Status.BLOCKED, "reason": "Manifest approval digest missing or changed",
                "manifest_sha256": digest, "steps": []}
    spec = json.loads(raw, object_pairs_hook=_unique_object)
    if not isinstance(spec, dict) or spec.keys() - {"version", "steps"}:
        raise ValueError("Expected an automation manifest with version and steps")
    if type(spec.get("version")) is not int or spec["version"] != 1:
        raise ValueError("Unsupported automation manifest version")
    steps = spec.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 256:
        raise ValueError("Automation requires a nonempty steps list")

    stages, invocations, arguments = [], {}, {}
    for entry in steps:
        if not isinstance(entry, dict) or entry.keys() - {"id", "argv", "needs", "approval"}:
            raise ValueError("Each step may contain id, argv, needs and approval")
        step_id, approval = entry.get("id"), entry.get("approval")
        if not isinstance(step_id, str) or not step_id.strip() or "\0" in step_id:
            raise ValueError("Each step needs a nonempty ID")
        if approval is not None and (
            not isinstance(approval, str) or not approval.strip() or "\0" in approval
        ):
            raise ValueError("Approval labels must be nonempty strings")
        needs = _strings(entry.get("needs", []), "needs")
        argv = _strings(entry.get("argv"), "argv")
        if len(argv) < 2:
            raise ValueError("Each step needs a local command and operation")
        capability, invoke = prepare(argv)
        stages.append(Stage(step_id, capability, step_id, depends_on=needs, approval=approval))
        invocations[step_id] = invoke
        arguments[step_id] = list(argv)

    workflow = Workflow(stages)
    if isinstance(approvals, (str, bytes)):
        raise ValueError("Approvals must be a collection of labels")
    known_approvals = {stage.approval or stage.id for stage in workflow.stages}
    if unknown := set(approvals) - known_approvals:
        raise ValueError(f"Unknown stage approvals: {', '.join(sorted(unknown))}")
    engine = Engine()
    for capability in dict.fromkeys(stage.capability for stage in workflow.stages):
        engine.register(capability, lambda step_id: _invoke(invocations[step_id]))
    results = engine.run_workflow(workflow, approvals=approvals, simulate=simulate)
    states = {result.status for result in results.values()}
    final = (Status.FAILED if Status.FAILED in states else Status.BLOCKED if Status.BLOCKED in states
             else Status.PLANNED if simulate else Status.SUCCESS)
    return {"status": final, "manifest_sha256": digest,
            "steps": [asdict(results[stage.id]) | {"id": stage.id,
            "argv": arguments[stage.id],
            "needs": list(stage.depends_on), "approval": stage.approval or stage.id}
            for stage in workflow.stages]}


def _invoke(callback: Callable) -> dict:
    try:
        payload = callback()
    except FileNotFoundError as exc:
        return {"status": Status.BLOCKED, "reason": type(exc).__name__}
    except (OSError, ValueError, BadZipFile) as exc:
        return {"status": Status.FAILED, "reason": type(exc).__name__}
    if not isinstance(payload, (dict, list)):
        return {"status": Status.FAILED, "reason": "Expected a JSON object or array from the command"}
    status = report_status(payload)
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    result = {"status": status, "evidence": "sha256(output JSON):" + hashlib.sha256(encoded).hexdigest(),
              "artifacts": {"output": json.loads(encoded)}}
    if status != Status.SUCCESS:
        result["reason"] = str(payload.get("reason") or payload.get("status"))
        if status == Status.PLANNED:
            result["status"] = Status.BLOCKED
    return result
