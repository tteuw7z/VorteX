# Security-first delivery policy

**Default deny.** A generated artifact is a candidate, not an approved delivery. Functionality, build success, a signed APK, syntax checks, and absence of scanner findings are insufficient on their own. Keep candidate files private. Never distribute, deploy, or install a candidate as ready until the independent security gate accepts it.

## Mandatory independent evidence

Every artifact requires threat modeling, secret scanning, dependency and provenance review, privacy review, functional tests, adversarial security tests, and manual review. The type-specific requirements are returned by `vortex security audit`: web access control, web security and deployment configuration; application access control, storage and build integrity; script input validation and least privilege; skill prompt injection, permissions and tool provenance; or format-specific review for other artifacts. Test applicable authorization boundaries, injection, credential handling, data minimization, encryption, safe logging, deletion, dependency integrity, deployment defaults and failure recovery. A check may not be marked PASS merely because an assistant says it passed.

## Gate protocol

Use a dedicated staging directory without Git metadata or symlinks. Audit reports include an artifact digest derived from sorted relative paths, lengths and SHA-256 hashes of captured bytes. Static findings are blockers, not proof of exploitation; remediate or redesign. The scanner has limited language coverage and cannot detect every vulnerability. Unparsed/binary formats must be independently reviewed with appropriate tooling. Scan archives and APK internals using separate tools; this scanner does not unpack them. Bounds: 8 MiB per file, 32 MiB total, 1000 files. Unsupported or oversized artifacts fail closed; larger artifacts need a separately designed streaming gate.

A separately trusted review service (not the code generator) must verify the actual artifact and keep evidence records. It authenticates a JSON object with exactly two fields, payload and signature. Payload contains policy_version (1), kind, artifact_sha256, reviewer, issued_at and expires_at (UTC Unix seconds, max seven days), and checks (each required check maps to {"status":"PASS","evidence_sha256":"<64 lowercase hex characters>"}). Signature is lowercase HMAC-SHA256 hex over the UTF-8/ASCII JSON of payload with ensure_ascii=true, sort_keys=true, separators=(",",":"), allow_nan=false. The verification key is supplied privately to the trusted publisher as VORTEX_DELIVERY_KEY_HEX; at least 32 bytes. Never put it in generated code, command arguments, a repository, or an untrusted build environment. The trusted publisher must be isolated from the code generator. HMAC is shared-secret authentication, not public-key nonrepudiation. Evidence hashes identify external records; the gate does not independently execute the checks or verify their contents.

`vortex security publish CANDIDATE OUTPUT --kind TYPE --attestation REVIEW.json` refuses invalid, expired or changed artifacts; writes only captured bytes in a fresh directory, never overwriting an existing delivery. Use a trusted staging/output filesystem without concurrent untrusted writers. POSIX files are private by default; Windows ACLs are host-managed. The gate cannot protect against a compromised publisher, forged reviewer conclusions, malicious local administrator, or undiscovered vulnerability. It cannot automatically intercept arbitrary host actions or chat file delivery. Host integrations must call it and prohibit alternate release paths. No external verifier is deployed by this checkpoint.

## Internal controls

Gradle runs executable project logic. A private copy is not a sandbox. Explicit trust is now required; use an isolated runner with no unrelated credentials, restricted network and reviewed wrapper/plugins. Do not infer safety from signature verification. Learning storage is opt-in and private on POSIX; SQLite secure_delete reduces recoverable deleted records but is not encryption or guaranteed erasure from backups or journals. Workflow approval labels must be distinct. Untrusted manifests are bounded and duplicate JSON keys are rejected.

## Release rule

If a required check is missing, a security issue is unresolved, evidence is unavailable, or review scope is uncertain: BLOCKED. Report findings and missing checks without exposing sensitive data. Never claim zero vulnerabilities or guaranteed security. A clean static audit is not certification.
