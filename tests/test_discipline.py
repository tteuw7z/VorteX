import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vortex.discipline import prepare_task, review_candidate
from vortex.security import snapshot, _review_coverage_valid


class DisciplineTests(unittest.TestCase):
    def test_economy_is_automatic_and_keeps_mandatory_roles(self):
        for task in ("Criar um site", "Build Python API", "Obrigado", "Editar vídeo"):
            result = prepare_task(task, agent_limit=1)
            economy = result["economy"]
            roles = {p["role"] for p in result["selected_profiles"]}
            self.assertTrue({"code reviewer", "qa", "security reviewer"} <= roles)
            self.assertTrue(economy["task_preserved"])
            if task == "Obrigado":
                self.assertEqual(economy["estimated_saved_tokens"], 0)
                self.assertTrue(economy["conservative_fallback"])
            else:
                self.assertGreater(economy["estimated_saved_tokens"], 0)
            self.assertIsNone(economy["actual_provider_tokens"])
            self.assertEqual(economy["performance_equivalence"], "NOT_MEASURED")
            self.assertFalse(result["delivery_authorized"])
            stages = [s["id"] for s in result["stages"]]
            self.assertLess(stages.index("functional_tests"), stages.index("security_tests"))
            self.assertEqual(stages[0], "economy")
            self.assertEqual(stages[-1], "delivery")

    def test_deferred_matching_specialists_are_disclosed(self):
        result = prepare_task("Python Android finance marketing sales game", agent_limit=1)
        self.assertTrue(result["economy"]["deferred_matching_skills"])
        self.assertTrue(result["economy"]["deferred_matching_roles"])
        roles = {p["role"] for p in result["selected_profiles"]}
        self.assertTrue(set(result["economy"]["automatically_expanded_roles"]) <= roles)
        self.assertFalse(roles.intersection(result["economy"]["omitted_profiles"]))
        self.assertTrue({"financial analyst", "marketing strategist", "sales analyst", "game developer"} <= roles)

    def test_review_inventory_and_exact_coverage(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_bytes(b"# Explain the purpose\nprint('ok')\n")
            (root / "empty.txt").touch()
            report = review_candidate(root)
            captured = snapshot(root)
            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["artifact_sha256"], captured.digest)
            self.assertEqual(len(report["files"]), 2)
            records = [{"path": row["path"], "sha256": row["sha256"],
                        "bytes_reviewed": row["size"], "status": "PASS"} for row in report["files"]]
            def valid(rows):
                return _review_coverage_valid(json.dumps({"artifact_sha256": captured.digest,
                                                           "files": rows}).encode(), captured)
            self.assertTrue(valid(records))
            self.assertFalse(valid(records[:-1]))
            self.assertFalse(valid(records + [records[0]]))
            self.assertFalse(valid([dict(records[0], bytes_reviewed=True), records[1]]))
            self.assertFalse(valid([dict(records[0], sha256="0" * 64), records[1]]))
            self.assertFalse(valid([dict(records[0], status="FAIL"), records[1]]))

    def test_generic_website_has_developer_not_only_reviewers(self):
        result = prepare_task("Criar um site", agent_limit=1)
        self.assertIn("software engineer", {p["role"] for p in result["selected_profiles"]})

    def test_explicit_config_disablement_is_not_overridden(self):
        from vortex.skills import SkillEngine
        result = prepare_task("Python Android finance", skills=SkillEngine(enabled=["android"]))
        self.assertEqual(set(result["economy"]["explicitly_disabled_matching_skills"]), {"engineering", "finance"})
        self.assertNotIn("financial analyst", {p["role"] for p in result["selected_profiles"]})

    def test_generic_development_aliases_do_not_change_legacy_plan(self):
        from vortex.core import plan
        self.assertTrue(plan("Criar um site")["fallback"])
        result = prepare_task("Criar um site")
        self.assertIn("engineering", result["economy"]["automatically_expanded_skills"])
        self.assertIn("software engineer", {p["role"] for p in result["selected_profiles"]})
        self.assertGreater(result["economy"]["estimated_saved_tokens"], 0)
