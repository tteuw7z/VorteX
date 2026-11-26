"""Phase 6: bounded, bilingual routing without claiming external execution."""
import unittest
from vortex.agents import AgentEngine
from vortex.core import Engine, plan
from vortex.skills import SKILLS, SkillEngine
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
