"""Quality coordinator for explicitly trusted host adapters.

The host owns isolation, adapter independence, authorization and evidence retention.
No candidate is signed or published here.
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


def _validate_candidate(root, captured, report, code_review, tests):
    """Return whether a normal validation failure is eligible for repair."""
    stages = report["stages"]
    stage = "code_review"

    def stop(reason, repairable=False):
        stages.append({"stage": stage, "status": "BLOCKED", "reason": reason})
        return repairable

    try:
        inventory = CodeSpector.inspect(captured)
        report["code_inventory"] = inventory
        if any(row["syntax"] == "INVALID" for row in inventory):
            return stop("Invalid Python source", True)
        coverage = code_review(root, captured.digest)
        evidence_hash = _log_digest(coverage)
        if snapshot(root).digest != captured.digest:
            return stop("Artifact changed during code review")
        if not _review_coverage_valid(coverage, captured):
            return stop("Incomplete or invalid byte-bound review")
        stages.append({"stage": stage, "status": "REPORTED_PASS",
                       "artifact_sha256": captured.digest, "evidence_sha256": evidence_hash})
        stage = "static_safety"
        if not SecuritySpector.clean(captured):
            report["static_findings"] = list(captured.findings)
            return stop("Static security findings require remediation", True)
        stages.append({"stage": stage, "status": "NO_STATIC_FINDINGS"})
        for stage, adapter in tests:
            passed, receipt = TestSpector.receipt(adapter(root, captured.digest), captured.digest)
            if snapshot(root).digest != captured.digest:
                return stop("Artifact changed during testing; review again")
            stages.append({"stage": stage, "status": "REPORTED_PASS" if passed else "BLOCKED",
                           **receipt})
            if not passed:
                return True
        DeliverySpector.pending(report)
        return False
    except Exception as exc:
        # Never surface arbitrary tool logs, exceptions or generated secrets.
        return stop("Stage failed: " + type(exc).__name__)


def coordinate_development(task: str, candidate: Path, *,
                           build: Callable | None = None,
                           code_review: Callable | None = None,
                           functional_tests: Callable | None = None,
                           security_tests: Callable | None = None,
                           logic_plan: Callable | None = None,
                           integration_tests: Callable | None = None,
                           regression_tests: Callable | None = None,
                           performance_tests: Callable | None = None,
                           repair: Callable | None = None, max_repairs: int = 2,
                           approved: bool = False, agent_limit: int = 3) -> dict:
    """Prepare, build, review, test and security-check in order.

    Logic adapter gets (task, preflight) and returns the structured plan.
    Builder gets (task, preflight including logic plan, private candidate directory).
    Reviewer gets (candidate, digest) and returns code_review.log bytes.
    Test adapters return exact-artifact receipts. An optional trusted repair adapter
    receives (root, digest, failure report) and returns log bytes. All checks restart
    after a repair; unexpected mutation or invalid evidence never triggers repair.
    Independent authorization remains necessary even after success.
    """
    prepared = prepare_task(task, agent_limit=agent_limit)
    stages = [{"stage": "economy", "status": "PREPARED"}]
    report = {"status": "BLOCKED", "preflight": prepared, "stages": stages,
              "delivery_authorized": False, "repair_history": [],
              "scope": "trusted adapter coordination; separate independent publication required"}

    def stop(stage, reason):
        stages.append({"stage": stage, "status": "BLOCKED", "reason": reason})
        return report

    if approved is not True:
        return stop("authorization", "Authorized host execution required")
    if type(max_repairs) is not int or not 0 <= max_repairs <= 3:
        return stop("adapters", "Invalid repair limit")
    if repair is not None and not callable(repair):
        return stop("adapters", "Invalid repair adapter")
    tests = (("functional_tests", functional_tests), ("integration_tests", integration_tests),
             ("regression_tests", regression_tests), ("performance_tests", performance_tests),
             ("security_tests", security_tests))
    if not all(callable(adapter) for adapter in (logic_plan, build, code_review,
                                                *(adapter for _, adapter in tests))):
        return stop("adapters", "Required host adapter unavailable")
    root = Path(candidate).absolute()
    stage = "logic_and_threat_plan"
    try:
        plan = logic_plan(task, deepcopy(prepared))
        plan_digest = LogicSpector.validate(task, plan)
        stages.append({"stage": stage, "status": "REPORTED_PASS", "evidence_sha256": plan_digest})
        stage = "implementation"
        root.mkdir(mode=0o700)
        log = build(task, {**deepcopy(prepared), "logic_plan": deepcopy(plan)}, root)
        digest = _log_digest(log)
        captured = snapshot(root)
        report["artifact_sha256"] = captured.digest
        stages.append({"stage": stage, "status": "REPORTED_PASS",
                       "evidence_sha256": digest, "artifact_sha256": captured.digest})
        for attempt in range(max_repairs + 1):
            start = len(stages)
            repairable = _validate_candidate(root, captured, report, code_review, tests)
            if not repairable or repair is None or attempt == max_repairs:
                return report
            stage = "repair"
            if snapshot(root).digest != captured.digest:
                return stop(stage, "Artifact changed before repair")
            failure = {"artifact_sha256": captured.digest,
                       "stages": deepcopy(stages[start:]),
                       "code_inventory": deepcopy(report.get("code_inventory", [])),
                       "static_findings": deepcopy(report.get("static_findings", []))}
            old_digest = captured.digest
            log_hash = _log_digest(repair(root, old_digest, deepcopy(failure)))
            captured = snapshot(root)
            if captured.digest == old_digest:
                return stop(stage, "Repair did not change artifact bytes")
            report["repair_history"].append({"previous_sha256": old_digest,
                                             "new_sha256": captured.digest,
                                             "evidence_sha256": log_hash,
                                             "validation": failure["stages"]})
            del stages[start:]
            stages.append({"stage": stage, "status": "REPORTED_PASS",
                           "artifact_sha256": captured.digest, "evidence_sha256": log_hash})
            report["artifact_sha256"] = captured.digest
            report.pop("static_findings", None)
            report.pop("code_inventory", None)
        return report
    except Exception as exc:
        return stop(stage, "Stage failed: " + type(exc).__name__)
