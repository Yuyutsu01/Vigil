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

## Open Items for M2+

| Item | Phase | Description |
|------|-------|-------------|
| OIDC integration | M2 | Replace local auth with Auth0/Keycloak |
| Encryption at rest | M2 | KMS-encrypted `SourceArtifact.content` |
| Patch generation | M3 | FR-105: unified-diff patch candidates |
| Sandbox execution | M4 | FR-106: gVisor/Firecracker dynamic analysis |
| SARIF export endpoint | M2 | `GET /v1/reviews/{id}/sarif` |
| Retention scheduler | M2 | Cron-based deletion at `retention_until` |
