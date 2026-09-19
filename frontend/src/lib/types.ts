/**
 * Vigil Enterprise Frontend - Comprehensive Type Definitions
 * Exact alignment with FastAPI Backend REST endpoints across Phases 1 to 5.1
 * and complete support for all Console & Workspace view models.
 */

// ==========================================
// Authentication & Tenant Types
// ==========================================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  tenant_id?: string;
  role?: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  organization_name: string;
}

export interface RegisterResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  tenant_id: string;
  user_id: string;
  role: string;
}

export interface TokenPayload {
  sub: string;
  tenant_id: string;
  role: 'admin' | 'analyst' | 'developer';
  exp: number;
  iat: number;
}

export interface Tenant {
  id: string;
  name: string;
  plan: 'Team' | 'Enterprise';
  region: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  avatar: string;
  tenant: Tenant;
  role: 'Security Engineer' | 'Lead Reviewer' | 'Compliance Officer';
}

// ==========================================
// Code Reviews & Submission Types
// ==========================================

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type FindingSeverity = Severity;
export type FindingSource = 'rule' | 'tool' | 'agent' | 'llm';
export type FindingOrigin = 'rule' | 'tool' | 'agent';
export type FindingStatus = 'open' | 'accepted' | 'false_positive' | 'fixed';
export type FindingDisposition = 'accepted' | 'rejected' | 'false_positive';

export type ReviewStatus =
  | 'queued'
  | 'pending'
  | 'running'
  | 'parsing'
  | 'parsing_ast'
  | 'baseline_rules'
  | 'running_static_rules'
  | 'llm_security'
  | 'running_llm_reasoners'
  | 'llm_quality'
  | 'triage'
  | 'triaging_findings'
  | 'complete'
  | 'completed'
  | 'partial'
  | 'budget_paused'
  | 'failed'
  | 'deleted';

export interface ReviewRequest {
  source_code: string;
  source_text?: string;
  language: 'python' | 'javascript' | 'typescript';
  target_file_path?: string;
  manifest_files?: Record<string, string>;
}

export interface ReviewRunResponse {
  run_id: string;
  status: ReviewStatus;
  language?: string;
  findings?: any[];
  finding_count?: number;
  source_text?: string | null;
  started_at?: string;
  completed_at?: string;
}

export interface BudgetStats {
  tokensUsed: number;
  tokenLimit: number;
  costUsed: number;
  costLimit: number;
  iterations: number;
  iterationLimit: number;
}

export interface Review {
  id: string;
  runId: string;
  title: string;
  language: 'python' | 'javascript' | 'typescript';
  status: ReviewStatus;
  createdAt: string;
  completedAt?: string;
  fileCount: number;
  totalFindings: number;
  severityCounts: Record<Severity, number>;
  budget: BudgetStats;
  deadlineAt?: string;
  legalHold: boolean;
  code: string;
  fileName: string;
  repoFullName?: string;
  refValue?: string;
  policyProfile: 'Default Policy' | 'Strict OWASP & CWE' | 'Custom Enterprise Guard';
  findings?: Finding[];
}

export interface Finding {
  id: string;
  reviewId: string;
  fingerprint: string;
  severity: Severity;
  source: FindingSource;
  category: string;
  title: string;
  description: string;
  file: string;
  source_file_path?: string;
  line: number;
  endLine?: number;
  column?: number;
  codeSnippet: string;
  confidence: number;
  cwe?: string;
  ruleId?: string;
  toolName?: string;
  evidence?: any;
  suggestedFix?: string;
  diffPatch?: {
    original: string[];
    replacement: string[];
  };
  status: FindingStatus;
  disposition?: FindingDisposition;
  userFeedback?: Feedback;
}

export interface Feedback {
  findingId: string;
  helpful: boolean;
  type?: 'helpful' | 'not_helpful' | 'false_positive' | 'incorrect_patch';
  reason?: 'false_positive' | 'not_actionable' | 'duplicate' | 'wrong_severity' | 'other';
  comment?: string;
  submittedAt: string;
}

export interface FindingFeedbackRequest {
  useful: boolean;
  disposition: FindingDisposition;
  comment?: string;
  reason_category?: string;
}

export interface FindingFeedbackResponse {
  feedback_id: string;
  finding_id: string;
  disposition: FindingDisposition;
}

// ==========================================
// 14-Stage Multi-Agent Tree Telemetry
// ==========================================

export type AgentStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'queued' | 'active' | 'idle';

