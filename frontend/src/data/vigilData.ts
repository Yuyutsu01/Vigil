import {
  Review,
  Finding,
  Report,
  EvaluationRun,
  GitHubRepo,
  PatchCandidate,
  AgentRun,
  User,
  ReviewStats,
  ComplianceReport,
  EvaluationBenchmark,
  PullRequestReview,
  PatchProposal,
} from '../lib/types';

export const CURRENT_USER: User = {
  id: 'usr-904',
  email: 'sec-lead@vigil.internal',
  name: 'Alex Rivera',
  avatar: 'AR',
  role: 'Lead Reviewer',
  tenant: {
    id: 'tnt-acme-corp-42',
    name: 'Acme Systems Security Team',
    plan: 'Enterprise',
    region: 'us-east-1 (SOC2 Type II)',
  },
};

export const SAMPLE_PYTHON_CODE = `import os
import pickle
import sqlite3
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

app = FastAPI(title="Order Gateway")
DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///prod.db")

class UserQuery(BaseModel):
    username: str
    include_archived: bool = False

@app.post("/api/v1/users/lookup")
async def get_user_profile(query: UserQuery):
    conn = sqlite3.connect("prod.db")
    cursor = conn.cursor()
    
    # CWE-89: Raw string concatenation in database query
    raw_query = f"SELECT id, username, email, role FROM users WHERE username = '{query.username}'"
    cursor.execute(raw_query)
    record = cursor.fetchone()
    
    if not record:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": record[0], "username": record[1], "role": record[3]}

@app.post("/api/v1/session/restore")
async def restore_session(request: Request):
    payload = await request.body()
    
    # CWE-502: Unsafe deserialization of untrusted stream
    session_data = pickle.loads(payload)
    return {"status": "restored", "session_id": session_data.get("id")}

@app.get("/api/v1/network/diagnostics")
async def run_diagnostics(target_host: str):
    # CWE-78: Improper Neutralization of Special Elements in OS Command
    cmd = f"ping -c 1 {target_host}"
    status = os.system(cmd)
    return {"exit_code": status}

@app.post("/api/v1/token/sign")
async def generate_nonce():
    # CWE-330: Use of insufficiently random values for security
    import random
    nonce = random.randint(100000, 999999)
    return {"nonce": nonce}`;

export const SAMPLE_TYPESCRIPT_CODE = `import jwt from 'jsonwebtoken';
import { Request, Response, NextFunction } from 'express';

// CWE-798: Use of Hard-coded Credentials
const JWT_FALLBACK_SECRET = "super_secret_dev_key_do_not_leak_9921!";
const SECRET_KEY = process.env.JWT_SECRET || JWT_FALLBACK_SECRET;

export interface TokenPayload {
  userId: string;
  role: 'admin' | 'user';
  iat?: number;
}

export function verifyUserToken(req: Request, res: Response, next: NextFunction) {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing bearer token' });
  }

  const token = authHeader.split(' ')[1];
  try {
    // CWE-327: Allowing 'none' algorithm bypass
    const decoded = jwt.verify(token, SECRET_KEY, {
      algorithms: ['HS256', 'none'],
    }) as TokenPayload;

    (req as any).user = decoded;
    next();
  } catch (err) {
    return res.status(403).json({ error: 'Invalid or expired signature' });
  }
}`;

