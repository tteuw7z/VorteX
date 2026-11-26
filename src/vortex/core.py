"""Deterministic planning and explicit capability dispatch."""
from collections.abc import Callable, Collection
from copy import deepcopy
from dataclasses import asdict, replace
import json

from .agents import AgentEngine
from .skills import SKILLS, Skill, SkillEngine, normalize  # Re-export legacy API.
from .workflow import Stage, StageResult, Status, Workflow


def plan(task: str, *, agent_limit: int = 3, skills: SkillEngine | None = None) -> dict:
    selected = (skills or SkillEngine()).select(task)
    agents = AgentEngine().select(selected, limit=agent_limit)
    return {"status": Status.PLANNED, "skills": [asdict(skill) for skill in selected],
            "agents": list(agents), "fallback": not selected}


class Engine:
    def __init__(self, skills: SkillEngine | None = None):
        self._skills = skills or SkillEngine()
        self._adapters: dict[str, tuple[Callable[..., dict], bool]] = {}

    def register(self, name: str, adapter: Callable[..., dict], *, with_context: bool = False) -> None:
        if name not in self._skills.names or name in self._adapters:
            raise ValueError("Unknown or duplicate capability")
        if not callable(adapter):
            raise TypeError("Adapter must be callable")
        self._adapters[name] = (adapter, with_context)

    def _invoke(self, name: str, task: str, prior: dict) -> dict:
        adapter, with_context = self._adapters[name]
        try:
            result = adapter(task, deepcopy(prior)) if with_context else adapter(task)
            allowed = (Status.SUCCESS, Status.BLOCKED, Status.FAILED)
            if not isinstance(result, dict) or result.get("status") not in allowed:
                raise ValueError("Adapter returned an invalid status")
            return result
        except Exception as exc:
            return {"status": Status.FAILED, "error_type": type(exc).__name__}

    def run(self, name: str, task: str, *, approved: bool = False) -> dict:
        if approved is not True or name not in self._adapters:
            return {"status": Status.BLOCKED, "reason": "Approval or configured adapter missing"}
        return self._invoke(name, task, {})

    def run_workflow(self, workflow: Workflow, *, approvals: Collection[str] = (),
                     simulate: bool = False) -> dict[str, StageResult]:
        if isinstance(approvals, (str, bytes)):
            raise ValueError("Provide approval labels as a collection of strings")
        results = {}
        for stage in workflow.stages:
            if simulate:
                result = StageResult(Status.PLANNED, reason="Simulation")
            elif any(results[dep].status != Status.SUCCESS for dep in stage.depends_on):
                result = StageResult(Status.BLOCKED, reason="Dependency did not succeed")
            elif (stage.approval or stage.id) not in approvals:
                result = StageResult(Status.BLOCKED, reason="Approval missing")
            else:
                prior = {dep: results[dep].artifacts for dep in stage.depends_on}
                result = self._run_stage(stage, prior)
            results[stage.id] = result
        return results

    def _run_stage(self, stage: Stage, prior: dict) -> StageResult:
        history = []
        attempted = []
        for name in (stage.capability, *stage.alternatives):
            if name not in self._adapters:
                continue
            value = self._invoke(name, stage.task, prior)
            attempted.append(name)
            outcome = replace(self._validate_result(name, value), attempted=tuple(attempted))
            if outcome.status == Status.SUCCESS or not stage.retry_safe:
                return replace(outcome, previous=tuple(history))
            history.append(outcome)
        if not history:
            return StageResult(Status.BLOCKED, reason="No configured adapter")
        return replace(history[-1], previous=tuple(history[:-1]))

    @staticmethod
    def _validate_result(name: str, value: dict) -> StageResult:
        status = Status(value["status"])
        evidence, artifacts = value.get("evidence"), value.get("artifacts", {})
        if not isinstance(artifacts, dict):
            return StageResult(Status.FAILED, name, reason="Invalid artifacts")
        if status == Status.SUCCESS or evidence is not None or artifacts:
            if not isinstance(evidence, str) or not evidence.strip():
                return StageResult(Status.FAILED, name, reason="Missing evidence")
        try:
            clean = json.loads(json.dumps(artifacts, allow_nan=False))
            if clean != artifacts:
                raise ValueError("Lossy JSON conversion")
        except (TypeError, ValueError, RecursionError):
            return StageResult(Status.FAILED, name, reason="Artifacts must be JSON data")
        reason = value.get("reason") or value.get("error_type") or status.value
        return StageResult(status, name, evidence, clean,
                           None if status == Status.SUCCESS else
                           reason if isinstance(reason, str) else status.value)
