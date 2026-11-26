"""Fail-closed local delivery gate. Static findings are not a security certification."""
import ast
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time
from dataclasses import dataclass

POLICY_VERSION = 1
_MAX_FILE = 8 * 1024 * 1024
_MAX_TOTAL = 32 * 1024 * 1024
_MAX_FILES = 1000
_MAX_AGE = 7 * 86400
_COMMON = frozenset(("threat_model", "secret_scan", "dependency_review", "privacy_review",
                     "functional_tests", "security_tests", "manual_review"))
_REQUIRED = {
    "script": _COMMON | {"input_validation", "least_privilege"},
    "website": _COMMON | {"access_control", "web_security", "deployment_config"},
    "application": _COMMON | {"access_control", "storage_security", "build_integrity"},
    "skill": _COMMON | {"prompt_injection_review", "permission_review", "tool_provenance"},
    "other": _COMMON | {"format_specific_review"},
}
_SECRET = re.compile(
    r"(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|"
    r"github_pat_[A-Za-z0-9_]{30,}|AIza[0-9A-Za-z_-]{35}|AKIA[0-9A-Z]{16}|"
    r"xox[baprs]-[A-Za-z0-9-]{15,}|-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----)"
)
_ASSIGN_SECRET = re.compile(
    r"""(?im)^\s*(?:export\s+)?["']?(?:api[_-]?key|client[_-]?secret|password|access[_-]?token|secret[_-]?key)["']?\s*[:=]\s*["']([^"'\r\n]{8,})["']"""
)
_WEB_RULES = (
    ("WEB_UNSAFE_HTML", re.compile(r"\b(?:innerHTML|outerHTML)\s*=|\bdocument\.write\s*\(|\bdangerouslySetInnerHTML\b")),
    ("WEB_EVAL", re.compile(r"\beval\s*\(|\bnew\s+Function\s*\(")),
    ("WEB_TOKEN_STORAGE", re.compile(r"\b(?:localStorage|sessionStorage)\.setItem\s*\(\s*['\"][^'\"]*(?:token|secret|password)[^'\"]*['\"]", re.I)),
    ("WEB_INLINE_HANDLER", re.compile(r"<[^>]*\son[a-z]+\s*=", re.I)),
)
_TEXT_SUFFIXES = {".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html",
                  ".htm", ".css", ".json", ".toml", ".yaml", ".yml", ".xml", ".md", ".txt",
                  ".sh", ".bat", ".ps1", ".ini", ".cfg", ".gradle", ".kt", ".java", ".sql"}
_WEB_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html", ".htm"}
_HEX = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class Snapshot:
    digest: str
    files: tuple[tuple[str, bytes], ...]
    findings: tuple[dict, ...]
    unparsed: tuple[str, ...]


def _finding(path, rule, line=None):
    # Never emit the matched source text, credential, or an absolute path.
    return {"path": path, "rule": rule, "line": line}


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _name(node.value) + "." + node.attr
    return ""


def _python_findings(path, data):
    try:
        tree = ast.parse(data, filename=path)
        compile(tree, path, "exec", dont_inherit=True)
    except (SyntaxError, ValueError, RecursionError):
        return [_finding(path, "PY_INVALID_SOURCE")]
    findings = []
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name if item.asname else item.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for item in node.names:
                aliases[item.asname or item.name] = node.module + "." + item.name
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _name(node.func)
        head, sep, tail = name.partition(".")
        name = aliases.get(head, head) + (sep + tail if sep else "")
        kw = {item.arg: item.value for item in node.keywords if item.arg is not None}
        def literal(key, value):
            return isinstance(kw.get(key), ast.Constant) and kw[key].value is value
        rule = None
        if name in {"eval", "exec", "builtins.eval", "builtins.exec"}:
            rule = "PY_DYNAMIC_EXECUTION"
        elif name in {"os.system", "os.popen"} or (name.startswith("subprocess.") and literal("shell", True)):
            rule = "PY_SHELL_EXECUTION"
        elif name in {"pickle.load", "pickle.loads", "dill.load", "dill.loads", "marshal.load", "marshal.loads"}:
            rule = "PY_UNSAFE_DESERIALIZATION"
        elif name == "ssl._create_unverified_context" or literal("verify", False):
            rule = "PY_TLS_VERIFICATION_DISABLED"
        elif name.endswith(".run") and literal("debug", True):
            rule = "PY_DEBUG_MODE"
        if rule:
            findings.append(_finding(path, rule, node.lineno))
    return findings


def _scan(path, data):
    findings = []
    suffix = Path(path).suffix.lower()
    name = Path(path).name.casefold()
    if name == ".env" or (name.startswith(".env.") and name not in {".env.example", ".env.sample"}):
        findings.append(_finding(path, "PRIVATE_ENV_FILE"))
    if suffix in {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}:
        findings.append(_finding(path, "KEY_MATERIAL_FILE"))
    # Check ASCII secret formats even inside a binary. Do not output matching strings.
    text = data.decode("utf-8", errors="replace")
    for match in _SECRET.finditer(text):
        findings.append(_finding(path, "POSSIBLE_CREDENTIAL", text.count("\n", 0, match.start()) + 1))
    for match in _ASSIGN_SECRET.finditer(text):
        findings.append(_finding(path, "HARDCODED_SECRET", text.count("\n", 0, match.start()) + 1))
    if suffix in {".py", ".pyi"}:
        findings.extend(_python_findings(path, data))
    if suffix in _WEB_SUFFIXES:
        for rule, pattern in _WEB_RULES:
            for match in pattern.finditer(text):
                findings.append(_finding(path, rule, text.count("\n", 0, match.start()) + 1))
    return findings, suffix not in {".py", ".pyi"} | _WEB_SUFFIXES