export const INITIAL_FINDINGS: Finding[] = [
  {
    id: 'fnd-89-01',
    reviewId: 'rev-a1b2',
    fingerprint: 'fp-sqli-src-app-l23',
    severity: 'critical',
    source: 'tool',
    toolName: 'Semgrep + Bandit',
    ruleId: 'semgrep.python.lang.security.deserialization.sqli_concat',
    category: 'Injection',
    title: 'SQL Injection via Unsanitized f-string formatting',
    description:
      'User-controlled input `query.username` is directly interpolated into a raw SQL statement via an f-string without parameterized binding, allowing an adversary to bypass authentication or extract sensitive records.',
    file: 'src/app.py',
    line: 23,
    endLine: 24,
    column: 5,
    codeSnippet: `raw_query = f"SELECT id, username, email, role FROM users WHERE username = '{query.username}'"\\ncursor.execute(raw_query)`,
    confidence: 0.98,
    cwe: 'CWE-89',
    evidence:
      'Found AST node `FormattedValue` inside SQL execute call. Dataflow tainted from `query.username` directly to `cursor.execute()`.',
    suggestedFix:
      'Use parameterized queries with placeholders (? or %s) to pass query parameters separately from the command structure.',
    diffPatch: {
      original: [
        'raw_query = f"SELECT id, username, email, role FROM users WHERE username = \'{query.username}\'"',
        'cursor.execute(raw_query)',
      ],
      replacement: [
        'cursor.execute(',
        '    "SELECT id, username, email, role FROM users WHERE username = ?",',
        '    (query.username,)',
        ')',
      ],
    },
    status: 'open',
  },
  {
    id: 'fnd-502-02',
    reviewId: 'rev-a1b2',
    fingerprint: 'fp-pickle-src-app-l34',
    severity: 'critical',
    source: 'rule',
    toolName: 'Bandit B301',
    ruleId: 'bandit.B301.pickle_loads',
    category: 'Deserialization',
    title: 'Arbitrary Code Execution via Insecure pickle.loads()',
    description:
      'The endpoint unpacks raw bytes from the HTTP request body directly with `pickle.loads()`. In Python, unpickling untrusted data allows arbitrary object instantiation and direct Remote Code Execution (RCE) via `__reduce__` exploit payloads.',
    file: 'src/app.py',
    line: 35,
    endLine: 35,
    column: 5,
    codeSnippet: 'session_data = pickle.loads(payload)',
    confidence: 0.99,
    cwe: 'CWE-502',
    evidence:
      'Direct invocation of `pickle.loads` on unverified payload obtained from `await request.body()`. Zero authentication or integrity HMAC check found.',
    suggestedFix:
      'Replace Python pickle serialization with a safe, language-neutral format such as `json.loads()` or cryptographically sign the payload with `itsdangerous.Signer`.',
    diffPatch: {
      original: ['session_data = pickle.loads(payload)'],
      replacement: [
        'import json',
        'try:',
        '    session_data = json.loads(payload.decode("utf-8"))',
        'except (json.JSONDecodeError, UnicodeDecodeError):',
        '    raise HTTPException(status_code=400, detail="Invalid session payload")',
      ],
    },
    status: 'open',
  },
  {
    id: 'fnd-78-03',
    reviewId: 'rev-a1b2',
    fingerprint: 'fp-cmd-src-app-l41',
    severity: 'high',
    source: 'llm',
    toolName: 'Vigil Reasoning Engine',
    ruleId: 'llm.sec.os_system_injection',
    category: 'Command Injection',
    title: 'OS Command Injection via os.system with Raw User Parameter',
    description:
      'The `target_host` parameter is concatenated directly into a shell command passed to `os.system()`. An attacker can pass `; cat /etc/passwd` or `127.0.0.1 && id` to execute arbitrary system binaries in the container runtime.',
    file: 'src/app.py',
    line: 41,
    endLine: 42,
    column: 5,
    codeSnippet: 'cmd = f"ping -c 1 {target_host}"\\nstatus = os.system(cmd)',
    confidence: 0.95,
    cwe: 'CWE-78',
    evidence:
      'LLM Security reasoner detected shell invocation without input neutralization. Regex validation for hostname/IPv4 format is absent.',
    suggestedFix:
      'Use `subprocess.run` with a sequence of arguments rather than a shell string, or strictly sanitize `target_host` against an IP address parser.',
    diffPatch: {
      original: ['cmd = f"ping -c 1 {target_host}"', 'status = os.system(cmd)'],
      replacement: [
        'import ipaddress, subprocess',
        'try:',
        '    ip = str(ipaddress.ip_address(target_host))',
        '    res = subprocess.run(["ping", "-c", "1", ip], capture_output=True, timeout=3)',
        '    status = res.returncode',
        'except ValueError:',
        '    raise HTTPException(status_code=400, detail="Invalid host address")',
      ],
    },
    status: 'open',
  },
  {
    id: 'fnd-330-04',
    reviewId: 'rev-a1b2',
    fingerprint: 'fp-rng-src-app-l49',
    severity: 'medium',
    source: 'rule',
    toolName: 'Bandit B311',
    ruleId: 'bandit.B311.random_module',
    category: 'Cryptography',
    title: 'Cryptographically Weak Pseudo-Random Number Generator',
    description:
      'Standard library `random` module uses Mersenne Twister, which is completely predictable after observing 624 generated values. It must not be utilized for security tokens, nonces, or salts.',
    file: 'src/app.py',
    line: 49,
    endLine: 50,
    column: 5,
    codeSnippet: 'import random\\nnonce = random.randint(100000, 999999)',
    confidence: 0.92,
    cwe: 'CWE-330',
    evidence: 'Inclusion of pseudo-random generator `random.randint` for security nonce.',
    suggestedFix: 'Utilize `secrets` module which interfaces with OS-level CSPRNG (`secrets.randbelow`).',
    diffPatch: {
      original: ['import random', 'nonce = random.randint(100000, 999999)'],
      replacement: ['import secrets', 'nonce = secrets.randbelow(900000) + 100000'],
    },
    status: 'open',
  },
  {
    id: 'fnd-info-05',
    reviewId: 'rev-a1b2',
    fingerprint: 'fp-db-hardcoded-path',
    severity: 'low',
    source: 'tool',
    toolName: 'ESLint / Ruff',
    ruleId: 'ruff.security.sqlite_direct_file',
    category: 'Hardcoded Configuration',
    title: 'Local SQLite File Bound Without Migration or Pooling Layer',
    description:
      'The connection is instantiated directly to `prod.db` inside the request handler, creating file lock contention under concurrent load and bypassing configured `DATABASE_URI`.',
    file: 'src/app.py',
    line: 20,
    endLine: 20,
    column: 5,
    codeSnippet: 'conn = sqlite3.connect("prod.db")',
    confidence: 0.88,
    cwe: 'CWE-1188',
    evidence: 'Direct path literal "prod.db" overrides environment config DATABASE_URI.',
    suggestedFix: 'Reference the global `DATABASE_URI` setting or configure an async database pool.',
    diffPatch: {
      original: ['conn = sqlite3.connect("prod.db")'],
      replacement: ['conn = sqlite3.connect(DATABASE_URI.replace("sqlite:///", ""))'],
    },
    status: 'open',
  },
];

