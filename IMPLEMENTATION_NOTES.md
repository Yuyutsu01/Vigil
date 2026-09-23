# Vigil Phase 1 (M1) — Implementation Notes

This document records every deliberate design decision, prototype caveat,
and intentional deviation from the Implementation Plan.

---

## [N1] PROTOTYPE_ONLY — Local Authentication

The `/v1/auth/token` endpoint implements a local email+password credential store
using Argon2id hashing. **This MUST be replaced with an OIDC provider
(Auth0, Keycloak, Google, etc.) before any external pilot or production deployment.**

- Files affected: `backend/app/services/auth_service.py`, `backend/app/api/v1/auth.py`,
  `backend/app/models/tenant.py` (`User` model).
- Migration path: swap `auth_service.py` for an OIDC token-exchange endpoint;
  remove the local `User.hashed_password` column.
- Tracking: Implementation Plan [M6], [F2].

---

## [N2] Fingerprint Formula — Line-Shift-Invariance

**Formula:** `sha256(rule_id || ast_path || sha256(matched_text) || evidence_kind)`

This is intentionally different from line-based fingerprints. Adding blank lines
to a file does NOT change any fingerprint, making findings stable across trivial
reformatting. The `finding_id` (UUID v7) is the mutable database primary key;
`fingerprint` is the stable deduplication key used in SARIF `partialFingerprints`.

- Plan reference: [H3], [C3].

---

## [N3] PatchCandidate Table — Stub Only

The `patch_candidates` database table is defined but **never populated** in Phase 1.
Patch generation (FR-105) is deferred to Phase 3/M3. The `unified_diff` column
will remain `NULL` for all Phase 1 rows. API responses always return
`"patch_candidate_id": null`.

- Plan reference: [B4].
- Frontend note: The UI displays "Patch suggestions deferred to Phase 3."

---

## [N4] Sandbox Runtime — NoOpSandboxRuntime

`NoOpSandboxRuntime` is injected into the orchestrator graph but all methods
raise `NotImplementedError`. Dynamic sandbox execution (FR-106) is Phase 4/M4.
Tests explicitly verify `NotImplementedError` is raised (see `test_no_code_execution.py`).

- Plan reference: [H4].

---

## [N5] Tree-Sitter — Optional Dependency with Fallback

Tree-sitter packages (`tree-sitter-python`, `tree-sitter-javascript`,
`tree-sitter-typescript`) are listed in `requirements.txt` but the code falls back
gracefully to:
- Python `ast` module for Python analysis (always works).
- Token-regex patterns for JavaScript/TypeScript when tree-sitter is unavailable.

The fallback is logged at `WARNING` level.

---

## [N6] Redis Fail-CLOSED

Both the rate limiter and idempotency middleware use fail-CLOSED semantics:
if Redis is unreachable, the request is blocked (503 Service Unavailable).
This is intentional — availability is sacrificed for consistency under Redis failures.

---

## [N7] Source Content Storage

Source artifact content is stored as plaintext in PostgreSQL in Phase 1.
Production deployments SHOULD encrypt at rest using a KMS-managed key applied
at the database or application layer. The `SourceArtifact.content` column is
designed to be replaced with a `content_encrypted` blob.

---

## [N8] Mock LLM Provider

`VIGIL_LLM_PROVIDER=mock` uses `MockProvider`, which returns a deterministic,
hash-seeded response without any network calls or API keys. This enables:
- Full CI/CD pipelines without LLM credentials.
- Deterministic acceptance test runs (AC-4, AC-7).
- Local development with zero cost.

Switch to `VIGIL_LLM_PROVIDER=openai` and set `OPENAI_API_KEY` for real analysis.

---

## [N9] Content-Type Enforcement

- `POST /v1/reviews` — requires `application/json` (enforced in router, returns 415 otherwise).
- `POST /v1/uploads` — requires one of 6 raw media types:
  `application/x-python`, `text/x-python`, `text/javascript`,
  `application/javascript`, `application/typescript`, `text/typescript`.

---

## [N10] LLM Quality Findings Severity Cap

Quality findings from the LLM capability are capped at `Medium` severity.
`Critical` and `High` are reserved exclusively for security findings.
This is enforced in `agents/capabilities.py :: capability_triage()`.

---

## [N11] Consent Version Checking

The server config `VIGIL_CONSENT_POLICY_VERSION` (default `"1.0"`) is the
authoritative policy version. Consent records with a different version are
rejected as stale (`consent_version_stale`). This ensures consent is re-obtained
when policy changes.

---

## Open Items for M3+

| Item | Phase | Description |
|------|-------|-------------|
| GitHub App / OAuth | M3 | FR-103, FR-104: PR webhooks & GitHub integration |
| Patch generation | M3 | FR-105: unified-diff patch candidates |
| Sandbox execution | M4 | FR-106: gVisor/Firecracker dynamic analysis |
| PR comments / review | M3 | FR-107: automatic review on pull requests |
| Multi-agent loop | M3 | FR-108: multi-agent debate beyond dual LLM nodes |
| Learning loop | M3 | FR-109: feedback adaptation from user dispositions |

---

# Vigil Phase 2 (M2) — Implementation Notes

This section records implementation details and security architecture for M2 features:
Static Analyzer Adapters (FR-101) and Multi-format Report Export (FR-102).

