# Security-first delivery policy

**Default deny.** A generated artifact is a candidate, not an approved delivery. Functionality, build success, a signed APK, syntax checks, and absence of scanner findings are insufficient on their own. Keep candidate files private. Never distribute, deploy, or install a candidate as ready until the independent security gate accepts it.

## Mandatory independent evidence

Every artifact requires threat modeling, secret scanning, dependency and provenance review, privacy review, functional tests, adversarial security tests, and manual review. The type-specific requirements are returned by `vortex security audit`: web access control, web security and deployment configuration; application access control, storage and build integrity; script input validation and least privilege; skill prompt injection, permissions and tool provenance; or format-specific review for other artifacts. Test applicable authorization boundaries, injection, credential handling, data minimization, encryption, safe logging, deletion, dependency integrity, deployment defaults and failure recovery. A check may not be marked PASS merely because an assistant says it passed.

## Gate protocol

Use a dedicated staging directory without Git metadata or symlinks. Audit reports include an artifact digest derived from sorted relative paths, lengths and SHA-256 hashes of captured bytes. Static findings are blockers, not proof of exploitation; remediate or redesign. The scanner has limited language coverage and cannot detect every vulnerability. Unparsed/binary formats must be independently reviewed with appropriate tooling. Scan archives and APK internals using separate tools; this scanner does not unpack them. Bounds: 8 MiB per file, 32 MiB total, 1000 files. Unsupported or oversized artifacts fail closed; larger artifacts need a separately designed streaming gate.

A separately trusted review service (not the code generator) must verify the actual artifact and keep evidence records. It authenticates a JSON object with exactly two fields, payload and signature. Payload contains policy_version (4), kind, artifact_sha256, reviewer, issued_at and expires_at (UTC Unix seconds, max seven days), and checks (each required check maps to {"status":"PASS","evidence_sha256":"<64 lowercase hex characters>"}). Signature is lowercase HMAC-SHA256 hex over the UTF-8/ASCII JSON of payload with ensure_ascii=true, sort_keys=true, separators=(",",":"), allow_nan=false. The verification key is supplied privately to the trusted publisher as VORTEX_DELIVERY_KEY_HEX; at least 32 bytes. Never put it in generated code, command arguments, a repository, or an untrusted build environment. The trusted publisher must be isolated from the code generator. HMAC is shared-secret authentication, not public-key nonrepudiation. Each evidence record must be available as CHECK_NAME.log in a separate trusted directory, nonempty, at most 2 MiB, and match the signed SHA-256. The gate verifies bytes, not whether the reviewer's conclusions are true.

`vortex security publish CANDIDATE OUTPUT --kind TYPE --attestation REVIEW.json --evidence-dir REVIEW_LOGS` refuses invalid, expired or changed artifacts; verifies actual evidence files and stages the captured bytes privately before atomically renaming the directory into place. A cooperative lock prevents parallel publishers targeting the same destination; no untrusted writers may control the parent. An abrupt process death can leave a private stage or lock requiring trusted cleanup, but not a partially published final directory. The gate never intentionally overwrites an existing delivery. Use a trusted staging/output filesystem without concurrent untrusted writers. POSIX files are private by default; Windows ACLs are host-managed. The gate cannot protect against a compromised publisher, forged reviewer conclusions, malicious local administrator, or undiscovered vulnerability. It cannot automatically intercept arbitrary host actions or chat file delivery. Host integrations must call it and prohibit alternate release paths. No external verifier is deployed by this checkpoint.

## Internal controls

Gradle runs executable project logic. A private copy is not a sandbox. Explicit trust is now required; use an isolated runner with no unrelated credentials, restricted network and reviewed wrapper/plugins. Do not infer safety from signature verification. Learning storage is opt-in and private on POSIX; SQLite secure_delete reduces recoverable deleted records but is not encryption or guaranteed erasure from backups or journals. Workflow approval labels must be distinct. Untrusted manifests are bounded and duplicate JSON keys are rejected.

## Release rule

If a required check is missing, a security issue is unresolved, evidence is unavailable, or review scope is uncertain: BLOCKED. Report findings and missing checks without exposing sensitive data. Never claim zero vulnerabilities or guaranteed security. A clean static audit is not certification.

## Additional internal protections (6.9)

Approval requires the exact manifest SHA-256 returned by planning, alongside unique per-stage labels; a changed manifest is blocked before preparing any command. The plan exposes argv for review. Approval does not bind mutable input-file content or authenticate the operator. Media/SDK subprocesses use a minimal environment, reserved verifier/provider credentials cannot be explicitly forwarded through Gradle. Tools may still read host files or access the network; execute untrusted inputs/builds in externally isolated hosts. Static artifact scanning additionally rejects reserved Windows device paths, normalization collisions, credentials in filenames and script URLs; reports are bounded. These checks are incomplete and do not replace independent review.

Policy version 2 additionally requires actual evidence logs, not just digest strings. Evidence and candidate/delivery trees must be disjoint; no review logs are copied to the released files. Old version 1 attestations are rejected.

### Privacidade de arquivos locais (6.11)

Saídas novas dos adaptadores principais usam permissões 0600 e diretórios 0700 em POSIX. No Windows, configure ACLs privadas no diretório de trabalho e de saída antes de processar dados. Não é criptografia em repouso e não impede acesso por outros processos da mesma conta ou administradores.

### Git and remote communication (6.12)

CI checks Git objects reachable from checked-out refs and HEAD for known credential formats. It does not cover deleted/unreachable refs, external artifacts, obfuscated secrets, or semantic personal data. Checkout disables persisted credentials. Remote planning blocks known credential patterns and the current API key in inputs and provider responses; it is not complete data loss prevention. Do not send sensitive data, and treat model text as untrusted planning, not release authorization.

### Programming review (policy version 3)

Every kind adds the required check `code_review`. Its log is JSON with exactly `artifact_sha256` and `files`; each file row has `path`, `sha256`, `bytes_reviewed` (integer equal to file size), and `status` (`PASS`). All captured files must occur exactly once, including empty files. The independent reviewer must actually inspect the content and verify logic, readability, validation and error paths; a byte count is a signed coverage declaration, not proof of semantic correctness. Earlier attestations are rejected. Functional tests precede final security tests in the recommended workflow; security design starts at requirements. The host still needs to enforce execution, independent review and delivery.

## Policy 4

Integration, regression and performance checks now require separate authenticated evidence logs in addition to functional and security checks. Older attestations do not authorize a policy-4 release. The host must define meaningful acceptance thresholds, run checks in an isolated environment, and verify independent review; receipts are not proof of their own truth.
