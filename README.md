# VorteX

A public Python framework for capability-aware orchestration, automation, research, software engineering and multimedia workflows.

Version 0.1.0. **Phase 2 structural engines.** Python 3.15.2 or newer. Apache-2.0.

## Quick start

```sh
python -m pip install .
vortex plan "compile APK Android"
vortex knowledge "compile APK Android" --agent-limit 2
vortex inventory project.zip
python -m unittest discover -s tests -v
```

Plans suggest skills and roles. `knowledge` returns the selected role profiles and, when configured, learning records for the selected capabilities.

## Configuration, context and learning

Settings are read only from the TOML file passed as `--config` before the subcommand. Omitted settings use the defaults. Relative database paths are resolved against the TOML file.

```toml
agent_limit = 2
skills = ["android", "engineering", "media"]
context_threshold = 4096
learning_db = "../vortex-learning.sqlite"
```

```sh
vortex --config vortex.toml learn add media "Review cuts" "synthetic clip" "Checked transitions"
vortex --config vortex.toml learn list --capability media
vortex --config vortex.toml knowledge video
vortex --config vortex.toml learn remove 1
vortex --config vortex.toml context checkpoint.json
```

For `context`, supply a JSON object with `checkpoint` and `observations` objects. Put decisions and evidence in the checkpoint. Designate reducible logs in observations. The CLI returns a reduced view and a rough byte-based token estimate. The Python API `ContextEngine.compact(...).restore()` restores the original objects from that in-memory view. Keep the original file to reproduce the CLI view.

Learning is explicit and local. Evidence records store user-supplied sources and observations. Use a database path outside the repository when storing private material.

## Execute a workflow from Python

```python
from vortex.core import Engine, Stage, Status, Workflow

engine = Engine()
engine.register("engineering", lambda text: {
    "status": Status.SUCCESS,
    "evidence": f"Counted {len(text)} characters in the input",
    "artifacts": {"length": len(text)},
})
flow = Workflow([Stage("measure", "engineering", "VorteX")])
results = engine.run_workflow(flow, approvals={"measure"})
print(results["measure"].artifacts)
```

Register the callbacks your host authorizes. Stages declare dependencies by ID. A callback registered with `with_context=True` receives `(task, dependency_artifacts)`. Each stage requires approval by its ID or its explicit approval label. Success requires evidence and JSON artifacts. Declared alternatives may replace missing adapters. Set `retry_safe=True` only for a stage where running another adapter after a failed attempt cannot duplicate side effects.

## Project status

[Parity matrix](PARITY.md) · [Test report](TEST_REPORT.md) · [Next phase](HANDOFF.md)
