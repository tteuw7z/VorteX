"""Read-only ZIP inspection; no implicit extraction or execution."""
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
import stat

def inventory(path: Path, *, max_entries: int = 10000, max_bytes: int = 2_000_000_000) -> list[dict]:
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > max_entries or sum(e.file_size for e in entries) > max_bytes:
            raise ValueError("Archive exceeds configured limits")
        result, seen = [], set()
        for entry in entries:
            name = PurePosixPath(entry.filename)
            mode = entry.external_attr >> 16
            if name.is_absolute() or ".." in name.parts or not name.parts or "\\" in entry.filename or ":" in entry.filename or stat.S_ISLNK(mode):
                raise ValueError("Unsafe archive entry")
            key = str(name).casefold()
            if key in seen:
                raise ValueError("Duplicate archive entry")
            seen.add(key)
            result.append({"path": str(name), "size": entry.file_size, "directory": entry.is_dir()})
        return result
