/**
 * Vigil Mock API Module (Development Only)
 * Returns deterministic fixtures and logs [MOCK] to console.
 * Strictly prohibited in production environments.
 */

import {
  LoginRequest,
  LoginResponse,
  ReviewRequest,
  ReviewRunResponse,
  AgentTreeResponse,
  FindingFeedbackRequest,
  FindingFeedbackResponse,
  Patch,
  ValidationResult,
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
  Review,
  Finding,
} from './types';

function logMock(endpoint: string, data?: unknown) {
  // eslint-disable-next-line no-console
  console.log(`[MOCK] Calling ${endpoint}`, data ? { payload: data } : '');
}

export const mockApi = {
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    logMock('/v1/auth/login', { email: credentials.email });
    return {
      access_token: 'mock-jwt-token-dev-mode',
      token_type: 'bearer',
      expires_in: 3600,
      tenant_id: 'tenant-dev-12345',
      role: 'admin',
    };
  },

  async recordConsent(data: BaseConsentRequest): Promise<BaseConsentResponse> {
    logMock('/v1/consent', data);
    return {
      consent_id: 'consent-mock-01',
      granted_at: new Date().toISOString(),
      version: data.version,
    };
  },

  async updateLearningConsent(granted: boolean): Promise<{ granted: boolean; purged_count?: number }> {
    logMock('/v1/consent/learning', { granted });
    return { granted, purged_count: granted ? 0 : 42 };
  },

  async getLearningConsentStatus(): Promise<LearningConsentResponse> {
    logMock('/v1/consent/learning/status');
    return { granted: false, updated_at: new Date().toISOString() };
  },

  async purgeTenantLearningData(): Promise<PurgeResponse> {
    logMock('/v1/tenants/me/learning-data');
    return { deleted_count: 42, completed_at: new Date().toISOString() };
  },

  async uploadBinary(binaryData: Blob | ArrayBuffer, contentType: string): Promise<ReviewRunResponse> {
    logMock('/v1/uploads', { contentType });
    return { run_id: 'run-upload-' + Date.now().toString().slice(-4), status: 'queued' };
  },

  async submitReview(data: ReviewRequest): Promise<ReviewRunResponse> {
    logMock('/v1/reviews', { language: data.language });
    return { run_id: 'run-mock-' + Date.now().toString().slice(-4), status: 'queued' };
  },

  async getReview(runId: string): Promise<Review> {
    logMock(`/v1/reviews/${runId}`);
    return {
      id: runId,
      runId: runId,
      title: 'orders-gateway.py Security Scan',
      language: 'python',
      status: 'completed',
      createdAt: new Date().toISOString(),
      fileCount: 1,
      totalFindings: 2,
      severityCounts: { critical: 1, high: 1, medium: 0, low: 0, info: 0 },
      budget: {
        tokensUsed: 84000,
        tokenLimit: 250000,
        costUsed: 0.168,
        costLimit: 5.0,
        iterations: 14,
        iterationLimit: 20,
      },
      legalHold: false,
      code: `import os\nfrom fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get("/orders")\ndef get_orders(status: str):\n    # Untrusted user input flowing to raw SQL\n    query = f"SELECT * FROM orders WHERE status = '{status}'"\n    return {"query": query}`,
      fileName: 'app/routers/orders.py',
      policyProfile: 'Strict OWASP & CWE',
    };
  },

  async deleteReview(runId: string): Promise<void> {
    logMock(`/v1/reviews/${runId}`);
  },

  async downloadReviewReport(runId: string, format: 'json' | 'html' | 'pdf'): Promise<Blob> {
    logMock(`/v1/reviews/${runId}/report?format=${format}`);
    return new Blob([`Vigil Audit Report for Run ${runId}`], { type: 'text/plain' });
  },

  async downloadExecutiveReport(runId: string): Promise<Blob> {
    logMock(`/v1/reviews/${runId}/report/executive.pdf`);
    return new Blob([`Vigil Executive Summary for Run ${runId}`], { type: 'application/pdf' });
  },

  async getAgentTree(runId: string): Promise<AgentTreeResponse> {
    logMock(`/v1/reviews/${runId}/agent-tree`);
    return {
      coordination_id: 'coord-' + runId,
      review_run_id: runId,
      status: 'completed',
      total_tokens_consumed: 84000,
      total_wall_clock_ms: 1840,
      failed_agents: [],
      agents: [
        { task_id: 't-1', agent_name: 'A1 Intake Parser', stage_type: 'deterministic', status: 'completed', duration_ms: 45, tokens_consumed: 0 },
        { task_id: 't-2', agent_name: 'A2 Static Analysis', stage_type: 'deterministic', status: 'completed', duration_ms: 110, tokens_consumed: 0 },
        { task_id: 't-3', agent_name: 'A3 Security Reasoner', stage_type: 'llm_agent', status: 'completed', duration_ms: 620, tokens_consumed: 32000 },
        { task_id: 't-4', agent_name: 'A4 Quality Reasoner', stage_type: 'llm_agent', status: 'completed', duration_ms: 310, tokens_consumed: 18000 },
        { task_id: 't-5', agent_name: 'A5 Finding Triage', stage_type: 'deterministic', status: 'completed', duration_ms: 60, tokens_consumed: 0 },
        { task_id: 't-6', agent_name: 'A6 Patch Synthesizer', stage_type: 'llm_agent', status: 'completed', duration_ms: 540, tokens_consumed: 24000 },
        { task_id: 't-7', agent_name: 'A7 gVisor Sandbox', stage_type: 'sandbox', status: 'completed', duration_ms: 155, tokens_consumed: 10000 },
      ],
    };
  },

  async getToolFindings(runId: string): Promise<Finding[]> {
    logMock(`/v1/reviews/${runId}/tool-findings`);
    return [];
  },

  async submitFindingFeedback(findingId: string, data: FindingFeedbackRequest): Promise<FindingFeedbackResponse> {
    logMock(`/v1/findings/${findingId}/feedback`, data);
    return {
      feedback_id: 'fb-' + Date.now().toString().slice(-4),
      finding_id: findingId,
      disposition: data.disposition,
    };
  },

  async generatePatchForFinding(findingId: string): Promise<{ patch_id: string; status: string }> {
    logMock(`/v1/findings/${findingId}/patches`);
    return { patch_id: 'patch-' + Date.now().toString().slice(-4), status: 'completed' };
  },

  async listPatchesForFinding(findingId: string): Promise<Patch[]> {
    logMock(`/v1/findings/${findingId}/patches`);
    return [
      {
        patch_id: 'patch-cwe89-01',
        finding_id: findingId,
        target_file: 'app/routers/orders.py',
        unified_diff: `--- a/app/routers/orders.py\n+++ b/app/routers/orders.py\n@@ -5,2 +5,2 @@\n-    query = f"SELECT * FROM orders WHERE status = '{status}'"\n+    query = "SELECT * FROM orders WHERE status = %s"\n`,
        rationale: 'Replaced format string query with parameterized SQL bindings.',
        status: 'approved',
        created_at: new Date().toISOString(),
        backward_compatible: true,
      },
    ];
  },

  async approvePatch(patchId: string): Promise<{ patch_id: string; status: string }> {
    logMock(`/v1/patches/${patchId}/approve`);
    return { patch_id: patchId, status: 'approved' };
  },

  async validatePatch(patchId: string): Promise<ValidationResult> {
    logMock(`/v1/patches/${patchId}/validate`);
    return {
      validation_id: 'val-' + Date.now().toString().slice(-4),
      status: 'completed',
      verdict: 'passed',
      stdout_log: 'Running gVisor isolated test suite...\npytest test_orders.py: 14 passed in 0.42s.\nAST syntax clean, no regressions detected.',
      stderr_log: '',
      execution_time_ms: 420,
      checks: [
        { name: 'Tree-sitter AST Parse', exit_code: 0, passed: true },
        { name: 'gVisor MicroVM Sandbox', exit_code: 0, passed: true },
        { name: 'Unit Test Reproduction', exit_code: 0, passed: true },
      ],
    };
  },

  async applyPatch(patchId: string, data: ApplyPatchRequest): Promise<ApplyPatchResponse> {
    logMock(`/v1/patches/${patchId}/apply`, data);
    return {
      patch_id: patchId,
      status: 'applied',
      pr_url: 'https://github.com/enterprise/orders/pull/104',
      commit_sha: '7f9a2b4',
    };
  },

  async withdrawPatch(patchId: string): Promise<{ patch_id: string; status: string }> {
    logMock(`/v1/patches/${patchId}/withdraw`);
    return { patch_id: patchId, status: 'withdrawn' };
  },

  async connectRepository(data: { repo_name: string; default_branch?: string }): Promise<Repository> {
    logMock('/v1/repositories/connect', data);
    return {
      repository_id: 'repo-' + Date.now().toString().slice(-4),
      repo_name: data.repo_name,
      default_branch: data.default_branch || 'main',
      is_active: true,
      connected_at: new Date().toISOString(),
    };
  },

  async listRepositories(): Promise<Repository[]> {
    logMock('/v1/repositories');
    return [
      {
        repository_id: 'repo-orders-core',
        repo_name: 'acme-corp/order-service',
        default_branch: 'main',
        is_active: true,
        connected_at: '2026-09-18T10:00:00Z',
      },
      {
        repository_id: 'repo-auth-gateway',
        repo_name: 'acme-corp/auth-gateway',
        default_branch: 'main',
        is_active: true,
        connected_at: '2026-09-18T09:30:00Z',
      },
    ];
  },

  async getRepository(repoId: string): Promise<Repository> {
    logMock(`/v1/repositories/${repoId}`);
    return {
      repository_id: repoId,
      repo_name: 'acme-corp/order-service',
      default_branch: 'main',
      is_active: true,
      connected_at: '2026-09-18T10:00:00Z',
    };
  },

  async updateRepositoryPolicy(repoId: string, policy: Partial<RepositoryPolicy>): Promise<RepositoryPolicy> {
    logMock(`/v1/repositories/${repoId}/policy`, policy);
    return {
      policy_id: 'pol-' + repoId,
      min_severity: policy.min_severity || 'high',
      enable_specialist_risk_scoring: policy.enable_specialist_risk_scoring ?? true,
      enable_dependency_risk: policy.enable_dependency_risk ?? true,
      enable_dataflow_investigation: policy.enable_dataflow_investigation ?? true,
      enable_test_generation_agent: policy.enable_test_generation_agent ?? true,
      enable_executive_summary: policy.enable_executive_summary ?? true,
      enable_bandit: policy.enable_bandit ?? true,
      enable_ruff: policy.enable_ruff ?? true,
      enable_semgrep: policy.enable_semgrep ?? true,
      require_human_approval_for_pr_review: policy.require_human_approval_for_pr_review ?? true,
    };
  },

  async disconnectRepository(repoId: string): Promise<{ status: string; repository_id: string }> {
    logMock(`/v1/repositories/${repoId}/disconnect`);
    return { status: 'disconnected', repository_id: repoId };
  },

  async previewCost(repoId: string, data: CostPreviewRequest): Promise<CostPreviewResponse> {
    logMock(`/v1/repositories/${repoId}/cost-preview`, data);
    return {
      estimated_token_cost: 45000,
      estimated_usd_cost: 0.09,
      file_count: 12,
      lines_of_code: 1420,
    };
  },

  async triggerRepositoryReview(repoId: string): Promise<{ review_id: string; status: string }> {
    logMock(`/v1/repositories/${repoId}/reviews`);
    return { review_id: 'rev-repo-' + Date.now().toString().slice(-4), status: 'running' };
  },

  async getRepositoryReviewStatus(repoId: string, reviewId: string): Promise<RepositoryReviewStatus> {
    logMock(`/v1/repositories/${repoId}/reviews/${reviewId}/status`);
    return {
      review_id: reviewId,
      repository_id: repoId,
      status: 'completed',
      progress_percent: 100,
    };
  },

  async generateDraftPRReview(repoId: string, reviewId: string): Promise<{ draft_id: string; status: string }> {
    logMock(`/v1/repositories/${repoId}/reviews/${reviewId}/generate-draft-review`);
    return { draft_id: 'draft-' + Date.now().toString().slice(-4), status: 'draft' };
  },

  async getDraftPRReview(repoId: string, reviewId: string): Promise<DraftPRReview> {
    logMock(`/v1/repositories/${repoId}/reviews/${reviewId}/draft-review`);
    return {
      draft_id: 'draft-sample',
      repository_id: repoId,
      review_id: reviewId,
      status: 'draft',
      summary: 'Automated Vigil AST Security Review: 1 critical finding detected.',
      comments: [
        {
          path: 'app/routers/orders.py',
          line: 22,
          body: 'Potential SQL Injection (CWE-89). Untrusted user input is concatenated directly into query.',
          cwe: 'CWE-89',
        },
      ],
    };
  },

  async publishPRReview(repoId: string, reviewId: string): Promise<{ published_count: number; github_review_id: string }> {
    logMock(`/v1/repositories/${repoId}/reviews/${reviewId}/publish-review`);
    return { published_count: 1, github_review_id: 'gh-rev-9821' };
  },

  async checkHealth(): Promise<{ status: string }> {
    logMock('/health');
    return { status: 'healthy' };
  },
};