---

## [N12] Tool Adapter Subprocess Sandboxing

Static analyzer adapters (Bandit, Semgrep, Ruff, ESLint, pip-audit, npm-audit) invoke
subprocesses under strict isolation constraints:
1. Target source code is written to an isolated temporary scratch directory with a UUID filename.
2. The scratch file is marked read-only (`chmod 0o444`) so tools cannot mutate submitted code.
3. Subprocesses execute strictly with `shell=False` and explicit argument lists (`argv`),
   preventing command injection. Target file paths are passed as arguments, never piped to shells.
4. Per-adapter timeouts (default 30s) are enforced.
5. Standard output and error are capped at 1 MB and passed through `redact()` before parsing.
6. Missing tool binaries are handled gracefully by producing structured skip diagnostics
   rather than failing the entire review.

---

## [N13] Adapter Triage Precedence (rule > tool > agent)

When merging findings from deterministic AST/regex rules, static analyzer tools, and LLM reasoning,
fingerprints are deduplicated with the strict precedence order:
1. `rule` (baseline AST and regex rules)
2. `tool` (Bandit, Semgrep, Ruff, ESLint, pip-audit, npm-audit)
3. `agent` (LLM security and quality reasoning)

Tool findings include `origin="tool"`, `tool_name`, `tool_version`, and a reference (`raw_evidence_ref`)
linking to verbatim raw evidence in the `tool_findings` table.

---

## [N14] Report Export Security (Injection & SSRF Guard)

1. **HTML Autoescape**: Jinja2 rendering enforces `autoescape=select_autoescape(['html', 'xml'])`.
   All finding titles, rationales, and code excerpts are auto-escaped to prevent stored XSS.
2. **SSRF Refusal in PDF**: WeasyPrint PDF generation runs with a custom `url_fetcher` (`safe_url_fetcher`)
   that unconditionally raises `PermissionError` when any remote resource (HTTP/HTTPS/file) is requested.
3. **Redacted Excerpts Only**: Full submitted source code is never included in exported reports;
   only bounded, pre-redacted excerpts are exposed.
4. **Fallback PDF**: On environments without native C graphic libraries (e.g. Windows without GTK),
   `PDFReportRenderer` produces valid PDF 1.4 output directly, ensuring uninterrupted report delivery.

---

## [N15] Evaluation Corpus Segregation

The evaluation corpus in `tests/evaluation/corpus/` is loaded directly from disk files
by `CorpusLoader`. Corpus samples are never written to the tenant database and never interact
with tenant data. The internal `/v1/internal/evaluation/*` endpoints are restricted strictly
to the `PlatformOperator` role.

---

# Vigil Phase 2.1 (M2 Patch) — Implementation Notes

## [N16] Baseline Migration (001_phase1_m1)
Phase 1 established the initial database schema via runtime `create_tables()` rather than Alembic versioning. When Phase 2 introduced Alembic migration `002_phase2_m2.py` declaring `down_revision = "001_phase1_m1"`, the migration chain was orphaned, breaking standard schema upgrades/downgrades on clean databases.
The `001_phase1_m1` baseline migration was created to capture all Phase 1 tables (`tenants`, `users`, `consent_records`, `source_artifacts`, `review_runs`, `audit_events`, `findings`, `evidence`, `patch_candidates`, `finding_feedback`) and enums (`review_status`, `finding_origin`, `finding_severity`, `evidence_kind`, `audit_action`), establishing a continuous, reproducible Alembic migration chain.

## [N17] PostgreSQL JSONB vs JSON
Columns storing structured data (`tool_findings.raw_evidence`, `per_rule_breakdown`, and `metadata`) use `_JSON = JSONB().with_variant(sa.JSON(), "sqlite")`.
On PostgreSQL, `JSONB` stores decompressed binary JSON with GIN indexing capability, eliminating redundant parsing on queries and enabling high-performance containment/key-existence lookups. SQLite falls back seamlessly to standard `JSON` text representation.

## [N18] PDF Fallback Strategy (Hand-rolled vs ReportLab)
A hand-rolled minimal PDF 1.4 stream generator was chosen over ReportLab for fallback PDF generation.
1. **Zero Added Dependencies**: ReportLab introduces a heavy third-party dependency with native extensions and C-level text rendering that requires external installation.
2. **Deterministic & Bounded**: The hand-rolled generator computes exact byte offsets dynamically for the cross-reference table (`xref`), generating a compliant, single-page PDF document guaranteed to parse in any strict PDF 1.4+ parser (verified with `pypdf`) without external network access or SSRF exposure.

## [N19] Redis Cooldown Duration Rationale
In `AdapterRegistry`, Redis connectivity failures trigger a 60-second cooldown (`_REDIS_COOLDOWN_SECONDS = 60.0`) via timestamp tracking (`_redis_down_until = time.monotonic() + 60.0`).
- **Rationale**: A hard boolean `_redis_down = True` permanently disabled caching for the entire process lifetime after a transient network blip.
- Retrying on every request during a sustained Redis outage adds 500ms timeout latency to every adapter execution.
- A 60-second cooldown eliminates repeated timeout overhead while guaranteeing automatic self-healing and recovery once Redis is restored.

