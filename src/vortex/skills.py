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
    Skill("engineering", ("python", "code", "codigo", "bug", "software", "api", "site", "website", "app",
                          "aplicativo", "script", "programa", "database", "banco", "sql"), ("software engineer", "qa"), ("inspect", "implement", "test", "review")),
    Skill("research", ("research", "pesquisa", "pesquisar", "investigar", "sources", "fontes"), ("researcher", "reviewer"), ("decompose", "gather sources", "cross-check", "synthesize")),
    Skill("design", ("design", "ui", "figma", "interface", "acessibilidade"), ("designer", "accessibility reviewer"), ("requirements", "prototype", "validate")),
    Skill("learning", ("study", "estudo", "estudar", "quiz", "aprender"), ("educator",), ("identify source", "explain", "practice", "review errors")),
    Skill("security", ("security", "seguranca", "audit", "auditoria"), ("security reviewer",), ("scope authorization", "inspect", "verify", "report")),
    Skill("automation", ("workflow", "automacao", "automation"), ("automation engineer",), ("map steps", "check permissions", "execute", "verify")),
    Skill("finance", ("finance", "financas", "orcamento", "budget", "contabilidade", "accounting"), ("financial analyst", "reviewer"),
          ("identify scope and assumptions", "check calculations and sources", "report risks and uncertainty")),
    Skill("healthcare", ("healthcare", "saude", "clinical", "clinico", "medico", "medical"), ("health information reviewer", "reviewer"),
          ("identify information need", "consult authoritative evidence", "flag uncertainty and need for professional review")),
    Skill("marketing", ("marketing", "campaign", "campanha", "seo", "branding", "advertising", "publicidade"), ("marketing strategist", "reviewer"),
          ("identify audience", "define campaign objectives", "measure results")),
    Skill("sales", ("sales", "vendas", "prospecting", "prospeccao", "crm"), ("sales analyst", "reviewer"),
          ("identify customer needs", "plan outreach with consent", "review outcomes")),
    Skill("product", ("product", "produto", "roadmap", "backlog", "discovery"), ("product strategist", "reviewer"),
          ("identify user needs", "prioritize requirements", "define acceptance criteria")),
    Skill("project", ("project", "projeto", "cronograma", "milestones", "milestone", "sprint"), ("project coordinator", "reviewer"),
          ("define scope", "map dependencies and milestones", "review delivery risks")),
    Skill("game", ("game", "games", "jogo", "jogos", "gameplay", "godot", "unity"), ("game developer", "reviewer"),
          ("define mechanics", "prototype gameplay", "test behavior and performance")),
    Skill("gis", ("gis", "geospatial", "geoespacial", "cartography", "cartografia", "qgis"), ("geospatial analyst", "reviewer"),
          ("identify coordinate system and data provenance", "check spatial transformations", "validate output")),
    Skill("spatial", ("xr", "arcore", "arkit", "spatial", "imersivo", "imersiva", "immersive", "3d"), ("spatial experience designer", "reviewer"),
          ("define interaction and coordinate frame", "prototype experience", "check accessibility and performance")),
    Skill("support", ("support", "suporte", "troubleshooting", "helpdesk", "incident", "incidente", "network", "rede"), ("support engineer", "reviewer"),
          ("collect symptoms", "isolate causes safely", "verify recovery")),
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
        index: dict[str, list[int]] = {}
        for position, skill in enumerate(self._skills):
            for keyword in set(skill.keywords):
                index.setdefault(keyword, []).append(position)
        self._keyword_index = {keyword: tuple(positions) for keyword, positions in index.items()}

    def select(self, task: str, *, limit: int = 3) -> tuple[Skill, ...]:
        if not task.strip() or type(limit) is not int or limit < 1:
            raise ValueError("Nonempty task and positive skill limit required")
        tokens = set(re.findall(r"\w+", normalize(task)))
        scores: dict[int, int] = {}
        for token in tokens:
            for position in self._keyword_index.get(token, ()):
                scores[position] = scores.get(position, 0) + 1
        ranked = sorted(scores, key=lambda position: (-scores[position], position))
        return tuple(self._skills[position] for position in ranked[:limit])
