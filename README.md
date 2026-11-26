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
vortex apk build ./authorized-android-project ./android-debug --variant debug --trust-project
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
vortex automation run flow.json --manifest-sha256 REVIEWED_SHA256 --approve unpack --approve list
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

## Remote planner (Phase 6 candidate)

The read-only planning tool can be used through OpenAI Responses or Anthropic Messages. By default no external request is made. For a live run, set the appropriate API key in the process environment using your own authorized account, choose an enabled model, and explicitly approve sending the task and incurring API costs:

```sh
vortex host openai MODEL_ID "Plan an Android build" --approve-network
vortex host anthropic MODEL_ID "Plan a ZIP analysis" --approve-network
```

Use `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`; do not commit keys or place them in arguments. The HTTPS transport uses fixed endpoints, no redirects or automatic retries, a bounded number of requests and output tokens, and per-response usage reported by the service. It sends task text and planning results to the chosen provider. Do not send private information without authorization. The OpenAI client disables response storage and replays tool-loop state; provider retention policies still apply. The model can invoke only the local planning tool, not technical execution. Contract tests use injected responses and mocked HTTPS; live credentials, model compatibility and billing telemetry remain unverified.

Protocol references: https://developers.openai.com/api/docs/guides/function-calling and https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls.

### Frame-aligned visual effects

Repeat `--effect KIND START END STRENGTH` with `vortex media edit` to apply flash, small rotational shake or blur in output seconds (not source-cut time). Strength is normalized to (0,1]; durations are 3 frames to 2 seconds. Flash and shake use a bounded pulse; flash starts must be at least one third of a second apart. `--contrast 1.2` applies an explicit contrast multiplier. These controls do not yet detect music beats or perform motion-aware transitions automatically.

Use `vortex media bass INPUT --fps 60` to inspect low-frequency onsets, or add `--bass-flash 0.6` to `vortex media edit` to schedule a bounded flash on detected transients through ordered cuts. This is a local energy-based heuristic, not verified musical beat/BPM recognition. Audio and input duration limits apply; use manual timing for critical edits.

## Security-first delivery policy (Phase 6.8)

Generated websites, scripts, applications, skills and other artifacts are untrusted candidates until independently reviewed. `vortex security audit CANDIDATE --kind website` performs a bounded static scan and deliberately returns BLOCKED even with no findings. `vortex security publish CANDIDATE OUTPUT --kind website --attestation REVIEW.json --evidence-dir REVIEW_LOGS` publishes only the exact captured bytes if there are no static findings and all mandatory checks are attested. The separately trusted verifier must provide a 32-byte-or-longer HMAC key via `VORTEX_DELIVERY_KEY_HEX` and authenticate the exact digest, artifact type, policy version, reviewer, expiry and evidence hashes. Every required check must have its actual matching log in a separate trusted directory; the logs are never copied to delivery. Never expose this key to generated code or the assistant generating the artifact. There is intentionally no self-signing CLI. See `docs/SECURITY_POLICY.md` for the trust model and limitations. The gate must be used by host delivery integrations; it cannot intercept external chat attachments or arbitrary tools. Gradle builds now require explicit `--trust-project` (not a sandbox). Existing POSIX learning databases with broad permissions must be reviewed and restricted before use.

Automation approval now binds to the SHA-256 printed by `vortex automation plan`; review the displayed argv and pass that exact value as `--manifest-sha256` when running. The digest authenticates neither the operator nor input file contents; use a trusted host and separately review inputs. Media and SDK subprocesses inherit only selected operational environment variables, not API or verifier credentials. This is not a filesystem or network sandbox.

The history check `python scripts/audit_git_history.py` requires a non-shallow clone and scans reachable local Git objects for known credential formats. An incomplete scan or finding blocks CI; reports contain object IDs and rule names, never matched text. Remote planning also blocks recognized credentials in input and response; do not send private data even if the scanner is silent.

## Programming discipline (6.13)

Planning and knowledge commands and the read-only host planning tool automatically prepare economical routing, compare selected profile context against the full catalog, and disclose deferred matching specialists. Estimates are based on compact JSON bytes, not billed tokens or a measured end-to-end speedup. Mandatory code, functional and security review roles do not count against the specialist cap. The planner does not execute stages. Use `vortex security review CANDIDATE` for a byte-bound inventory; policy v3 requires a signed `code_review.log` with every file's exact digest and declared full-byte review. See the security policy. Clear names, purposeful comments, simple modular functions, test traces and safe data handling are required review practices; no claim of zero errors.

The initial specialist cap no longer silently excludes matching enabled roles in the selected execution context: preflight expands all keyword-matched roles automatically and discloses explicitly disabled matches. See `AGENTS.md` for the coding and delivery discipline. Provider usage totals are separated from estimates and injected fixtures; actual savings require a comparable live baseline.

`vortex.development.coordinate_development` is an opt-in Python host integration for ordered, authorized execution. It runs economical preflight before building a new candidate, requires byte-bound code review, blocks static findings before tests, and requires functional then security test receipts against unchanged bytes. It never authorizes release or signs evidence. Trusted host adapters and actual isolation remain required; no arbitrary shell runner is provided.

## Chat activation and menu (Phase 6.16 candidate)

`vortex chat --locale pt Vortex sim 2` previews a complete session as JSON events. Use a fresh `vortex.conversation.Conversation` per conversation; call `handle` only on user messages. Explicit Vortex or 🇮🇪 activation emits the official greeting once; menu categories support textual navigation and structured rendering by an interactive host. No unsolicited voice greeting. The local CLI shows planning capabilities, never claims bound execution tools. Trusted Python hosts can supply enabled and actually bound capability IDs; all execution still needs existing authorization and delivery checks. Native rendering, other language localization and installing the [skill instructions](SKILL.md) depend on the host. ChatGPT, Claude and DeepSeek compatibility has not been tested in live sessions. Direct requests after activation run the existing automatic preflight, not arbitrary execution.

### Motion UI (candidate)

Generate a local, offline menu or control gallery with `vortex design motion CANDIDATE --mode menu --locale pt-BR` or `--mode gallery`. Add `--still` for no animation. The candidate is read-only and requires independent review before release. See [Motion UI](docs/MOTION_UI.md).
