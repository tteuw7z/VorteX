"""File identity shared by media and Android reports."""
import hashlib
from pathlib import Path


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()
