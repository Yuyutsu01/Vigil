# Vigil Enterprise Frontend

> Autonomous Multi-Agent Code Security Review & Automated Remediation Platform

This standalone frontend integrates the public **Marketing Hub & Product Showcase** with the **Autonomous SecOps Console**, communicating with the Vigil FastAPI backend across Phases 1 through 5.1.

---

## 1. Quick Start

### Prerequisites
- Node.js 20.x or higher
- npm 10.x or higher

### Installation & Local Run
```bash
# 1. Install dependencies
npm install

# 2. Configure environment (optional, defaults to http://localhost:8000 in real mode)
cp .env.example .env.local

# 3. Launch development server on port 3000
npm run dev
```

The application will be accessible at:
- **Marketing Landing Page**: [http://localhost:3000](http://localhost:3000)
- **SecOps Console Sign-In**: [http://localhost:3000/login](http://localhost:3000/login)
- **SecOps Operational Console**: [http://localhost:3000/dashboard](http://localhost:3000/dashboard)

---

## 2. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the Vigil FastAPI backend. |
| `NEXT_PUBLIC_API_MODE` | `real` | `real` for live backend requests; `mock` for isolated development fixtures with `[MOCK]` logging. |

> **Production Safety Note**: If `NEXT_PUBLIC_API_MODE=mock` is detected during a production build (`NODE_ENV === 'production'`), the application throws an immediate startup exception to prevent accidental mock data deployment.

---

## 3. Architecture & Safety Guarantees

1. **Dual-Role Frontend**:
   - **Marketing Hub (`/`)**: High-converting editorial landing with WebGL 3D particle vortex, 14-stage DAG visualizer, benchmark metrics, and interactive AST demos.
   - **Autonomous SecOps Console (`/dashboard/*`)**: In-app workspace for code reviews, triage, findings feedback, gVisor microVM patch validation, repo governance, and compliance exports.
2. **Strict Multi-Tenant Isolation**:
   - The frontend automatically injects `X-Tenant-Hint` derived strictly from the decoded JWT payload (`tenant_id`). Manual tampering from user input is prohibited.
3. **Idempotency & Mutation Safety**:
   - Mutating actions (`POST`, `DELETE`) inject a unique UUID v4 `X-Idempotency-Key` header, generated once at click time and preserved across retries.
4. **14-Stage Multi-Agent Breakdown**:
   - 8 LLM Reasoning Agents (`A3`, `A4`, `A6`, `A9`, `A10`, `A12`, `A13`, `A14`)
   - 5 Deterministic Verification Stages (`A1`, `A2`, `A5`, `A8`, `A11`)
   - 1 Hermetic Sandbox Executor (`A7`)
   - 6 Static Tool Adapters (run as sub-processes inside `A2 Static Analysis`).