export const INITIAL_REVIEWS: Review[] = [
  {
    id: 'rev-a1b2',
    runId: 'run-984210',
    title: 'Order Gateway Service API',
    fileName: 'src/app.py',
    language: 'python',
    status: 'complete',
    createdAt: '2026-09-18T08:30:12Z',
    completedAt: '2026-09-18T08:30:16Z',
    fileCount: 1,
    totalFindings: 5,
    severityCounts: {
      critical: 2,
      high: 1,
      medium: 1,
      low: 1,
      info: 0,
    },
    budget: {
      tokensUsed: 14820,
      tokenLimit: 25000,
      costUsed: 0.29,
      costLimit: 1.5,
      iterations: 12,
      iterationLimit: 20,
    },
    deadlineAt: '4m 32s remain',
    legalHold: false,
    policyProfile: 'Strict OWASP & CWE',
    code: SAMPLE_PYTHON_CODE,
  },
  {
    id: 'rev-7720b',
    runId: 'run-984180',
    title: 'Identity & JWT Verifier Module',
    fileName: 'src/auth/jwt.ts',
    language: 'typescript',
    status: 'complete',
    createdAt: '2026-09-18T07:15:00Z',
    completedAt: '2026-09-18T07:15:04Z',
    fileCount: 1,
    totalFindings: 2,
    severityCounts: {
      critical: 1,
      high: 1,
      medium: 0,
      low: 0,
      info: 0,
    },
    budget: {
      tokensUsed: 9400,
      tokenLimit: 25000,
      costUsed: 0.18,
      costLimit: 1.5,
      iterations: 8,
      iterationLimit: 20,
    },
    deadlineAt: 'Completed',
    legalHold: true,
    policyProfile: 'Custom Enterprise Guard',
    code: SAMPLE_TYPESCRIPT_CODE,
  },
  {
    id: 'rev-6314c',
    runId: 'run-983994',
    title: 'Checkout Cart Calculator',
    fileName: 'src/cart/calc.js',
    language: 'javascript',
    status: 'complete',
    createdAt: '2026-09-17T19:44:20Z',
    completedAt: '2026-09-17T19:44:23Z',
    fileCount: 1,
    totalFindings: 0,
    severityCounts: {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
      info: 0,
    },
    budget: {
      tokensUsed: 4200,
      tokenLimit: 25000,
      costUsed: 0.08,
      costLimit: 1.5,
      iterations: 4,
      iterationLimit: 20,
    },
    deadlineAt: 'Completed',
    legalHold: false,
    policyProfile: 'Default Policy',
    code: '// Clean review without active vulnerabilities\\nexport function calculateCart(items) { return items.reduce((a, b) => a + b.price, 0); }',
  },
];

