# Phase 7 — ChatGPT host integration candidate

## Local gateway

After installing the trusted package at a reviewed commit using its supported
Python version, a host can invoke a fixed local process:
`python -m vortex.host_gateway`. Send one UTF-8 JSON object to stdin, close
stdin, read one JSON object from stdout. Example:

```json
{"schema":1,"operation":"design.audit","arguments":{"document":{"colors":{"fg":"#000","bg":"#fff"},"contrast_pairs":[{"foreground":"fg","background":"bg"}]}}}
```

The gateway executes the existing design audit in Python and returns its
contrast result and deterministic request/result SHA-256 digests. A plan
operation runs the existing planner but explicitly does not execute its task.
The capabilities operation lists only locally bound operations. Fixed dispatch,
duplicate-key rejection, size limits, strict schema, sanitized errors and no
shell, filesystem parameters, provider calls or network access. No response
authorizes delivery. Hashes are reproducibility evidence, not signatures or
independent attestation.

This is a candidate local transport, not an installed ChatGPT binding, MCP
server or public deployment. A trusted host must bind and invoke the process.
Do not transmit private task inputs to GitHub or deploy an unauthenticated
endpoint. Do not execute code from the live catalog.

## Master acceptance checklist

| Area | Next gate |
|---|---|
| Inventory | Reconcile original authorized inventory; preserve current phase-6 work |
| Core | Re-run full CI; verify actual runtime for each adapter |
| Host | Demonstrate a ChatGPT-authorized invocation against a deployed or host-local binding |
| Live | Verify immutable channel and publisher CI; add trusted rollback/cache and compatibility tests |
| Agents | Separate role selection from independent execution; validate isolation and limits |
| Skills | Map every catalog command to real binding, prerequisites, evidence and status |
| Tokens | Paired quality/cost benchmarks using real authorized provider telemetry |
| Learning | Opt-in private store, deletion, retention, validation and cross-session integration |
| Security | Independent review, sandbox, signed releases, license review and delivery gate |
| UI | Validate actual host/mobile behavior; preserve fallback |
| Release | Full integration/regression suite, independent approval and verified install/update |

Starting point: source commit f848c3e2779f2c05aab2c554fd57b67819e33ac9;
live channel 004c6b8abcd2bb102f688a7ec239b852b8b051b3. The preceding
CI passed four test jobs. The new gateway remains a candidate pending CI
and real host invocation. No claim of complete parity, release readiness,
autonomous independent agents or measured ChatGPT token savings.
