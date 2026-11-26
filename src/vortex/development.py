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

_MAX_LOG_BYTES = 2 * 1024 * 1024


def _log_digest(log):
    if not isinstance(log, bytes) or not log.strip() or len(log) > _MAX_LOG_BYTES:
        raise ValueError("Missing or oversized stage evidence")
    return hashlib.sha256(log).hexdigest()


def _test_receipt(report, digest):
    """Check receipt shape and exact artifact identity, not the truth of a claim."""
    if not isinstance(report, dict) or set(report) != {
        "artifact_sha256", "passed", "failed", "skipped", "log"
    }:
        raise ValueError("Invalid test receipt")
    if report["artifact_sha256"] != digest:
        raise ValueError("Test receipt refers to another artifact")
    counts = tuple(report[k] for k in ("passed", "failed", "skipped"))
    if any(type(n) is not int or n < 0 for n in counts):
        raise ValueError("Invalid test counts")
    receipt = {"artifact_sha256": digest, "evidence_sha256": _log_digest(report["log"]),
               "passed": counts[0], "failed": counts[1], "skipped": counts[2]}
    return counts[0] > 0 and counts[1:] == (0, 0), receipt


def coordinate_development(task: str, candidate: Path, *,
                           build: Callable | None = None,
                           code_review: Callable | None = None,
                           functional_tests: Callable | None = None,
                           security_tests: Callable | None = None,
                           approved: bool = False, agent_limit: int = 3) -> dict:
    """Prepare automatically, then build, review, test and security-check in order.

    Builder gets (task, preflight, private candidate directory) and returns log bytes.
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
    if not all(callable(adapter) for adapter in (build, code_review, functional_tests, security_tests)):
        return stop("adapters", "Required host adapter unavailable")
    root = Path(candidate).absolute()
    stage = "implementation"
    try:
        # Never overwrite an existing candidate or use the final delivery directory.
        root.mkdir(mode=0o700)
        log = build(task, deepcopy(prepared), root)
        digest = _log_digest(log)
        captured = snapshot(root)
        report["artifact_sha256"] = captured.digest
        stages.append({"stage": stage, "status": "REPORTED_PASS",
                       "evidence_sha256": digest, "artifact_sha256": captured.digest})
        stage = "code_review"
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
        if captured.findings:
            return stop(stage, "Static security findings require remediation")
        stages.append({"stage": stage, "status": "NO_STATIC_FINDINGS"})
        for stage, adapter in (("functional_tests", functional_tests),
                               ("security_tests", security_tests)):
            passed, receipt = _test_receipt(adapter(root, captured.digest), captured.digest)
            if snapshot(root).digest != captured.digest:
                return stop(stage, "Artifact changed during testing; review again")
            stages.append({"stage": stage, "status": "REPORTED_PASS" if passed else "BLOCKED",
                           **receipt})
            if not passed:
                return report
        report["status"] = "REVIEW_REQUIRED"
        report["reason"] = "Ordered adapter checks completed; independent gate still required"
        return report
    except Exception as exc:
        # Never surface arbitrary tool logs, exceptions or generated secrets.
        return stop(stage, "Stage failed: " + type(exc).__name__)