export const INITIAL_REPORTS: Report[] = [
  {
    id: 'rep-001',
    reviewId: 'rev-a1b2',
    reviewTitle: 'Order Gateway Service API',
    formats: ['json', 'html', 'pdf'],
    executiveSummary:
      'The Order Gateway review flagged 2 Critical vulnerabilities (CWE-89 SQLi, CWE-502 Arbitrary Pickle Deserialization) and 1 High (CWE-78 Command Injection). Code execution was rejected by Vigil static guard. Remediation patches have been automatically generated for developer inspection.',
    createdAt: '2026-09-18T08:30:18Z',
    complianceScore: 42,
    threatLevel: 'Critical',
    adaptersUsed: ['Semgrep 1.70.0', 'Bandit 1.7.5', 'Vigil LLM Reasoner v4', 'Ruff 0.4.2'],
  },
  {
    id: 'rep-002',
    reviewId: 'rev-7720b',
    reviewTitle: 'Identity & JWT Verifier Module',
    formats: ['json', 'html', 'pdf'],
    executiveSummary:
      'Identity verifier code contains hardcoded credential fallback and allows "none" cryptographic algorithm bypass, enabling token forgery. Marked for immediate remediation prior to staging deployment.',
    createdAt: '2026-09-18T07:15:06Z',
    complianceScore: 68,
    threatLevel: 'Elevated',
    adaptersUsed: ['ESLint Security 3.0', 'Vigil LLM Reasoner v4'],
  },
];

export const INITIAL_EVALUATIONS: EvaluationRun[] = [
  {
    id: 'eval-corp-v4.2',
    corpusVersion: 'CWE-SANS-Bench-v4.2 (1,240 cases)',
    precision: 0.942,
    recall: 0.918,
    f1: 0.93,
    falsePositives: 18,
    falseNegatives: 24,
    adapterCoverage: {
      'Semgrep AST Rules': 0.98,
      'Bandit Python': 0.94,
      'ESLint Security': 0.96,
      'Vigil LLM Reasoning': 0.92,
    },
    createdAt: '2026-09-18T06:00:00Z',
    status: 'passed',
  },
  {
    id: 'eval-corp-v4.1',
    corpusVersion: 'CWE-SANS-Bench-v4.1 (1,150 cases)',
    precision: 0.925,
    recall: 0.894,
    f1: 0.909,
    falsePositives: 26,
    falseNegatives: 33,
    adapterCoverage: {
      'Semgrep AST Rules': 0.96,
      'Bandit Python': 0.91,
      'ESLint Security': 0.94,
      'Vigil LLM Reasoning': 0.88,
    },
    createdAt: '2026-09-15T12:00:00Z',
    status: 'passed',
  },
];