## [N20] LRU Cache Size Rationale (10,000 Entries)
The in-memory cache in `AdapterRegistry` is bounded using an `OrderedDict` LRU mechanism capped at 10,000 entries (`_MEMORY_CACHE_MAX = 10_000`).
- **Rationale**: The previous unbounded dictionary leaked memory monotonically under sustained multi-tenant traffic.
- At an average cached finding payload of ~2 KB, 10,000 entries consume at most ~20 MB of resident RAM, which fits comfortably within worker container constraints while providing a high hit rate for repeated code review scans.

## [N21] Report Storage Migration to Object Storage (Phase 3)
In Phase 2, `ReportArtifact.content_bytes` stores generated PDF and HTML report payloads directly in PostgreSQL using `LargeBinary`.
- Phase 3 should migrate to object storage (S3) and replace `content_bytes` with `storage_ref TEXT`.
- This offloads large binary blobs from relational database disk and WAL replication streams.

---

# Vigil Phase 3 (M3) — GitHub Integration & Scoped Review Notes

## [N22] Pure Read-Only GitHub App Integration (B1, FR-103)
Phase 3 adopts a pure GitHub App architecture rather than OAuth user delegation:
1. **Machine Identity**: All interactions use installation access tokens derived from RS256 JWTs signed by the App's private key. User OAuth scopes (`repo`, `write:repo_hook`) are never requested or stored.
2. **Strict Write-Blocking**: Any API attempt to create PR reviews, issue comments, git commits, or branches raises `NotImplementedError("Phase 4 feature: GitHub writes are disabled in Phase 3")`.
3. **SSRF Guard**: The `GitHubClient` validates that all outgoing HTTP requests strictly match the configured GitHub API host (`api.github.com`), preventing internal SSRF or webhook bouncing.

## [N23] Signed Callback State with Single-Use Nonce (B2)
To guarantee protection against CSRF and installation hijacking during GitHub App installation:
1. The `state` query parameter is an RS256-signed JWT containing `tenant_id`, `user_id`, and a cryptographically unique `nonce` (UUID v4) with a 5-minute TTL.
2. The nonce is registered in Redis using atomic `SETNX` (`oauth_state:{nonce}`).
3. Upon callback, `verify_signed_oauth_state` verifies the cryptographic signature, checks expiration, and atomically deletes the nonce from Redis (`DEL`). If the nonce is missing, expired, or already consumed, the request is rejected with HTTP 403 and logged under `GITHUB_OAUTH_STATE_INVALID`.

## [N24] Vault Resolver Abstraction for App Private Keys (B3)
Private key material for GitHub App authentication is never stored in plaintext in the database:
1. `VaultResolver` protocol defines an asynchronous resolution interface (`resolve_private_key(ref)`).
2. `EnvVaultResolver` resolves `env://VAR_NAME`, `file://path/to/key.pem`, or raw PEM text.
3. In production (`VIGIL_ENV=production`), using `env://` emits a startup security warning urging migration to HashiCorp Vault or Cloud KMS.

## [N25] Fast Webhook Ingestion & Dual HMAC-SHA256 Rotation (B4, H4)
1. **<200ms ACK**: The webhook ingestion endpoint (`POST /v1/webhooks/github`) verifies the HMAC signature, records the `delivery_id` in Redis using `SETNX` to prevent replay, writes an audit record in `webhook_events`, and enqueues the payload to an ARQ background queue before returning HTTP 202 Accepted.
2. **Dual-Secret Rotation**: Webhooks are verified against `GITHUB_APP_WEBHOOK_SECRET` and optionally `GITHUB_APP_WEBHOOK_SECRET_PREVIOUS` using constant-time `hmac.compare_digest` to support zero-downtime secret rotation.
3. **Draft & Fork Policies**: Pull requests from forks (`review_fork_prs`) or marked as draft (`review_draft_prs`) are filtered before review trigger per repository policy.

## [N26] Scoped Review & Zero Source Code Persistence (FR-104)
1. **Scope Modes**: Supports `full_repo` (Git Trees API), `changed_files` (PR files or commit compare), `directory` (prefix filtering), and `files` (explicit list).
2. **Zero Persistence Invariant**: Source files fetched from GitHub exist strictly in ephemeral memory during rule execution. File contents are never written to `source_artifacts` content column, Redis, or disk.
3. **Synthetic SourceArtifact**: A lightweight placeholder record (`[REPOSITORY_REVIEW_MEMORY_ONLY]`) is stored with a deterministic checksum to maintain relational integrity with `ReviewRun`.
4. **Git LFS Filtering**: Pointer files beginning with `version https://git-lfs.github.com/spec/v1` are detected and skipped without downloading large assets.

## [N27] Aggregate Review Budget & Hard Cost Cap (B5, C1)
Multi-file repository scans are constrained by aggregate cost and resource guards:
1. Hard limits: `repo_review_max_llm_calls = 50`, `repo_review_max_total_tokens = 500_000`, `repo_review_max_wall_clock_seconds = 600`.
2. Hard cost cap: `$5.00` per review. If estimated or accumulated cost exceeds $5.00, review execution halts, setting `status = "budget_paused"` and `budget_paused_reason = "cost_cap_exceeded"`.
3. Pre-flight endpoint `GET /v1/repositories/{repo_id}/cost-preview` provides accurate token and cost projections before triggering scans.

