# Future Work — Deferred from Phase 1

These items were intentionally omitted from Phase 1 (M1). They are NOT
required for any Phase 1 acceptance criterion. Re-introduce them when
the milestone below demands it. Do not re-invent them from scratch.

## Phase 2 (M2) — Static Analysis Adapters & Reports
- **Deterministic finding fingerprints.**
  Replace `(rule_id, source_range)` dedup with a stable SHA-256 hash
  (rule_id + AST path + matched-text hash). Required for cross-run
  trend analysis in evaluation dashboards (FR-102) and future SARIF
  `partialFingerprints`.

- **Markdown prompts (`prompts/*.md`).**
  Migrate from `agents/prompts.py` string constants to versioned
  markdown files hashed at startup. Required for auditable prompt
  diffs in PRs and `prompt_version` recording on every ReviewRun.

## Phase 3 (M3) — Repository Integration
- **Policy wrapper around LLM calls.**
  Introduce `RuntimeSettings` (token budget, wall-clock deadline,
  max iterations) and a `policy.py` supervisor. Required when repo
  context makes LLM costs unpredictable.

## Phase 4 (M4) — Sandbox Validation
- **`SandboxRuntime` interface.**
  Define abstract runtime (`create_or_reuse`, `start`, `execute`,
  `cleanup`) before wiring any sandbox calls into the orchestrator.

## Phase 5 (M5) — Multi-Agent Orchestration
- **Think/act/observe agent loop.**
  Restructure `nodes.py` pipeline into a loop with an outer policy
  layer. Required when specialist agents (triage, dataflow,
  dependency) run in parallel.