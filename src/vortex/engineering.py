"""Inspect Python projects and check an independently authored reconstruction."""

import ast
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tomllib

from .research import synthesize


_IGNORED_DIRECTORIES = {".git", ".venv", "venv", "__pycache__", "build", "dist", "node_modules"}
_PYTHON_SUFFIXES = {".py", ".pyi"}
_MAX_FILE_BYTES = 4 * 1024 * 1024
_MAX_PROJECT_BYTES = 64 * 1024 * 1024


def _io_error(error: OSError) -> None:
    raise error


def _project_files(root: Path):
    for directory, children, names in os.walk(root, onerror=_io_error, followlinks=False):
        current = Path(directory)
        children[:] = sorted(name for name in children if name not in _IGNORED_DIRECTORIES)
        for name in sorted(names):
            path = current / name
            if path.suffix not in _PYTHON_SUFFIXES and not (
                path == root / "pyproject.toml" or name.startswith("requirements") and path.suffix == ".txt"
            ):
                continue
            if stat.S_ISREG(path.lstat().st_mode):
                yield path


def _module_root(path: str) -> str | None:
    relative = PurePosixPath(path)
    parts = relative.parts
    if parts[0] == "src":
        parts = parts[1:]
    if not parts:
        return None
    if len(parts) > 1:
        return parts[0]
    stem = relative.stem
    return stem if stem != "__init__" else None


def _declared_symbols(tree: ast.Module) -> list[str]:
    declarations = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    symbols = set()
    for node in tree.body:
        if isinstance(node, declarations):
            symbols.add(node.name)
            if isinstance(node, ast.ClassDef):
                symbols.update(f"{node.name}.{child.name}" for child in node.body
                               if isinstance(child, declarations))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            symbols.update(target.id for target in targets if isinstance(target, ast.Name))
    return sorted(symbols)


def _imports(tree: ast.Module, local_modules: set[str]) -> list[dict]:
    occurrences = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = ["." * node.level + (node.module or "")]
        else:
            continue
        for name in names:
            root = name.split(".", 1)[0]
            if name.startswith(".") or root in local_modules:
                category = "project"
            elif root in sys.stdlib_module_names:
                category = "stdlib"
            else:
                category = "external_or_unresolved"
            occurrences.append({"module": name, "line": node.lineno, "category": category})
    return sorted(occurrences, key=lambda item: (item["line"], item["module"]))


def _package(data: bytes) -> dict:
    manifest = tomllib.loads(data.decode("utf-8"))
    project = manifest.get("project", {})
    build = manifest.get("build-system", {})
    if not isinstance(project, dict) or not isinstance(build, dict):
        raise ValueError("Invalid pyproject tables")
    optional = project.get("optional-dependencies", {})
    if not isinstance(optional, dict):
        raise ValueError("Invalid pyproject optional-dependencies table")
    name = project.get("name")
    python_version = project.get("requires-python")
    backend = build.get("build-backend")
    if any(value is not None and not isinstance(value, str)
           for value in (name, python_version, backend)):
        raise ValueError("Project name, Python constraint and build backend must be text")
    dependencies = project.get("dependencies", [])
    build_requires = build.get("requires", [])
    for group in (dependencies, build_requires, *optional.values()):
        if not isinstance(group, list) or any(not isinstance(item, str) for item in group):
            raise ValueError("Dependency groups must be arrays of text")
    return {"name": name, "requires_python": python_version,
            "dependencies": dependencies, "optional_dependencies": optional,
            "build_requires": build_requires, "build_backend": backend}


