"""Explicit local persistence for reusable techniques and their evidence."""
from contextlib import contextmanager
from pathlib import Path
import os
import stat
import sqlite3

from .skills import normalize


class LearningEngine:
    def __init__(self, database: Path):
        self.database = Path(database).absolute()
        if self.database.is_symlink():
            raise ValueError("Learning database cannot be a symlink")

    def _private_file(self, write):
        if write and not self.database.exists():
            try:
                fd = os.open(self.database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(fd)
        metadata = self.database.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("Learning database must be a regular file")
        if os.name == "posix" and metadata.st_mode & 0o077:
            raise ValueError("Learning database permissions must be private (chmod 600)")

    @contextmanager
    def _connect(self, *, write=False):
        self._private_file(write)
        uri = self.database.as_uri() + ("?mode=rwc" if write else "?mode=ro")
        connection = sqlite3.connect(uri, uri=True)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            if write:
                connection.execute("PRAGMA secure_delete = ON")
            with connection:
                yield connection
        finally:
            connection.close()

    def remember(self, capability: str, technique: str, source: str, evidence: str) -> int:
        capability, technique, source, evidence = (
            value.strip() for value in (capability, technique, source, evidence)
        )
        if not all((capability, technique, source, evidence)):
            raise ValueError("Capability, technique, source and evidence are required")
        capability = capability.casefold()
        key = " ".join(normalize(technique).split())
        with self._connect(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS techniques (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capability TEXT NOT NULL, technique TEXT NOT NULL, key TEXT NOT NULL,
                    UNIQUE (capability, key)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS evidence (
                    technique_id INTEGER NOT NULL REFERENCES techniques(id) ON DELETE CASCADE,
                    source TEXT NOT NULL, observation TEXT NOT NULL,
                    PRIMARY KEY (technique_id, source, observation)
                )
            """)
            connection.execute("""
                INSERT INTO techniques (capability, technique, key) VALUES (?, ?, ?)
                ON CONFLICT (capability, key) DO NOTHING
            """, (capability, technique, key))
            entry_id, = connection.execute("""
                SELECT id FROM techniques WHERE capability = ? AND key = ?
            """, (capability, key)).fetchone()
            connection.execute("""
                INSERT INTO evidence (technique_id, source, observation) VALUES (?, ?, ?)
                ON CONFLICT (technique_id, source, observation) DO NOTHING
            """, (entry_id, source, evidence))
        return entry_id

    def recall(self, capability: str | None = None) -> list[dict]:
        if not self.database.exists():
            return []
        records = {}
        clause = "" if capability is None else "WHERE t.capability = ?"
        params = () if capability is None else (capability.strip().casefold(),)
        with self._connect() as connection:
            for entry_id, name, technique, source, evidence in connection.execute(f"""
                SELECT t.id, t.capability, t.technique, e.source, e.observation
                FROM techniques AS t JOIN evidence AS e ON e.technique_id = t.id
                {clause}
                ORDER BY t.id, e.source, e.observation
            """, params):
                record = records.setdefault(entry_id, {"id": entry_id, "capability": name,
                                                       "technique": technique, "evidence": []})
                record["evidence"].append({"source": source, "observation": evidence})
        return list(records.values())

    def forget(self, entry_id: int) -> bool:
        if type(entry_id) is not int or entry_id < 1:
            raise ValueError("Entry ID must be a positive integer")
        if not self.database.exists():
            return False
        with self._connect(write=True) as connection:
            return connection.execute("DELETE FROM techniques WHERE id = ?", (entry_id,)).rowcount > 0