export const INITIAL_REPOS: GitHubRepo[] = [
  {
    id: 'gh-repo-01',
    fullName: 'acme-inc/order-gateway-api',
    defaultBranch: 'main',
    policyScope: 'Strict OWASP & CWE',
    lastReviewStatus: 'findings_pending',
    pullRequestsCount: 3,
    automatedPRGate: true,
  },
  {
    id: 'gh-repo-02',
    fullName: 'acme-inc/auth-service',
    defaultBranch: 'production',
    policyScope: 'Custom Enterprise Guard',
    lastReviewStatus: 'blocked',
    pullRequestsCount: 1,
    automatedPRGate: true,
  },
  {
    id: 'gh-repo-03',
    fullName: 'acme-inc/checkout-ui',
    defaultBranch: 'main',
    policyScope: 'Default Policy',
    lastReviewStatus: 'clean',
    pullRequestsCount: 5,
    automatedPRGate: false,
  },
];

export const INITIAL_PATCHES: PatchCandidate[] = [
  {
    id: 'ptc-01',
    reviewId: 'rev-a1b2',
    findingId: 'fnd-89-01',
    title: 'Replace Raw String Concatenation with Parameterized SQLite Query',
    diff: `--- a/src/app.py\\n+++ b/src/app.py\\n@@ -22,3 +22,3 @@\\n-    raw_query = f"SELECT id, username, email, role FROM users WHERE username = '{query.username}'"\\n-    cursor.execute(raw_query)\\n+    cursor.execute("SELECT id, username, email, role FROM users WHERE username = ?", (query.username,))`,
    status: 'passed',
    sandbox: {
      cpu: 12.4,
      memory: 48,
      networkEgress: 0,
      isolationType: 'gVisor MicroVM',
      logs: '[Vigil Sandbox] Booted isolated container in 48ms.\\n[Test Suite] Running test_user_lookup_sqli_resilience... PASSED\\n[Egress Guard] 0 network bytes emitted (Blocked by policy).\\n[Exit] Status 0.',
    },
  },
  {
    id: 'ptc-02',
    reviewId: 'rev-a1b2',
    findingId: 'fnd-502-02',
    title: 'Replace pickle.loads with Safe JSON Deserialization',
    diff: `--- a/src/app.py\\n+++ b/src/app.py\\n@@ -34,2 +34,4 @@\\n-    session_data = pickle.loads(payload)\\n+    import json\\n+    session_data = json.loads(payload.decode("utf-8"))`,
    status: 'passed',
    sandbox: {
      cpu: 14.1,
      memory: 52,
      networkEgress: 0,
      isolationType: 'Firecracker Sandboxed Container',
      logs: '[Sandbox] Injected malformed pickle RCE payload into test suite.\\n[Sandbox] Exception caught safely as json.JSONDecodeError.\\n[Sandbox] Patch verified successfully.',
    },
  },
];

export const INITIAL_AGENTS: AgentRun[] = [
  {
    id: 'agt-101',
    type: 'triage',
    name: 'Triage & Deduplication Agent',
    status: 'complete',
    startedAt: '08:30:12',
    completedAt: '08:30:13',
    cost: 0.04,
    latencyMs: 380,
    decisionExplanation:
      'Merged raw Semgrep AST warnings with Bandit B608 detections into unified CWE-89 finding.',
  },
  {
    id: 'agt-102',
    type: 'dependency',
    name: 'Dependency & Supply Chain Risk Agent',
    status: 'complete',
    startedAt: '08:30:13',
    completedAt: '08:30:14',
    cost: 0.06,
    latencyMs: 490,
    decisionExplanation:
      'Verified FastAPI 0.110.0 and Pydantic v2 lockfiles against OSV and CVE feeds. No vulnerable transitive packages.',
  },
  {
    id: 'agt-103',
    type: 'dataflow',
    name: 'Dataflow Investigation Agent',
    status: 'complete',
    startedAt: '08:30:14',
    completedAt: '08:30:15',
    cost: 0.09,
    latencyMs: 720,
    decisionExplanation:
      'Traced taint origin from FastAPI route parameter `query.username` across function boundary into `cursor.execute()`.',
  },
  {
    id: 'agt-104',
    type: 'testing',
    name: 'Patch Validation & Sandbox Agent',
    status: 'complete',
    startedAt: '08:30:15',
    completedAt: '08:30:16',
    cost: 0.07,
    latencyMs: 640,
    decisionExplanation:
      'Compiled replacement AST in isolated micro-sandbox. Syntax and parameterized bindings verified clean.',
  },
  {
    id: 'agt-105',
    type: 'report',
    name: 'Report Synthesis & Executive Guard',
    status: 'complete',
    startedAt: '08:30:16',
    completedAt: '08:30:16',
    cost: 0.03,
    latencyMs: 310,
    decisionExplanation:
      'Generated multi-format SARIF/JSON and executive summary. Compliance rating computed as Critical.',
  },
];

