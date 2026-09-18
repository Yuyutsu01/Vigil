# Vigil Phase 1 — Operations Runbook

## Quick Reference

| Service | URL | Health Check |
|---------|-----|--------------|
| Backend API | http://localhost:8000 | `GET /health` |
| Frontend | http://localhost:3000 | HTTP 200 on `/` |
| PostgreSQL | localhost:5432 | `pg_isready -U vigil` |
| Redis | localhost:6379 | `redis-cli ping` |
| API Docs | http://localhost:8000/docs | Swagger UI |

---

## Starting Up (Docker Compose)

```bash
# 1. Copy and fill env file
cp backend/.env.template backend/.env
# Edit backend/.env — at minimum change JWT_SECRET_KEY

# 2. Start all services
docker compose up -d

# 3. Verify health
curl http://localhost:8000/health

# 4. View logs
docker compose logs -f backend
```

---

## Starting Up (Local Development)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.template .env
# Edit .env

# Start PostgreSQL and Redis (via Docker)
docker run -d --name vigil-pg -e POSTGRES_USER=vigil -e POSTGRES_PASSWORD=vigil \
  -e POSTGRES_DB=vigil -p 5432:5432 postgres:16-alpine
docker run -d --name vigil-redis -p 6379:6379 redis:7-alpine

# Run backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

---

## Running Tests

```bash
# From project root
pip install -r backend/requirements.txt -r backend/requirements-test.txt

# Unit tests (no external dependencies)
pytest tests/unit/ tests/security/ tests/acceptance/ -v

# Integration tests (requires running PostgreSQL + Redis)
pytest tests/integration/ -v

# Full test suite with coverage
pytest --cov=backend/app --cov-report=term-missing -v

# Single test
pytest tests/unit/test_rule_engine.py::TestRuleEngineDetection::test_detects_unsafe_eval -v
```

---

## Sandbox Testing (Phase 4 / gVisor)

Vigil patch validation tests (`tests/security/test_sandbox_isolation.py`) are strictly divided into two distinct categories:

### Test Categories
- **Category A (Configuration Assertions)**:
  - Tests verify that GVisor configuration dictionaries contain strict isolation flags (`network_mode="none"`, `read_only=True`, `mem_limit=512m`, `pids_limit=256`, zero host secrets passed).
  - Uses mocked Docker clients; runs on every operating system and host without runsc.
- **Category B (Runtime Behavioral Isolation)**:
  - Tests verify actual runtime security boundaries by launching real containers via `docker.from_env()`.
  - Executes adversarial commands inside the container: egress probes (`curl 8.8.8.8`), rootfs write attempts (`touch /usr/bin/test`), fork bombs (PIDs limit enforcement), memory allocation (OOM killing above 512MB), and `/proc/self/environ` secret scanning.
  - Requires the `runsc` (gVisor) OCI runtime registered with Docker daemon.
  - Each test has an enforced 30-second timeout and guarantees container cleanup in `finally` blocks.

### Local Development vs CI
- **Local Developer Environments**:
  - If `runsc` is not installed on your host machine, Category B tests **skip gracefully** with a clear skip reason (`runsc runtime not available; install gVisor to run`). They do not fail.
  - Developers wanting to run Category B locally can install `runsc` on Linux:
    ```bash
    curl -fsSL https://gvisor.dev/archive.key | sudo gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main" | sudo tee /etc/apt/sources.list.d/gvisor.list > /dev/null
    sudo apt-get update && sudo apt-get install -y runsc
    sudo runsc install
    sudo systemctl restart docker
    ```
- **Continuous Integration (CI)**:
  - CI **MUST** run Category B tests. CI runner installs gVisor and configures Docker.
  - CI includes an explicit guard that fails the build if any test in `test_sandbox_isolation.py` is skipped:
    ```bash
    pytest tests/security/test_sandbox_isolation.py -v | tee out.txt
    if grep -q "SKIPPED" out.txt; then
      echo "::error::Sandbox isolation tests were skipped in CI"
      exit 1
    fi
    ```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | postgresql+asyncpg://… | PostgreSQL async DSN |
