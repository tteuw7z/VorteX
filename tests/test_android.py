import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from vortex.android import AndroidTools, build_apk, build_fixture, verify_apk


class AndroidValidationTests(unittest.TestCase):
    def test_discovery_chooses_latest_stable_version_and_rejects_paths(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for version in ("34.0.0", "35.0.0", "36.0.0-rc1"):
                (root / "build-tools" / version).mkdir(parents=True)
            tools = AndroidTools.discover(root)
            self.assertEqual(tools.build_tools.name, "35.0.0")
            with self.assertRaises(ValueError):
                AndroidTools.discover(root, "../other")
            with self.assertRaises(FileNotFoundError):
                tools.binary("aapt2")

    def test_build_rejects_invalid_inputs_before_execution(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tools = AndroidTools(root, root)
            with self.assertRaises(ValueError):
                build_apk(root, root / "dest", tools, module=":../app")
            with self.assertRaises(ValueError):
                build_apk(root, root / "dest", tools)
            with self.assertRaisesRegex(ValueError, "variable names"):
                build_apk(root, root / "dest", tools, pass_env=["PASSWORD=value"])
            (root / "settings.gradle").touch()
            with self.assertRaises(ValueError):
                build_apk(root, root / "new" / "dest", tools)
            self.assertFalse((root / "new").exists())

    def test_manifest_and_abi_requirements_precede_signature_check(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            apk = root / "sample.apk"
            tools = AndroidTools(root, root)
            with ZipFile(apk, "w") as output:
                output.writestr("unrelated.txt", "bad fixture")
            with self.assertRaisesRegex(ValueError, "AndroidManifest"):
                verify_apk(apk, tools)
            with ZipFile(apk, "w") as output:
                output.writestr("AndroidManifest.xml", "invalid test manifest")
                output.writestr("lib/x86_64/fixture.so", b"shape only")
            with self.assertRaisesRegex(ValueError, "native ABI"):
                verify_apk(apk, tools, required_abi="arm64-v8a")
            with self.assertRaisesRegex(ValueError, "ELF architecture"):
                verify_apk(apk, tools, required_abi="x86_64")


    def test_abi_requires_a_shared_object_header(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            apk = root / "sample.apk"
            header = bytearray(64)
            header[:7] = b"\x7fELF\x02\x01\x01"
            header[16:20] = b"\x02\x00\xb7\x00"  # ELF64 AArch64 executable, not a shared object.
            with ZipFile(apk, "w") as output:
                output.writestr("AndroidManifest.xml", "test manifest")
                output.writestr("lib/arm64-v8a/fixture.so", header)
            with self.assertRaisesRegex(ValueError, "not an ELF shared object"):
                verify_apk(apk, AndroidTools(root, root), required_abi="arm64-v8a")


@unittest.skipUnless(os.environ.get("VORTEX_TEST_ANDROID_SDK"), "Android SDK fixture test is opt-in")
class AndroidSdkIntegrationTests(unittest.TestCase):
    def test_signed_sdk_fixture_and_reverification(self):
        tools = AndroidTools.discover(Path(os.environ["VORTEX_TEST_ANDROID_SDK"]), "35.0.0")
        with TemporaryDirectory() as directory:
            out = Path(directory) / "out"
            result = build_fixture(out, tools)
            [apk] = result["apks"]
            file = Path(apk["path"])
            self.assertEqual(apk["package"], "org.vortex.fixture")
            self.assertEqual(apk["abis"], [])
            self.assertIn("v2", apk["schemes"])
            self.assertEqual(apk["sha256"], hashlib.sha256(file.read_bytes()).hexdigest())
            self.assertTrue(verify_apk(file, tools)["verified"])
            self.assertEqual(result, json.loads((out / "report.json").read_text()))
            self.assertEqual(sorted(p.name for p in out.iterdir()),
                             ["report.json", "vortex-fixture.apk"])
            with self.assertRaises(FileExistsError):
                build_fixture(out, tools)


def _gradle_project(root):
    """Create a declarative fixture with no application code or dependencies of its own."""
    main = root / "app" / "src" / "main"
    main.mkdir(parents=True)
    (root / "settings.gradle").write_text(
        "pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }\n"
        "dependencyResolutionManagement { repositories { google(); mavenCentral() } }\n"
        "rootProject.name = 'VorteXFixture'\ninclude ':app'\n",
        encoding="utf-8",
    )
    (root / "app" / "build.gradle").write_text(
        "plugins { id 'com.android.application' version '8.7.3' }\n"
        "android { namespace 'org.vortex.gradlefixture'; compileSdk 35; buildToolsVersion '35.0.0'\n"
        "defaultConfig { applicationId 'org.vortex.gradlefixture'; minSdk 23; targetSdk 35; "
        "versionCode 1; versionName '1.0' } }\n",
        encoding="utf-8",
    )
    (main / "AndroidManifest.xml").write_text(
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">'
        '<application android:label="VorteX Gradle Fixture" android:hasCode="false" />'
        '</manifest>\n',
        encoding="utf-8",
    )
    return root


@unittest.skipUnless(os.environ.get("VORTEX_TEST_GRADLE") == "1",
                     "Gradle integration requires an available Android SDK and Gradle")
class GradleIntegrationTests(unittest.TestCase):
    def test_build_in_isolation_and_reverify(self):
        tools = AndroidTools.discover()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project = _gradle_project(root / "project")
            result = build_apk(project, root / "out", tools)
            self.assertEqual(result["mode"], "gradle-debug")
            [apk] = result["apks"]
            self.assertTrue(apk["verified"])
            self.assertEqual(apk["package"], "org.vortex.gradlefixture")
            self.assertFalse((project / "app" / "build").exists())
