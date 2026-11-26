"""Explicit chat activation and a read-only, host-aware capability menu."""
from dataclasses import dataclass, field

from .agents import AgentEngine
from .discipline import prepare_task
from .skills import SKILLS, SkillEngine

GREETING = "🇮🇪 𝘏𝘦𝘭𝘭𝘰, 𝘐’𝘮 𝘝𝘰𝘳𝘵𝘦𝘹\n𝘏𝘰𝘸 𝘤𝘢𝘯 𝘐 𝘩𝘦𝘭𝘱 𝘺𝘰𝘶 𝘳𝘪𝘨𝘩𝘵 𝘯𝘰𝘸?"
_TRIGGERS = frozenset(("vortex", "🇮🇪"))
_YES = frozenset(("yes", "sim", "quero", "claro", "sure"))
_NO = frozenset(("no", "não", "nao"))
_CATEGORIES = (
    ("agents", "Agentes", "Agents"),
    ("functions", "Funcionalidades", "Capabilities"),
    ("security", "Segurança", "Security"),
    ("tools", "Ferramentas", "Tools"),
    ("settings", "Configurações", "Settings"),
    ("help", "Ajuda", "Help"),
)
_LABELS = {
    "archive": "Arquivos ZIP", "android": "Android e APK", "media": "Áudio e vídeo",
    "engineering": "Desenvolvimento", "research": "Pesquisa", "design": "Design",
    "learning": "Estudos", "security": "Segurança", "automation": "Automação",
    "finance": "Finanças", "healthcare": "Informação de saúde", "marketing": "Marketing",
    "sales": "Vendas", "product": "Produto", "project": "Projetos", "game": "Jogos",
    "gis": "Geoinformação", "spatial": "Experiências imersivas", "support": "Suporte",
}


@dataclass(slots=True)
class Conversation:
    """One instance per conversation; never share it between users."""

    locale: str = "en"
    enabled: frozenset[str] | None = None
    execution_capabilities: frozenset[str] = field(default_factory=frozenset)
    interactive: bool = False
    agent_limit: int = 3
    _active: bool = field(default=False, init=False)
    _offered: bool = field(default=False, init=False)
    _menu_open: bool = field(default=False, init=False)

    def __post_init__(self):
        self.enabled = SkillEngine(enabled=self.enabled).names
        # Only trusted host bindings may supply execution capabilities.
        self.execution_capabilities = frozenset(self.execution_capabilities)
        if not self.execution_capabilities <= self.enabled:
            raise ValueError("Execution capabilities must be enabled catalog entries")
        if type(self.interactive) is not bool:
            raise ValueError("Interactive support must be a host boolean")
        if type(self.agent_limit) is not int or not 1 <= self.agent_limit <= 4:
            raise ValueError("Invalid agent limit")
        if not isinstance(self.locale, str):
            raise ValueError("Invalid locale")

    def _say(self, pt, en):
        return pt if self.locale.lower().split("-")[0] == "pt" else en

    def _menu(self, section=None):
        skills = [skill for skill in SKILLS if skill.name in self.enabled]
        planning = self._say("planejamento", "planning")
        bound = self._say("execução vinculada; autorização necessária",
                          "execution bound; authorization required")
        entries = [{"id": key, "label": self._say(pt, en)} for key, pt, en in _CATEGORIES]
        if section == "functions":
            rows = [{"id": skill.name, "label": self._say(_LABELS[skill.name], skill.name),
                     "agents": list(skill.agents),
                     "status": bound if skill.name in self.execution_capabilities else planning}
                    for skill in skills]
        elif section == "agents":
            roles = {role for skill in skills for role in skill.agents}
            roles.update(("code reviewer", "qa", "security reviewer"))
            if "design" in self.enabled:
                roles.update(("motion designer", "ui interaction tester"))
            rows = [{"id": p.role, "label": p.role, "detail": p.focus, "status": planning}
                    for p in AgentEngine().catalog() if p.role in roles]
        elif section == "tools":
            rows = [{"id": skill.name, "label": self._say(_LABELS[skill.name], skill.name),
                     "status": bound} for skill in skills
                    if skill.name in self.execution_capabilities]
        elif section == "security":
            rows = [{"label": self._say("Revisão, testes e verificação independente obrigatórios.",
                                       "Review, testing and independent verification required.")},
                    {"label": self._say("Nenhuma entrega insegura ou não verificada é autorizada.",
                                       "Unsafe or unverified delivery is not authorized.")}]
        elif section == "settings":
            rows = [{"label": self._say("Economia automática; revisões obrigatórias preservadas.",
                                       "Automatic economy; mandatory reviews preserved.")},
                    {"label": self._say("Idioma e interface controlados pelo host.",
                                       "Language and interface controlled by the host.")}]
        elif section == "help":
            rows = [{"label": self._say("Escreva seu pedido diretamente; não precisa selecionar agente.",
                                       "Write your request directly; no agent selection needed.")}]
        else:
            rows = entries
        title = self._say("Menu VorteX", "VorteX menu")
        if section:
            title += " — " + next(e["label"] for e in entries if e["id"] == section)
        lines = [title]
        for index, row in enumerate(rows, 1):
            line = (f"{index}. " if section is None else "• ") + row["label"]
            if row.get("agents"):
                line += " (" + ", ".join(row["agents"]) + ")"
            if row.get("status"):
                line += " — " + row["status"]
            if row.get("detail"):
                line += " — " + row["detail"]
            lines.append(line)
        if not rows:
            lines.append(self._say("Nenhuma ferramenta vinculada pelo host.",
                                   "No tools bound by the host."))
        if section:
            lines.append(self._say("0. Voltar", "0. Back"))
        lines.append(self._say("Ou escreva o que deseja fazer.", "Or type what you want to do."))
        self._menu_open = True
        self._offered = False
        return {"kind": "menu", "section": section, "entries": rows,
                "navigation": entries, "interactive_supported": self.interactive,
                "text": "\n".join(lines), "delivery_authorized": False}

    def handle(self, message: str):
        """Consume user text only; no startup event, tool call, network or publication."""
        if not isinstance(message, str) or not message.strip() or len(message) > 8192:
            raise ValueError("Expected 1 to 8192 characters of user text")
        command = message.strip().casefold()
        if command in _TRIGGERS:
            if self._active:
                return {"kind": "already_active",
                        "text": self._say("Como posso ajudar?", "How can I help?")}
            self._active = True
            self._offered = True
            return {"kind": "greeting", "text": GREETING + "\n\n" +
                    self._say("Você quer ver o menu?", "Would you like to see the menu?")}
        if not self._active:
            return {"kind": "pass_through", "task": message}
        if command == "menu" or (self._offered and command in _YES):
            return self._menu()
        if self._offered and command in _NO:
            self._offered = False
            return {"kind": "prompt", "text": self._say("Como posso ajudar?", "How can I help?")}
        if self._menu_open:
            if command in ("0", "back", "voltar"):
                return self._menu()
            for index, (key, pt, en) in enumerate(_CATEGORIES, 1):
                if command in (str(index), key, pt.casefold(), en.casefold()):
                    return self._menu(key)
        self._offered = self._menu_open = False
        # Preserve the original request; planning never grants execution privileges.
        return {"kind": "task", "task": message,
                "plan": prepare_task(message, agent_limit=self.agent_limit,
                                     skills=SkillEngine(enabled=self.enabled)),
                "delivery_authorized": False}