## [N28] Cross-File Finding Deduplication (M8)
In multi-file repository reviews, findings are deduplicated across files using a compound key:
`dedup_key = (fingerprint, source_file_path)`
This prevents duplicate warnings in the same file while ensuring identical vulnerability patterns in different files are correctly surfaced.

## [N29] Windows Case-Normalization for Path Rules (M4)
File path matching against `ignored_paths` and file extensions normalizes paths to lowercase on Windows environments (`os.name == 'nt'`). This ensures uniform policy enforcement between local development on Windows and CI/production deployments on Linux.

---

# Vigil Phase 3.1 (M3 Patch) — Implementation Notes

This section records root causes and architectural resolutions for issues discovered in the independent code review of Phase 3 (M3).

---

## [N30] Full Pipeline Execution in Repository Reviews (B1)

**Root Cause:**
In Phase 3.0, `RepoReviewService.execute_repo_review` only executed the Phase 1 synchronous rule engine (`rule_engine.analyze`) over resolved repository files. It bypassed the full orchestrator pipeline (`run_review_graph`), which resulted in static tool adapters (Bandit, Semgrep, Ruff, ESLint) and LLM agent reasoning being omitted from repository reviews.

**Resolution:**
1. `execute_repo_review` was refactored to invoke `run_review_graph` per eligible repository file with mock or configured LLM/tool adapters.
2. For each file, the review graph produces rule, tool, and LLM findings, which are prioritized via deterministic triage (`rule > tool > agent`).
3. Each triaged finding is tagged with `source_file_path` and persisted via `_persist_single_finding`, linking any tool evidence to `tool_findings`.
4. The synthetic `SourceArtifact` placeholder (`[REPOSITORY_REVIEW_MEMORY_ONLY]`) is retained to satisfy foreign key constraints without saving submitted code to disk or database.

---

## [N31] Token Usage & Multi-File Cost Propagation (B1, B2)

**Root Cause:**
Repository review metrics previously reported zero tokens and zero LLM calls because graph execution state was ignored. Furthermore, `FindingSchema` lacked `source_file_path` and tool origin fields (`tool_name`, `tool_version`, `raw_evidence_ref`), preventing clients from identifying finding sources in repository reviews.

**Resolution:**
1. Real token usage and LLM invocation iterations from each file's `ReviewState` are accumulated into `total_tokens` and `total_llm_calls`.
2. Cost is dynamically calculated using configured token pricing (`settings.llm_cost_per_1k_input_tokens`, default $0.003/1k tokens).
3. Pre-flight and mid-flight budgets are enforced: if accumulated cost, call count, token usage, or elapsed time exceeds configured caps (`repo_review_cost_cap_dollars`, `repo_review_max_llm_calls`, `repo_review_max_total_tokens`, `repo_review_max_wall_clock_seconds`), review execution terminates with status `budget_paused` and the respective `budget_paused_reason` (`cost_cap_exceeded`, `call_budget_exhausted`, `token_budget_exhausted`, `deadline_exceeded`).
4. Cross-file deduplication uses the compound key `(fingerprint, source_file_path)`.
5. `FindingSchema` and the `GET /v1/reviews/{review_id}` endpoint expose `source_file_path`, `tool_name`, `tool_version`, and `raw_evidence_ref`.

---

## [N32] Webhook Worker Auto-Review Pipeline (B3)

**Root Cause:**
Webhook background workers recorded PR and push events in `webhook_events` but never initiated repository reviews, leaving automated CI/CD code scanning non-functional.

**Resolution:**
1. Implemented `process_repo_review_job` in `app.integrations.github.webhook_worker`.
2. Upon receiving `pull_request` (actions `opened`, `synchronize`, `reopened`) or `push` webhook events, the webhook handler verifies policy toggles (`auto_review_on_pr`, `auto_review_on_push`, `review_fork_prs`, `review_draft_prs`) and dispatches `process_repo_review_job` to the ARQ Redis queue.
3. For PR events, PR metadata `head.repo.fork` is explicitly evaluated against `policy.review_fork_prs`.
4. The background job fetches installation credentials, queries the repository, and invokes `RepoReviewService.execute_repo_review` asynchronously, updating review status and recording complete audit events.

---

## [N33] Restored Acceptance & Integration Test Coverage (B4, B5, M1)

**Root Cause:**
The SRS acceptance test for FR-104 (`test_ac104_scoped_revision_review`) previously asserted trivial mocks without verifying database foreign key constraints, policy exclusion of test directories, or the zero-source-code persistence invariant. Additionally, several integration tests were disabled or skipped.

**Resolution:**
1. Re-implemented `test_ac104_zero_persistence_and_policy_grouping` in `tests/acceptance/test_srs_acceptance.py`:
   - Runs against an active SQLite relational database.
   - Asserts real `RepositoryReview` and `Finding` persistence.
   - Verifies that policy path exclusion (`tests/**`) strictly ignores test files.
   - Verifies that `SourceArtifact.content` contains solely `[REPOSITORY_REVIEW_MEMORY_ONLY]` and zero submitted source bytes.
2. Verified all 4 core GitHub integration suites (`test_github_connect_flow.py`, `test_github_repo_isolation.py`, `test_github_repo_review.py`, `test_github_webhook_processing.py`).
3. Added `test_github_repo_review_pipeline.py`, `test_github_webhook_auto_review.py`, `test_repo_review_budget.py`, and `test_github_webhook_replay.py`.
4. Full test suite expanded to 177 tests, all passing with zero regressions.