export const MOCK_REVIEWS: Review[] = INITIAL_REVIEWS;
export const MOCK_FINDINGS: Finding[] = INITIAL_FINDINGS;

export const INITIAL_STATS: ReviewStats = {
  totalReviews: 3,
  totalFindings: 7,
  criticalFindings: 3,
  highFindings: 2,
  falsePositiveRate: 0.001,
  totalCostSpent: 0.55,
  avgReviewTime: '3.8s',
};

export const COMPLIANCE_REPORTS: ComplianceReport[] = [
  {
    id: 'dos-soc2-q3-2026',
    title: 'SOC2 Type II Continuous Audit Attestation',
    framework: 'SOC2 Type II / Trust Services Criteria',
    target: 'order-gateway-api, auth-service',
    auditedBy: 'Vigil Continuous Compliance Guard',
    auditedFiles: 48,
    totalFindings: 7,
    generatedAt: '2026-09-18T08:30:18Z',
    status: 'Certified',
    sha256Digest: 'a8f5b2149b803f27f8721c5613da826e7b1a4597b830fa9822a101b0f16248cc',
  },
  {
    id: 'dos-iso27001-sec',
    title: 'ISO/IEC 27001 Annex A.14 Secure Engineering Report',
    framework: 'ISO 27001:2022',
    target: 'Full Monorepo (Production Branch)',
    auditedBy: 'Vigil Continuous Compliance Guard',
    auditedFiles: 142,
    totalFindings: 14,
    generatedAt: '2026-09-15T12:00:00Z',
    status: 'Passed',
    sha256Digest: '3c7d91e84a5f36e8b220d912440b8f05b1c5e4a7d6e3f890123456789abcdef0',
  },
  {
    id: 'dos-nist-ssdf-2026',
    title: 'NIST SP 800-218 Secure Software Development Framework (SSDF)',
    framework: 'NIST SSDF v1.1',
    target: 'Microservices & Ingress Endpoints',
    auditedBy: 'Vigil Security Pipeline',
    auditedFiles: 92,
    totalFindings: 9,
    generatedAt: '2026-09-10T16:20:00Z',
    status: 'Certified',
    sha256Digest: 'f94a6e812d05b761c4e2098b1a3c7d5f0e4b8a2134567890abcdef1234567890',
  },
];

export const EVALUATION_BENCHMARK: EvaluationBenchmark = {
  suiteName: 'OWASP Benchmark v1.2 + SEC-Eval v2.4 (Frozen 2,400 Corpus)',
  overallPrecision: 0.984,
  overallRecall: 0.946,
  f1Score: 0.965,
  falsePositiveRate: 0.001,
  totalVulnerabilitiesEvaluated: 2400,
  breakdown: [
    {
      category: 'SQL Injection (CWE-89)',
      sampleCount: 520,
      accuracy: 0.992,
      precision: 0.995,
      recall: 0.988,
      falsePositiveRate: 0.002,
    },
    {
      category: 'Insecure Deserialization (CWE-502)',
      sampleCount: 380,
      accuracy: 0.988,
      precision: 0.991,
      recall: 0.985,
      falsePositiveRate: 0.001,
    },
    {
      category: 'Command Injection (CWE-78)',
      sampleCount: 410,
      accuracy: 0.978,
      precision: 0.982,
      recall: 0.974,
      falsePositiveRate: 0.003,
    },
    {
      category: 'Cryptographic Weakness (CWE-327 / CWE-798)',
      sampleCount: 460,
      accuracy: 0.982,
      precision: 0.989,
      recall: 0.975,
      falsePositiveRate: 0.002,
    },
    {
      category: 'Cross-Site Scripting (CWE-79)',
      sampleCount: 630,
      accuracy: 0.974,
      precision: 0.979,
      recall: 0.968,
      falsePositiveRate: 0.004,
    },
  ],
};

