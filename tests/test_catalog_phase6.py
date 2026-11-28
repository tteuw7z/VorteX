"""Phase 6: bounded, bilingual routing without claiming external execution."""
import unittest
from vortex.agents import AgentEngine
from vortex.core import Engine, plan
from vortex.skills import SKILLS, Skill, SkillEngine, normalize
import re
from vortex.workflow import Status


class CatalogReconciliationTests(unittest.TestCase):
    def test_new_domains_bilingual(self):
        cases = (
            ("finance", "financial analyst", "Revisar orçamento", "Review budget"),
            ("healthcare", "health information reviewer", "Informações de saúde", "Review healthcare information"),
            ("marketing", "marketing strategist", "Criar campanha", "Review campaign"),
            ("sales", "sales analyst", "Planejar vendas", "Plan sales"),
            ("product", "product strategist", "Priorizar produto", "Prioritize product"),
            ("project", "project coordinator", "Montar cronograma", "Review milestones"),
            ("game", "game developer", "Criar jogo", "Prototype game"),
            ("gis", "geospatial analyst", "Analisar cartografia", "Analyze geospatial data"),
            ("spatial", "spatial experience designer", "Experiência imersiva", "Build XR experience"),
            ("support", "support engineer", "Resolver incidente", "Review helpdesk incident"),
        )
        for name, role, *tasks in cases:
            for task in tasks:
                with self.subTest(task=task):
                    result = plan(task, agent_limit=1)
                    self.assertEqual(result["skills"][0]["name"], name)
                    self.assertEqual(result["agents"], [role])
                    self.assertEqual(result["status"], Status.PLANNED)
                    self.assertEqual(AgentEngine().load([role])[0].role, role)
                    self.assertEqual(Engine().run(name, task, approved=True)["status"], Status.BLOCKED)

    def test_all_catalog_roles_have_profiles(self):
        for skill in SKILLS:
            self.assertEqual(tuple(p.role for p in AgentEngine().load(skill.agents)), skill.agents)

    def test_explicit_configuration_still_limits_catalog(self):
        self.assertTrue(plan("Review budget", skills=SkillEngine(enabled=["android"]))["fallback"])
        self.assertLessEqual(len(plan("Python Android finance marketing sales", agent_limit=2)["agents"]), 2)

    def test_index_preserves_reference_scoring_and_catalog_order(self):
        custom = (
            Skill("one", ("alpha", "alpha", "beta"), ("reviewer",), ("check",)),
            Skill("two", ("alpha", "gamma"), ("reviewer",), ("check",)),
            Skill("three", ("gamma",), ("reviewer",), ("check",)),
        )
        for skills in (SKILLS, custom):
            for enabled in (None, [], [skills[0].name]):
                active = [s for s in skills if enabled is None or s.name in enabled]
                engine = SkillEngine(skills, enabled=enabled)
                for task in ("alpha beta gamma alpha", "gamma alpha", "ÁLPHA", "Audit Android security",
                             "Legendar vídeos ZIP", "Experiência imersiva", "Obrigado"):
                    words = set(re.findall(r"\w+", normalize(task)))
                    expected = sorted(active, key=lambda s: -len(words.intersection(s.keywords)))
                    expected = [s for s in expected if words.intersection(s.keywords)]
                    for limit in (1, 2, 3):
                        self.assertEqual(engine.select(task, limit=limit), tuple(expected[:limit]))
