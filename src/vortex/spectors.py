"""Small, deterministic quality checks on the existing trusted-host boundary.

No candidate code is executed here. Adapter evidence is not independent proof.
"""
import ast
import hashlib
import io
import json
from pathlib import PurePosixPath
import tokenize


class TokenSpector:
    @staticmethod
    def select(task, catalog, selected):
        def size(profiles):
            payload = {"task": task, "profiles": profiles}
            return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                                  allow_nan=False).encode("utf-8"))

        before, after = size(catalog), size(selected)
        # Keep the full context if the proposed reduction does not save tokens.
        estimate = lambda n: (n + 3) // 4
        if estimate(after) >= estimate(before):
            selected, after = catalog, before
        saved = estimate(before) - estimate(after)
        return selected, {
            "baseline_bytes": before, "selected_bytes": after,
            "estimated_baseline_tokens": estimate(before),
            "estimated_selected_tokens": estimate(after),
            "estimated_saved_tokens": saved,
            "estimated_saved_percent": round(100 * saved / estimate(before), 2),
            "optimization_applied": saved > 0,
            "discarded_task_information": [],
            "possible_loss": "Nonmatching profiles may contain semantically relevant guidance; expand on ambiguity.",
            "performance_equivalence": "NOT_MEASURED",
            "actual_provider_tokens": None,
        }


class LogicSpector:
    """Validate a host-authored plan before any build side effects."""
    FIELDS = frozenset(("inputs", "processing", "outputs", "acceptance",
                        "edge_cases", "data_flows", "threats"))

    @classmethod
    def validate(cls, task, plan):
        if not isinstance(plan, dict) or set(plan) != cls.FIELDS:
            raise ValueError("Incomplete logic and threat plan")
        for field in sorted(cls.FIELDS):
            value = plan[field]
            if (not isinstance(value, list) or not 1 <= len(value) <= 64
                    or any(not isinstance(item, str) or not item.strip()
                           or len(item) > 2048 for item in value)):
                raise ValueError("Invalid logic and threat plan")
        payload = json.dumps({"task": task, "plan": plan}, sort_keys=True,
                             ensure_ascii=True, separators=(",", ":")).encode("ascii")
        return hashlib.sha256(payload).hexdigest()


class CodeSpector:
    """Inspect exact captured bytes, tokenize and compile Python without executing it."""
    @staticmethod
    def inspect(captured):
        rows = []
        for path, data in captured.files:
            row = {"path": path, "sha256": hashlib.sha256(data).hexdigest(),
                   "size": len(data), "lines": len(data.splitlines()),
                   "review_status": "PENDING_INDEPENDENT_REVIEW",
                   "syntax": "NOT_CHECKED", "advisories": []}
            if PurePosixPath(path).suffix.lower() in {".py", ".pyi"}:
                try:
                    count = sum(1 for _ in tokenize.tokenize(io.BytesIO(data).readline))
                    tree = ast.parse(data, filename=path)
                    compile(tree, path, "exec", dont_inherit=True)
                    row["syntax"] = "COMPILED"
                    row["lexical_tokens"] = count
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ExceptHandler) and node.type is None:
                            row["advisories"].append({"rule": "BARE_EXCEPT", "line": node.lineno})
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if any(isinstance(default, (ast.List, ast.Dict, ast.Set))
                                   for default in (*node.args.defaults, *node.args.kw_defaults)):
                                row["advisories"].append({"rule": "MUTABLE_DEFAULT", "line": node.lineno})
                    row["advisories"] = row["advisories"][:100]
                except (SyntaxError, ValueError, UnicodeError, RecursionError, tokenize.TokenError):
                    row["syntax"] = "INVALID"
            rows.append(row)
        return rows


class TestSpector:
    """Validate separate evidence receipts for the same immutable candidate."""
    @staticmethod
    def receipt(report, digest):
        if not isinstance(report, dict) or set(report) != {
            "artifact_sha256", "passed", "failed", "skipped", "log"
        } or report["artifact_sha256"] != digest:
            raise ValueError("Invalid or mismatched test receipt")
        counts = tuple(report[k] for k in ("passed", "failed", "skipped"))
        if any(type(n) is not int or n < 0 for n in counts):
            raise ValueError("Invalid test counts")
        log = report["log"]
        if not isinstance(log, bytes) or not log.strip() or len(log) > 2 * 1024 * 1024:
            raise ValueError("Missing or oversized stage evidence")
        receipt = {"artifact_sha256": digest, "evidence_sha256": hashlib.sha256(log).hexdigest(),
                   "passed": counts[0], "failed": counts[1], "skipped": counts[2]}
        return counts[0] > 0 and counts[1:] == (0, 0), receipt


class SecuritySpector:
    """Reuse the existing security snapshot; no duplicate scanner."""
    @staticmethod
    def clean(captured):
        return not captured.findings


class DeliverySpector:
    """The coordinator cannot grant publication; use the separate authenticated gate."""
    @staticmethod
    def pending(report):
        report["status"] = "REVIEW_REQUIRED"
        report["delivery_authorized"] = False
        report["reason"] = "Ordered adapter checks completed; independent gate still required"
        return report
