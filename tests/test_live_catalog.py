import unittest
from vortex.live_catalog import export


class LiveCatalogTests(unittest.TestCase):
    def test_catalog_matches_real_parser_and_planning_roles(self):
        result = export("a" * 40)
        paths = {tuple(row["path"]) for row in result["commands"]}
        for path in (("chat",), ("design", "motion"), ("security", "audit"),
                     ("security", "publish"), ("host",)):
            self.assertIn(path, paths)
        self.assertEqual(len(paths), len(result["commands"]))
        roles = {row["role"] for row in result["agents"]}
        for skill in result["skills"]:
            self.assertLessEqual(set(skill["agents"]), roles)
        self.assertFalse(result["delivery_authorized"])
        self.assertEqual(result["execution"], "host_binding_required")

    def test_rejects_non_commit_reference(self):
        for value in ("main", "../main", "a" * 39, None):
            with self.assertRaises(ValueError):
                export(value)
