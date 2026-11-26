"""Inspect, extract and rebuild ZIPs without executing their contents."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import errno
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
from tempfile import TemporaryDirectory
from typing import BinaryIO
import unicodedata
import zipfile
from zipfile import BadZipFile, ZIP_BZIP2, ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo
import zlib

MAX_ENTRIES = 10_000
MAX_BYTES = 2_000_000_000
_CHUNK_BYTES = 256 * 1024
_MAX_DEPTH = 128
_DEVICE_NAMES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$"} | {
    f"{prefix}{digit}" for prefix in ("COM", "LPT") for digit in "123456789¹²³"
}
_VIDEO_SUFFIXES = frozenset({
    ".3g2", ".3gp", ".asf", ".avi", ".flv", ".m2ts", ".m4v", ".mkv", ".mov",
    ".mp4", ".mpeg", ".mpg", ".mts", ".mxf", ".ogv", ".ts", ".vob", ".webm", ".wmv",
})
_COMPRESSION = {ZIP_STORED, ZIP_DEFLATED, ZIP_BZIP2}
_DECODE_ERRORS = (EOFError, zlib.error)
try:
    from compression.zstd import ZstdError
except ImportError:
    pass
else:
    _COMPRESSION.add(zipfile.ZIP_ZSTANDARD)
    _DECODE_ERRORS += (ZstdError,)


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    destination: str
    files: int
    directories: int
    bytes_written: int


@dataclass(frozen=True, slots=True)
class RepackResult:
    output: str
    files: int
    bytes_uncompressed: int
    replaced: tuple[str, ...]


@dataclass(slots=True)
class _PathNode:
    spelling: str = ""
    entry: ZipInfo | None = None
    children: dict[str, "_PathNode"] = field(default_factory=dict)


def _portable_parts(info: ZipInfo) -> list[str]:
    name = info.orig_filename
    if name != info.filename:
        raise ValueError(f"Ambiguous ZIP member name: {name!r}")
    parts = name.removesuffix("/").split("/")
    if len(parts) > _MAX_DEPTH:
        raise ValueError(f"ZIP member has too many directory levels: {name!r}")
    for part in parts:
        if (not part or part in {".", ".."} or part.endswith((".", " "))
                or any(c in '<>:"\\|?*' or ord(c) < 32 or ord(c) == 127 for c in part)
                or part.partition(".")[0].rstrip(" ").upper() in _DEVICE_NAMES):
            raise ValueError(f"Unsafe ZIP member path: {name!r}")
    mode = stat.S_IFMT(info.external_attr >> 16)
    expected = stat.S_IFDIR if info.is_dir() else stat.S_IFREG
    if (mode not in {0, expected} or info.external_attr & 0x400
            or not info.is_dir() and info.external_attr & 0x10):
        raise ValueError(f"Unsupported ZIP member type: {name!r}")
    if info.is_dir() and info.file_size != 0:
        raise ValueError(f"ZIP directory contains data: {name!r}")
    return parts


def _validate_limits(max_entries: int, max_bytes: int) -> None:
    if type(max_entries) is not int or max_entries < 1 or type(max_bytes) is not int or max_bytes < 0:
        raise ValueError("ZIP limits require positive max_entries and non-negative max_bytes")


def _manifest(archive: ZipFile, max_entries: int, max_bytes: int, *,
              writing: bool = False, expanding: bool = False) -> dict[str, ZipInfo]:
    _validate_limits(max_entries, max_bytes)
    infos = archive.infolist()
    if len(infos) > max_entries or sum(info.file_size for info in infos) > max_bytes:
        raise ValueError("Archive exceeds configured limits")
    entries = {}
    root = _PathNode()
    node_count = 0
    offsets = set()
    for info in infos:
        parts = _portable_parts(info)
        if writing:
            if info.flag_bits & 0x61:
                raise ValueError(f"Encrypted or patched ZIP member is unsupported: {info.filename!r}")
            # The stdlib ZIP LZMA reader accepts a raw dictionary without an allocation limit.
            if info.compress_type not in _COMPRESSION:
                raise ValueError(f"Unsupported compression for ZIP member: {info.filename!r}")
            if info.compress_type == ZIP_STORED and info.compress_size != info.file_size:
                raise BadZipFile(f"Inconsistent size for ZIP member: {info.filename!r}")
            if info.header_offset < 0 or info.header_offset in offsets:
                raise BadZipFile(f"Invalid or shared ZIP member offset: {info.filename!r}")
            offsets.add(info.header_offset)
        node = root
        for part in parts:
            if node.entry is not None and not node.entry.is_dir():
                raise ValueError(f"ZIP file used as a directory: {info.filename!r}")
            key = unicodedata.normalize("NFC", unicodedata.normalize("NFC", part).casefold())
            child = node.children.get(key)
            if child is None:
                child = node.children[key] = _PathNode(part)
                node_count += 1
                if expanding and node_count > max_entries:
                    raise ValueError("Extraction exceeds path limit including implicit directories")
            elif child.spelling != part:
                raise ValueError(f"Conflicting ZIP member name: {info.filename!r}")
            node = child
        if node.entry is not None or node.children and not info.is_dir():
            raise ValueError(f"Duplicate or conflicting ZIP member: {info.filename!r}")
        node.entry = info
        entries["/".join(parts)] = info
    return entries


def inventory(path: Path, *, max_entries: int = MAX_ENTRIES, max_bytes: int = MAX_BYTES) -> list[dict]:
    """Return the validated central-directory manifest without reading member data."""
    with ZipFile(path) as archive:
        return [{"path": name, "size": info.file_size, "directory": info.is_dir()}
                for name, info in _manifest(archive, max_entries, max_bytes).items()]


def _target(path: Path) -> Path:
    path = Path(path).absolute()
    if path.name in {"", ".", ".."}:
        raise ValueError("Choose a new output name")
    target = path.parent.resolve(strict=True) / path.name
    if os.path.lexists(target):
        raise FileExistsError(errno.EEXIST, "Output already exists", target)
    return target


def _publish(staged: Path, target: Path) -> None:
    """Publish at a new name atomically, including when another writer races us."""
    if os.name == "nt":
        staged.rename(target)
        return
    if staged.is_file():
        target.hardlink_to(staged)
        return

    from ctypes import CDLL, c_char_p, c_int, c_uint, get_errno

    libc = CDLL(None, use_errno=True)
    source, destination = os.fsencode(staged), os.fsencode(target)
    if sys.platform == "linux" and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = (c_int, c_char_p, c_int, c_char_p, c_uint)
        result = rename(-100, source, -100, destination, 1)  # AT_FDCWD, RENAME_NOREPLACE.
    elif sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        rename = libc.renamex_np
        rename.argtypes = (c_char_p, c_char_p, c_uint)
        result = rename(source, destination, 4)  # RENAME_EXCL.
    else:
        raise OSError(errno.ENOTSUP, "Atomic directory publication unavailable", target)
    if result:
        error = get_errno()
        raise OSError(error, os.strerror(error), target)


def _copy(source: BinaryIO, target: BinaryIO | None, size: int) -> None:
    remaining = size
    while chunk := source.read(min(_CHUNK_BYTES, remaining + 1)):
        remaining -= len(chunk)
        if remaining < 0:
            raise BadZipFile("Member exceeds its declared size or replacement size changed")
        if target is not None:
            target.write(chunk)
    if remaining:
        raise BadZipFile("Truncated member or replacement size changed")


def _read_member(archive: ZipFile, info: ZipInfo, target: BinaryIO | None) -> None:
    try:
        with archive.open(info) as source:
            _copy(source, target, info.file_size)
    except _DECODE_ERRORS as error:
        raise BadZipFile(f"Cannot decode ZIP member: {info.filename!r}") from error
    except NotImplementedError as error:
        raise ValueError(f"Unsupported ZIP compression for member: {info.filename!r}") from error


def extract_archive(path: Path, destination: Path, *, max_entries: int = MAX_ENTRIES,
                    max_bytes: int = MAX_BYTES) -> ExtractionResult:
    """Validate all paths first, unpack privately, then publish the finished directory."""
    with ZipFile(path) as archive:
        entries = _manifest(archive, max_entries, max_bytes, writing=True, expanding=True)
        total = sum(member.file_size for member in entries.values())
        target = _target(destination)
        if total > shutil.disk_usage(target.parent).free:
            raise OSError(errno.ENOSPC, "Insufficient space for ZIP extraction", target)
        files = 0
        directories = set()
        for name, info in entries.items():
            directory = name if info.is_dir() else name.rpartition("/")[0]
            while directory and directory not in directories:
                directories.add(directory)
                directory = directory.rpartition("/")[0]
        with TemporaryDirectory(prefix=".vortex-zip-", dir=target.parent) as temp:
            unpacked = Path(temp) / "contents"
            unpacked.mkdir(mode=0o700)
            for directory in sorted(directories):
                (unpacked / directory).mkdir()
            for name, info in entries.items():
                if info.is_dir():
                    _read_member(archive, info, None)
                else:
                    with (unpacked / name).open("xb") as output:
                        _read_member(archive, info, output)
                    files += 1
            _publish(unpacked, target)
        return ExtractionResult(str(target), files, len(directories), total)


def repack_archive(path: Path, output: Path, replacements: Mapping[str, Path], *,
                   max_entries: int = MAX_ENTRIES, max_bytes: int = MAX_BYTES) -> RepackResult:
    """Build a new ZIP, replacing existing regular members by exact archive path."""
    with ZipFile(path) as archive:
        entries = _manifest(archive, max_entries, max_bytes, writing=True)
        if not replacements:
            raise ValueError("Supply at least one replacement")
        sources = {}
        for name, source in replacements.items():
            if name not in entries or entries[name].is_dir():
                raise ValueError(f"Replacement must name an existing ZIP file: {name!r}")
            replacement = Path(source)
            metadata = replacement.lstat()
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError(f"Replacement must be a regular file: {replacement}")
            sources[name] = (replacement, metadata)

        total = sum(sources[name][1].st_size if name in sources else info.file_size
                    for name, info in entries.items())
        if total > max_bytes:
            raise ValueError("Repacked archive exceeds configured byte limit")
        destination = _target(output)
        with TemporaryDirectory(prefix=".vortex-zip-", dir=destination.parent) as temp:
            staged = Path(temp) / "repacked.zip"
            with ZipFile(staged, "x") as packed:
                packed.comment = archive.comment
                for name, info in entries.items():
                    member = ZipInfo(info.filename, info.date_time)
                    member.comment = info.comment
                    member.file_size = info.file_size
                    if info.is_dir():
                        _read_member(archive, info, None)
                        member.external_attr = ((stat.S_IFDIR | 0o755) << 16) | 0x10
                        packed.writestr(member, b"")
                        continue
                    member.compress_type = ZIP_DEFLATED
                    if name not in sources:
                        with packed.open(member, "w") as destination_file:
                            _read_member(archive, info, destination_file)
                        continue
                    _read_member(archive, info, None)  # Reject corruption even in replaced members.
                    replacement, expected = sources[name]
                    member.file_size = expected.st_size
                    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                    flags |= getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
                    with os.fdopen(os.open(replacement, flags), "rb") as source:
                        observed = os.fstat(source.fileno())
                        if not stat.S_ISREG(observed.st_mode) or not os.path.samestat(expected, observed):
                            raise ValueError(f"Replacement changed before reading: {replacement}")
                        with packed.open(member, "w") as destination_file:
                            _copy(source, destination_file, expected.st_size)
            staged.chmod(0o600)
            _publish(staged, destination)
        files = sum(not info.is_dir() for info in entries.values())
        return RepackResult(str(destination), files, total, tuple(sorted(sources)))


def discover_videos(path: Path, *, max_entries: int = MAX_ENTRIES,
                    max_bytes: int = MAX_BYTES) -> list[dict]:
    """Find candidates by suffix in a ZIP or directory without probing streams."""
    path = Path(path)
    if path.is_dir():
        _validate_limits(max_entries, max_bytes)
        candidates = []
        encountered = total = 0
        for directory, subdirectories, names in path.walk(on_error=_raise_walk_error):
            encountered += len(subdirectories) + len(names)
            if encountered > max_entries:
                raise ValueError("Directory exceeds configured entry limit")
            for name in names:
                file = directory / name
                if file.suffix.lower() not in _VIDEO_SUFFIXES:
                    continue
                metadata = file.stat(follow_symlinks=False)
                if stat.S_ISREG(metadata.st_mode):
                    total += metadata.st_size
                    if total > max_bytes:
                        raise ValueError("Video candidates exceed configured byte limit")
                    candidates.append({"path": file.relative_to(path).as_posix(), "size": metadata.st_size,
                                       "directory": False})
        return sorted(candidates, key=lambda candidate: candidate["path"])
    return sorted(
        (member for member in inventory(path, max_entries=max_entries, max_bytes=max_bytes)
         if not member["directory"] and PurePosixPath(member["path"]).suffix.lower() in _VIDEO_SUFFIXES),
        key=lambda candidate: candidate["path"],
    )


def _raise_walk_error(error: OSError) -> None:
    raise error
