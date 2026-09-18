# Triage Rules — Deterministic Deduplication and Ranking

**TRIAGE IS DETERMINISTIC. NO LLM IS INVOKED DURING TRIAGE.**

This document describes the exact algorithm used by `capability_triage()` in
`agents/capabilities.py` and `services/triage_service.py`.

---

## Algorithm

### Step 1 — Convert LLM Findings to DetectedFinding Format

LLM raw findings (`RawLLMFinding`) are converted to `DetectedFinding` objects:
- Quality findings are **severity-capped at Medium** (Critical/High → Medium).
- `ast_path` defaults to `line_{N}/llm_reasoning` if not provided.
- `matched_text` defaults to the finding title.

### Step 2 — Compute Fingerprints

Every finding (rule + LLM) gets a fingerprint:

```
fingerprint = sha256(rule_id || ast_path || sha256(matched_text) || evidence_kind)
```

This is **line-shift-invariant**: inserting blank lines above the affected code
does NOT change the fingerprint.

### Step 3 — Deduplicate by Fingerprint

- Rule findings are inserted first into a seen-set.
- LLM findings skip if the fingerprint already exists (rule wins).
- On exact fingerprint collision between two rule findings, the first one wins.

### Step 4 — Sort

Final findings are sorted by:
1. **Severity** (Critical=0 → Info=4) ascending.
2. **Confidence** (0.0–1.0) descending within the same severity.

---

## Severity Cap Rules

| Origin | Allowed Severities |
|--------|-------------------|
| Rule engine (`origin=rule`) | Critical, High, Medium, Low, Info |
| LLM security (`origin=agent`) | Critical, High, Medium, Low, Info |
| LLM quality (`origin=agent`) | **Medium, Low, Info only** |

The cap is enforced in `capability_triage()` before fingerprinting.

---

## Precedence Order

1. Rule engine findings (deterministic, highest trust)
2. LLM security findings (AI-generated, evidence-backed)
3. LLM quality findings (AI-generated, capped at Medium)

On fingerprint collision: rule > llm_security > llm_quality.

---

## Invariants (tested in `tests/unit/test_triage.py`)

- `deduplicate_and_rank(findings) == deduplicate_and_rank(findings)` for any input (AC-4).
- Rule findings never lose to LLM findings on fingerprint collision.
- Quality findings never appear at Critical or High severity.
- Output is always sorted Critical → High → Medium → Low → Info.
