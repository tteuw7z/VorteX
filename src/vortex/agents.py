"""Original, role-based profiles loaded only for selected work."""
from collections.abc import Iterable
from dataclasses import dataclass

from .skills import Skill


@dataclass(frozen=True, slots=True)
class AgentProfile:
    role: str
    focus: str
    output: str


_PROFILE_DATA = {
    "android engineer": ("Inspect Android build inputs and environment",
                         "Build result with signature evidence and artifact digest"),
    "qa": ("Check acceptance criteria and regressions",
           "Verification results with commands, observations and gaps"),
    "media engineer": ("Inspect streams, timing and encoding requirements",
                       "Media measurements and a reproducible processing record"),
    "editor": ("Plan and validate cuts, captions and synchronization",
               "Timecoded edit decisions and review observations"),
    "software engineer": ("Understand existing interfaces and implement the scoped change",
                          "Tested patch with behavioral evidence"),
    "researcher": ("Resolve the question from relevant primary evidence",
                   "Findings with provenance and unresolved questions"),
    "reviewer": ("Check claims against their supporting evidence",
                 "Corrections, uncertainty and coverage"),
    "designer": ("Turn requirements into a usable visual hierarchy",
                 "Prototype and interaction decisions"),
    "accessibility reviewer": ("Check keyboard use, contrast and accessible names",
                               "Observed failures and verification steps"),
    "educator": ("Match examples and practice to the learner's goals",
                 "Exercises with explanations and feedback"),
    "security reviewer": ("Inspect permission boundaries and defensive controls",
                          "Findings with evidence and mitigation"),
    "automation engineer": ("Check prerequisites, permissions and failure recovery",
                            "Workflow with verification and recovery behavior"),
}


class AgentEngine:
    def select(self, skills: Iterable[Skill], *, limit: int = 3) -> tuple[str, ...]:
        if type(limit) is not int or not 1 <= limit <= 4:
            raise ValueError("Agent limit must be between 1 and 4")
        selected = tuple(skills)
        roles = tuple(dict.fromkeys(role for skill in selected for role in skill.agents))
        if len(roles) <= limit:
            return roles
        leads = (skill.agents[0] for skill in selected if skill.agents)
        return tuple(dict.fromkeys((*leads, *roles)))[:limit]

    def load(self, roles: Iterable[str]) -> tuple[AgentProfile, ...]:
        return tuple(AgentProfile(role, *_PROFILE_DATA[role]) for role in roles
                     if role in _PROFILE_DATA)
