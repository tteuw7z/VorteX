"""Deterministic planning and explicit capability dispatch."""
from dataclasses import dataclass, asdict
from enum import StrEnum
from collections.abc import Callable
import unicodedata

class Status(StrEnum):
    PLANNED = "PLAN_ONLY"
    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"

@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    keywords: tuple[str, ...]
    agents: tuple[str, ...]
    steps: tuple[str, ...]

SKILLS = (
    Skill("android", ("apk", "android", "gradle"), ("android engineer", "qa"), ("inspect project", "resolve build tools", "build", "verify signature and hash")),
    Skill("media", ("video", "audio", "transcribe", "transcrever", "motion"), ("media engineer", "editor"), ("inventory inputs", "inspect audio and frames", "process", "validate output")),
    Skill("engineering", ("python", "code", "codigo", "bug", "software", "api"), ("software engineer", "qa"), ("inspect", "implement", "test", "review")),
    Skill("research", ("research", "pesquisa", "investigar", "sources"), ("researcher", "reviewer"), ("decompose", "gather sources", "cross-check", "synthesize")),
    Skill("design", ("design", "ui", "figma", "interface"), ("designer", "accessibility reviewer"), ("requirements", "prototype", "validate")),
    Skill("learning", ("study", "estudar", "quiz", "aprender"), ("educator",), ("identify source", "explain", "practice", "review errors")),
    Skill("security", ("security", "seguranca", "audit", "auditoria"), ("security reviewer",), ("scope authorization", "inspect", "verify", "report")),
    Skill("automation", ("workflow", "automacao", "automation"), ("automation engineer",), ("map steps", "check permissions", "execute", "verify")),
)

def normalize(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))

def plan(task: str, *, agent_limit: int = 3) -> dict:
    if not task.strip() or not 1 <= agent_limit <= 4:
        raise ValueError("Nonempty task and agent limit 1–4 required")
    import re
    tokens = set(re.findall(r"\w+", normalize(task)))
    ranked = sorted(((len(tokens.intersection(s.keywords)), i, s) for i, s in enumerate(SKILLS)), key=lambda x: (-x[0], x[1]))
    selected = [s for score, _, s in ranked if score > 0][:3]
    agents = list(dict.fromkeys(a for s in selected for a in s.agents))[:agent_limit]
    return {"status": Status.PLANNED, "skills": [asdict(s) for s in selected], "agents": agents, "fallback": not selected}

class Engine:
    def __init__(self):
        self._adapters: dict[str, Callable[[str], dict]] = {}

    def register(self, name: str, adapter: Callable[[str], dict]) -> None:
        if name not in {s.name for s in SKILLS} or name in self._adapters:
            raise ValueError("Unknown or duplicate capability")
        self._adapters[name] = adapter

    def run(self, name: str, task: str, *, approved: bool = False) -> dict:
        if not approved or name not in self._adapters:
            return {"status": Status.BLOCKED, "reason": "Approval or configured adapter missing"}
        try:
            result = self._adapters[name](task)
            if not isinstance(result, dict) or result.get("status") not in {Status.SUCCESS, Status.BLOCKED, Status.FAILED}:
                raise ValueError("Adapter returned an invalid status")
            return result
        except Exception as exc:
            return {"status": Status.FAILED, "error_type": type(exc).__name__}
