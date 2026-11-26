"""Commands for the Android SDK adapter."""
from pathlib import Path

from .android import AndroidTools, build_apk, build_fixture, verify_apk


def _execute(args):
    tools = AndroidTools.discover(args.sdk_root, args.build_tools)
    if args.operation == "verify":
        return verify_apk(args.file, tools, required_abi=args.abi)
    if args.operation == "fixture":
        return build_fixture(args.destination, tools, api=args.api)
    return build_apk(args.project, args.destination, tools, module=args.module,
                     variant=args.variant, required_abi=args.abi, offline=args.offline,
                     lint=args.lint, timeout=args.timeout, pass_env=args.pass_env)


def add_commands(subparsers):
    apk = subparsers.add_parser("apk", help="Build and verify Android APK files")
    commands = apk.add_subparsers(dest="operation", required=True)

    verify = commands.add_parser("verify", help="Verify an APK signature and inspect native ABIs")
    verify.add_argument("file", type=Path)
    verify.add_argument("--abi")

    fixture = commands.add_parser("fixture", help="Build a signed synthetic APK with the SDK")
    fixture.add_argument("destination", type=Path)
    fixture.add_argument("--api", type=int, default=35)

    build = commands.add_parser("build", help="Build a trusted, self-contained Android Gradle project")
    build.add_argument("project", type=Path)
    build.add_argument("destination", type=Path)
    build.add_argument("--module", default="app")
    build.add_argument("--variant", choices=("debug", "release"), default="debug")
    build.add_argument("--abi")
    build.add_argument("--offline", action="store_true")
    build.add_argument("--lint", action="store_true")
    build.add_argument("--pass-env", action="append", default=[], metavar="NAME",
                       help="Forward a named environment variable to the trusted Gradle build")
    build.add_argument("--timeout", type=int, default=900)

    for command in (verify, fixture, build):
        command.add_argument("--sdk-root", type=Path)
        command.add_argument("--build-tools")
        command.set_defaults(technical_handler=_execute)
