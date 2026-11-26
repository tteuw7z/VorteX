"""Compile trusted Android projects and verify APKs with the installed SDK."""
from collections.abc import Iterable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from .evidence import file_sha256


_ELF_BY_ABI = {
    "armeabi": (1, 40), "armeabi-v7a": (1, 40), "arm64-v8a": (2, 183),
    "x86": (1, 3), "x86_64": (2, 62), "riscv64": (2, 243),
}

@dataclass(frozen=True, slots=True)
class AndroidTools:
    sdk: Path
    build_tools: Path

    @classmethod
    def discover(cls, sdk_root: Path | None = None, revision: str | None = None):
        configured = sdk_root or os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        if not configured:
            raise FileNotFoundError("Set ANDROID_HOME or pass --sdk-root to use the Android SDK")
        sdk = Path(configured).expanduser().resolve(strict=True)
        if revision is not None and not re.fullmatch(r"\d+\.\d+\.\d+", revision):
            raise ValueError("Build Tools revision must be in major.minor.patch form")
        base = sdk / "build-tools"
        if revision is None:
            versions = [d.name for d in base.glob("*")
                        if d.is_dir() and re.fullmatch(r"\d+\.\d+\.\d+", d.name)]
            if not versions:
                raise FileNotFoundError("No stable Android SDK Build Tools are installed")
            revision = max(versions, key=lambda name: tuple(map(int, name.split("."))))
        chosen = base / revision
        if not chosen.is_dir():
            raise FileNotFoundError(f"Android SDK Build Tools {revision} are absent")
        return cls(sdk, chosen)

    def binary(self, name: str) -> str:
        if os.name == "nt" and name == "apksigner":
            raise ValueError("The APK compiler currently requires a POSIX Android SDK")
        filename = f"{name}.exe" if os.name == "nt" else name
        path = self.build_tools / filename
        if not path.is_file() or not os.access(path, os.X_OK):
            raise FileNotFoundError(f"{name} is absent or not executable in the selected Build Tools")
        return str(path)


def _run(program, args, *, step, cwd=None, env=None, timeout=120):
    try:
        result = subprocess.run([program, *map(str, args)], cwd=cwd, env=env,
                                capture_output=True, text=True, errors="replace", check=False,
                                stdin=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"{step} exceeded its time limit") from exc
    if result.returncode:
        raise ValueError(f"{step} failed (exit {result.returncode})")
    return result.stdout


def verify_apk(file: Path, tools: AndroidTools, *, required_abi: str | None = None) -> dict:
    """Use Android tools to confirm manifest/package and signature; report native ABIs."""
    file = file.resolve(strict=True)
    if not file.is_file():
        raise ValueError("APK must be a regular local file")
    with ZipFile(file) as archive:
        members = archive.namelist()
        if members.count("AndroidManifest.xml") != 1:
            raise ValueError("Expected one AndroidManifest.xml")
        native = [(match[1], name) for name in members
                  if (match := re.fullmatch(r"lib/([A-Za-z0-9_-]+)/[^/]+\.so", name))]
        if len(native) != len(set(native)):
            raise ValueError("APK has duplicate native library paths")
        abis = sorted({abi for abi, _ in native})
        if required_abi is not None and required_abi not in abis:
            raise ValueError(f"APK lacks the requested native ABI {required_abi}")
        if required_abi is not None and required_abi not in _ELF_BY_ABI:
            raise ValueError(f"No ELF validation is available for ABI {required_abi}")
        for abi, name in native:
            if expected := _ELF_BY_ABI.get(abi):
                header_size = 52 if expected[0] == 1 else 64
                with archive.open(name) as library:
                    header = library.read(header_size)
                if (len(header) != header_size
                        or header[:4] != b"\x7fELF" or header[5:7] != b"\x01\x01"
                        or (header[4], int.from_bytes(header[18:20], "little")) != expected):
                    raise ValueError(f"Native library ELF architecture does not match {abi}: {name}")
                if int.from_bytes(header[16:18], "little") != 3:
                    raise ValueError(f"Native library is not an ELF shared object: {name}")

    badging = _run(tools.binary("aapt2"), ["dump", "badging", file], step="Android manifest inspection")
    package = re.search(r"^package: name='([^']+)' versionCode='([^']*)' versionName='([^']*)'",
                        badging, re.M)
    if not package:
        raise ValueError("Android manifest package metadata is unreadable")

    signature = _run(tools.binary("apksigner"), ["verify", "--verbose", "--print-certs", file],
                     step="APK signature verification")
    certificates = re.findall(r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})$",
                              signature, re.M | re.I)
    if not certificates:
        raise ValueError("APK verification returned no signer certificate")
    schemes = re.findall(r"^Verified using (v\d+(?:\.\d+)?) scheme.*: true$", signature, re.M)
    return {
        "path": str(file), "bytes": file.stat().st_size, "sha256": file_sha256(file),
        "package": package[1], "version_code": package[2], "version_name": package[3],
        "abis": abis, "verified": True, "schemes": schemes, "certificates_sha256": certificates,
        "build_tools": tools.build_tools.name,
    }


