# VorteX

A public Python framework for capability-aware orchestration, automation, research, software engineering and multimedia workflows.

Version 0.1.0. **Phase 3 local tool engines.** Python 3.15.2 or newer. Apache-2.0.

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

## Technical commands

Install FFmpeg and FFprobe for media. Transcription uses a separately installed `whisper-cli` and a local model supplied by the caller. No model is downloaded by VorteX. Android commands use an SDK selected with `--sdk-root` or `ANDROID_HOME`. A Gradle build requires a trusted and self-contained project, an installed Gradle or wrapper, and Java. The compiler builds in a temporary copy. Release signing comes from the project configuration. Use `--pass-env NAME` for each configured signing variable the trusted build needs.

```sh
vortex archive extract footage.zip extracted
vortex archive repack footage.zip revised.zip --replace "clips/a.mp4" replacement.mp4
vortex media batch footage.zip inspection --interval 2
vortex media transcribe interview.mp4 transcript --model /models/ggml-tiny.bin
vortex media edit interview.mp4 output.mp4 --cut 1 8 --captions transcript/transcript.json --full-hd --fade 0.15
vortex media qa output.mp4 --fps 60
vortex apk fixture sample-build
vortex apk build ./authorized-android-project ./android-debug --variant debug
vortex apk verify ./android-debug/app-debug.apk
```

Add `--ocr-language eng` to `media frames` or `media batch` to read visible
text from sampled frames. Install Tesseract and the selected language data in
the host environment. Each sample keeps its timestamp and recognized text.
For local speech recognition, give a known language with `--language pt` or
`--language fr` when automatic detection is unreliable.

ZIP mutations require a new destination with an existing parent. They enforce path, type, count, size and integrity checks. `media batch` reports each candidate by path and emits timecoded JPEGs, with optional ASR via `--model`. Candidates are found by video extensions and confirmed with FFprobe. Visual interpretation and transcript review remain separate from sampling and inference. Transcript outputs include TXT, JSON, SRT and progressive ASS. Grapheme timing is estimated from recognized word or segment intervals.

Android verification reports package and version, signature schemes, certificate digest, APK SHA-256 and native ABI names. Check a required native architecture with `--abi arm64-v8a`. A resource-only APK can have an empty ABI list.

```sh
vortex design audit tokens.json
vortex design preview tokens.json tokens.html
vortex research synthesize claims.json --source-root ./sources
vortex engineering inspect ./candidate
vortex engineering rebuild contract.json ./candidate --source-root ./evidence
```

Design checks the contrast pairs declared by the caller and produces a standalone HTML token sheet. Research locates exact excerpts in local sources and retains line numbers and digests. Engineering inventories Python dependencies and compiles source to check syntax without executing project code. Rebuild checks the independently authored candidate against source-backed capabilities and expected files and symbols. `READY_FOR_RUNTIME_TEST` identifies work that still needs behavioral verification. See the [method fixtures](tests/test_methods.py) for complete JSON examples.

## Local automation

Write a versioned JSON file using the supported command arguments. A dependency must succeed before its downstream step runs. Files written by a stage can be named explicitly in downstream arguments.

```json
{
  "version": 1,
  "steps": [
    {"id": "unpack", "argv": ["archive", "extract", "footage.zip", "extracted"]},
    {"id": "list", "argv": ["archive", "videos", "extracted"], "needs": ["unpack"]}
  ]
}
```

```sh
vortex automation plan flow.json
vortex automation run flow.json --approve unpack --approve list
```

The runner uses the same command parsers and the workflow approval API. It accepts a fixed set of local operations and reports stage status, results and evidence digests. Arbitrary shell commands, Gradle builds and external publishing are outside the manifest runner.

## Assistant tool hosts

Use `vortex.assistant.planner_tool("openai")` in the Responses tool list or
`planner_tool("anthropic")` in the Messages tool list. Pass one decoded tool-call
dictionary to `answer_planner_call(provider, call)`. For Responses, send its
return value as a function output item. For Messages, include it as a tool result
block in the next user message. The host owns authentication and transport.
The bridge exposes only local planning. See [contract tests](tests/test_assistant.py).

## Project status

[Parity matrix](PARITY.md) · [Test report](TEST_REPORT.md) · [Next phase](HANDOFF.md)
