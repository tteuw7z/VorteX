import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from vortex.core import Engine, Status, plan
from vortex.archive import inventory

class CoreTests(unittest.TestCase):
    def test_routing(self):
        result = plan("compilar APK Android", agent_limit=1)
        self.assertEqual(result["skills"][0]["name"], "android")
        self.assertEqual(len(result["agents"]), 1)
        self.assertEqual(result["status"], Status.PLANNED)

    def test_unknown(self):
        self.assertTrue(plan("hello")["fallback"])

    def test_dispatch(self):
        engine = Engine()
        engine.register("android", lambda _: {"status": Status.SUCCESS})
        self.assertEqual(engine.run("android", "build")["status"], Status.BLOCKED)
        self.assertEqual(engine.run("android", "build", approved=True)["status"], Status.SUCCESS)
        with self.assertRaises(ValueError):
            engine.register("android", lambda _: {})

    def test_zip(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "test.zip"
            with ZipFile(path, "w") as archive:
                archive.writestr("src/example.py", "pass")
            self.assertEqual(inventory(path)[0]["path"], "src/example.py")
            with ZipFile(path, "w") as archive:
                archive.writestr("../escape", "bad")
            with self.assertRaises(ValueError):
                inventory(path)