export interface AgentNode {
  task_id: string;
  agent_name: string;
  stage_type: 'llm_agent' | 'deterministic' | 'sandbox' | 'tool_adapter';
  status: AgentStatus;
  duration_ms: number;
  tokens_consumed: number;
  error_message?: string | null;
  started_at?: string;
  completed_at?: string;
}

export interface AgentTreeResponse {
  coordination_id: string;
  review_run_id: string;
  status: ReviewStatus;
  total_tokens_consumed: number;
  total_wall_clock_ms: number;
  failed_agents: string[];
  agents: AgentNode[];
}

export interface AgentRun {
  id: string;
  type: 'triage' | 'dependency' | 'dataflow' | 'testing' | 'report';
  name: string;
  status: 'queued' | 'running' | 'complete' | 'failed' | 'active' | 'idle';
  startedAt: string;
  completedAt?: string;
  cost: number;
  latencyMs: number;
  decisionExplanation: string;
  role?: string;
  model?: string;
  findingsProduced?: number;
  avgExecutionTime?: string;
  description?: string;
}

// ==========================================
// Patches & Sandbox Validation Types
// ==========================================

export type PatchStatus = 'draft' | 'validating' | 'approved' | 'withdrawn' | 'applied' | 'pending' | 'running' | 'passed' | 'failed' | 'tested';
export type ValidationVerdict = 'passed' | 'failed' | 'error' | 'timeout';

export interface Patch {
  patch_id: string;
  finding_id: string;
  unified_diff: string;
  rationale: string;
  status: PatchStatus;
  created_at: string;
  target_file: string;
  backward_compatible: boolean;
}

export interface ValidationCheck {
  name: string;
  exit_code: number;
  passed: boolean;
}

export interface ValidationResult {
  validation_id: string;
  status: 'completed' | 'failed';
  verdict: ValidationVerdict;
  stdout_log: string; // First 4 KB inline
  stderr_log: string; // First 4 KB inline
  stdout_ref?: string; // Reference for full log download
  stderr_ref?: string; // Reference for full log download
  execution_time_ms: number;
  checks: ValidationCheck[];
}

export interface ValidationStatus {
  patch_id: string;
  status: 'idle' | 'validating' | 'completed' | 'failed';
  validation_id?: string;
}

export interface ApplyPatchRequest {
  target_branch: string;
  commit_message: string;
}

export interface ApplyPatchResponse {
  patch_id: string;
  status: 'applied';
  pr_url: string;
  commit_sha: string;
}

export interface PatchCandidate {
  id: string;
  reviewId: string;
  findingId: string;
  title: string;
  diff: string;
  status: 'pending' | 'running' | 'passed' | 'failed' | 'applied' | 'tested';
  sandbox?: {
    cpu: number;
    memory: number;
    networkEgress: number;
    logs: string;
    isolationType: 'gVisor MicroVM' | 'Firecracker Sandboxed Container';
  };
}

export interface PatchProposal {
  id: string;
  relatedReviewId: string;
  title: string;
  severity: Severity;
  cwe: string;
  targetFile: string;
  linesAffected: string;
  explanation: string;
  diffSnippet: string;
}

// ==========================================
// GitHub Repositories & Governance Types
// ==========================================

export interface Repository {
  repository_id: string;
  full_name?: string;
  repo_name?: string;
  default_branch: string;
  is_connected?: boolean;
  is_active?: boolean;
  connected_at?: string;
  created_at?: string;
  last_review_at?: string;
  policy?: any;
}

export interface GitHubRepo {
  id: string;
  fullName: string;
  defaultBranch: string;
  policyScope: string;
  lastReviewStatus: 'clean' | 'findings_pending' | 'blocked';
  pullRequestsCount: number;
  automatedPRGate: boolean;
}

export interface RepositoryPolicy {
  policy_id: string;
  min_severity: FindingSeverity;
  enable_specialist_risk_scoring: boolean;
  enable_dependency_risk: boolean;
  enable_dataflow_investigation: boolean;
  enable_test_generation_agent: boolean;
  enable_executive_summary: boolean;
  enable_bandit: boolean;
  enable_ruff: boolean;
  enable_semgrep: boolean;
  require_human_approval_for_pr_review: boolean;
}

export interface CostPreviewRequest {
  ref_type: 'branch' | 'commit' | 'tag';
  ref_value: string;
  scope_mode: 'diff_only' | 'full_repo';
}

export interface CostPreviewResponse {
  file_count: number;
  total_bytes?: number;
  estimated_input_tokens?: number;
  estimated_output_tokens?: number;
  estimated_cost_usd?: number;
  cost_cap_usd?: number;
  exceeds_cap?: boolean;
  within_budget?: boolean;
  estimated_token_cost?: number;
  estimated_usd_cost?: number;
  lines_of_code?: number;
}