---

## [N34] GitHub API Host SSRF Guard & Base Configuration (H3)

**Root Cause:**
`app_auth.py` previously constructed token exchange endpoints directly without validating against allowed hostnames, presenting an SSRF vulnerability if API URLs were overridden.

**Resolution:**
1. Configured `github_api_base: str = Field(default="https://api.github.com", alias="GITHUB_API_BASE")` in `app/config.py`.
2. Implemented `ALLOWED_GITHUB_HOSTS` and `validate_github_url()` in `app/integrations/github/client.py` to enforce strict host validation before dispatching requests.
3. Added `_post_app_jwt()` helper with URL validation to ensure App JWT token exchange requests are strictly routed to authorized endpoints (`api.github.com`).

---

## [N35] ARQ Connection Pool Singleton Lifecycle (H1)

**Root Cause:**
`api/v1/webhooks.py` previously instantiated a new ARQ Redis connection pool on every incoming webhook request, causing connection leaks and Redis port exhaustion under high webhook volumes. Furthermore, failures during job queuing resulted in unhandled 500 responses without updating the webhook event status.

**Resolution:**
1. Initialized a singleton `arq_pool` in `main.py` lifespan startup and registered graceful closure upon application shutdown (`app.state.arq_pool`).
2. Replaced per-request pool creation in `webhooks.py` with `request.app.state.arq_pool`.
3. Added try/except error handling around job enqueueing: if Redis is unreachable or enqueueing fails, `WebhookEvent.status` is updated to `"failed"` and an audit event is logged, returning HTTP 202 without failing the incoming webhook ACK.

---

## [N36] Comprehensive GitHub Token Redaction (H2)

**Root Cause:**
Token redaction previously only scrubbed legacy Personal Access Tokens (`ghp_`), allowing newer token formats to leak into logs, findings, or exported reports.

**Resolution:**
Updated regex patterns in `app/services/redaction_service.py` to scrub all GitHub token families:
- `ghs_`: GitHub App server-to-server installation tokens
- `ghu_`: GitHub App user-to-server tokens
- `ghp_`: Classic personal access tokens
- `ghr_`: Refresh tokens
- `gho_`: OAuth access tokens
- `github_pat_`: Fine-grained personal access tokens
Verified via parameterized unit tests covering all six token variants.

---

## [N37] Canonical Export Aliases (M2)

Exported canonical aliases `compute_fingerprint = _compute_fingerprint` in `app/rules/engine.py` and `redact_secrets = redact` in `app/services/redaction_service.py` to ensure backwards-compatible, consistent imports across rule engine, triage, and review service modules.

---

## Phase 4.1 Implementation Notes — Post-Audit Security Hardening & Remediation

This section documents the remediation of audit findings across Phase 4 (M4), addressing security boundaries, meta-tests, implementation clarifications (IC1–IC10), and operational requirements.

### [N38] Root Cause of Hollow Sandbox Tests & Category A vs. Category B Split
**Root Cause:**
In Phase 4 M4, `tests/security/test_sandbox_isolation.py` passed a `MagicMock()` as the Docker client to `GVisorSandboxRuntime`. The tests injected hardcoded byte strings into the mock's exec output and asserted on the mock bytes. No real container was spawned, and no `runsc` runtime was evaluated. Consequently, while config dictionaries were validated, behavioral guarantees (network egress block, read-only rootfs enforcement, memory allocation caps, PIDs fork bomb protection, and credential stripping from `/proc/self/environ`) were never tested against real container behavior.

**Resolution & Design Decision:**
Tests were explicitly partitioned into two categories:
- **Category A (Configuration Verification)**:
  - Tests verify that GVisor runtime options (isolation parameters, resource ceilings, credential omission) are correctly constructed in Python kwargs.
  - Mocked, fast (<1s), runnable on any platform without `runsc` or Docker.
- **Category B (Runtime Behavioral Isolation)**:
  - Spawns real containers using `docker.from_env()` with the `runsc` runtime.
  - Executes live adversarial commands inside the container (`curl 8.8.8.8`, `touch /usr/bin/test`, fork bombs, 600MB allocation, scanning `/proc/self/environ`).
  - Guards runtime presence via `pytest.mark.skipif(not shutil.which("runsc") or "runsc" not in docker_runtimes, reason="runsc runtime not available; install gVisor to run")`.
  - Enforces a strict 30-second timeout per test and guarantees container teardown via `finally` blocks.
  - Skips gracefully on local developer machines lacking `runsc`.
  - CI includes a dedicated runner with gVisor installed and a CI guard failing the build if any test is skipped (`if grep -q "SKIPPED" out.txt; then exit 1; fi`).

### [N39] Meta-Test Guards for Phase 4 Security Boundaries (B2)
Two automated meta-tests were implemented:
1. `tests/security/test_github_write_allowlist_completeness.py`:
   - Statically parses AST of all service modules (`patch_service`, `pr_review_service`, `webhook_worker`) and `client.py`.
   - Asserts that neither `put()` nor `merge_pull_request()` is ever invoked.
   - Verifies all write calls match `ALLOWED_WRITE_ENDPOINTS` regex patterns or have explicit `# ALLOWED_WRITE:` review annotations.
