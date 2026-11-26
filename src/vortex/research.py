"""Build a local synthesis from exact excerpts with source provenance."""

from dataclasses import dataclass
import hashlib
from pathlib import Path


_MAX_SOURCE_BYTES = 8 * 1024 * 1024
_MAX_TOTAL_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class _Source:
    id: str
    path: str
    digest: str
    canonical_id: str
    content: str
    origin: str | None

    def metadata(self) -> dict:
        return {"id": self.id, "path": self.path, "sha256": self.digest,
                "canonical_id": self.canonical_id, "origin": self.origin}


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")
    return value.strip()


def _source_path(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute():
        raise ValueError("Source paths must be relative to the source root")
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Source path escapes the source root")
    if not target.is_file():
        raise FileNotFoundError(f"Source is not a regular file: {name}")
    return target


def _sources(raw_sources: dict, root: Path) -> dict[str, _Source]:
    if not isinstance(raw_sources, dict):
        raise ValueError("sources must map source IDs to file descriptors")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Source root must be a directory")
    canonical: dict[str, _Source] = {}
    records = {}
    total_bytes = 0
    for source_id, descriptor in raw_sources.items():
        if _require_text(source_id, "Source ID") != source_id:
            raise ValueError("Source IDs cannot contain surrounding whitespace")
        if not isinstance(descriptor, dict) or descriptor.keys() - {"path", "origin"}:
            raise ValueError("Source descriptors accept path and optional origin")
        name = _require_text(descriptor.get("path"), "Source path")
        origin = descriptor.get("origin")
        if origin is not None:
            origin = _require_text(origin, "Source origin")
        path = _source_path(root, name)
        limit = min(_MAX_SOURCE_BYTES, _MAX_TOTAL_BYTES - total_bytes)
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Research source byte limit exceeded")
        total_bytes += len(data)
        digest = hashlib.sha256(data).hexdigest()
        duplicate = canonical.get(digest)
        if duplicate is None:
            content = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
            source = _Source(source_id, name, digest, source_id, content, origin)
            canonical[digest] = source
        else:
            source = _Source(source_id, name, digest, duplicate.id, duplicate.content, origin)
        records[source_id] = source
    return records


def _evidence(descriptor: dict, sources: dict[str, _Source]) -> dict:
    if not isinstance(descriptor, dict) or descriptor.keys() - {"source", "quote", "stance"}:
        raise ValueError("Evidence accepts source, quote, and optional stance")
    source_id = _require_text(descriptor.get("source"), "Evidence source")
    if source_id not in sources:
        raise ValueError(f"Unknown source: {source_id}")
    quote = _require_text(descriptor.get("quote"), "Evidence quote")
    quote = quote.replace("\r\n", "\n").replace("\r", "\n")
    stance = descriptor.get("stance", "supports")
    if stance not in ("supports", "challenges"):
        raise ValueError("Evidence stance must be supports or challenges")
    source = sources[source_id]
    start = source.content.find(quote)
    result = {"source": source.id, "canonical_source": source.canonical_id,
              "sha256": source.digest, "quote": quote, "stance": stance,
              "status": "EXCERPT_FOUND" if start >= 0 else "EXCERPT_NOT_FOUND"}
    if start >= 0:
        line = source.content.count("\n", 0, start) + 1
        result.update({"line_start": line, "line_end": line + quote.count("\n")})
    return result


def synthesize(document: dict, source_root: Path) -> dict:
    """Organize supplied claims; verify excerpts in named files and flag gaps."""
    if not isinstance(document, dict) or document.keys() - {"question", "sources", "claims"}:
        raise ValueError("Research manifest requires question, sources, and claims")
    question = _require_text(document.get("question"), "Research question")
    raw_claims = document.get("claims")
    if not isinstance(raw_claims, list) or not raw_claims:
        raise ValueError("claims must be a nonempty array")
    sources = _sources(document.get("sources"), source_root)
    claims = []
    seen = set()
    for claim in raw_claims:
        if not isinstance(claim, dict) or claim.keys() - {"id", "statement", "evidence"}:
            raise ValueError("Claim accepts id, statement, and evidence")
        claim_id = _require_text(claim.get("id"), "Claim ID")
        if claim_id in seen:
            raise ValueError(f"Duplicate claim ID: {claim_id}")
        seen.add(claim_id)
        statement = _require_text(claim.get("statement"), "Claim statement")
        supplied = claim.get("evidence", [])
        if not isinstance(supplied, list):
            raise ValueError("Claim evidence must be an array")
        verified = [_evidence(item, sources) for item in supplied]
        matching = [item for item in verified if item["status"] == "EXCERPT_FOUND"]
        supporting = sorted({item["canonical_source"] for item in matching
                             if item["stance"] == "supports"})
        challenging = sorted({item["canonical_source"] for item in matching
                              if item["stance"] == "challenges"})
        if supporting and challenging:
            status = "MIXED_EXCERPTS"
        elif supporting:
            status = "SUPPORTING_EXCERPTS"
        elif challenging:
            status = "CHALLENGING_EXCERPTS"
        else:
            status = "INSUFFICIENT_EVIDENCE"
        claims.append({"id": claim_id, "statement": statement, "status": status,
                       "evidence": verified, "supporting_sources": supporting,
                       "challenging_sources": challenging})
    return {
        "question": question,
        "sources": [source.metadata() for source in sources.values()],
        "claims": claims,
        "coverage": {"claims": len(claims),
                     "claims_with_support": sum(bool(claim["supporting_sources"]) for claim in claims),
                     "claims_with_challenge": sum(bool(claim["challenging_sources"]) for claim in claims),
                     "unverified_excerpts": sum(item["status"] == "EXCERPT_NOT_FOUND"
                                                for claim in claims for item in claim["evidence"]),
                     "unresolved": sum(claim["status"] != "SUPPORTING_EXCERPTS" for claim in claims)},
        "scope": "local exact excerpt matching with caller-supplied source stance",
    }
