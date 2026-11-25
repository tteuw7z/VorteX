# VorteX

A public Python framework for capability-aware orchestration, automation, research, software engineering and multimedia workflows.

**Version 0.1.0 — foundation, not full feature parity.** Python 3.15.2 or newer. Apache-2.0.

## Quick start

```sh
python -m pip install .
vortex plan "compile APK Android"
vortex inventory project.zip
python -m unittest discover -s tests -v
```

The planner selects up to three relevant skills and a limited set of specialist roles using deterministic keyword matching. Roles are suggestions, not autonomous agents. Adapters must be explicitly registered and approved before execution. ZIP inventory is read-only; no archive content is executed.

## Status

Implemented: planning, role selection, adapter contract, CLI, ZIP inventory, tests and CI configuration.

Planned: APK build, transcription, media rendering, evidence-based research, context optimization and host integration. See [roadmap](docs/ROADMAP.md). CI results must be verified before claiming compatibility.

No private conversations, source archives, credentials or third-party agent catalogs are included in this independent public implementation.
