"""Private output creation; Windows permissions depend on the host ACL."""
import os
from pathlib import Path


def private_open(path: Path, *, text: bool = False):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o600)
    return os.fdopen(fd, "w" if text else "wb", **({"encoding": "utf-8"} if text else {}))


def restrict_file(path: Path):
    if os.name == "posix":
        path.chmod(0o600)