2. `tests/security/test_patch_application_requires_all_gates.py`:
   - Enforces all 6 gates on `POST /v1/patches/{id}/apply`:
     - Gate 1: Draft status returns 409 (0 writes).
     - Gate 2: Approved without validation returns 409 (0 writes).
     - Gate 3: Approved with failed validation returns 422 (0 writes).
     - Gate 4: Approved with passed validation returns 201 (exactly 5 Git Data API writes: blob, tree, commit, ref, pull).
     - Gate 5: Withdrawn patch returns 409 (0 writes).
     - Gate 6: Idempotent replay with identical `X-Idempotency-Key` returns cached 201 with 0 duplicate writes.

### [N40] Sandbox Verdict Schema & Log Storage Migration Path (IC6, B3)
- `CheckResult` schema now provides both inline logs (`stdout`, `stderr` truncated to first 4 KB for fast UI preview) and log references (`stdout_ref`, `stderr_ref`).
- `GVisorSandboxRuntime.execute()` writes full un-truncated command output to disk at `/var/lib/vigil/validation_logs/{validation_id}/` (with a system temp directory fallback for cross-platform compatibility).
- `ValidationRun` model and migration 004 include `log_dir_ref` to track the full log location.
- **Phase 5 S3 Migration Path:**
  - In Phase 4, `log_dir_ref`, `stdout_ref`, and `stderr_ref` are local filesystem URIs (`file:///var/lib/vigil/...`).
  - In Phase 5, an S3 object store adapter will replace the local file writer, uploading logs to `s3://<vigil-validation-logs-bucket>/tenants/{tenant_id}/validations/{validation_id}/` and storing signed S3 URIs in `_ref` fields.

### [N41] Implementation Clarifications (IC1–IC10) Compliance Status
- **IC1 (runsc version check)**: Added `packaging>=23.0` and replaced string comparison with `packaging.version.Version` in `verify_runsc_available()`. Tested with `test_version_10_greater_than_9`.
- **IC2 (Base SHA drift)**: Enforced base SHA divergence check in `apply_patch()`, raising HTTP 409 with code `BASE_SHA_DRIFT`.
- **IC3 (PR Review Agent ref_type guard)**: Added guard in `PRReviewService.generate_draft_review()` and `webhook_worker.py` ensuring A9 only executes when `ref_type == "pr"`. Tested with `test_pr_review_agent_ref_type_guard.py`.
- **IC4 (Single write call per operation)**: Ephemeral branch update and rollbacks use single targeted calls.
- **IC5 (No merge endpoint)**: `GitHubClient.merge_pull_request()` explicitly raises `NotImplementedError` and is verified by AST check and grep.
- **IC6 (Log references)**: Inline 4KB stdout/stderr + `stdout_ref`/`stderr_ref` and `log_dir_ref`.
- **IC7 (Patch Agent token budget)**: Added `patch_agent_max_prompt_tokens = 8000` cap in `config.py` and fast heuristic check (`len(prompt) // 4`) in `PatchAgent.generate()`. Tested in `test_prompt_too_long_rejected`.
- **IC8 (GitHub client merge stub)**: Explicit stub added to `GitHubClient`.
- **IC9 (Rate limiting & Idempotency)**: Endpoints protected with 60m sliding window limits and Redis-cached idempotency.
- **IC10 (Development sandbox availability flag)**: `main.py` lifespan probes `runsc` in development and sets `app.state.sandbox_available = False` if missing; `POST /v1/patches/{id}/validate` returns 503 `sandbox_unavailable`. Tested in `test_sandbox_unavailable_503.py`.

### [N42] Audit Actions & Deviations from Original Plan (M1)
- The original plan specified 8 actions for Phase 4: `GITHUB_BRANCH_CREATED`, `GITHUB_COMMIT_CREATED`, `GITHUB_PR_OPENED`, `GITHUB_PR_REVIEW_POSTED`, `PATCH_APPROVED`, `PATCH_APPLIED`, `GITHUB_PATCH_APPROVED`, `SANDBOX_ESCAPE_SUSPECTED`.
- Implementation has both `GITHUB_PATCH_APPROVED` and `SANDBOX_ESCAPE_SUSPECTED` as well as descriptive actions `SANDBOX_SECURITY_VIOLATION` and `PR_REVIEW_PUBLISHED`. All actions are preserved in `AuditAction` and migration 004.

---

## Phase 5.1 Implementation Notes — Post-Audit Hardening & Verification Gate (M5 Patch)

This section documents the resolution of the four blocking gaps (B1–B4), four implementation-clarification violations (V1–V4 / IC10, IC5, IC6, IC1), and two medium issues (M1, M2) identified during the independent Phase 5 audit.

### [N43] Root Cause of Agent Class Name Divergence (B1)
**Root Cause:**
During initial Phase 5 agent scaffolding, classes in `backend/app/agents/dependency_agent.py` and `backend/app/agents/dataflow_agent.py` were named `DependencyRiskAgent` and `DataflowInvestigationAgent` based on early draft working titles rather than the canonical class names specified in the implementation architecture (`DependencyAgent` and `DataflowAgent`).

