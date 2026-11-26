"""Explicit TOML settings for local execution."""
from dataclasses import dataclass
from pathlib import Path
import tomllib

from .skills import SKILLS


@dataclass(frozen=True, slots=True)
class Config:
    agent_limit: int = 3
    skills: tuple[str, ...] | None = None
    context_threshold: int = 4096
    learning_db: Path | None = None

    @classmethod
    def load(cls, path: Path) -> "Config":
        with path.open("rb") as source:
            data = tomllib.load(source)
        if unknown := data.keys() - {"agent_limit", "skills", "context_threshold", "learning_db"}:
            raise ValueError(f"Unknown configuration keys: {', '.join(sorted(unknown))}")
        agent_limit = data.get("agent_limit", 3)
        if type(agent_limit) is not int or not 1 <= agent_limit <= 4:
            raise ValueError("agent_limit must be an integer between 1 and 4")
        skills = data.get("skills")
        if skills is not None:
            known = {skill.name for skill in SKILLS}
            if not isinstance(skills, list) or any(
                not isinstance(name, str) or name not in known for name in skills
            ):
                raise ValueError("skills must list known capabilities")
            if len(set(skills)) != len(skills):
                raise ValueError("skills cannot contain duplicates")
        threshold = data.get("context_threshold", 4096)
        if type(threshold) is not int or threshold < 1:
            raise ValueError("context_threshold must be a positive integer")
        database = data.get("learning_db")
        if database is not None:
            if not isinstance(database, str) or not database.strip():
                raise ValueError("learning_db must be a nonempty path")
            database = path.resolve().parent / database
        return cls(agent_limit, tuple(skills) if skills is not None else None, threshold, database)
