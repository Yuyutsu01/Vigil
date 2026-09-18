# Vigil — Agentic Code Review & Security Assistant
### Phase 1 (M1 Working Prototype)

[![Tests](https://img.shields.io/badge/tests-passing-22c55e?style=flat-square)](tests/)
[![Python](https://img.shields.io/badge/python-3.12-3b82f6?style=flat-square)](backend/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?style=flat-square)](https://nextjs.org)
[![License](https://img.shields.io/badge/license-MIT-f59e0b?style=flat-square)](LICENSE)

Vigil is a **zero-execution, agentic AI code review system** that detects security
vulnerabilities and quality issues in Python, JavaScript, and TypeScript source code.

> 🔒 **Submitted code is never executed.** All analysis uses Python `ast` module
> and Tree-sitter parse trees — no subprocess, no shell, no interpreter is invoked on user content.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Next.js Frontend (Port 3000)                        │
│  Paste/Upload → Submit → Poll → Results + Feedback  │
└────────────────────┬────────────────────────────────┘
                     │ HTTPS / REST
┌────────────────────▼────────────────────────────────┐
│  FastAPI Backend (Port 8000)                         │
│                                                      │
│  ┌─ Rate Limit (Redis, fail-CLOSED) ──────────────┐  │
│  │  ┌─ Idempotency (Redis, 24h TTL) ────────────┐ │  │
│  │  │  ┌─ JWT Auth (tenant_id from claim only) ┐ │ │  │
│  │  │  │                                       │ │ │  │
│  │  │  │   POST /v1/reviews                    │ │ │  │
│  │  │  │      │                                │ │ │  │
│  │  │  │   Consent Check ──── Revoke/Grant     │ │ │  │
│  │  │  │      │                                │ │ │  │
│  │  │  │   LangGraph Agent                     │ │ │  │
│  │  │  │    ├─ [1] Parse (ast/tree-sitter)     │ │ │  │
│  │  │  │    ├─ [2] Rules (7 baseline cats)     │ │ │  │
│  │  │  │    ├─ [3] LLM Security (policy-wrap)  │ │ │  │
│  │  │  │    ├─ [4] LLM Quality (policy-wrap)   │ │ │  │
│  │  │  │    └─ [5] Triage (DETERMINISTIC)      │ │ │  │
│  │  │  │                                       │ │ │  │
│  │  │  └───────────────────────────────────────┘ │ │  │
│  │  └─────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────┘  │
│                                                      │
│  PostgreSQL (findings, audit log, consent records)   │
│  Redis (rate limiting, idempotency)                  │
└─────────────────────────────────────────────────────┘
```

---

## Features

| Category | Details |
|----------|---------|
| **Languages** | Python, JavaScript, TypeScript (≤250 KB, UTF-8) |
| **Submission** | Paste via JSON (`POST /v1/reviews`) or upload file (`POST /v1/uploads`) |
| **Rule Engine** | 7 deterministic baseline categories (see below) |
| **AI Reasoning** | Policy-guarded LLM security + quality review (MockProvider by default) |
| **Fingerprinting** | Line-shift-invariant: `sha256(rule_id‖ast_path‖matched_text_hash‖evidence_kind)` |
| **Deduplication** | Rule findings take precedence over LLM findings on fingerprint collision |
| **Feedback** | Per-finding disposition: `accepted`, `rejected`, `false_positive` |
| **Deletion** | `DELETE /v1/reviews/{id}` with legal-hold check and audit trail |
| **Audit Log** | Append-only audit events (no source code or secrets stored) |
| **Consent** | FR-009: per-user versioned consent gate before any processing |

### Baseline Rule Categories

| Rule ID | Category | Severity |
|---------|----------|---------|
| VIGIL-SEC-001 | Hardcoded secrets & credentials | Critical |
| VIGIL-SEC-002 | Unsafe eval/exec/new Function() | Critical |
| VIGIL-SEC-003 | SQL & OS command injection | High |
| VIGIL-SEC-004 | Insecure deserialization (pickle, yaml.load) | High |
| VIGIL-SEC-005 | Weak cryptography (MD5, SHA-1, DES, RC4) | Medium |
| VIGIL-QUAL-006 | Improper error handling (bare except, empty catch) | Low |
| VIGIL-MAINT-007 | Maintainability (long functions, high complexity) | Low |

---

## Quick Start

### With Docker Compose (recommended)

```bash
git clone https://github.com/yuyutsu01/Vigil.git
cd Vigil
cp backend/.env.template backend/.env
# Edit backend/.env — change JWT_SECRET_KEY at minimum
docker compose up -d
open http://localhost:3000
```

### Without Docker

See **[RUNBOOK.md](RUNBOOK.md)** for full local setup instructions.

---

## Running Tests

```bash
pip install -r backend/requirements.txt -r backend/requirements-test.txt

# All unit, security, and acceptance tests (no external dependencies)
pytest tests/unit/ tests/security/ tests/acceptance/ -v

# Coverage report
pytest tests/unit/ tests/security/ tests/acceptance/ \
  --cov=backend/app --cov-report=term-missing
```

---

## Project Structure

```
Vigil/
├── backend/
│   ├── app/
│   │   ├── agents/          # LangGraph orchestration + policy wrapper
│   │   ├── api/v1/          # FastAPI routers (auth, consent, reviews, uploads)
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── parser/          # Syntax validator, tree-sitter engine
│   │   ├── rules/           # Rule loader + deterministic rule engine
│   │   ├── sandbox/         # NoOpSandboxRuntime stub (Phase 4)
│   │   ├── schemas/         # Pydantic API schemas
│   │   ├── services/        # Auth, audit, consent, review, triage services
│   │   ├── config.py        # Settings + RuntimeSettings
│   │   ├── database.py      # Async SQLAlchemy engine
│   │   ├── main.py          # FastAPI app + middleware
│   │   └── redis_client.py  # Redis client factory
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js App Router (layout, page, globals.css)
│   │   ├── components/      # LoginForm, CodeEditor, FindingsPanel
│   │   └── lib/             # API client, token store
│   └── Dockerfile
├── skills/                  # Versioned rule markdown files
├── prompts/                 # Versioned LLM prompt markdown files
├── tests/
│   ├── unit/               # Rule engine, policy, triage
│   ├── security/           # No-code-execution, tenant isolation, prompt injection
│   ├── acceptance/         # AC-1 through AC-7
│   └── integration/        # API flow, Content-Type, size limits
├── docker-compose.yml
├── IMPLEMENTATION_NOTES.md
└── RUNBOOK.md
```

---

## Security Guarantees

1. **Zero code execution**: No `subprocess`, `os.system`, `eval`, or interpreter is invoked on submitted code.
2. **JWT-only tenant isolation**: `tenant_id` comes exclusively from the verified JWT claim. Client headers are cross-checked and rejected on mismatch.
3. **Prompt injection resistance**: Source code is enclosed in `<<<SOURCE_START>>>`/`<<<SOURCE_END>>>` delimiters with explicit instructions to treat it as data.
4. **Secret redaction**: A `RedactionFilter` is attached to the root logger, stripping credential-shaped strings from all log output.
5. **Fail-CLOSED Redis**: Rate limiting and idempotency fail to 503, not open.
6. **Append-only audit log**: No source code or secrets are stored in audit events.

---

## Phase Roadmap

| Phase | Milestone | Key Features |
|-------|-----------|--------------|
| **Phase 1** | M1 ✅ | Rules engine, LangGraph agent, consent, audit, frontend |
| Phase 2 | M2 | OIDC auth, SARIF export, encrypted storage, retention scheduler |
| Phase 3 | M3 | Patch candidate generation (FR-105) |
| Phase 4 | M4 | Sandbox dynamic execution (FR-106, gVisor) |

---

## License

MIT — see [LICENSE](LICENSE).