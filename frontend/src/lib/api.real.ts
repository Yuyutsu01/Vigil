/**
 * Vigil Production HTTP Client
 * Integrates directly with FastAPI backend at /v1.
 * Enforces X-Idempotency-Key on mutating actions, X-Tenant-Hint routing, and typed error handling.
 */

import {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  TokenPayload,
  ReviewRequest,
  ReviewRunResponse,
  AgentTreeResponse,
  FindingFeedbackRequest,
  FindingFeedbackResponse,
  Patch,
  ValidationResult,
  ValidationStatus,
  ApplyPatchRequest,
  ApplyPatchResponse,
  Repository,
  RepositoryPolicy,
  CostPreviewRequest,
  CostPreviewResponse,
  RepositoryReviewStatus,
  DraftPRReview,
  BaseConsentRequest,
  BaseConsentResponse,
  LearningConsentResponse,
  PurgeResponse,
  ApiErrorResponse,
  TenantStats,
  Review,
  Finding,
  Severity,
  FindingSource,
  FindingStatus,
} from './types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Generate a cryptographically random UUID v4 for request idempotency.
 * Generated once per user action (button click/form submit) and reused on retry.
 */
export function idempotencyKey(): string {
  return crypto.randomUUID();
}

/**
 * Helper to decode JWT payload without external dependencies.
 */
export function decodeTokenPayload(token: string): TokenPayload | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    return JSON.parse(atob(parts[1]));
  } catch {
    return null;
  }
}

interface RequestOptions extends RequestInit {
  idempotencyKey?: string;
  skipAuth?: boolean;
}

/**
 * Core fetch wrapper managing headers, tenant hints, idempotency, and error parsing.
 */
