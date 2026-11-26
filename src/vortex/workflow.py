"""Types and validation for an executable workflow graph."""
from dataclasses import dataclass, field, replace
from enum import StrEnum
from graphlib import TopologicalSorter
from typing import Iterable


class Status(StrEnum):
    PLANNED = "PLAN_ONLY"
    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


def report_status(payload) -> Status:
    """Translate a technical report into a workflow outcome."""
    if not isinstance(payload, (dict, list)):
        return Status.FAILED
    if isinstance(payload, dict):
        label = str(payload.get("status", "")).upper()
        if label in ("FAIL", "FAILED", "ERROR"):
            return Status.FAILED
        if label in ("BLOCKED", "UNAVAILABLE", "PARTIAL", "REVIEW_REQUIRED", "UNVERIFIED"):
            return Status.BLOCKED
        if label in ("PLAN_ONLY", "SIMULATED", "SIMULATION"):
            return Status.PLANNED
        if "status" in payload and label not in ("SUCCESS", "PASS", "INSPECTED", "READY_FOR_RUNTIME_TEST"):
            return Status.BLOCKED
    return Status.SUCCESS


@dataclass(frozen=True, slots=True)
class Stage:
    id: str
    capability: str
    task: str
    depends_on: tuple[str, ...] = ()
    approval: str | None = None
    alternatives: tuple[str, ...] = ()
    retry_safe: bool = False


@dataclass(frozen=True, slots=True)
class StageResult:
    status: Status
    adapter: str | None = None
    evidence: str | None = None
    artifacts: dict = field(default_factory=dict)
    reason: str | None = None
    attempted: tuple[str, ...] = ()
    previous: tuple["StageResult", ...] = ()
    cache_hit: bool = False


@dataclass(frozen=True, slots=True, init=False)
class Workflow:
    stages: tuple[Stage, ...]

    def __init__(self, stages: Iterable[Stage]):
        entries = []
        for stage in stages:
            for field_name in ("depends_on", "alternatives"):
                names = getattr(stage, field_name)
                if not isinstance(names, (tuple, list)) or any(
                    not isinstance(name, str) or not name.strip() for name in names
                ):
                    raise ValueError(f"{field_name} must contain nonempty strings")
            entries.append(replace(stage, depends_on=tuple(stage.depends_on),
                                   alternatives=tuple(stage.alternatives)))
        index = {stage.id: stage for stage in entries}
        if not entries or len(index) != len(entries):
            raise ValueError("Workflow needs nonempty, unique stages")
        for stage in entries:
            if type(stage.retry_safe) is not bool:
                raise ValueError("retry_safe must be a boolean")
            fields = (stage.id, stage.capability, stage.task)
            if any(not field.strip() for field in fields):
                raise ValueError("Stage ID, capability and task are required")
            if stage.approval is not None and not stage.approval.strip():
                raise ValueError("Approval label cannot be empty")
            if unknown := set(stage.depends_on) - index.keys():
                raise ValueError(f"Unknown dependencies for {stage.id}: {', '.join(sorted(unknown))}")
            access = (stage.capability, *stage.alternatives)
            if any(not name.strip() for name in access) or len(access) != len(set(access)):
                raise ValueError("Alternatives must be distinct nonempty capabilities")
        graph = {stage.id: stage.depends_on for stage in entries}
        ordered = tuple(index[stage_id] for stage_id in TopologicalSorter(graph).static_order())
        object.__setattr__(self, "stages", ordered)