export const PULL_REQUEST_REVIEWS: PullRequestReview[] = [
  {
    id: 'pr-check-492',
    reviewId: 'rev-a1b2',
    prNumber: 492,
    title: 'feat(order): optimize order query with direct SQL cursor',
    repository: 'acme-inc/order-gateway-api',
    branch: 'feat/order-lookup',
    commitSha: '8f4c20e',
    author: 'dev-sarah',
    severityCounts: {
      critical: 2,
      high: 1,
      medium: 1,
      low: 1,
      info: 0,
    },
    ciStatus: 'blocked',
  },
  {
    id: 'pr-check-489',
    reviewId: 'rev-7720b',
    prNumber: 489,
    title: 'refactor(auth): support fallback secret and algorithm override',
    repository: 'acme-inc/auth-service',
    branch: 'fix/token-verification',
    commitSha: 'b19e4a2',
    author: 'dev-alex',
    severityCounts: {
      critical: 1,
      high: 1,
      medium: 0,
      low: 0,
      info: 0,
    },
    ciStatus: 'blocked',
  },
  {
    id: 'pr-check-481',
    reviewId: 'rev-6314c',
    prNumber: 481,
    title: 'perf(cart): memoize calculation and sum logic',
    repository: 'acme-inc/checkout-ui',
    branch: 'perf/cart-calc',
    commitSha: '3d5a1b0',
    author: 'dev-elena',
    severityCounts: {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
      info: 0,
    },
    ciStatus: 'passed',
  },
];

export const PATCH_PROPOSALS: PatchProposal[] = [
  {
    id: 'patch-cwe-89-order',
    relatedReviewId: 'rev-a1b2',
    title: 'Replace Raw f-string with Parameterized SQLite Query',
    severity: 'critical',
    cwe: 'CWE-89',
    targetFile: 'src/app.py',
    linesAffected: '22–24',
    explanation:
      'Removes unsanitized user query interpolation and replaces it with native SQLite positional parameter binding `?`, completely neutralizing SQL injection attempts without performance degradation.',
    diffSnippet: `--- a/src/app.py
+++ b/src/app.py
@@ -23,2 +23,4 @@
-    raw_query = f"SELECT id, username, email, role FROM users WHERE username = '{query.username}'"
-    cursor.execute(raw_query)
+    cursor.execute(
+        "SELECT id, username, email, role FROM users WHERE username = ?",
+        (query.username,)
+    )`,
  },
  {
    id: 'patch-cwe-502-pickle',
    relatedReviewId: 'rev-a1b2',
    title: 'Replace Insecure pickle.loads() with Safe JSON Parser',
    severity: 'critical',
    cwe: 'CWE-502',
    targetFile: 'src/app.py',
    linesAffected: '34–37',
    explanation:
      'Eliminates arbitrary Python object deserialization vectors. Uses strict UTF-8 JSON parsing with graceful exception handling to block RCE exploits.',
    diffSnippet: `--- a/src/app.py
+++ b/src/app.py
@@ -35,1 +35,6 @@
-    session_data = pickle.loads(payload)
+    import json
+    try:
+        session_data = json.loads(payload.decode("utf-8"))
+    except (json.JSONDecodeError, UnicodeDecodeError):
+        raise HTTPException(status_code=400, detail="Invalid session payload")`,
  },
  {
    id: 'patch-cwe-327-jwt',
    relatedReviewId: 'rev-7720b',
    title: 'Disallow "none" Algorithm & Remove Insecure Hardcoded Secret',
    severity: 'critical',
    cwe: 'CWE-327',
    targetFile: 'src/auth/jwt.ts',
    linesAffected: '96–100',
    explanation:
      'Enforces strict HS256 algorithm validation and throws an immediate startup exception if the mandatory JWT_SECRET environment variable is missing.',
    diffSnippet: `--- a/src/auth/jwt.ts
+++ b/src/auth/jwt.ts
@@ -79,3 +79,3 @@
-const JWT_FALLBACK_SECRET = "super_secret_dev_key_do_not_leak_9921!";
-const SECRET_KEY = process.env.JWT_SECRET || JWT_FALLBACK_SECRET;
+const SECRET_KEY = process.env.JWT_SECRET;
+if (!SECRET_KEY) throw new Error("JWT_SECRET environment variable is required");
@@ -98,1 +98,1 @@
-      algorithms: ['HS256', 'none'],
+      algorithms: ['HS256'],`,
  },
];

