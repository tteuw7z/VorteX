"""Verify the installed v1 adapter can discover a new release without replacement."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("live_skill_route", Path(__file__).resolve().parents[1] / "scripts" / "route.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def catalog(sha, new=False):
    return {"schema": 1, "source_sha": sha,
            "skills": [{"name": "engineering", "keywords": ["python"],
                        "agents": ["software engineer"], "steps": ["test"]}]
            + ([{"name": "motion", "keywords": ["animation"],
                 "agents": ["motion designer"], "steps": ["review"]}] if new else []),
            "agents": [{"role": role, "focus": "review", "output": "evidence"}
                       for role in ("software engineer", "motion designer", "code reviewer",
                                    "qa", "security reviewer")],
            "commands": [{"path": ["design", "motion"], "arguments": []}]
            + ([{"path": ["design", "new"], "arguments": []}] if new else []),
            "execution": "host_binding_required", "delivery_authorized": False}


class InstalledSkillTests(unittest.TestCase):
    def test_same_adapter_discovers_updated_catalog(self):
        for new in (False, True):
            channel = ("b" if new else "a") * 40
            data = catalog(("d" if new else "c") * 40, new)
            seen = []
            def fetch(url):
                seen.append(url)
                if url == adapter.ROOT:
                    return {"ref": "refs/heads/chatgpt-live",
                            "object": {"type": "commit", "sha": channel}}
                return data
            result = adapter.sync(fetch)
            self.assertEqual(seen, [adapter.ROOT, adapter.RAW + channel + "/catalog.json"])
            plan = adapter.route("animation", result)
            self.assertEqual(plan["skills"], ["motion"] if new else [])
            self.assertFalse(plan["execution"])
            self.assertFalse(plan["delivery_authorized"])

    def test_invalid_remote_data_fails_closed(self):
        for key, value in (("schema", True), ("delivery_authorized", True),
                           ("source_sha", "../main")):
            data = catalog("a" * 40)
            data[key] = value
            with self.assertRaises(ValueError):
                adapter.validate(data)
        data = catalog("a" * 40)
        data["skills"][0]["agents"] = ["unknown"]
        with self.assertRaises(ValueError):
            adapter.validate(data)
        with self.assertRaises(ValueError):
            adapter.decode(b'{"schema":1,"schema":2}')

    def test_real_export_is_accepted_by_installed_adapter(self):
        from vortex.live_catalog import export
        data = adapter.validate(adapter.decode(__import__("json").dumps(export("a" * 40)).encode()))
        self.assertIn(["design", "motion"], [row["path"] for row in data["commands"]])

    def test_phrase_routing_and_bounds(self):
        data = catalog("a" * 40, True)
        data["skills"][1]["keywords"] = ["motion design", "edição visual"]
        self.assertEqual(adapter.route("Fazer EDIÇÃO visual", data)["skills"], ["motion"])
        self.assertEqual(adapter.route("motion unrelated design", data)["skills"], [])
        self.assertEqual(adapter.route("motion designer", data)["skills"], [])
        with self.assertRaises(ValueError):
            adapter.route("x" * 8193, data)

    def test_malformed_refs_and_duplicate_arguments(self):
        for ref in ([], {"object": None}, {"ref": "refs/heads/main", "object": {"type": "commit", "sha": "a" * 40}}):
            with self.assertRaises(ValueError):
                adapter.sync(lambda _: ref)
        data = catalog("a" * 40)
        data["commands"][0]["arguments"] = [
            {"name": "a", "flags": ["--x"], "required": False},
            {"name": "b", "flags": ["--x"], "required": False}]
        with self.assertRaises(ValueError):
            adapter.validate(data)
        with self.assertRaises(ValueError):
            adapter.decode(b'{"value":NaN}')
