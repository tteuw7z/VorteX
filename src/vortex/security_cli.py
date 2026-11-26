"""Explicit delivery gate; key belongs to a separately trusted verifier."""
import json
import os
from pathlib import Path

from .assistant import _unique_object
from .security import audit, publish, _REQUIRED


def add_commands(subparsers):
    group = subparsers.add_parser("security", help="Inspect or gate delivery of generated artifacts")
    commands = group.add_subparsers(dest="security_operation", required=True)
    inspect = commands.add_parser("audit", help="Static inspection; cannot authorize delivery alone")
    release = commands.add_parser("publish", help="Publish an independently attested snapshot")
    for command in (inspect, release):
        command.add_argument("candidate", type=Path)
        command.add_argument("--kind", choices=tuple(_REQUIRED), required=True)
    release.add_argument("output", type=Path)
    release.add_argument("--attestation", type=Path, required=True)

    def verify(args):
        if not args.attestation.is_file():
            raise ValueError("Attestation must be a regular file")
        with args.attestation.open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError("Attestation exceeds size limit")
        document = json.loads(raw, object_pairs_hook=_unique_object)
        secret = os.environ.get("VORTEX_DELIVERY_KEY_HEX", "")
        try:
            key = bytes.fromhex(secret)
        except ValueError:
            key = None
        return publish(args.candidate, args.output, args.kind, attestation=document, key=key)

    inspect.set_defaults(technical_handler=lambda args: audit(args.candidate, args.kind))
    release.set_defaults(technical_handler=verify)
