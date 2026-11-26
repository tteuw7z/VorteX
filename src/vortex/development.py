"""Ordered development coordinator for explicitly trusted host adapters.

This module neither executes untrusted shell commands nor signs a release.
The host owns isolation, adapter independence, authorization and evidence retention.
"""
from collections.abc import Callable
from copy import deepcopy
import hashlib
from pathlib import Path

from .discipline import prepare_task
from .security import snapshot, _review_coverage_valid
from .spectors import LogicSpector, CodeSpector, TestSpector, SecuritySpector, DeliverySpector

_MAX_LOG_BYTES = 2 * 1024 * 1024


def _log_digest(log):
    if not isinstance(log, bytes) or not log.strip() or len(log) > _MAX_LOG_BYTES:
        raise ValueError("Missing or oversized stage evidence")
    return hashlib.sha256(log).hexdigest()


def coordinate_development(task: str, candidate: Path, *,
                           build: Callable | None = None,
                           code_review: Callable | None = None,
                           functional_tests: Callable | None = None,
                           security_tests: Callable | None = None,
                           logic_plan: Callable | None = None,
                           integration_tests: Callable | None = None,
                           regression_tests: Callable | None = None,
                           performance_tests: Callable | None = None,
                           approved: bool = False, agent_limit: int = 3) -> dict:
    """Prepare automatically, then build, review, test and security-check in order.

    Logic adapter gets (task, preflight) and returns the structured plan.
    Builder gets (task, preflight including logic plan, private candidate directory) and returns log bytes.
    Reviewer gets (candidate, digest) and returns the structured code_review.log bytes.
    Test adapters get (candidate, digest) and return a test receipt. Callers must
    isolate untrusted builds and verify reviewer independence outside this process.
    The candidate stays private; even a successful run requires separate publication.
    """
    prepared = prepare_task(task, agent_limit=agent_limit)
    stages = [{"stage": "economy", "status": "PREPARED"}]
    report = {"status": "BLOCKED", "preflight": prepared, "stages": stages,
              "delivery_authorized": False,
              "scope": "trusted adapter coordination; separate independent publication required"}

    def stop(stage, reason):
        stages.append({"stage": stage, "status": "BLOCKED", "reason": reason})
        return report

    if approved is not True:
        return stop("authorization", "Authorized host execution required")
    if not all(callable(adapter) for adapter in (logic_plan, build, code_review, functional_tests,
                                                integration_tests, regression_tests, performance_tests,
                                                security_tests)):
        return stop("adapters", "Required host adapter unavailable")
    root = Path(candidate).absolute()
    stage = "logic_and_threat_plan"
    try:
        plan = logic_plan(task, deepcopy(prepared))
        plan_digest = LogicSpector.validate(task, plan)
        stages.append({"stage": stage, "status": "REPORTED_PASS", "evidence_sha256": plan_digest})
        stage = "implementation"
        # Never overwrite an existing candidate or use the final delivery directory.
        root.mkdir(mode=0o700)
        log = build(task, {**deepcopy(prepared), "logic_plan": deepcopy(plan)}, root)
        digest = _log_digest(log)
        captured = snapshot(root)
        report["artifact_sha256"] = captured.digest
        stages.append({"stage": stage, "status": "REPORTED_PASS",
                       "evidence_sha256": digest, "artifact_sha256": captured.digest})
        stage = "code_review"
        inventory = CodeSpector.inspect(captured)
        if any(row["syntax"] == "INVALID" for row in inventory):
            return stop(stage, "Invalid Python source")
        report["code_inventory"] = inventory
        coverage = code_review(root, captured.digest)
        evidence_hash = _log_digest(coverage)
        if not _review_coverage_valid(coverage, captured):
            return stop(stage, "Incomplete or invalid byte-bound review")
        if snapshot(root).digest != captured.digest:
            return stop(stage, "Artifact changed during code review")
        stages.append({"stage": stage, "status": "REPORTED_PASS",
                       "artifact_sha256": captured.digest, "evidence_sha256": evidence_hash})
        # Known static issues stop execution before potentially unsafe tests.
        stage = "static_safety"
        if not SecuritySpector.clean(captured):
            return stop(stage, "Static security findings require remediation")
        stages.append({"stage": stage, "status": "NO_STATIC_FINDINGS"})
        for stage, adapter in (("functional_tests", functional_tests),
                               ("integration_tests", integration_tests),
                               ("regression_tests", regression_tests),
                               ("performance_tests", performance_tests),
                               ("security_tests", security_tests)):
            passed, receipt = TestSpector.receipt(adapter(root, captured.digest), captured.digest)
            if snapshot(root).digest != captured.digest:
                return stop(stage, "Artifact changed during testing; review again")
            stages.append({"stage": stage, "status": "REPORTED_PASS" if passed else "BLOCKED",
                           **receipt})
            if not passed:
                return report
        return DeliverySpector.pending(report)
    except Exception as exc:
        # Never surface arbitrary tool logs, exceptions or generated secrets.
        return stop(stage, "Stage failed: " + type(exc).__name__)
