# Vigil — Enterprise Multi-Agent AI Code Review & Security Remediation Platform

[![Tests](https://img.shields.io/badge/tests-309%20passed-22c55e?style=for-the-badge&logo=pytest&logoColor=white)](tests/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-3b82f6?style=for-the-badge&logo=python&logoColor=white)](backend/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169e1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-dc2626?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![gVisor](https://img.shields.io/badge/Sandbox-gVisor%20runsc-ea580c?style=for-the-badge)](https://gvisor.dev)
[![License](https://img.shields.io/badge/license-MIT-f59e0b?style=for-the-badge)](LICENSE)

**Vigil** is a production-grade, enterprise-ready **autonomous multi-agent AI code review and automated remediation platform**. It orchestrates a directed acyclic graph (DAG) of **14 specialized agents** to perform static vulnerability analysis, AST taint tracking, dependency risk audits, candidate patch generation, gVisor-isolated test validation, and PR review governance across Python, JavaScript, and TypeScript codebases.

Vigil is architected around strict zero-trust security invariants: **user code is never executed during static review**, **rule findings are immune to AI suppression**, **remediation patches are validated inside isolated gVisor sandboxes**, and **all learning occurs on sanitized metadata under strict GDPR consent**.

---

## Key Capabilities & Highlights

- **Multi-Agent Orchestration (FR-108, SRS §14 Final Milestone)**
  Coordinates 14 specialist agents with Subtree 1 parallel fan-out (Risk Scoring, Dependency, Dataflow) and Subtree 2 strictly serialized validation (Patch -> Test Gen -> Sandbox Validation).
- **Deterministic Triage Supremacy (A5)**
  Rule-detected security vulnerabilities (OWASP Top 10, CWE) can never be suppressed or downgraded by LLM advisory agents.
- **Automated Surgical Remediation (FR-105)**
  Generates minimal unified diffs for verified vulnerabilities and enforces a 6-gate security pipeline before applying changes via atomic GitHub Data API transactions.
- **gVisor Sandbox Runtime (FR-106)**
  Candidate patches and AI-generated regression tests execute inside hardened `runsc` containers with zero network egress, read-only root filesystems, strict memory/CPU limits, and credential stripping.
- **Governed Learning Loop (FR-109)**
  Zero raw tenant source code is ever persisted for learning. Tenant disposition feedback is passed through a multi-stage sanitization barrier and retrieved via semantic RAG with delimiter injection defense.
- **GDPR Right-to-be-Forgotten**
  Tenant consent defaults to OFF. Revocation triggers an immediate (< 5.0s) cryptographic cascade purge of all indexed learning precedents.
- **Enterprise Guardrails & Circuit Breakers**
  Redis fail-closed rate limiting, 24-hour request idempotency, emergency specialist agent kill switch (`vigil:killswitch:multi_agent`), and atomic 24h UTC daily spend budgets.
- **Multi-Format Export & OpenTelemetry**
  Export results to SARIF v2.1.0 (GitHub Advanced Security compatible), JSON, Markdown, HTML, and PDF. Full distributed tracing via OpenTelemetry root and child spans.

---

## System Architecture

```
                                    ┌─────────────────────────────────────────────────────────┐
                                    │               GitHub App / Developer Client             │
                                    │       Webhooks (PR, Push)  │  REST API  │  Next.js UI   │
                                    └────────────────────────────┬────────────────────────────┘
                                                                 │ HTTPS (JWT + HMAC SHA-256)
┌────────────────────────────────────────────────────────────────▼────────────────────────────────────────────────────────┐
│                                                 Vigil FastAPI Core Engine                                               │
│                                                                                                                         │
│  ┌─ Rate Limiting (Redis Token Bucket, Fail-Closed) ──────────────────────────────────────────────────────────────────┐  │
│  │  ┌─ Idempotency Engine (Redis 24h TTL, Deterministic Replay) ────────────────────────────────────────────────────┐ │  │
│  │  │  ┌─ Tenant Isolation Middleware (JWT Claim Only, X-Tenant-Hint Cross-Checked) ───────────────────────────────┐ │ │  │
│  │  │  │                                                                                                           │ │ │  │
│  │  │  │                                 Multi-Agent Orchestrator DAG (FR-108)                                     │ │ │  │
│  │  │  │                                                                                                           │ │ │  │
│  │  │  │   [A1] AST Parser (ast / Tree-sitter) ────► [A2] Tool Adapters (Bandit, Ruff, Semgrep)                    │ │ │  │
│  │  │  │                                                       │                                                   │ │ │  │
│  │  │  │   [A3] LLM Security Agent ────────────────────────────┼────────────────► [A4] LLM Quality Agent           │ │ │  │
│  │  │  │                                                       │                                                   │ │ │  │
│  │  │  │                                           Base Findings Synthesis                                         │ │ │  │
│  │  │  │                                                       │                                                   │ │ │  │
│  │  │  │               ┌───────────────────────────────┴───────────────────────────────┐                   │ │ │  │
│  │  │  │               │ Subtree 1: Parallel Fan-Out Benchmarked Fan-Out               │                   │ │ │  │
│  │  │  │               │   ├─ [A10] Risk Scoring Agent (Historical RAG Precedents)     │                   │ │ │  │
│  │  │  │               │   ├─ [A11] Dependency Risk Agent (Supply Chain Vulnerabilities│                   │ │ │  │
│  │  │  │               │   └─ [A12] Dataflow Agent (Cross-File AST Taint Tracking)     │                   │ │ │  │
│  │  │  │               └───────────────────────────────┬───────────────────────────────┘                   │ │ │  │
│  │  │  │                                               │                                                   │ │ │  │
│  │  │  │                                   [A5] Deterministic Triage                                       │ │ │  │
│  │  │  │                         (SUPREME ARBITER: Rules Override AI Advisory)                             │ │ │  │
│  │  │  │                                               │                                                   │ │ │  │
│  │  │  │               ┌───────────────────────────────┴───────────────────────────────┐                   │ │ │  │
│  │  │  │               │ Subtree 2: Strictly Serialized Remediation Pipeline           │                   │ │ │  │
│  │  │  │               │   [A6] Patch Agent (Unified Diff Generation)                  │                   │ │ │  │
│  │  │  │               │                      │                                        │                   │ │ │  │
│  │  │  │               │   [A13] Test Generation Agent (Automated Regressions)         │                   │ │ │  │
│  │  │  │               │                      │                                        │                   │ │ │  │
│  │  │  │               │   [A7] Validation Agent ──► [gVisor / runsc Sandbox Isolation] │                   │ │ │  │
│  │  │  │               └───────────────────────────────┬───────────────────────────────┘                   │ │ │  │
│  │  │  │                                               │                                                   │ │ │  │
│  │  │  │                               [A14] Executive Summary Agent                                       │ │ │  │
│  │  │  │                         (Resilient Synthesis & Composite Scoring)                                 │ │ │  │
│  │  │  │                                               │                                                   │ │ │  │
│  │  │  │                                   [A9] PR Review Governance                                       │ │ │  │
│  │  │  │                               (Human Gate Required for Publication)                               │ │ │  │
│  │  │  │                                                                                                           │ │ │  │
│  │  │  └───────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │ │  │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                                             │
│       PostgreSQL 16 (Append-Only Audit, Findings, Consent)  │  Redis 7 (Lua Atomic Budgets, Kill Switch, Rate Limits)       │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## The 14 Autonomous Agents

| Agent ID | Name | Execution Model | Responsibilities & Guardrails |
|:---|:---|:---|:---|
| **A1** | **AST Parser** | Deterministic AST | Parses code using Python `ast` and Tree-sitter. Zero code execution. Extracts AST nodes and call sites. |
| **A2** | **Tool Adapter Runner** | Sandboxed CLI | Wraps Bandit, Ruff, and Semgrep with isolated CLI parsing and JSON schema normalization. |
| **A3** | **LLM Security Agent** | LLM (Policy Guard) | Inspects AST nodes for complex semantic security vulnerabilities with prompt-injection defense. |
| **A4** | **LLM Quality Agent** | LLM (Policy Guard) | Analyzes code quality, cyclomatic complexity, and error-handling patterns; capped at Medium severity. |
| **A5** | **Deterministic Triage** | Heuristic Arbiter | **Supreme Arbiter**. Deduplicates findings via line-shift-invariant fingerprinting. Rules supersede LLMs. |
| **A6** | **Patch Agent** | LLM (Structured) | Generates minimal unified diffs for critical/high findings under strict prompt token caps ($1.00 max). |
| **A7** | **Validation Agent** | gVisor Sandbox | Validates candidate patches inside hardened `runsc` containers. Inspects test outputs and exit codes. |
| **A8** | **Report Agent** | Template Engine | Renders review findings into SARIF v2.1.0, Markdown, JSON, HTML, and PDF with SSRF/XSS sanitization. |
| **A9** | **PR Review Agent** | LLM + Governance | Generates structured PR reviews with inline comments. Strictly requires human approval before publishing. |
| **A10** | **Risk Scoring Agent** | RAG + LLM | Evaluates findings against historical tenant precedents. Skips LLM on empty index for deterministic speed. |
| **A11** | **Dependency Agent** | Static Heuristic | Evaluates manifest files (`requirements.txt`, `package.json`) against known advisory feeds without network egress. |
| **A12** | **Dataflow Agent** | Multi-step AST | Performs inter-procedural taint tracking from untrusted sources to sinks. Validates sanitizer coverage. |
| **A13** | **Test Generation Agent** | LLM (Structured) | Synthesizes regression test cases verifying patch validity. Tests undergo strict command safety validation. |
| **A14** | **Executive Summary Agent** | LLM (Synthesis) | Produces holistic risk synthesis and remediation roadmaps. Resilient to earlier specialist agent timeouts. |

---

## Security Invariants & Governance Directives

### 1. Zero Code Execution During Review
User-submitted source code is never executed during analysis. Parsing is performed strictly using Python `ast` and Tree-sitter parse trees. Dynamic commands, subprocesses, or evaluation functions (`eval`, `exec`) are never run against user input during static analysis.

### 2. Deterministic Triage Supremacy (AC-108.5)
The **A5 Triage Agent** is the supreme arbiter of finding persistence. While specialist AI agents can advise adjustments to confidence scores or suggest downgrades, **rule-origin findings (origin='rule') can never be suppressed**.

### 3. gVisor Sandbox Behavioral Isolation (FR-106)
When candidate patches and generated tests are validated (Subtree 2), they are executed inside containerized sandboxes powered by Google's **gVisor (`runsc`)**:
- **Zero Network Egress:** Host network access is disabled (`--net=none`).
- **Read-Only Root Filesystem:** Rootfs is mounted read-only (`--read-only`). Ephemeral writes restricted to temporary in-memory tmpfs.
- **Resource Ceilings:** Strictly enforced limits: 512 MB RAM, 1.0 vCPU, 1024 MB disk, 120-second timeout, 256 PID limit (fork-bomb defense).
- **Credential Stripping:** All host environment variables, tokens, and secrets are completely stripped prior to container execution.

### 4. Atomic 6-Gate Patch Application (FR-105)
Before a patch can be applied to an upstream GitHub branch, it must successfully pass through six sequential gates:
1. **Status Gate:** Patch must be in `approved` status (drafts return 409).
2. **Validation Gate:** Patch must have run through sandbox validation (unvalidated return 409).
3. **Verdict Gate:** Sandbox validation verdict must be `passed` (failed validations return 422).
4. **Base SHA Gate:** Target branch HEAD must match the patch base commit (divergence returns 409 with `BASE_SHA_DRIFT`).
5. **Lifecycle Gate:** Withdrawn patches cannot be applied (returns 409).
6. **Atomic Transaction:** Patch commit, tree creation, blob write, branch update, and PR creation are executed as an exact 5-write atomic Git Data API transaction.

### 5. Governed Learning Loop & Zero Raw Code Persistence (FR-109)
Vigil allows models to learn from user dispositions (`false_positive`, `accepted`) without compromising confidentiality:
- **Zero Raw Code Storage:** Tenant source code is never stored in vector databases or learning indices.
- **Sanitization Barrier:** All user comments pass through `sanitize_disposition_comment` which scrubs code definitions (`def`, `eval`, `class`), file paths, line numbers, and secrets (`ghp_*`), truncating to 500 characters max.
- **Prompt Injection Defense:** Historical precedents retrieved via semantic RAG are strictly wrapped between `<<<PRECEDENT_START>>>` and `<<<PRECEDENT_END>>>` delimiters. System prompts strictly forbid models from treating content inside delimiters as instructions.
- **GDPR Right-to-be-Forgotten:** Revoking consent purges all tenant vector indices and disposition records in under 5.0 seconds.

### 6. Emergency Specialist Kill Switch (IC10)
If upstream LLMs experience outages or specialist agents behave erratically, operators can disable all Phase 5 specialist agents globally with zero downtime:
```bash
redis-cli SET vigil:killswitch:multi_agent true
```
The orchestrator immediately bypasses agents A10–A14, routing requests strictly through the deterministic Phase 1–4 pipeline.

---

## REST API Reference

| Method | Endpoint | Description | Auth |
|:---|:---|:---|:---|
| `POST` | `/v1/reviews` | Submit code snippet or artifact for multi-agent review | JWT |
| `GET` | `/v1/reviews/{id}` | Poll review status, triaged findings, and patch drafts | JWT |
| `GET` | `/v1/reviews/{id}/agent-tree` | Get multi-agent DAG telemetry, agent durations, and token attributions | JWT |
| `GET` | `/v1/reviews/{id}/report` | Download review report in SARIF, Markdown, JSON, HTML, or PDF | JWT |
| `DELETE` | `/v1/reviews/{id}` | Delete review run and source artifact (under GDPR compliance) | JWT |
| `POST` | `/v1/patches/{id}/validate` | Trigger gVisor sandbox validation on candidate patch | JWT |
| `POST` | `/v1/patches/{id}/apply` | Apply validated patch to GitHub branch via Git Data API | JWT |
| `POST` | `/v1/consent/learning` | Grant or revoke tenant consent for governed feedback learning | JWT |
| `POST` | `/v1/repositories/connect` | Connect a GitHub repository for automated CI review | JWT |
| `POST` | `/v1/webhooks/github` | GitHub App webhook ingestion endpoint (HMAC verified) | Secret |

---

## Getting Started

### Prerequisites
- **Docker & Docker Compose** (Recommended)
- **Python 3.11+**
- **PostgreSQL 16+** & **Redis 7+**
- **gVisor (`runsc`)** (Optional for local development; required for live sandbox execution)

### 1. Run with Docker Compose

```bash
# 1. Clone repository
git clone https://github.com/yuyutsu01/Vigil.git
cd Vigil

# 2. Configure environment
cp backend/.env.template backend/.env
# Update JWT_SECRET_KEY and optional LLM keys in backend/.env

# 3. Launch database, Redis, backend, and frontend
docker compose up -d

# 4. Access the web console
open http://localhost:3000
```

### 2. Local Bare-Metal Setup

```bash
# 1. Setup Python virtual environment
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure PostgreSQL & Redis connections
export DATABASE_URL="postgresql+asyncpg://vigil:vigil@localhost:5432/vigil"
export REDIS_URL="redis://localhost:6379/0"

# 3. Apply database migrations
alembic upgrade head

# 4. Start backend API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Verification & Test Suite

Vigil features a comprehensive, multi-layered verification suite with **309+ passing tests** covering acceptance criteria, security boundaries, isolation invariants, and privacy guarantees.

```bash
# Run the complete test suite
pytest -v tests/

# Run Multi-Agent Orchestration acceptance tests (AC-108)
pytest -v tests/acceptance/test_ac108_multi_agent_orchestration.py

# Run Governed Learning Loop acceptance tests (AC-109)
pytest -v tests/acceptance/test_ac109_governed_learning_loop.py

# Run Security & Sandbox Isolation tests
pytest -v tests/security/

# Run Privacy & GDPR Consent tests
pytest -v tests/privacy/
```

### Test Suite Distribution

```
========================================================================================
Test Category                                  Target Focus                     Status
========================================================================================
tests/acceptance/test_ac108_*.py               Multi-Agent DAG & Telemetry      PASSED (7/7)
tests/acceptance/test_ac109_*.py               Governed Learning Loop           PASSED (1/1)
tests/security/test_no_shared_state.py         Agent State Isolation            PASSED (2/2)
tests/privacy/test_consent_default_off.py      GDPR Consent Default OFF         PASSED (2/2)
tests/integration/test_killswitch.py           Emergency Kill Switch (IC10)     PASSED (2/2)
tests/integration/test_daily_budget_window.py  Lua Atomic Budgets (IC1)         PASSED (3/3)
tests/unit/test_sanitization_module.py         Comment Sanitization (B2)        PASSED (6/6)
tests/unit/test_risk_scoring_agent.py          Risk Scoring Fallback (IC5)      PASSED (4/4)
tests/unit/test_executive_summary_agent.py     Summary Fallback (IC6)           PASSED (3/3)
tests/security/test_patch_application_*.py     6-Gate Patch Safety              PASSED (6/6)
Full Test Suite Total                          All Suites & Invariants          309 PASSED
========================================================================================
```

---

## Project Directory Structure

```
Vigil/
├── backend/
│   ├── app/
│   │   ├── adapters/          # Tool adapters (Bandit, Ruff, Semgrep)
│   │   ├── agents/            # The 14 Autonomous Specialist Agents (A1–A14)
│   │   │   ├── dataflow_agent.py          # A12: AST Taint & Dataflow Analyzer
│   │   │   ├── dependency_agent.py        # A11: Advisory Supply Chain Scanner
│   │   │   ├── executive_summary_agent.py # A14: Narrative Synthesis Agent
│   │   │   ├── orchestrator.py            # Master DAG Orchestrator (FR-108)
│   │   │   ├── patch_agent.py             # A6: Surgical Unified Diff Generator
│   │   │   ├── pr_review_agent.py         # A9: PR Review & Governance Agent
│   │   │   ├── risk_scoring_agent.py      # A10: Historical Precedent Scorer
│   │   │   ├── test_generation_agent.py   # A13: Automated Regression Test Agent
│   │   │   └── validation_agent.py        # A7: Sandbox Validation Agent
│   │   ├── api/               # FastAPI REST router and versioned endpoints
│   │   │   └── v1/            # Reviews, Patches, Repositories, Consent, Webhooks
│   │   ├── learning/          # Governed Learning Loop (FR-109) & Sanitization
│   │   ├── migrations/        # Alembic database migration chain (001 to 005)
│   │   ├── models/            # SQLAlchemy 2.0 ORM models (Tenant, Review, Patch, etc.)
│   │   ├── reports/           # SARIF, Markdown, JSON, HTML, and PDF generators
│   │   ├── rules/             # Deterministic AST rule engine & fingerprinting
│   │   ├── sandbox/           # gVisor (runsc) runtime and resource controllers
│   │   ├── services/          # Core business services (Auth, Budget, Triage, Patch)
│   │   ├── config.py          # Centralized Pydantic settings & environment flags
│   │   └── main.py            # Application factory, lifespan, and middleware
│   └── requirements.txt       # Python dependencies
├── frontend/                  # Next.js 15 Management Console
│   └── src/
│       ├── components/        # AgentTreeVisualization, LearningConsentBanner, etc.
│       └── app/               # Next.js App Router views
├── prompts/                   # Externalized markdown system prompts (Patch, PR, Risk)
├── tests/                     # 309+ Automated tests
│   ├── acceptance/            # SRS Acceptance tests (AC-105 through AC-109)
│   ├── integration/           # Pipeline, webhook, budget, and API tests
│   ├── privacy/               # Consent, GDPR purge, and data isolation tests
│   ├── security/              # Sandboxing, write allowlists, SSRF, prompt injection
│   └── unit/                  # Fast component and agent unit tests
├── docker-compose.yml         # Container orchestration manifest
├── IMPLEMENTATION_NOTES.md    # Detailed audit trail, architectural notes & caveats
├── RUNBOOK.md                 # Production operations, disaster recovery & runbook
└── README.md                  # Project overview and documentation
```

---

## License

Vigil is open-source software licensed under the **[MIT License](LICENSE)**.