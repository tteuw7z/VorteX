"""Bounded read-only scan of Git objects reachable from refs; never print matched bytes."""
import json
import re
import subprocess
import sys
from pathlib import Path

# Literal formats, not a proof that no credentials or private data exist.
_RULES = {
    "provider_key": rb"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}",
    "github_token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})",
    "google_key": rb"AIza[0-9A-Za-z_-]{35}",
    "aws_key_id": rb"(?:AKIA|ASIA)[0-9A-Z]{16}",
    "slack_token": rb"xox[baprs]-[A-Za-z0-9-]{15,}",
    "private_key": rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----",
}
_RULES = {name: re.compile(pattern) for name, pattern in _RULES.items()}
_MAX_OBJECTS = 100000
_MAX_OBJECT_BYTES = 16 * 1024 * 1024
_MAX_TOTAL_BYTES = 512 * 1024 * 1024


def git(root, args, data=None):
    return subprocess.run(["git", "-C", str(root), *args], input=data, capture_output=True,
                          check=True, timeout=120).stdout


def audit_history(root: Path) -> dict:
    if git(root, ["rev-parse", "--is-shallow-repository"]).strip() != b"false":
        raise ValueError("Full reachable history required; shallow checkout refused")
    head = git(root, ["rev-parse", "HEAD"]).decode("ascii").strip()
    raw = git(root, ["rev-list", "--objects", "--all", "--no-object-names", "HEAD"])
    objects = sorted(set(raw.splitlines()))
    if not objects or len(objects) > _MAX_OBJECTS:
        raise ValueError("Git object count exceeds limits or history is empty")
    if any(not re.fullmatch(rb"(?:[a-f0-9]{40}|[a-f0-9]{64})", oid) for oid in objects):
        raise ValueError("Unexpected Git object identifier")
    metadata = git(root, ["cat-file", "--batch-check"], b"\n".join(objects) + b"\n").splitlines()
    if len(metadata) != len(objects):
        raise ValueError("Git object metadata coverage incomplete")
    scanned = total = 0
    findings = []
    for expected, line in zip(objects, metadata):
        fields = line.split()
        if len(fields) != 3 or fields[0] != expected:
            raise ValueError("Missing or invalid Git object")
        oid, kind, size = fields
        if kind not in {b"blob", b"commit", b"tag", b"tree"}:
            raise ValueError("Unknown Git object type")
        length = int(size)
        if length < 0 or length > _MAX_OBJECT_BYTES or total + length > _MAX_TOTAL_BYTES:
            raise ValueError("History scan byte limit exceeded; no clean result")
        # Tree names can themselves contain secrets. Scan raw tree bytes too.
        content = git(root, ["cat-file", kind.decode("ascii"), oid.decode("ascii")])
        if len(content) != length:
            raise ValueError("Git object size changed")
        scanned += 1
        total += length
        for rule, pattern in _RULES.items():
            if pattern.search(content):
                findings.append({"object": oid.decode("ascii"), "kind": kind.decode("ascii"), "rule": rule})
                if len(findings) > 1000:
                    raise ValueError("History finding limit exceeded; no clean result")
    return {"status": "BLOCKED" if findings else "NO_KNOWN_PATTERN_MATCHES",
            "head": head, "objects_scanned": scanned, "bytes_scanned": total,
            "findings": findings,
            "scope": "Git objects reachable from locally available refs and HEAD; excludes unreachable objects, external artifacts and unknown formats"}


if __name__ == "__main__":
    try:
        report = audit_history(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd())
    except (OSError, ValueError, subprocess.SubprocessError):
        print(json.dumps({"status": "BLOCKED", "reason": "History scan incomplete or unavailable"}))
        raise SystemExit(1)
    print(json.dumps(report, indent=2))
    raise SystemExit(1 if report["findings"] else 0)
