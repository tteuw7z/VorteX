"""Capability descriptors and deterministic selection."""
from dataclasses import dataclass
import re
import unicodedata

@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    keywords: tuple[str, ...]
    agents: tuple[str, ...]
    steps: tuple[str, ...]

SKILLS = (
    Skill("archive", ("zip", "unzip", "repack", "descompactar", "descompacte", "zipado", "zipada"), ("software engineer",),
          ("inventory members", "validate limits", "process archive", "verify outputs")),
    Skill("android", ("apk", "android", "gradle"), ("android engineer", "qa"), ("inspect project", "resolve build tools", "build", "verify signature and hash")),
    Skill("media", ("video", "videos", "audio", "captions", "legendas", "legendar", "transcreva", "transcribe", "transcrever", "motion"), ("media engineer", "editor"), ("inventory inputs", "inspect audio and frames", "process", "validate output")),
    Skill("engineering", ("python", "code", "codigo", "bug", "software", "api"), ("software engineer", "qa"), ("inspect", "implement", "test", "review")),
    Skill("research", ("research", "pesquisa", "pesquisar", "investigar", "sources", "fontes"), ("researcher", "reviewer"), ("decompose", "gather sources", "cross-check", "synthesize")),
    Skill("design", ("design", "ui", "figma", "interface", "acessibilidade"), ("designer", "accessibility reviewer"), ("requirements", "prototype", "validate")),
    Skill("learning", ("study", "estudo", "estudar", "quiz", "aprender"), ("educator",), ("identify source", "explain", "practice", "review errors")),
    Skill("security", ("security", "seguranca", "audit", "auditoria"), ("security reviewer",), ("scope authorization", "inspect", "verify", "report")),
    Skill("automation", ("workflow", "automacao", "automation"), ("automation engineer",), ("map steps", "check permissions", "execute", "verify")),
)

def normalize(value: str) -> str:
    if value.isascii():
        return value.casefold()
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))


class SkillEngine:
    def __init__(self, skills=SKILLS, *, enabled=None):
        source = tuple(skills)
        names = {skill.name for skill in source}
        if len(names) != len(source):
            raise ValueError("Duplicate skill")
        selected = names if enabled is None else set(enabled)
        if unknown := selected - names:
            raise ValueError(f"Unknown skills: {', '.join(sorted(unknown))}")
        self.names = frozenset(selected)
        self._skills = tuple(skill for skill in source if skill.name in selected)

    def select(self, task: str, *, limit: int = 3) -> tuple[Skill, ...]:
        if not task.strip() or type(limit) is not int or limit < 1:
            raise ValueError("Nonempty task and positive skill limit required")
        tokens = set(re.findall(r"\w+", normalize(task)))
        scores = [(len(tokens.intersection(s.keywords)), s) for s in self._skills]
        ranked = sorted(scores, key=lambda match: -match[0])
        return tuple(s for score, s in ranked if score > 0)[:limit]