def _read_regular(path, limit):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("Artifact contains a symlink or special file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError("Artifact changed during inspection")
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if len(data) > limit:
            raise ValueError("Artifact exceeds inspection byte limit")
        if (opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Artifact changed during inspection")
    return data


def snapshot(root: Path) -> Snapshot:
    """Capture a bounded artifact directory without executing any of its content."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Artifact must be a dedicated regular directory")
    root = root.resolve(strict=True)
    files, findings, unparsed = [], [], []
    total = 0
    names = set()
    def fail(error):
        raise error
    for folder, dirs, filenames in os.walk(root, topdown=True, followlinks=False, onerror=fail):
        current = Path(folder)
        for name in sorted(dirs + filenames):
            path = current / name
            relative = path.relative_to(root).as_posix()
            if name.casefold() == ".git" or path.is_symlink():
                raise ValueError("Artifact cannot contain Git metadata or symlinks")
            if any(part.endswith((" ", ".")) or ":" in part or "\\" in part
                   for part in path.relative_to(root).parts):
                raise ValueError("Artifact path is not portable")
            if relative.casefold() in names:
                raise ValueError("Artifact has case-colliding paths")
            names.add(relative.casefold())
            if len(names) > 2 * _MAX_FILES:
                raise ValueError("Artifact exceeds path count limit")
        for name in sorted(filenames):
            path = current / name
            relative = path.relative_to(root).as_posix()
            if len(files) >= _MAX_FILES:
                raise ValueError("Artifact exceeds file count limit")
            data = _read_regular(path, min(_MAX_FILE, _MAX_TOTAL - total))
            total += len(data)
            hits, limited = _scan(relative, data)
            findings.extend(hits)
            if limited:
                unparsed.append(relative)
            files.append((relative, data))
    if not files:
        raise ValueError("Artifact is empty")
    files.sort(key=lambda pair: pair[0])
    manifest = [[name, len(data), hashlib.sha256(data).hexdigest()] for name, data in files]
    digest = hashlib.sha256(_canonical(manifest)).hexdigest()
    return Snapshot(digest, tuple(files), tuple(findings), tuple(sorted(unparsed)))


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def audit(root: Path, kind: str) -> dict:
    if kind not in _REQUIRED:
        raise ValueError("Unknown artifact type")
    captured = snapshot(root)
    return _report(captured, kind)


def _report(captured, kind):
    return {"status": "BLOCKED", "policy_version": POLICY_VERSION, "kind": kind,
            "artifact_sha256": captured.digest, "files": len(captured.files),
            "findings": list(captured.findings), "limited_static_coverage": list(captured.unparsed),
            "required_checks": sorted(_REQUIRED[kind]),
            "reason": "Static findings require remediation" if captured.findings else
                      "Independent authenticated security evidence required",
            "scope": "bounded local static heuristics; not a security certification"}


def _attestation_valid(attestation, key, captured, kind, now):
    if not isinstance(key, bytes) or len(key) < 32 or not isinstance(attestation, dict):
        return False
    if set(attestation) != {"payload", "signature"}:
        return False
    payload, signature = attestation["payload"], attestation["signature"]
    if not isinstance(payload, dict) or not isinstance(signature, str) or not _HEX.fullmatch(signature):
        return False
    if set(payload) != {"policy_version", "kind", "artifact_sha256", "reviewer", "issued_at", "expires_at", "checks"}:
        return False
    try:
        expected = hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()
    except (ValueError, TypeError, RecursionError):
        return False
    if not hmac.compare_digest(signature, expected):
        return False
    if (type(payload["policy_version"]) is not int or payload["policy_version"] != POLICY_VERSION
            or payload["kind"] != kind or payload["artifact_sha256"] != captured.digest
            or not isinstance(payload["reviewer"], str) or not payload["reviewer"].strip()):
        return False
    issued, expires = payload["issued_at"], payload["expires_at"]
    if type(issued) is not int or type(expires) is not int or not issued <= now < expires <= issued + _MAX_AGE:
        return False
    checks = payload["checks"]
    if not isinstance(checks, dict) or set(checks) != _REQUIRED[kind]:
        return False
    return all(isinstance(item, dict) and set(item) == {"status", "evidence_sha256"}
               and item["status"] == "PASS" and isinstance(item["evidence_sha256"], str)
               and _HEX.fullmatch(item["evidence_sha256"]) for item in checks.values())


def publish(root: Path, output: Path, kind: str, *, attestation=None, key=None) -> dict:
    """Publish only the captured, independently attested bytes; never run artifact code."""
    if kind not in _REQUIRED:
        raise ValueError("Unknown artifact type")
    captured = snapshot(root)
    report = _report(captured, kind)
    if captured.findings or not _attestation_valid(attestation, key, captured, kind, int(time.time())):
        return report
    target = Path(output).absolute()
    parent = target.parent.resolve(strict=True)
    target = parent / target.name
    source = Path(root).resolve(strict=True)
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError("Delivery and candidate must be separate directories")
    target.mkdir(mode=0o700)  # exclusive; never overwrite existing delivery
    try:
        for relative, data in captured.files:
            path = target / relative
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
    except BaseException:
        shutil.rmtree(target)
        raise
    return {**report, "status": "SUCCESS", "reason": "Policy checks and authenticated attestation accepted",
            "output": str(target), "reviewer": attestation["payload"]["reviewer"],
            "scope": "approved snapshot under configured policy; not a guarantee of zero vulnerabilities"}
