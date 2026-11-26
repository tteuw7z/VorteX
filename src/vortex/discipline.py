"""Automatic preflight and review inventory; never treats a plan as execution."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re

from .agents import AgentEngine
from .core import plan
from .skills import SKILLS, normalize
from .security import snapshot

_STAGES = (
    ("economy", "Select relevant profiles; keep the task and mandatory checks intact"),
    ("analysis", "Define inputs, processing, outputs, constraints and acceptance criteria"),
    ("algorithm", "Decompose and trace normal, boundary and invalid cases"),
    ("implementation", "Use clear names, small functions, purposeful comments and simple design"),
    ("code_review", "Separate reviewer checks all files and error paths against exact hashes"),
    ("functional_tests", "Execute normal, boundary, invalid-input and regression cases"),
    ("security_tests", "Verify privacy, permissions, abuse cases and dependency integrity"),
    ("delivery", "Require independent signed evidence for the exact artifact; otherwise block"),
)
_MANDATORY = ("code reviewer", "qa", "security reviewer")
_DEVELOPMENT_WORDS = frozenset(("app", "apk", "android", "aplicativo", "website", "site", "web",
                                "script", "codigo", "code", "python", "software", "api",
                                "programa", "program", "skill", "database", "banco", "sql"))


def _bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def _estimate(size):
    return (size + 3) // 4


def prepare_task(task, *, agent_limit=3, skills=None):
    """Run economical routing automatically, without removing requirements."""
    if not isinstance(task, str) or not task.strip() or len(task) > 8192:
        raise ValueError("Planning task must contain 1 to 8192 characters")
    route = plan(task, agent_limit=agent_limit, skills=skills)
    engine = AgentEngine()
    catalog = [asdict(profile) for profile in engine.catalog()]
    words = set(re.findall(r"\w+", normalize(task)))
    is_development = bool(words & _DEVELOPMENT_WORDS)
    roles = tuple(route["agents"])
    if not roles:
        roles = ("software engineer",) if is_development else ("reviewer",)
    # Use the cap for the first route only. Keep every matching enabled role,
    # even when doing so saves fewer tokens; review roles are non-negotiable.
    allowed = skills.names if skills is not None else {s.name for s in SKILLS}
    all_matches = [s for s in SKILLS if words.intersection(s.keywords)]
    matched = [s for s in all_matches if s.name in allowed]
    initial = tuple(dict.fromkeys((*roles, *_MANDATORY)))
    matched_roles = tuple(dict.fromkeys(role for skill in matched for role in skill.agents))
    chosen = tuple(dict.fromkeys((*initial, *matched_roles)))
    selected = [asdict(profile) for profile in engine.load(chosen)]
    omitted = [profile["role"] for profile in catalog if profile["role"] not in chosen]
    chosen_skills = {s["name"] for s in route["skills"]}
    deferred_skills = [s.name for s in matched if s.name not in chosen_skills]
    deferred_roles = [role for role in matched_roles if role not in initial]
    disabled_matches = [s.name for s in all_matches if s.name not in allowed]
    before = _bytes({"task": task, "profiles": catalog})
    after = _bytes({"task": task, "profiles": selected})
    # This compares two defined context payloads, not provider billing or latency.
    return {"status": "PLAN_ONLY", "route": route,
            "economy": {"baseline": "full local profile catalog plus unchanged task",
                        "candidate": "selected profiles plus unchanged task",
                        "baseline_bytes": before, "selected_bytes": after,
                        "estimated_baseline_tokens": _estimate(before),
                        "estimated_selected_tokens": _estimate(after),
                        "estimated_saved_tokens": _estimate(before) - _estimate(after),
                        "estimated_saved_percent": round(100 * (1 - _estimate(after) / _estimate(before)), 2),
                        "omitted_profiles": omitted, "deferred_matching_skills": deferred_skills,
                        "deferred_matching_roles": deferred_roles,
                        "automatically_expanded_roles": deferred_roles,
                        "automatically_expanded_skills": deferred_skills,
                        "explicitly_disabled_matching_skills": disabled_matches,
                        "all_enabled_keyword_matches_covered": True,
                        "task_preserved": True, "mandatory_review_roles_preserved": True,
                        "actual_provider_tokens": None, "performance_equivalence": "NOT_MEASURED",
                        "method": "ceil(compact UTF-8 JSON bytes / 4); excludes report and other request overhead"},
            "selected_profiles": selected,
            "stages": [{"id": name, "instruction": instruction} for name, instruction in _STAGES],
            "development_detected": is_development,
            "review_policy": "all enabled keyword matches expanded automatically; semantic coverage still requires review",
            "delivery_authorized": False}


def review_candidate(root: Path):
    """Inventory the exact bytes for a separate reviewer, without running untrusted code."""
    captured = snapshot(root)
    rows = []
    for name, data in captured.files:
        rows.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(),
                     "size": len(data), "lines": len(data.splitlines()),
                     "review_status": "PENDING_INDEPENDENT_REVIEW"})
    return {"status": "BLOCKED", "artifact_sha256": captured.digest, "files": rows,
            "total_bytes": sum(row["size"] for row in rows),
            "static_findings": list(captured.findings),
            "limited_static_coverage": list(captured.unparsed),
            "reviewer": "code reviewer",
            "checklist": ["trace inputs, processing and outputs", "check boundary cases and failure paths",
                          "verify clear names and useful, concise comments",
                          "prefer simple functions; justify classes and inheritance",
                          "check data validation, transactions and integrity where relevant",
                          "review all file bytes and record exact hashes",
                          "run functional and regression tests in a trusted isolated environment",
                          "require independent security and privacy evidence"],
            "scope": "all captured file bytes inventoried; human/independent semantic review not yet performed"}