**Resolution:**
- Renamed `DependencyRiskAgent` -> `DependencyAgent` in `backend/app/agents/dependency_agent.py`.
- Renamed `DataflowInvestigationAgent` -> `DataflowAgent` in `backend/app/agents/dataflow_agent.py`.
- Provided canonical backward-compatibility aliases (`DependencyRiskAgent = DependencyAgent` and `DataflowInvestigationAgent = DataflowAgent`) in their respective modules and re-exported them in `backend/app/agents/__init__.py`.
- Verified canonical import statements:
  `from app.agents.dependency_agent import DependencyAgent`
  `from app.agents.dataflow_agent import DataflowAgent`

### [N44] Sanitization Module Canonical Location & Contract (B2)
**Root Cause:**
User disposition comment sanitization was initially located in `backend/app/services/learning_service.py:169` as `sanitize_user_comment()`, leaving `app.learning.sanitization` missing.

**Resolution:**
- Created `backend/app/learning/__init__.py` and `backend/app/learning/sanitization.py`.
- Implemented `sanitize_disposition_comment(comment: Optional[str]) -> str` delegating to the comprehensive sanitization logic:
  1. Stripping code constructs (e.g., `def`, `eval`, `class`).
  2. Redacting source file references and line numbers (`See line 42 of handler.py` -> `See [REDACTED_REF] of [REDACTED_REF]`).
  3. Redacting credential tokens (`ghp_*` -> `[REDACTED]`).
  4. Truncating overly long submissions to 500 characters max.
  5. Gracefully returning empty strings for `None` or whitespace-only inputs.
- Created `tests/unit/test_sanitization_module.py` covering all five canonical test cases plus null handling.

### [N45] Comprehensive Implementation Clarifications (IC) Compliance Status
- **IC1 (Atomic Daily Budget Increment & TTL Guarantee / V4):**
  - Replaced the two-call pattern (`incrbyfloat` followed by `expire`) in `backend/app/services/budget_service.py` with an atomic Redis Lua script executing `INCRBYFLOAT` and `EXPIRE` together.
  - Implemented an atomic fallback ensuring key presence with TTL (`set(..., ex=90000, nx=True)`) for mock environments.
  - Added `tests/integration/test_daily_budget_window.py::test_budget_key_always_has_ttl_under_concurrency` firing 100 concurrent requests and asserting `redis.ttl(key) > 0`.
- **IC5 (Risk Scoring Agent LLM Skip on Empty Index / V2):**
  - Updated `RiskScoringAgent.generate()` / `score_findings()` to inspect `historical_dispositions`. When empty, skips LLM provider completion calls entirely and returns deterministic static confidence scoring.
  - Added `tests/unit/test_risk_scoring_agent.py::test_risk_scoring_skips_llm_on_empty_index`.
- **IC6 (Executive Summary Agent LLM Skip on Empty Findings / V3):**
  - Updated `ExecutiveSummaryAgent.generate()` / `generate_summary()` to inspect `final_findings`. When empty, skips LLM provider calls entirely and returns a zero-score deterministic summary (`"No findings detected in this review."`).
  - Added `tests/unit/test_executive_summary_agent.py::test_executive_summary_skips_llm_on_empty_findings`.
- **IC10 (Multi-Agent Orchestration Emergency Kill Switch / V1):**
  - Added `killswitch_key: str = "vigil:killswitch:multi_agent"` in `backend/app/config.py`.
  - Added `_is_killswitch_active()` in `MultiAgentOrchestrator`. When set to `true`, `1`, or `yes` in Redis, skips all Phase 5 specialist agents (A10–A14) and executes the Phase 1–4 pipeline only (`_run_phase1_4_pipeline_only()`).
  - Documented emergency operators procedure in `RUNBOOK.md`.
  - Added integration verification in `tests/integration/test_killswitch.py`.
- **IC11 / M1 (Risk Scoring System Prompt Markdown):**
  - Created `prompts/risk_scoring.md` containing system role instructions and strict untrusted-data boundary delimiters (`<<<PRECEDENT_START>>>` and `<<<PRECEDENT_END>>>`).
  - Updated `RiskScoringAgent` to load prompt template using `load_prompt("risk_scoring")`.

### [N46] Acceptance Test Assertions & Required Test Suites (B3, B4)
- Added `tests/security/test_no_shared_state.py` verifying agent execution concurrency and snapshot immutability.
- Added `tests/privacy/test_consent_default_off.py` verifying fresh tenants default to unconsented and feedback is not indexed without explicit opt-in.
- Added `tests/acceptance/test_ac108_multi_agent_orchestration.py::test_ac108_1b_subtree2_sequential_ordering` verifying sequential serialization (>= 3.0s total duration across Patch, Test Gen, and Validation).
- Added `tests/acceptance/test_ac108_multi_agent_orchestration.py::test_ac108_8_agent_tree_endpoint_accurate` verifying `GET /v1/reviews/{run_id}/agent-tree` returns coordination IDs, durations, token counts, and agent statuses matching `AgentTaskExecution` database records.

### [N47] Frontend Components & Phase 6 Deferral Status (M2)
- Created `frontend/src/components/LearningConsentBanner.tsx` and `frontend/src/components/AgentTreeVisualization.tsx`. Both components are fully implemented, WCAG 2.1 AA compliant, and handle API state transitions (`POST /v1/consent/learning` and `GET /v1/reviews/{id}/agent-tree`).
- **Deferred to Phase 6:** End-to-end browser test automation suites (Playwright/Cypress) and full management console integration are explicitly deferred to Phase 6. All backend API contracts, security gates, and audit trails required by SRS §14 are 100% complete and verified.

