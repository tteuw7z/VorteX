import contextlib
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from vortex.agents import AgentEngine
from vortex.archive import inventory
from vortex.cli import main
from vortex.config import Config
from vortex.context import ContextEngine
from vortex.core import Engine, Status, plan
from vortex.learning import LearningEngine
from vortex.skills import SkillEngine
from vortex.workflow import Stage, Workflow


class WorkflowTests(unittest.TestCase):
    def test_dependencies_and_evidence(self):
        stages = Workflow([
            Stage("review", "security", "check result", depends_on=("work",)),
            Stage("work", "engineering", "prepare result", approval="prepare"),
        ])
        engine = Engine()
        engine.register("engineering", lambda task: {
            "status": "SUCCESS", "evidence": "generated fixture", "artifacts": {"item": [task]},
        })

        def review(task, prior):
            self.assertEqual(prior, {"work": {"item": ["prepare result"]}})
            prior["work"]["item"].clear()
            return {"status": "SUCCESS", "evidence": "fixture checked", "artifacts": {"done": True}}

        engine.register("security", review, with_context=True)
        result = engine.run_workflow(stages, approvals={"prepare", "review"})
        self.assertEqual(list(result), ["work", "review"])
        self.assertEqual(result["work"].artifacts, {"item": ["prepare result"]})
        self.assertEqual(result["review"].evidence, "fixture checked")

    def test_graph_validation(self):
        for stages in (
            [],
            [Stage("a", "engineering", "x"), Stage("a", "engineering", "y")],
            [Stage("a", "engineering", "x", depends_on=("missing",))],
            [Stage("a", "engineering", "x", depends_on=("b",)),
             Stage("b", "engineering", "x", depends_on=("a",))],
        ):
            with self.subTest(stages=stages), self.assertRaises(ValueError):
                Workflow(stages)

    def test_blocked_simulated_and_missing_evidence(self):
        calls = []
        engine = Engine()

        def adapter(task):
            calls.append(task)
            return {"status": Status.SUCCESS}

        engine.register("engineering", adapter)
        graph = Workflow([Stage("first", "engineering", "x"),
                          Stage("second", "engineering", "y", depends_on=("first",))])
        simulated = engine.run_workflow(graph, approvals={"first"}, simulate=True)
        self.assertTrue(all(r.status == Status.PLANNED for r in simulated.values()))
        blocked = engine.run_workflow(graph, approvals={"second"})
        self.assertEqual(blocked["first"].reason, "Approval missing")
        self.assertEqual(blocked["second"].reason, "Dependency did not succeed")
        self.assertEqual(calls, [])
        run = engine.run_workflow(graph, approvals={"first", "second"})
        self.assertEqual(calls, ["x"])
        self.assertEqual(run["first"].status, Status.FAILED)
        self.assertEqual(run["first"].reason, "Missing evidence")

    def test_fallback_stops_after_possible_side_effect(self):
        engine = Engine()
        engine.register("engineering", lambda _: {"status": "FAILED"})
        engine.register("research", lambda _: {"status": "SUCCESS", "evidence": "fixture"})
        for retry in (False, True):
            graph = Workflow([Stage("work", "engineering", "x",
                                    alternatives=("research",), retry_safe=retry)])
            result = engine.run_workflow(graph, approvals={"work"})["work"]
            self.assertEqual(result.status, Status.SUCCESS if retry else Status.FAILED)
            self.assertEqual(result.attempted, ("engineering", "research") if retry else ("engineering",))
        missing = Workflow([Stage("x", "android", "x", alternatives=("research",))])
        self.assertEqual(engine.run_workflow(missing, approvals={"x"})["x"].attempted, ("research",))

    def test_local_archive_workflow_records_real_artifacts(self):
        with TemporaryDirectory() as directory:
            archive = Path(directory) / "fixture.zip"
            with ZipFile(archive, "w") as output:
                output.writestr("fixture.txt", "phase two")

            def inspect_archive(path):
                file = Path(path)
                return {"status": Status.SUCCESS, "evidence": "ZIP inventory read",
                        "artifacts": {"entries": inventory(file), "file": path}}

            def verify(_task, prior):
                artifacts = prior["inventory"]
                if [entry["path"] for entry in artifacts["entries"]] != ["fixture.txt"]:
                    return {"status": Status.FAILED, "reason": "Missing expected entry"}
                digest = hashlib.sha256(Path(artifacts["file"]).read_bytes()).hexdigest()
                return {"status": Status.SUCCESS, "evidence": f"sha256:{digest}"}

            engine = Engine()
            engine.register("engineering", inspect_archive)
            engine.register("security", verify, with_context=True)
            flow = Workflow([Stage("inventory", "engineering", str(archive)),
                             Stage("verify", "security", "verify fixture",
                                   depends_on=("inventory",))])
            report = engine.run_workflow(flow, approvals={"inventory", "verify"})
            self.assertEqual(report["inventory"].artifacts["entries"][0]["size"], 9)
            self.assertEqual(report["verify"].status, Status.SUCCESS)
            self.assertEqual(report["verify"].evidence,
                             "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_workflow_rejects_lossy_artifacts(self):
        engine = Engine()
        engine.register("engineering", lambda _: {
            "status": Status.SUCCESS, "evidence": "fixture", "artifacts": {"x": (1, 2)},
        })
        graph = Workflow([Stage("work", "engineering", "x")])
        result = engine.run_workflow(graph, approvals={"work"})["work"]
        self.assertEqual(result.status, Status.FAILED)


class KnowledgeTests(unittest.TestCase):
    def test_selective_catalog_and_profiles(self):
        skills = SkillEngine(enabled=["engineering", "android"])
        result = plan("Android código vídeo", skills=skills, agent_limit=3)
        self.assertEqual([s["name"] for s in result["skills"]], ["android", "engineering"])
        self.assertEqual(result["agents"], ["android engineer", "qa", "software engineer"])
        profiles = AgentEngine().load(result["agents"])
        self.assertEqual([p.role for p in profiles], result["agents"])
        self.assertTrue(all(p.focus and p.output for p in profiles))
        self.assertTrue(plan("vídeo", skills=skills)["fallback"])

    def test_context_preserves_checkpoint_and_restores_deduplicated_text(self):
        large = "ação" * 30
        checkpoint = {"decisions": [large], "evidence": "fixture"}
        observations = {"stderr": large, "stdout": large, "short": "ok", "structured": {"n": 2}}
        view = ContextEngine(threshold=32).compact(checkpoint, observations)
        self.assertEqual(view.summary()["checkpoint"], checkpoint)
        self.assertEqual(view.summary()["observations"], {"short": "ok", "structured": {"n": 2}})
        self.assertEqual(len(view.originals), 1)
        self.assertEqual(view.restore(), {"checkpoint": checkpoint, "observations": observations})
        self.assertGreater(view.summary()["estimated_tokens"], 0)

    def test_learning_is_explicit_and_deduplicates_with_provenance(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "knowledge.sqlite"
            store = LearningEngine(path)
            self.assertEqual(store.recall(), [])
            self.assertFalse(path.exists())
            entry = store.remember("media", "Revisão  de cortes", "source-a", "observed")
            self.assertEqual(entry, store.remember("MEDIA", "revisao de CORTES", "source-b", "checked"))
            self.assertEqual(entry, store.remember("media", "revisão de cortes", "source-a", "observed"))
            records = LearningEngine(path).recall("media")
            self.assertEqual(len(records), 1)
            self.assertEqual(len(records[0]["evidence"]), 2)
            self.assertEqual(store.recall("android"), [])
            self.assertTrue(store.forget(entry))
            self.assertFalse(store.forget(entry))
            self.assertEqual(store.recall(), [])


class CliTests(unittest.TestCase):
    def invoke(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(args), 0)
        return json.loads(output.getvalue())

    def test_configured_knowledge_and_legacy_plan(self):
        with TemporaryDirectory() as directory:
            config = Path(directory) / "vortex.toml"
            config.write_text('agent_limit = 1\nskills = ["android"]\nlearning_db = "learn.db"\n')
            common = ("--config", str(config))
            legacy = self.invoke(*common, "plan", "Android código")
            self.assertEqual(set(legacy), {"status", "skills", "agents", "fallback"})
            self.assertEqual(len(legacy["agents"]), 1)
            added = self.invoke(*common, "learn", "add", "android", "verify signature",
                                "fixture", "signature read")
            self.invoke(*common, "learn", "add", "media", "review cuts", "fixture", "reviewed")
            knowledge = self.invoke(*common, "knowledge", "Android código", "--agent-limit", "2")
            self.assertEqual(len(knowledge["profiles"]), 2)
            self.assertEqual([e["id"] for e in knowledge["learned"]], [added["id"]])
            self.assertTrue(self.invoke(*common, "learn", "remove", str(added["id"]))["removed"])

    def test_context_command_and_configuration_validation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "vortex.toml"
            config.write_text("context_threshold = 3")
            data = root / "context.json"
            data.write_text(json.dumps({"checkpoint": {"goal": "hello"},
                                        "observations": {"trace": "large"}}))
            result = self.invoke("--config", str(config), "context", str(data))
            self.assertIn("trace", result["omitted"])
            self.assertEqual(result["checkpoint"], {"goal": "hello"})
            for invalid in ('agent_limit = true', 'skills = ["unknown"]', 'extra = 1'):
                config.write_text(invalid)
                with self.assertRaises(ValueError):
                    Config.load(config)