def _publish(artifacts, dest: Path, tools: AndroidTools, *, mode: str, required_abi=None) -> dict:
    # Verify first, then exclusively create the destination and publish the full report.
    reports = []
    for file in artifacts:
        row = verify_apk(file, tools, required_abi=required_abi)
        row["path"] = str(dest / file.name)
        reports.append(row)
    report = {"mode": mode, "apks": reports, "report": str(dest / "report.json")}
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.mkdir()
    created = []
    try:
        for file, row in zip(artifacts, reports, strict=True):
            target = Path(row["path"])
            with file.open("rb") as source, target.open("xb") as output:
                created.append(target)
                shutil.copyfileobj(source, output)
        manifest = Path(report["report"])
        with manifest.open("x", encoding="utf-8") as output:
            created.append(manifest)
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write("\n")
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        try:
            dest.rmdir()
        except OSError:
            pass
        raise
    return report


def _destination(path: Path) -> Path:
    target = path.absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"Output already exists: {target}")
    return target.parent.resolve() / target.name


def _ignore_project(_directory, names):
    excluded = {".git", ".gradle", ".kotlin", ".idea"}
    settings = {"settings.gradle", "settings.gradle.kts"}
    if settings.intersection(names):
        excluded.add("local.properties")
    if (settings | {"build.gradle", "build.gradle.kts"}).intersection(names):
        excluded.add("build")
    return excluded.intersection(names)


def build_apk(project: Path, destination: Path, tools: AndroidTools, *, module="app",
              variant="debug", required_abi=None, lint=False, offline=False, timeout=900,
              pass_env: Iterable[str] = ()) -> dict:
    """Build a trusted, self-contained Gradle checkout in a private working copy."""
    if os.name == "nt":
        raise ValueError("Gradle builds currently require a POSIX host")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*(?::[A-Za-z][A-Za-z0-9_-]*)*", module):
        raise ValueError("Invalid Gradle module")
    if variant not in {"debug", "release"}:
        raise ValueError("Variant must be debug or release")
    if type(timeout) is not int or timeout <= 0:
        raise ValueError("Build timeout must be a positive integer")
    forwarded = tuple(pass_env)
    for name in forwarded:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError("Forwarded environment arguments must be variable names")
        if name not in os.environ:
            raise ValueError(f"Requested environment variable is unset: {name}")
    project = project.resolve(strict=True)
    if not any((project / name).is_file() for name in ("settings.gradle", "settings.gradle.kts")):
        raise ValueError("Expected an Android Gradle project with settings.gradle or settings.gradle.kts")
    target = _destination(destination)
    if target.is_relative_to(project):
        raise ValueError("Choose an output directory outside the source project")
    # Fail early when the output could not be verified.
    tools.binary("aapt2")
    tools.binary("apksigner")

    with TemporaryDirectory(prefix="vortex-gradle-") as scratch:
        source = Path(scratch) / "project"
        shutil.copytree(project, source, ignore=_ignore_project, symlinks=True)
        if any(path.is_symlink() for path in source.rglob("*")):
            raise ValueError("The copied Gradle project must be self-contained (no symlinks)")
        wrapper = source / "gradlew"
        if wrapper.is_file():
            gradle = shutil.which("sh")
            prefix = [str(wrapper)]
        else:
            gradle = shutil.which("gradle")
            prefix = []
        if not gradle:
            raise FileNotFoundError("No Gradle executable or usable Gradle wrapper is available")

        env_keys = ("PATH", "HOME", "JAVA_HOME", "GRADLE_USER_HOME", "TMPDIR", "LANG", "LC_ALL")
        environ = {key: os.environ[key] for key in (*env_keys, *forwarded) if key in os.environ}
        environ.update(ANDROID_HOME=str(tools.sdk), ANDROID_SDK_ROOT=str(tools.sdk))
        capitalized = variant.capitalize()
        tasks = [f":{module}:assemble{capitalized}"]
        if lint:
            tasks.append(f":{module}:lint{capitalized}")
        flags = ["--no-daemon", "--console=plain", "--no-build-cache"]
        if offline:
            flags.append("--offline")
        _run(gradle, [*prefix, *flags, *tasks], cwd=source, env=environ,
             timeout=timeout, step="Gradle APK build")

        apk_dir = source.joinpath(*module.split(":"), "build", "outputs", "apk", variant)
        artifacts = sorted(apk_dir.glob("*.apk"))
        if not artifacts or any(not file.is_file() or file.is_symlink()
                                or not file.resolve().is_relative_to(source) for file in artifacts):
            raise ValueError("Gradle produced no regular APK in the module's standard variant directory")
        return _publish(artifacts, target, tools, mode=f"gradle-{variant}", required_abi=required_abi)