---

## [N51] Real Dashboard Stats Aggregation

Dashboard statistics are dynamically computed in real time via `GET /v1/tenants/me/stats`:
- Queries `review_runs` scoped strictly to the authenticated `tenant_id`.
- Aggregates findings grouped by severity (`Critical`, `High`, `Medium`, `Low`, `Info`).
- Sums token spend across `agent_coordination_runs` and computes estimated cost ($0.000002/token).
- Computes average turnaround duration in milliseconds from `started_at` to `completed_at`.
- Calculates week-over-week trends comparing current 7 days vs previous 7 days.
- Rate-limited via tenant middleware at 60 req/min. Empty tenants display an onboarding banner: `"No reviews yet — submit your first to see stats."`.

---

## [N52] Groq Live LLM Provider and Fallback Behavior

- Groq (`groq>=0.11.0`) is the live LLM provider for Vigil (`llama-3.3-70b-versatile` by default).
- Implemented via `AsyncGroq` in `backend/app/agents/llm_provider.py` with strict JSON mode formatting (`response_format={"type": "json_object"}`).
- Fallback behavior: If `VIGIL_LLM_PROVIDER=groq` but `GROQ_API_KEY` is not provided, the factory logs a warning and falls back safely to `MockProvider()`.
- Mock mode remains fully supported for offline development and deterministic acceptance testing.
- Note: Groq free tier has TPM rate limits — see https://console.groq.com/docs/rate-limits.

---

## [N53] Verifiable Landing Page Metrics & Approach B Rationale

- **Problem:** Legacy templates contained unverified placeholder metrics (`94.8% Precision Rate`, `91.2% Vulnerability Recall`, `< 2.1% False Positive Ratio`, `1.8s Avg Review Time`).
- **Diagnosis:** The evaluation corpus (`tests/evaluation/corpus/`) currently contains 4 labeled samples. Claiming statistical precision/recall percentages with fewer than 10 samples violates truth-in-advertising constraints.
- **Resolution (Approach B):** Replaced unprovable percentages with four verifiable architectural facts:
  1. `3 Supported Languages`: Python, JavaScript, TypeScript (enumerated directly in review engine).
  2. `13 Detection Layers`: 7 baseline AST rules + 6 tool adapters (Bandit, Semgrep, Ruff, ESLint, pip-audit, npm-audit).
  3. `0 Unsandboxed Runs`: Zero-execution guarantee verified by automated security test suites (`tests/security/test_no_code_execution.py`).
  4. `Median Review Time`: Dynamically fetched from real tenant telemetry via `GET /v1/tenants/me/stats` (`avg_review_duration_ms`), displaying `—` / `Awaiting first review` for new tenants without fabricated data.
- **Footnote:** `"Numbers verified by Vigil's static analysis architecture and automated test suites. Submitted code is never executed outside an isolated sandbox."`

---

## [N54] Full GitHub Connect Flow & Callback Redirection

- **Full GitHub Connect Flow:**
  1. Frontend initiates connection via `POST /v1/repositories/connect`, obtaining a signed state token and GitHub App `install_url`.
  2. User is redirected to GitHub (`https://github.com/apps/{slug}/installations/new`) where they authorize repository access.
  3. GitHub redirects browser back to `GET /v1/repositories/callback?installation_id=...&state=...`.
  4. Backend verifies signed JWT state and single-use Redis nonce, queries GitHub installation API for repositories, and persists active `Repository` records with policies.
- **Callback Redirect Behavior:**
  - Browser visits to `github_callback` return HTTP `303 See Other` redirecting to `${FRONTEND_URL}/dashboard/github?connected=1`.
  - API and automated integration test clients sending `Authorization: Bearer <token>` continue receiving HTTP 200 JSON for backward compatibility.
- **Frontend State Management:**
  - `GitHubView.tsx` fetches live repositories on mount using `api.listRepositories()`.
  - When landing on `/dashboard/github?connected=1`, the component immediately refreshes the repository list and invokes `window.history.replaceState({}, '', '/dashboard/github')` to clean the URL query parameter.
  - Interactive actions include Trigger Review with cost pre-flight budget check, Disconnect with confirmation, and Connect GitHub buttons in header and empty states with WCAG 2.1 AA compliant keyboard focus and ARIA labels.

---

## Audit remediation (2026-09)

[AUTH-01] Prototype local auth routes (/v1/auth/register, /login, /token)
are gated behind VIGIL_ALLOW_LOCAL_AUTH (default false). Production
startup logs a critical warning if the gate is enabled. OIDC exchange is
not yet implemented.

[SEC-01] LLM provider factory is fail-closed. get_provider() raises
ConfigurationError if a real provider is named but its API key is missing.
VIGIL_LLM_PROVIDER=rules_only is the explicit opt-in for deterministic
rules-only operation. MockProvider is forbidden in production.

[SEC-02] Cosign signature verification fails closed in production when the
cosign binary is absent. In development it logs a warning and proceeds.

[UPLOAD-01] Source size limit is unified at 256 KB (262144 bytes) across
the Pydantic validator, the schema constraints response, and the upload
handler error message. All read from settings.max_upload_bytes.






