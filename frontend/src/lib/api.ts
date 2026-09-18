/**
 * API client for the Vigil backend.
 * Reads the base URL from the NEXT_PUBLIC_API_URL environment variable.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Types ────────────────────────────────────────────────────────────────────

export type Severity = 'Critical' | 'High' | 'Medium' | 'Low' | 'Info';

export interface SourceRange {
  start_line: number | null;
  start_col: number | null;
  end_line: number | null;
  end_col: number | null;
}

export interface Evidence {
  evidence_id: string;
  source_range: SourceRange;
  ast_path: string | null;
  tool_name: string | null;
  rule_id: string | null;
  code_excerpt: string | null;
  evidence_kind: 'ast_node' | 'token_regex' | 'llm_reasoning';
}

export interface Finding {
  finding_id: string;
  run_id: string;
  /** Deterministic sha256(rule_id||ast_path||matched_text_hash||evidence_kind) */
  fingerprint: string;
  origin: 'rule' | 'agent';
  rule_id: string | null;
  category: string;
  severity: Severity;
  confidence: number;
  title: string;
  rationale: string;
  remediation: string;
  evidence: Evidence[];
  status: 'open' | 'accepted' | 'rejected' | 'false_positive';
  /** Always null in Phase 1 — patch generation deferred to Phase 3 */
  patch_candidate_id: null;
}

export interface ReviewRun {
  run_id: string;
  status: 'pending' | 'running' | 'partial' | 'completed' | 'failed' | 'budget_paused' | 'deleted';
  language: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  parked_reason: string | null;
  prompt_version: string | null;
  findings: Finding[];
  finding_count: number;
  timing_ms: number | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/v1/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail?.message || `Login failed: ${res.status}`);
  }
  return res.json();
}

// ── Consent ───────────────────────────────────────────────────────────────────

export async function grantConsent(token: string, version: string, granted: boolean) {
  const res = await fetch(`${API_BASE}/v1/consent`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ purpose: 'code_review_processing', version, granted }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail?.message || `Consent request failed: ${res.status}`);
  }
  return res.json();
}

// ── Reviews ───────────────────────────────────────────────────────────────────

export async function createReview(
  token: string,
  language: string,
  sourceText: string
): Promise<{ run_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/v1/reviews`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ language, source_text: sourceText }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err?.detail;
    if (detail?.code === 'consent_required') {
      throw new Error('CONSENT_REQUIRED');
    }
    throw new Error(detail?.message || `Review submission failed: ${res.status}`);
  }
  return res.json();
}

export async function getReview(token: string, runId: string): Promise<ReviewRun> {
  const res = await fetch(`${API_BASE}/v1/reviews/${runId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail?.message || `Failed to fetch review: ${res.status}`);
  }
  return res.json();
}

export async function deleteReview(
  token: string,
  runId: string
): Promise<{ deletion_status: string; audit_id: string }> {
  const res = await fetch(`${API_BASE}/v1/reviews/${runId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail?.message || `Delete failed: ${res.status}`);
  }
  return res.json();
}

export async function submitFeedback(
  token: string,
  runId: string,
  findingId: string,
  payload: { useful?: boolean; disposition?: string; comment?: string }
): Promise<{ feedback_id: string }> {
  const res = await fetch(
    `${API_BASE}/v1/reviews/${runId}/findings/${findingId}/feedback`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail?.message || `Feedback failed: ${res.status}`);
  }
  return res.json();
}

/** Poll a review run until it reaches a terminal status. */
export async function pollReview(
  token: string,
  runId: string,
  maxAttempts = 30,
  intervalMs = 2000
): Promise<ReviewRun> {
  const terminalStatuses = new Set(['completed', 'partial', 'failed', 'budget_paused', 'deleted']);
  for (let i = 0; i < maxAttempts; i++) {
    const run = await getReview(token, runId);
    if (terminalStatuses.has(run.status)) return run;
    if (i < maxAttempts - 1) {
      await new Promise(r => setTimeout(r, intervalMs));
    }
  }
  return getReview(token, runId);
}