export const AGENT_RUNS: AgentRun[] = [
  {
    id: 'agt-ast-taint',
    type: 'dataflow',
    name: 'Deterministic AST Taint Tracer',
    role: 'Static Dataflow Analyzer',
    model: 'Tree-sitter + Semgrep Core 1.70',
    status: 'complete',
    startedAt: '08:30:12',
    completedAt: '08:30:13',
    cost: 0.02,
    latencyMs: 190,
    findingsProduced: 3,
    avgExecutionTime: '190ms',
    description:
      'Parses code into abstract syntax trees without executing runtime code, tracking user tainted sources directly to database and system call sinks.',
    decisionExplanation: 'Matched 3 tainted paths through FastAPI route arguments.',
  },
  {
    id: 'agt-llm-reasoner',
    type: 'triage',
    name: 'Gemini Security Reasoner',
    role: 'Deep Semantic & Context Analyzer',
    model: 'Gemini 2.5 Pro (Server-Side)',
    status: 'complete',
    startedAt: '08:30:13',
    completedAt: '08:30:15',
    cost: 0.14,
    latencyMs: 1420,
    findingsProduced: 4,
    avgExecutionTime: '1.4s',
    description:
      'Evaluates complex business logic vulnerabilities, cryptographic bypasses, and cross-file authentication flows with explainable traces.',
    decisionExplanation: 'Identified JWT "none" algorithm bypass and privilege escalation risks.',
  },
  {
    id: 'agt-microvm-testbed',
    type: 'testing',
    name: 'MicroVM Sandbox Verification Agent',
    role: 'Patch & Exploit Verifier',
    model: 'gVisor MicroVM + Firecracker',
    status: 'complete',
    startedAt: '08:30:15',
    completedAt: '08:30:16',
    cost: 0.08,
    latencyMs: 820,
    findingsProduced: 2,
    avgExecutionTime: '820ms',
    description:
      'Boots patched code inside an ephemeral, network-isolated MicroVM to verify that exploit testbeds fail while all existing unit tests pass cleanly.',
    decisionExplanation: 'Exploit payload blocked in sandbox. 100% unit tests passed.',
  },
  {
    id: 'agt-triage-dedupe',
    type: 'report',
    name: 'Triage & Deduplication Synthesizer',
    role: 'Audit Evidence Synthesizer',
    model: 'Vigil Triage Consensus Core',
    status: 'complete',
    startedAt: '08:30:16',
    completedAt: '08:30:16',
    cost: 0.01,
    latencyMs: 95,
    findingsProduced: 0,
    avgExecutionTime: '95ms',
    description:
      'Cross-references static linters with LLM findings, filters out verified false positives, and generates SARIF v2.1 attestation dossiers.',
    decisionExplanation: 'Pruned 2 duplicate warnings and certified 0 false positives.',
  },
];