export interface RepositoryReviewStatus {
  review_id: string;
  repository_id: string;
  status: ReviewStatus;
  progress_percent: number;
}

export interface DraftPRComment {
  path: string;
  line: number;
  body: string;
  cwe?: string;
}

export interface DraftPRReview {
  draft_id: string;
  repository_id: string;
  review_id: string;
  status: 'draft' | 'published';
  summary: string;
  comments: DraftPRComment[];
}

export interface PullRequestReview {
  id: string;
  reviewId: string;
  prNumber: number;
  title: string;
  repository: string;
  branch: string;
  commitSha: string;
  author: string;
  severityCounts: Record<Severity, number>;
  ciStatus: 'passed' | 'blocked';
}

// ==========================================
// Reports & Compliance Types
// ==========================================

export interface ComplianceReport {
  id: string;
  title: string;
  framework: string;
  target: string;
  auditedBy: string;
  auditedFiles: number;
  totalFindings: number;
  generatedAt: string;
  status: 'Passed' | 'Action Required' | 'Certified';
  sha256Digest: string;
}

export interface Report {
  id: string;
  reviewId: string;
  reviewTitle: string;
  formats: ('json' | 'html' | 'pdf')[];
  executiveSummary: string;
  summary?: string;
  createdAt: string;
  generatedAt?: string;
  complianceScore: number;
  threatLevel: 'Low' | 'Moderate' | 'Elevated' | 'Critical';
  adaptersUsed: string[];
}

// ==========================================
// Evaluations & Benchmarks Types
// ==========================================

export interface EvaluationConfusionMatrix {
  tp: number;
  fp: number;
  tn: number;
  fn: number;
}

export interface EvaluationReport {
  eval_run_id: string;
  dataset_name: string;
  precision: number;
  recall: number;
  f1_score: number;
  confusion_matrix: EvaluationConfusionMatrix;
  evaluation_date: string;
}

export interface EvaluationRun {
  id: string;
  name?: string;
  corpusVersion: string;
  precision: number;
  recall: number;
  f1: number;
  falsePositives: number;
  falseNegatives: number;
  adapterCoverage: Record<string, number>;
  createdAt: string;
  testedAt?: string;
  status: 'passed' | 'review_required';
  metrics?: {
    precision: number;
    recall: number;
    f1: number;
    falsePositiveRate: number;
  };
  corporaBreakdown?: {
    corpus: string;
    sampleCount: number;
    precision: number;
    recall: number;
    f1: number;
  }[];
}

export interface EvaluationBenchmark {
  suiteName: string;
  overallPrecision: number;
  overallRecall: number;
  f1Score: number;
  falsePositiveRate: number;
  totalVulnerabilitiesEvaluated: number;
  breakdown: {
    category: string;
    sampleCount: number;
    accuracy: number;
    precision: number;
    recall: number;
    falsePositiveRate: number;
  }[];
}

// ==========================================
// Governed Learning & GDPR Consent Types
// ==========================================

export interface BaseConsentRequest {
  purpose: string;
  version: string;
  granted: boolean;
}

export interface BaseConsentResponse {
  consent_id: string;
  granted_at: string;
  version: string;
}

export interface LearningConsentResponse {
  granted: boolean;
  updated_at: string;
}

export interface PurgeResponse {
  deleted_count: number;
  completed_at: string;
}

// ==========================================
export interface TenantStats {
  total_reviews: number;
  total_findings: number;
  findings_by_severity: {
    Critical: number;
    High: number;
    Medium: number;
    Low: number;
    Info: number;
  };
  total_tokens_used: number;
  total_cost_usd: number;
  avg_review_duration_ms: number;
  reviews_last_7_days: number;
  reviews_previous_7_days: number;
}

export interface ReviewStats {
  totalReviews: number;
  totalFindings: number;
  criticalFindings: number;
  highFindings: number;
  falsePositiveRate: number;
  totalCostSpent: number;
  avgReviewTime: string;
}

export type VigilNavSection =
  | 'dashboard'
  | 'reviews'
  | 'new_review'
  | 'compliance'
  | 'evaluation'
  | 'github'
  | 'patches'
  | 'agents'
  | 'settings';


// ==========================================
// Error Response Types
// ==========================================

export interface ApiErrorDetail {
  code: string;
  message: string;
  field_errors?: Record<string, string[]>;
}

export interface ApiErrorResponse {
  detail: ApiErrorDetail;
  correlation_id: string;
}