def build_fixture(destination: Path, tools: AndroidTools, *, api: int = 35) -> dict:
    """Compile an original resource-only app and sign it with a disposable test key."""
    if type(api) is not int or not 23 <= api <= 100:
        raise ValueError("Fixture API must be between 23 and 100")
    platform = tools.sdk / "platforms" / f"android-{api}" / "android.jar"
    if not platform.is_file():
        raise FileNotFoundError(f"Android SDK platform {api} is not installed")
    keytool = shutil.which("keytool")
    if keytool is None:
        raise FileNotFoundError("Java keytool is required to sign the test fixture")
    aapt2, aligner, signer = (tools.binary(name) for name in ("aapt2", "zipalign", "apksigner"))
    target = _destination(destination)

    with TemporaryDirectory(prefix="vortex-apk-fixture-") as scratch:
        root = Path(scratch)
        manifest = root / "AndroidManifest.xml"
        manifest.write_text(
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
            'package="org.vortex.fixture" android:versionCode="1" android:versionName="1.0">'
            f'<uses-sdk android:minSdkVersion="23" android:targetSdkVersion="{api}" />'
            '<application android:label="VorteX APK Fixture" android:hasCode="false" />'
            '</manifest>\n',
            encoding="utf-8",
        )
        unsigned, aligned, signed = (root / name for name in
                                     ("unsigned.apk", "aligned.apk", "vortex-fixture.apk"))
        _run(aapt2, ["link", "-I", platform, "--manifest", manifest, "-o", unsigned],
             step="AAPT2 package link")
        _run(aligner, ["4", unsigned, aligned], step="APK alignment")
        key = root / "fixture.p12"
        pass_var = "VORTEX_EPHEMERAL_APK_PASS"
        signing_env = dict(os.environ)
        signing_env[pass_var] = secrets.token_urlsafe(32)
        _run(keytool, ["-genkeypair", "-noprompt", "-keystore", key, "-storetype", "PKCS12",
                       "-alias", "vortex-fixture", "-keyalg", "RSA", "-keysize", 2048,
                       "-validity", 90, "-dname", "CN=VorteX Test Fixture",
                       "-storepass:env", pass_var], env=signing_env, step="Fixture key generation")
        _run(signer, ["sign", "--ks", key, "--ks-key-alias", "vortex-fixture",
                      "--ks-pass", f"env:{pass_var}", "--key-pass", f"env:{pass_var}",
                      "--out", signed, aligned], env=signing_env, step="Test APK signing")
        return _publish([signed], target, tools, mode="sdk-fixture")