| `REDIS_URL` | redis://localhost:6379/0 | Redis DSN |
| `JWT_SECRET_KEY` | **CHANGE ME** | JWT signing secret (≥32 bytes) |
| `VIGIL_LLM_PROVIDER` | `mock` | `mock` / `openai` / `anthropic` |
| `OPENAI_API_KEY` | _(empty)_ | Required if provider=openai |
| `VIGIL_ENV` | `development` | `development` / `production` / `test` |
| `VIGIL_CORS_ORIGINS` | http://localhost:3000 | Comma-separated allowed origins |
| `VIGIL_CONSENT_POLICY_VERSION` | `1.0` | Enforced consent version |
| `VIGIL_TOKEN_BUDGET_PER_RUN` | `50000` | Max tokens per review run |
| `VIGIL_WALL_CLOCK_DEADLINE_SECONDS` | `60` | Max seconds per run |
| `VIGIL_RATE_LIMIT_TENANT_PER_MINUTE` | `60` | Tenant request cap |
| `VIGIL_RATE_LIMIT_USER_PER_MINUTE` | `20` | User request cap |

---

## Common Troubleshooting

### "Redis unavailable" — all requests return 503
Rate limiter and idempotency middleware fail-CLOSED. Ensure Redis is running:
```bash
docker start vigil-redis  # or
docker compose up redis -d
```

### "consent_required" error on review submission
POST to `/v1/consent` first:
```bash
curl -X POST http://localhost:8000/v1/consent \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"purpose":"code_review_processing","version":"1.0","granted":true}'
```

### "consent_version_stale" error
The consent record was made against an older policy version. Re-grant consent
with the current version (check `VIGIL_CONSENT_POLICY_VERSION` env var).

### LLM findings not appearing (only rule findings)
If `VIGIL_LLM_PROVIDER=mock`, LLM findings will be a deterministic placeholder.
Set provider to `openai` and configure `OPENAI_API_KEY` for real analysis.

### Database tables missing
In development mode, tables are auto-created on startup. If using production mode,
run Alembic migrations:
```bash
cd backend
alembic upgrade head
```

---

## API Quick Reference

```bash
# Login (PROTOTYPE_ONLY)
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"secret"}' | jq -r .access_token)

# Grant consent
curl -X POST http://localhost:8000/v1/consent \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"purpose":"code_review_processing","version":"1.0","granted":true}'

# Submit review
RUN_ID=$(curl -s -X POST http://localhost:8000/v1/reviews \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"language":"python","source_text":"import pickle\npickle.loads(data)"}' | jq -r .run_id)

# Get results
curl http://localhost:8000/v1/reviews/$RUN_ID \
  -H "Authorization: Bearer $TOKEN" | jq .

# Delete review
curl -X DELETE http://localhost:8000/v1/reviews/$RUN_ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## Security Checklist (before external deployment)

- [ ] Replace `JWT_SECRET_KEY` with a 256-bit random secret
- [ ] Replace local auth with OIDC provider (see IMPLEMENTATION_NOTES.md [N1])
- [ ] Enable TLS termination at the reverse proxy
- [ ] Set `VIGIL_ENV=production` (disables auto-create tables, enables strict mode)
- [ ] Review CORS origins — remove `localhost`
- [ ] Enable PostgreSQL SSL and restrict network access
- [ ] Enable Redis AUTH and TLS
- [ ] Review source retention policy (`VIGIL_SOURCE_RETENTION_DAYS`)
- [ ] Deploy legal hold policy for compliance requirements

---

## Emergency Operations & Kill Switches (IC10)

### Specialist Agent Kill Switch
To disable all specialist agents in an emergency:
```bash
redis-cli SET vigil:killswitch:multi_agent true
```

To re-enable:
```bash
redis-cli DEL vigil:killswitch:multi_agent
```

When active, `MultiAgentOrchestrator` strictly bypasses A10 (Risk Scoring), A11 (Dependency Risk), A12 (Dataflow Investigation), A13 (Test Generation), and A14 (Executive Summary), executing only the core Phase 1–4 pipeline (A1–A5 and optional A6/A7 patch validation).