def inspect_project(project: Path) -> dict:
    """Record source digests, static dependencies and compilation diagnostics."""
    root = project.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Project must be a directory")
    paths = list(_project_files(root))
    local_modules = {
        module for path in paths if path.suffix in _PYTHON_SUFFIXES
        if (module := _module_root(path.relative_to(root).as_posix()))
    }
    files, errors, package = [], [], {}
    total_bytes = 0
    for path in paths:
        relative = path.relative_to(root).as_posix()
        limit = min(_MAX_FILE_BYTES, _MAX_PROJECT_BYTES - total_bytes)
        with path.open("rb") as source:
            data = source.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Project source byte limit exceeded")
        total_bytes += len(data)
        info = {"path": relative, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        files.append(info)
        if path.suffix in _PYTHON_SUFFIXES:
            info.update({"kind": "python", "compiled": False, "symbols": [], "imports": []})
            try:
                tree = ast.parse(data, relative)
                compile(tree, relative, "exec", dont_inherit=True)
                info.update({"compiled": True, "symbols": _declared_symbols(tree),
                             "imports": _imports(tree, local_modules)})
            except SyntaxError as error:
                errors.append({"path": relative, "line": error.lineno, "message": error.msg})
            except RecursionError:
                errors.append({"path": relative, "line": None,
                               "message": "Source exceeded compiler nesting limits"})
        else:
            info["kind"] = "dependency_manifest"
            if relative == "pyproject.toml":
                try:
                    package = _package(data)
                except ValueError as error:
                    errors.append({"path": relative, "line": None, "message": str(error)})
    return {"status": "REVIEW_REQUIRED" if errors else "INSPECTED",
            "files": files, "package": package, "errors": errors,
            "compiled_sources": sum(item.get("compiled", False) for item in files),
            "scope": "Python source and dependency manifests, static imports and compile checks"}


def _text(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value.strip()


def _check_spec(check: dict) -> dict:
    if not isinstance(check, dict) or check.keys() - {"path", "symbols"}:
        raise ValueError("Static checks require a path and accept a symbols array")
    path = _text(check.get("path"), "Check path")
    if "\\" in path or ":" in path or any(part in ("", ".", "..") for part in path.split("/")):
        raise ValueError("Check path must be a normalized relative POSIX path")
    symbols = check.get("symbols", [])
    if not isinstance(symbols, list):
        raise ValueError("Check symbols must be an array")
    return {"path": path, "symbols": [_text(symbol, "Symbol") for symbol in symbols]}


def _study(document: dict, root: Path) -> tuple[dict, dict]:
    if not isinstance(document, dict) or document.keys() != {"question", "sources", "capabilities"}:
        raise ValueError("Spec requires question, sources, and capabilities")
    capabilities = document["capabilities"]
    if not isinstance(capabilities, list) or not capabilities:
        raise ValueError("capabilities must be a nonempty array")
    claims, expectations = [], {}
    for item in capabilities:
        if not isinstance(item, dict) or item.keys() - {"id", "statement", "evidence", "checks"}:
            raise ValueError("Capabilities require id, statement, and checks")
        identifier = _text(item.get("id"), "Capability ID")
        checks = item.get("checks")
        if not isinstance(checks, list) or not checks:
            raise ValueError("Each capability requires static checks")
        if identifier in expectations:
            raise ValueError(f"Duplicate capability: {identifier}")
        expectations[identifier] = [_check_spec(check) for check in checks]
        claims.append({key: value for key, value in item.items() if key != "checks"})
    findings = synthesize({"question": document["question"], "sources": document["sources"],
                           "claims": claims}, root)
    return findings, expectations


def _supplement(study: dict, document: dict, root: Path) -> dict | None:
    """Consider additional evidence only for claims with primary evidence gaps."""
    if not isinstance(document, dict) or not isinstance(document.get("claims"), list):
        raise ValueError("Supplemental research must contain a claims array")
    unresolved = {claim["id"] for claim in study["claims"]
                  if claim["status"] != "SUPPORTING_EXCERPTS"}
    selected = []
    for claim in document["claims"]:
        if not isinstance(claim, dict):
            raise ValueError("Supplemental claim must be an object")
        if _text(claim.get("id"), "Supplemental claim ID") in unresolved:
            selected.append(claim)
    if not selected:
        return None
    source_ids = set()
    for claim in selected:
        evidence = claim.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValueError("Supplemental claim evidence must be an array")
        for item in evidence:
            if not isinstance(item, dict):
                raise ValueError("Supplemental evidence must be an object")
            source_ids.add(_text(item.get("source"), "Supplemental source"))
    sources = document.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("Supplemental sources must be an object")
    return synthesize({**document, "claims": selected,
                       "sources": {key: value for key, value in sources.items()
                                   if key in source_ids}}, root)


def _check_outputs(study: dict, expectations: dict, inspection: dict) -> list[dict]:
    files = {item["path"]: item for item in inspection["files"]}
    results = []
    for claim in study["claims"]:
        checks = []
        for required in expectations[claim["id"]]:
            actual = files.get(required["path"])
            actual_symbols = set(actual.get("symbols", [])) if actual is not None else set()
            missing = sorted(set(required["symbols"]) - actual_symbols)
            compiled = actual is not None and actual.get("compiled") is not False
            checks.append({**required, "present": actual is not None,
                           "sha256": actual["sha256"] if actual else None,
                           "missing_symbols": missing, "passes": compiled and not missing})
        match = claim["status"] == "SUPPORTING_EXCERPTS" and all(check["passes"] for check in checks)
        results.append({"id": claim["id"], "status": "STATIC_MATCH" if match else "GAP",
                        "primary_evidence": claim["status"], "checks": checks})
    return results


def _matching_sources(reference: dict, candidate: dict) -> list[dict]:
    by_digest: dict[str, list[str]] = {}
    for file in reference["files"]:
        if file["kind"] == "python" and file["size"]:
            by_digest.setdefault(file["sha256"], []).append(file["path"])
    return [
        {"candidate": file["path"], "reference": by_digest[file["sha256"]],
         "sha256": file["sha256"]}
        for file in candidate["files"] if file["kind"] == "python" and file["sha256"] in by_digest
    ]


def rebuild(document: dict, candidate: Path, *, source_root: Path,
            reference_source: Path | None = None,
            supplemental: tuple[dict, Path] | None = None) -> dict:
    """Study source evidence, compile candidate Python, and compare static checks."""
    study, expectations = _study(document, source_root)
    if supplemental is not None:
        study["supplemental"] = _supplement(study, *supplemental)
    candidate = candidate.resolve(strict=True)
    if reference_source is not None:
        reference_source = reference_source.resolve(strict=True)
        if candidate.is_relative_to(reference_source) or reference_source.is_relative_to(candidate):
            raise ValueError("Candidate and authorized reference source must be separate projects")
        study["authorized_reference"] = inspect_project(reference_source)
    build = inspect_project(candidate)
    checks = _check_outputs(study, expectations, build)
    overlaps = (_matching_sources(study["authorized_reference"], build)
                if reference_source is not None else [])
    ready = (not build["errors"] and not overlaps
             and all(check["status"] == "STATIC_MATCH" for check in checks))
    return {"status": "READY_FOR_RUNTIME_TEST" if ready else "REVIEW_REQUIRED",
            "study": study, "build": build,
            "check": {"capabilities": checks, "exact_source_matches": overlaps,
                      "reference_source_reviewed": reference_source is not None,
                      "scope": "static evidence and file/symbol checks without runtime execution"}}