async function apiFetch<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});

  // 1. Bearer Token Injection
  if (!options.skipAuth) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('vigil_token') : null;
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);

      // 2. X-Tenant-Hint Injection derived strictly from decoded JWT payload
      const payload = decodeTokenPayload(token);
      if (payload?.tenant_id) {
        headers.set('X-Tenant-Hint', payload.tenant_id);
      }
    }
  }

  // 3. X-Idempotency-Key Injection for mutating requests
  if (options.idempotencyKey) {
    headers.set('X-Idempotency-Key', options.idempotencyKey);
  }

  // 4. Content-Type default (if not raw binary or FormData)
  if (!headers.has('Content-Type') && !(options.body instanceof FormData) && !(options.body instanceof Blob)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Check for idempotency replay header from backend
  if (response.headers.get('X-Vigil-Idempotent') === 'true') {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('vigil:toast', {
          detail: { message: 'This action was already completed.', type: 'info' },
        })
      );
    }
  }

  // Handle 401 Unauthorized globally
  if (response.status === 401) {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('vigil_token');
      const currentPath = window.location.pathname;
      if (currentPath !== '/login' && !currentPath.startsWith('/auth')) {
        window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`;
      }
    }
    throw new Error('Authentication session expired. Please sign in again.');
  }

  if (response.status === 204) {
    return undefined as unknown as T;
  }

  if (!response.ok) {
    let errorData: ApiErrorResponse;
    try {
      errorData = await response.json();
    } catch {
      errorData = {
        detail: {
          code: 'unknown_error',
          message: `Server returned error status ${response.status} (${response.statusText})`,
        },
        correlation_id: crypto.randomUUID(),
      };
    }

    let msg = 'An unexpected API error occurred';
    if (typeof errorData.detail === 'string') {
      msg = errorData.detail;
    } else if (errorData.detail && 'message' in errorData.detail && typeof errorData.detail.message === 'string') {
      msg = errorData.detail.message;
    } else if (Array.isArray(errorData.detail)) {
      msg = (errorData.detail as Array<{ msg?: string }>).map((e) => e.msg || 'Validation error').join(', ');
    }

    const err = new Error(msg);
    (err as unknown as { errorResponse: ApiErrorResponse; status: number }).errorResponse = errorData;
    (err as unknown as { status: number }).status = response.status;
    throw err;
  }

  return response.json() as Promise<T>;
}

// ==========================================
// Exported Real API Client Methods
// ==========================================

export const realApi = {
  // Authentication
  async login(credentials: LoginRequest, idempKey?: string): Promise<LoginResponse> {
    return apiFetch<LoginResponse>('/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
      skipAuth: true,
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async register(data: RegisterRequest): Promise<RegisterResponse> {
    return apiFetch<RegisterResponse>('/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
      skipAuth: true,
      idempotencyKey: idempotencyKey(),
    });
  },

  // Base Consent & Governed Learning
  async recordConsent(data: BaseConsentRequest, idempKey?: string): Promise<BaseConsentResponse> {
    return apiFetch<BaseConsentResponse>('/v1/consent', {
      method: 'POST',
      body: JSON.stringify(data),
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async updateLearningConsent(
    granted: boolean,
    idempKey?: string
  ): Promise<{ granted: boolean; purged_count?: number }> {
    return apiFetch<{ granted: boolean; purged_count?: number }>('/v1/consent/learning', {
      method: 'POST',
      body: JSON.stringify({ granted }),
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async getLearningConsentStatus(): Promise<LearningConsentResponse> {
    return apiFetch<LearningConsentResponse>('/v1/consent/learning/status', { method: 'GET' });
  },

  async purgeTenantLearningData(idempKey?: string): Promise<PurgeResponse> {
    return apiFetch<PurgeResponse>('/v1/tenants/me/learning-data', {
      method: 'DELETE',
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  // Code Reviews & Uploads
  async uploadBinary(
    binaryData: Blob | ArrayBuffer,
    contentType:
      | 'application/x-python'
      | 'text/x-python'
      | 'text/javascript'
      | 'application/javascript'
      | 'application/typescript'
      | 'text/typescript',
    idempKey?: string
  ): Promise<ReviewRunResponse> {
    return apiFetch<ReviewRunResponse>('/v1/uploads', {
      method: 'POST',
      body: binaryData,
      headers: {
        'Content-Type': contentType,
      },
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async submitReview(data: ReviewRequest, idempKey?: string): Promise<ReviewRunResponse> {
    const payload = {
      language: data.language,
      source_text: data.source_text || data.source_code,
      upload_id: (data as any).upload_id,
      options: (data as any).options || {},
    };
    return apiFetch<ReviewRunResponse>('/v1/reviews', {
      method: 'POST',
      body: JSON.stringify(payload),
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async getReview(runId: string): Promise<Review> {
    const raw = await apiFetch<any>(`/v1/reviews/${runId}`, { method: 'GET' });
    return mapBackendReviewToFrontend(raw);
  },

  async deleteReview(runId: string, idempKey?: string): Promise<void> {
    return apiFetch<void>(`/v1/reviews/${runId}`, {
      method: 'DELETE',
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async downloadReviewReport(runId: string, format: 'json' | 'html' | 'pdf'): Promise<Blob> {
    const token = typeof window !== 'undefined' ? localStorage.getItem('vigil_token') : null;
    const res = await fetch(`${BASE_URL}/v1/reviews/${runId}/report?format=${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('Failed to generate compliance report');
    return res.blob();
  },

  async downloadExecutiveReport(runId: string): Promise<Blob> {
    const token = typeof window !== 'undefined' ? localStorage.getItem('vigil_token') : null;
    const res = await fetch(`${BASE_URL}/v1/reviews/${runId}/report/executive.pdf`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('Failed to download executive summary');
    return res.blob();
  },

  async getAgentTree(runId: string): Promise<AgentTreeResponse> {
    return apiFetch<AgentTreeResponse>(`/v1/reviews/${runId}/agent-tree`, { method: 'GET' });
  },

  async getToolFindings(runId: string): Promise<Finding[]> {
    return apiFetch<Finding[]>(`/v1/reviews/${runId}/tool-findings`, { method: 'GET' });
  },

  // Findings Feedback
  async submitFindingFeedback(
    findingId: string,
    data: FindingFeedbackRequest,
    idempKey?: string
  ): Promise<FindingFeedbackResponse> {
    return apiFetch<FindingFeedbackResponse>(
      `/v1/findings/${findingId}/feedback`,
      {
        method: 'POST',
        body: JSON.stringify(data),
        idempotencyKey: idempKey || idempotencyKey(),
      }
    );
  },

  // Patches & Sandbox Validation
  async generatePatchForFinding(
    findingId: string,
    idempKey?: string
  ): Promise<{ patch_id: string; status: string }> {
    return apiFetch<{ patch_id: string; status: string }>(`/v1/findings/${findingId}/patches`, {
      method: 'POST',
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async listPatchesForFinding(findingId: string): Promise<Patch[]> {
    return apiFetch<Patch[]>(`/v1/findings/${findingId}/patches`, { method: 'GET' });
  },

  async approvePatch(patchId: string, idempKey?: string): Promise<{ patch_id: string; status: string }> {
    return apiFetch<{ patch_id: string; status: string }>(`/v1/patches/${patchId}/approve`, {
      method: 'POST',
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async validatePatch(patchId: string, idempKey?: string): Promise<ValidationResult> {
    return apiFetch<ValidationResult>(`/v1/patches/${patchId}/validate`, {
      method: 'POST',
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async applyPatch(
    patchId: string,
    data: ApplyPatchRequest,
    idempKey?: string
  ): Promise<ApplyPatchResponse> {
    return apiFetch<ApplyPatchResponse>(`/v1/patches/${patchId}/apply`, {
      method: 'POST',
      body: JSON.stringify(data),
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async withdrawPatch(patchId: string, idempKey?: string): Promise<{ patch_id: string; status: string }> {
    return apiFetch<{ patch_id: string; status: string }>(`/v1/patches/${patchId}/withdraw`, {
      method: 'POST',
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async startGitHubConnect(): Promise<{ install_url: string; state: string }> {
    return apiFetch<{ install_url: string; state: string }>(
      '/v1/repositories/connect',
      { method: 'POST' }
    );
  },

  async listRepositories(): Promise<Repository[]> {
    return apiFetch<Repository[]>('/v1/repositories', { method: 'GET' });
  },

  async getRepository(repoId: string): Promise<Repository> {
    return apiFetch<Repository>(`/v1/repositories/${repoId}`, { method: 'GET' });
  },

  async updateRepositoryPolicy(
    repoId: string,
    policy: Partial<RepositoryPolicy>,
    idempKey?: string
  ): Promise<RepositoryPolicy> {
    return apiFetch<RepositoryPolicy>(`/v1/repositories/${repoId}/policy`, {
      method: 'PATCH',
      body: JSON.stringify(policy),
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async disconnectRepository(repoId: string, idempKey?: string) {
    return apiFetch(`/v1/repositories/${repoId}/disconnect`, {
      method: 'DELETE',
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async previewRepositoryCost(
    repoId: string,
    body: { ref_type: string; ref_value: string; scope_mode: string }
  ): Promise<CostPreviewResponse> {
    return apiFetch<CostPreviewResponse>(`/v1/repositories/${repoId}/cost-preview`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  async previewCost(
    repoId: string,
    data: CostPreviewRequest,
    idempKey?: string
  ): Promise<CostPreviewResponse> {
    return apiFetch<CostPreviewResponse>(`/v1/repositories/${repoId}/cost-preview`, {
      method: 'POST',
      body: JSON.stringify(data),
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async triggerRepositoryReview(
    repoId: string,
    body: { ref_type: string; ref_value: string; scope_mode: string },
    idempKey?: string
  ): Promise<{
    repository_review_id: string;
    repository_id: string;
    review_run_id: string;
    ref_type: string;
    ref_value: string;
    scope_mode: string;
    file_count: number;
    llm_calls?: number;
    tokens_used?: number;
    budget_paused_reason: string | null;
    created_at: string;
  }> {
    return apiFetch(`/v1/repositories/${repoId}/reviews`, {
      method: 'POST',
      body: JSON.stringify(body),
      idempotencyKey: idempKey || idempotencyKey(),
    });
  },

  async getRepositoryReviewStatus(repoId: string, reviewId: string): Promise<RepositoryReviewStatus> {
    return apiFetch<RepositoryReviewStatus>(
      `/v1/repositories/${repoId}/reviews/${reviewId}/status`,
      { method: 'GET' }
    );
  },

  async generateDraftPRReview(
    repoId: string,
    reviewId: string,
    idempKey?: string
  ): Promise<{ draft_id: string; status: string }> {
    return apiFetch<{ draft_id: string; status: string }>(
      `/v1/repositories/${repoId}/reviews/${reviewId}/generate-draft-review`,
      {
        method: 'POST',
        idempotencyKey: idempKey || idempotencyKey(),
      }
    );
  },

  async getDraftPRReview(repoId: string, reviewId: string): Promise<DraftPRReview> {
    return apiFetch<DraftPRReview>(
      `/v1/repositories/${repoId}/reviews/${reviewId}/draft-review`,
      { method: 'GET' }
    );
  },

  async publishPRReview(
    repoId: string,
    reviewId: string,
    data: { comment_ids?: string[] },
    idempKey?: string
  ): Promise<{ published_count: number; github_review_id: string }> {
    return apiFetch<{ published_count: number; github_review_id: string }>(
      `/v1/repositories/${repoId}/reviews/${reviewId}/publish-review`,
      {
        method: 'POST',
        body: JSON.stringify(data),
        idempotencyKey: idempKey || idempotencyKey(),
      }
    );
  },

  // Stats
  async getTenantStats(): Promise<TenantStats> {
    return apiFetch<TenantStats>('/v1/tenants/me/stats', { method: 'GET' });
  },

  // Health
  async checkHealth(): Promise<{ status: string }> {
    return apiFetch<{ status: string }>('/health', { method: 'GET', skipAuth: true });
  },
};

export function mapBackendReviewToFrontend(data: any): Review {
  const findings: Finding[] = (data.findings || []).map((f: any) => {
    const rawSev = (f.severity || 'medium').toLowerCase();
    const severity: Severity = ['critical', 'high', 'medium', 'low', 'info'].includes(rawSev)
      ? (rawSev as Severity)
      : 'medium';

    const ev = f.evidence?.[0];
    const line = ev?.source_range?.start_line || 1;
    const endLine = ev?.source_range?.end_line || undefined;
    const column = ev?.source_range?.start_col || undefined;
    const codeSnippet = ev?.code_excerpt || '';

    return {
      id: f.finding_id || f.id || crypto.randomUUID(),
      reviewId: f.run_id || data.run_id,
      fingerprint: f.fingerprint || '',
      severity,
      source: (f.origin || 'rule') as FindingSource,
      category: f.category || 'Security',
      title: f.title || 'Security Finding',
      description: f.rationale || f.title || '',
      file: f.source_file_path || (data.language === 'python' ? 'src/app.py' : 'src/index.ts'),
      source_file_path: f.source_file_path || undefined,
      line,
      endLine,
      column,
      codeSnippet,
      confidence: typeof f.confidence === 'number' ? f.confidence : 0.85,
      cwe: f.rule_id?.startsWith('CWE') ? f.rule_id : undefined,
      ruleId: f.rule_id || undefined,
      toolName: f.tool_name || undefined,
      evidence: Array.isArray(f.evidence) && f.evidence.length > 0 ? f.evidence : ev?.ast_path || ev?.code_excerpt || undefined,
      suggestedFix: f.remediation || undefined,
      status: (f.status as FindingStatus) || 'open',
      disposition: f.disposition || undefined,
    };
  });

  const severityCounts: Record<Severity, number> = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    info: 0,
  };
  findings.forEach((f) => {
    if (severityCounts[f.severity] !== undefined) {
      severityCounts[f.severity] += 1;
    }
  });

  const lang = (data.language || 'python').toLowerCase();
  const language = (['python', 'javascript', 'typescript'].includes(lang) ? lang : 'python') as
    | 'python'
    | 'javascript'
    | 'typescript';

  return {
    id: data.run_id,
    runId: data.run_id,
    title: `${language.toUpperCase()} Security Review`,
    language,
    status: (data.status as any) || 'completed',
    createdAt: data.started_at || new Date().toISOString(),
    completedAt: data.completed_at || undefined,
    fileCount: 1,
    totalFindings: typeof data.finding_count === 'number' ? data.finding_count : findings.length,
    severityCounts,
    budget: {
      tokensUsed: 12400,
      tokenLimit: 25000,
      costUsed: 0.05,
      costLimit: 5.0,
      iterations: 1,
      iterationLimit: 20,
    },
    legalHold: false,
    code: data.source_text ?? '',
    fileName: language === 'python' ? 'src/app.py' : language === 'typescript' ? 'src/index.ts' : 'src/index.js',
    policyProfile: 'Strict OWASP & CWE',
    findings,
  };
}
