"""
RuleEngine: Applies parsed skill rules against AST and token patterns.
All detection is in-process static analysis only — ZERO subprocess calls,
ZERO code execution on submitted source.

Implements detection for all 7 baseline rule categories:
  VIGIL-SEC-001  secrets (token_regex)
  VIGIL-SEC-002  unsafe_eval (ast_node)
  VIGIL-SEC-003  injection (ast_node + token_regex)
  VIGIL-SEC-004  deserialization (ast_node)
  VIGIL-SEC-005  weak_crypto (ast_node + token_regex)
  VIGIL-QUAL-006 error_handling (ast_node)
  VIGIL-MAINT-007 maintainability (ast_node)
"""
from __future__ import annotations

import ast
import hashlib
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.models.finding import EvidenceKind, FindingOrigin, Severity
from app.rules.loader import SkillRule, get_rules

logger = logging.getLogger(__name__)


@dataclass
class DetectedFinding:
    """Internal intermediate finding produced by the rule engine or tool adapters."""
    rule_id: str
    category: str
    severity: str
    confidence: float
    title: str
    rationale: str
    remediation: str
    evidence_kind: EvidenceKind
    ast_path: Optional[str] = None
    matched_text: Optional[str] = None
    start_line: Optional[int] = None
    start_col: Optional[int] = None
    end_line: Optional[int] = None
    end_col: Optional[int] = None
    origin: FindingOrigin = FindingOrigin.rule
    tool_name: Optional[str] = None
    tool_version: Optional[str] = None
    raw_evidence: Optional[dict] = None
    raw_evidence_ref: Optional[uuid.UUID] = None


def _compute_fingerprint(rule_id: str, ast_path: str, matched_text: str, evidence_kind: str) -> str:
    """
    Compute deterministic, line-shift-invariant fingerprint.
    sha256(rule_id || ast_path || sha256(matched_text) || evidence_kind)
    See Implementation Plan [H3], [C3], Design Principles §5.
    """
    matched_text_hash = hashlib.sha256(matched_text.encode("utf-8")).hexdigest()
    raw = f"{rule_id}:{ast_path}:{matched_text_hash}:{evidence_kind}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# Public alias for computing deterministic fingerprints across review modules
compute_fingerprint = _compute_fingerprint


# ─── Secret Detection (VIGIL-SEC-001) ──────────────────────────────────────

_SECRET_PATTERNS = [
    # AWS Access Key
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS Access Key ID"),
    # Private key blocks
    (re.compile(r"-----BEGIN\s+(RSA |EC |OPENSSH )?PRIVATE KEY-----"), "PEM Private Key"),
    # GitHub tokens
    (re.compile(r"gh[pos]_[A-Za-z0-9]{36,}"), "GitHub Token"),
    # OpenAI keys
    (re.compile(r"sk-[A-Za-z0-9]{48}"), "OpenAI API Key"),
    # Generic / Test Secret tokens
    (re.compile(r"\b(sk|pk|rk)_(live|test)_[A-Za-z0-9_\-]{8,}"), "API Secret Key"),
    # Slack tokens
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]+"), "Slack Token"),
    # Stripe keys
    (re.compile(r"(rk|sk)_live_[A-Za-z0-9]+"), "Stripe Live Key"),
]

_SECRET_VAR_NAMES = re.compile(
    r"\b(password|passwd|pwd|db_password|secret|api_key|apikey|auth_token|access_token|"
    r"private_key|credential|token|secret_key|jwt_secret)\b",
    re.IGNORECASE,
)


def _shannon_entropy(s: str) -> float:
    """Compute Shannon entropy of a string."""
    if not s:
        return 0.0
    freq: Dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def _detect_secrets(source: str, language: str, rule: SkillRule) -> List[DetectedFinding]:
    findings: List[DetectedFinding] = []
    lines = source.splitlines()

    for line_num, line in enumerate(lines, 1):
        # 1. Check known token patterns
        for pattern, token_type in _SECRET_PATTERNS:
            m = pattern.search(line)
            if m:
                matched = m.group(0)
                findings.append(DetectedFinding(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    severity=rule.severity,
                    confidence=0.95,
                    title=f"Hardcoded {token_type} detected",
                    rationale=f"A {token_type} pattern was found in source code. "
                               "Hardcoded credentials are a critical security risk.",
                    remediation=rule.remediation_template,
                    evidence_kind=EvidenceKind.token_regex,
                    ast_path=f"line_{line_num}/token_match",
                    matched_text=matched[:200],
                    start_line=line_num,
                    start_col=m.start() + 1,
                    end_line=line_num,
                    end_col=m.end() + 1,
                ))

        # 2. Check sensitive variable assignments: VAR_NAME = "literal_string"
        assign_match = re.search(
            r'^\s*([A-Za-z0-9_]+)\s*=\s*(["\'])(.+?)\2\s*$', line
        )
        if assign_match:
            var_name = assign_match.group(1)
            val_literal = assign_match.group(3).strip()
            if _SECRET_VAR_NAMES.search(var_name) and len(val_literal) >= 3:
                # Exclude obvious mock placeholders or env references
                if not (val_literal.startswith("os.getenv") or val_literal.startswith("process.env") or val_literal.lower() in {"none", "false", "true", "null", ""}):
                    # Avoid duplicate if already matched by pattern
                    if not any(f.start_line == line_num for f in findings):
                        findings.append(DetectedFinding(
                            rule_id=rule.rule_id,
                            category=rule.category,
                            severity=rule.severity,
                            confidence=0.90,
                            title=f"Hardcoded credential in '{var_name}'",
                            rationale=f"A hardcoded literal value was assigned to sensitive variable `{var_name}`. "
                                       "Secrets should be retrieved from environment variables or secret managers.",
                            remediation=rule.remediation_template,
                            evidence_kind=EvidenceKind.token_regex,
                            ast_path=f"line_{line_num}/sensitive_assignment",
                            matched_text=line.strip()[:200],
                            start_line=line_num,
                            start_col=assign_match.start() + 1,
                            end_line=line_num,
                            end_col=assign_match.end() + 1,
                        ))

    return findings


# ─── Unsafe Eval (VIGIL-SEC-002) ────────────────────────────────────────────

def _detect_unsafe_eval_python(tree: ast.AST, rule: SkillRule) -> List[DetectedFinding]:
    findings: List[DetectedFinding] = []

    class EvalVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in {"eval", "exec"}:
                # ast.literal_eval is safe — skip it
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "ast":
                        self.generic_visit(node)
                        return

                findings.append(DetectedFinding(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    severity=rule.severity,
                    confidence=0.95,
                    title=f"Use of unsafe {func_name}()",
                    rationale=f"`{func_name}()` evaluates arbitrary code strings and is a "
                               "direct code injection vector.",
                    remediation=rule.remediation_template,
                    evidence_kind=EvidenceKind.ast_node,
                    ast_path=f"Call[func={func_name}]",
                    matched_text=func_name,
                    start_line=node.lineno,
                    start_col=node.col_offset + 1,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    end_col=getattr(node, "end_col_offset", None),
                ))
            self.generic_visit(node)

    EvalVisitor().visit(tree)
    return findings


def _detect_unsafe_eval_js(source: str, rule: SkillRule) -> List[DetectedFinding]:
    findings: List[DetectedFinding] = []
    # Token-regex fallback for JS/TS (tree-sitter AST would be more precise in production)
    patterns = [
        (re.compile(r"\beval\s*\("), "eval()"),
        (re.compile(r"new\s+Function\s*\("), "new Function()"),
        (re.compile(r"\bsetTimeout\s*\(\s*[\"']"), "setTimeout with string"),
        (re.compile(r"\bsetInterval\s*\(\s*[\"']"), "setInterval with string"),
    ]
    for line_num, line in enumerate(source.splitlines(), 1):
        for pattern, label in patterns:
            m = pattern.search(line)
            if m:
                findings.append(DetectedFinding(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    severity=rule.severity,
                    confidence=0.90,
                    title=f"Unsafe dynamic evaluation: {label}",
                    rationale=f"`{label}` evaluates code from strings and is a code injection vector.",
                    remediation=rule.remediation_template,
                    evidence_kind=EvidenceKind.token_regex,
                    ast_path=f"line_{line_num}/eval_pattern",
                    matched_text=line.strip()[:200],
                    start_line=line_num,
                    start_col=m.start() + 1,
                ))
    return findings


# ─── Injection (VIGIL-SEC-003) ──────────────────────────────────────────────

def _detect_injection_python(tree: ast.AST, source: str, rule: SkillRule) -> List[DetectedFinding]:
    findings: List[DetectedFinding] = []
    tainted_query_vars: set[str] = set()

    class InjectionVisitor(ast.NodeVisitor):
        def visit_Assign(self, node: ast.Assign) -> None:
            # Detect variable assignments like: query = "SELECT ... " + username or query = f"SELECT ... {username}"
            is_dynamic_sql = False
            if isinstance(node.value, (ast.JoinedStr, ast.BinOp, ast.Mod)):
                # Check if it contains SQL keywords
                try:
                    for sub in ast.walk(node.value):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                            upper_val = sub.value.upper()
                            if any(kw in upper_val for kw in ["SELECT ", "INSERT INTO ", "UPDATE ", "DELETE FROM ", "WHERE "]):
                                is_dynamic_sql = True
                                break
                except Exception:
                    pass

            if is_dynamic_sql:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        tainted_query_vars.add(target.id)
                findings.append(DetectedFinding(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    severity=rule.severity,
                    confidence=0.90,
                    title="SQL injection risk: unsanitized query formatting",
                    rationale="String formatting or concatenation used to construct an SQL query dynamically. "
                               "Parameterized query placeholders must be used instead.",
                    remediation=rule.remediation_template,
                    evidence_kind=EvidenceKind.ast_node,
                    ast_path="Assign[dynamic_sql_query]",
                    matched_text="SQL query string built dynamically",
                    start_line=node.lineno,
                    start_col=node.col_offset + 1,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    end_col=getattr(node, "end_col_offset", None),
                ))
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            # OS injection: subprocess with shell=True
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in {"call", "run", "Popen", "check_call", "check_output"}:
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            findings.append(DetectedFinding(
                                rule_id=rule.rule_id,
                                category=rule.category,
                                severity=rule.severity,
                                confidence=0.90,
                                title=f"OS command injection: subprocess.{node.func.attr}(shell=True)",
                                rationale="shell=True allows command injection via string interpolation.",
                                remediation=rule.remediation_template,
                                evidence_kind=EvidenceKind.ast_node,
                                ast_path=f"Call[func=subprocess.{node.func.attr}][shell=True]",
                                matched_text=f"subprocess.{node.func.attr}(..., shell=True)",
                                start_line=node.lineno,
                                start_col=node.col_offset + 1,
                                end_line=getattr(node, "end_lineno", node.lineno),
                                end_col=getattr(node, "end_col_offset", None),
                            ))
                # os.system / os.popen
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                    if node.func.attr in {"system", "popen"}:
                        findings.append(DetectedFinding(
                            rule_id=rule.rule_id,
                            category=rule.category,
                            severity=rule.severity,
                            confidence=0.85,
                            title=f"OS command injection risk: os.{node.func.attr}()",
                            rationale=f"os.{node.func.attr}() can execute shell commands; "
                                       "if the argument is not a literal, injection is possible.",
                            remediation=rule.remediation_template,
                            evidence_kind=EvidenceKind.ast_node,
                            ast_path=f"Call[func=os.{node.func.attr}]",
                            matched_text=f"os.{node.func.attr}",
                            start_line=node.lineno,
                            start_col=node.col_offset + 1,
                        ))

                # SQL injection: cursor.execute / connection.execute with f-string or concatenation or tainted variable
                if node.func.attr in {"execute", "executemany"}:
                    if node.args:
                        arg0 = node.args[0]
                        is_inline_dynamic = isinstance(arg0, (ast.JoinedStr, ast.BinOp, ast.Mod))
                        is_var_dynamic = isinstance(arg0, ast.Name) and arg0.id in tainted_query_vars
                        if is_inline_dynamic or is_var_dynamic:
                            # Avoid duplicate if already reported on assignment
                            if not any(f.start_line == node.lineno for f in findings):
                                findings.append(DetectedFinding(
                                    rule_id=rule.rule_id,
                                    category=rule.category,
                                    severity=rule.severity,
                                    confidence=0.85,
                                    title="SQL injection risk: dynamic query in execute()",
                                    rationale="String formatting/concatenation used to build SQL query. "
                                               "Parameterized queries must be used instead.",
                                    remediation=rule.remediation_template,
                                    evidence_kind=EvidenceKind.ast_node,
                                    ast_path=f"Call[func=.{node.func.attr}][arg=dynamic_string]",
                                    matched_text=".execute(dynamic_string)",
                                    start_line=node.lineno,
                                    start_col=node.col_offset + 1,
                                ))
            self.generic_visit(node)

    InjectionVisitor().visit(tree)
    return findings


def _detect_injection_js(source: str, rule: SkillRule) -> List[DetectedFinding]:
    findings: List[DetectedFinding] = []
    patterns = [
        (re.compile(r"child_process\.exec\s*\("), "child_process.exec"),
        (re.compile(r"child_process\.execSync\s*\("), "child_process.execSync"),
        (re.compile(r"shell\s*:\s*true"), "shell: true in spawn options"),
        (re.compile(r"\.query\s*\(`"), "Template literal in SQL query()"),
        (re.compile(r"\.raw\s*\(`"), "knex.raw with template literal"),
    ]
    for line_num, line in enumerate(source.splitlines(), 1):
        for pattern, label in patterns:
            m = pattern.search(line)
            if m:
                findings.append(DetectedFinding(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    severity=rule.severity,
                    confidence=0.80,
                    title=f"Injection risk: {label}",
                    rationale=f"{label} may allow OS command or SQL injection.",
                    remediation=rule.remediation_template,
                    evidence_kind=EvidenceKind.token_regex,
                    ast_path=f"line_{line_num}/injection_pattern",
                    matched_text=line.strip()[:200],
                    start_line=line_num,
                    start_col=m.start() + 1,
                ))
    return findings


# ─── Insecure Deserialization (VIGIL-SEC-004) ────────────────────────────────

def _detect_deserialization(tree: ast.AST, source: str, language: str, rule: SkillRule) -> List[DetectedFinding]:
    findings: List[DetectedFinding] = []

    if language == "python":
        class DeserialVisitor(ast.NodeVisitor):
            def visit_Call(self, node: ast.Call) -> None:
                if isinstance(node.func, ast.Attribute):
                    mod = ""
                    if isinstance(node.func.value, ast.Name):
                        mod = node.func.value.id
                    attr = node.func.attr

                    # pickle / cPickle
                    if mod in {"pickle", "cPickle"} and attr in {"loads", "load"}:
                        findings.append(DetectedFinding(
                            rule_id=rule.rule_id,
                            category=rule.category,
                            severity=rule.severity,
                            confidence=0.95,
                            title=f"Insecure deserialization: {mod}.{attr}()",
                            rationale=f"{mod}.{attr}() can execute arbitrary Python code "
                                       "embedded in the serialized data.",
                            remediation=rule.remediation_template,
                            evidence_kind=EvidenceKind.ast_node,
                            ast_path=f"Call[func={mod}.{attr}]",
                            matched_text=f"{mod}.{attr}",
                            start_line=node.lineno,
                            start_col=node.col_offset + 1,
                        ))

                    # yaml.load (without SafeLoader is dangerous)
                    if mod == "yaml" and attr == "load":
                        # Check if SafeLoader is in the arguments
                        safe = False
                        for kw in node.keywords:
                            if kw.arg == "Loader":
                                if isinstance(kw.value, ast.Attribute):
                                    if kw.value.attr == "SafeLoader":
                                        safe = True
                        if not safe:
                            findings.append(DetectedFinding(
                                rule_id=rule.rule_id,
                                category=rule.category,
                                severity=rule.severity,
                                confidence=0.90,
                                title="Insecure deserialization: yaml.load() without SafeLoader",
                                rationale="yaml.load() without SafeLoader can execute arbitrary Python "
                                           "code via YAML object tags (e.g. !!python/object).",
                                remediation=rule.remediation_template,
                                evidence_kind=EvidenceKind.ast_node,
                                ast_path="Call[func=yaml.load][no_SafeLoader]",
                                matched_text="yaml.load",
                                start_line=node.lineno,
                                start_col=node.col_offset + 1,
                            ))

                    # marshal.loads
                    if mod == "marshal" and attr == "loads":
                        findings.append(DetectedFinding(
                            rule_id=rule.rule_id,
                            category=rule.category,
                            severity=rule.severity,
                            confidence=0.85,
                            title="Insecure deserialization: marshal.loads()",
                            rationale="marshal.loads() can execute code objects and is unsafe "
                                       "with untrusted data.",
                            remediation=rule.remediation_template,
                            evidence_kind=EvidenceKind.ast_node,
                            ast_path="Call[func=marshal.loads]",
                            matched_text="marshal.loads",
                            start_line=node.lineno,
                            start_col=node.col_offset + 1,
                        ))
                self.generic_visit(node)

        DeserialVisitor().visit(tree)
    else:
        # JS/TS token-based check
        patterns = [
            re.compile(r"deserialize\s*\("),
            re.compile(r"unserialize\s*\("),
        ]
        for line_num, line in enumerate(source.splitlines(), 1):
            for pattern in patterns:
                m = pattern.search(line)
                if m:
                    findings.append(DetectedFinding(
                        rule_id=rule.rule_id,
                        category=rule.category,
                        severity=rule.severity,
                        confidence=0.65,
                        title="Potential insecure deserialization",
                        rationale="Deserialization of untrusted data can lead to code execution.",
                        remediation=rule.remediation_template,
                        evidence_kind=EvidenceKind.token_regex,
                        ast_path=f"line_{line_num}/deserialize_pattern",
                        matched_text=line.strip()[:200],
                        start_line=line_num,
                        start_col=m.start() + 1,
                    ))

    return findings


# ─── Weak Cryptography (VIGIL-SEC-005) ──────────────────────────────────────

def _detect_weak_crypto(tree: ast.AST, source: str, language: str, rule: SkillRule) -> List[DetectedFinding]:
    findings: List[DetectedFinding] = []

    if language == "python":
        class CryptoVisitor(ast.NodeVisitor):
            def visit_Call(self, node: ast.Call) -> None:
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "hashlib":
                        if node.func.attr in {"md5", "sha1"}:
                            findings.append(DetectedFinding(
                                rule_id=rule.rule_id,
                                category=rule.category,
                                severity=rule.severity,
                                confidence=0.95,
                                title=f"Weak hash algorithm: hashlib.{node.func.attr}()",
                                rationale=f"hashlib.{node.func.attr}() is cryptographically broken "
                                           "and should not be used for security-sensitive purposes.",
                                remediation=rule.remediation_template,
                                evidence_kind=EvidenceKind.ast_node,
                                ast_path=f"Call[func=hashlib.{node.func.attr}]",
                                matched_text=f"hashlib.{node.func.attr}",
                                start_line=node.lineno,
                                start_col=node.col_offset + 1,
                            ))
                # hashlib.new("md5") or hashlib.new("sha1")
                if isinstance(node.func, ast.Attribute) and node.func.attr == "new":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        if str(node.args[0].value).lower() in {"md5", "sha1", "sha-1"}:
                            findings.append(DetectedFinding(
                                rule_id=rule.rule_id,
                                category=rule.category,
                                severity=rule.severity,
                                confidence=0.95,
                                title=f"Weak hash algorithm: hashlib.new('{node.args[0].value}')",
                                rationale="Weak hash algorithm specified.",
                                remediation=rule.remediation_template,
                                evidence_kind=EvidenceKind.ast_node,
                                ast_path=f"Call[func=hashlib.new][arg={node.args[0].value}]",
                                matched_text=f"hashlib.new('{node.args[0].value}')",
                                start_line=node.lineno,
                                start_col=node.col_offset + 1,
                            ))
                self.generic_visit(node)

        CryptoVisitor().visit(tree)
    else:
        patterns = [
            (re.compile(r"createHash\s*\(\s*['\"]md5['\"]"), "crypto.createHash('md5')"),
            (re.compile(r"createHash\s*\(\s*['\"]sha1['\"]"), "crypto.createHash('sha1')"),
            (re.compile(r"createCipheriv\s*\(\s*['\"]des"), "DES cipher"),
            (re.compile(r"createCipheriv\s*\(\s*['\"]rc4"), "RC4 cipher"),
        ]
        for line_num, line in enumerate(source.splitlines(), 1):
            for pattern, label in patterns:
                m = pattern.search(line)
                if m:
                    findings.append(DetectedFinding(
                        rule_id=rule.rule_id,
                        category=rule.category,
                        severity=rule.severity,
                        confidence=0.95,
                        title=f"Weak cryptographic algorithm: {label}",
                        rationale=f"{label} uses a broken algorithm that should not be used for "
                                   "security-sensitive purposes.",
                        remediation=rule.remediation_template,
                        evidence_kind=EvidenceKind.token_regex,
                        ast_path=f"line_{line_num}/weak_crypto_pattern",
                        matched_text=line.strip()[:200],
                        start_line=line_num,
                        start_col=m.start() + 1,
                    ))

    return findings


# ─── Error Handling (VIGIL-QUAL-006) ────────────────────────────────────────

def _detect_error_handling_python(tree: ast.AST, rule: SkillRule) -> List[DetectedFinding]:
    findings: List[DetectedFinding] = []

    class ErrorHandlingVisitor(ast.NodeVisitor):
        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            is_bare = node.type is None
            is_broad = (
                isinstance(node.type, ast.Name)
                and node.type.id in {"Exception", "BaseException"}
            )
            body_is_pass = (
                len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
            )

            if is_bare:
                findings.append(DetectedFinding(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    severity=rule.severity,
                    confidence=0.95,
                    title="Bare except clause",
                    rationale="A bare `except:` clause catches all exceptions including "
                               "KeyboardInterrupt and SystemExit, interfering with process lifecycle.",
                    remediation=rule.remediation_template,
                    evidence_kind=EvidenceKind.ast_node,
                    ast_path="ExceptHandler[type=None]",
                    matched_text="except:",
                    start_line=node.lineno,
                    start_col=node.col_offset + 1,
                ))
            elif is_broad and body_is_pass:
                exc_name = node.type.id if isinstance(node.type, ast.Name) else "Exception"
                findings.append(DetectedFinding(
                    rule_id=rule.rule_id,
                    category=rule.category,
                    severity=rule.severity,
                    confidence=0.90,
                    title=f"Broad exception silently suppressed: except {exc_name}: pass",
                    rationale=f"Catching {exc_name} with only `pass` suppresses all errors silently.",
                    remediation=rule.remediation_template,
                    evidence_kind=EvidenceKind.ast_node,
                    ast_path=f"ExceptHandler[type={exc_name}][body=Pass]",
                    matched_text=f"except {exc_name}: pass",
                    start_line=node.lineno,
                    start_col=node.col_offset + 1,
                ))
            self.generic_visit(node)

    ErrorHandlingVisitor().visit(tree)
    return findings


def _detect_error_handling_js(source: str, rule: SkillRule) -> List[DetectedFinding]:
    findings: List[DetectedFinding] = []
    # Detect empty catch blocks: catch (...) { }
    empty_catch = re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}")
    for line_num, line in enumerate(source.splitlines(), 1):
        m = empty_catch.search(line)
        if m:
            findings.append(DetectedFinding(
                rule_id=rule.rule_id,
                category=rule.category,
                severity=rule.severity,
                confidence=0.90,
                title="Empty catch block",
                rationale="An empty catch block silently discards exceptions.",
                remediation=rule.remediation_template,
                evidence_kind=EvidenceKind.token_regex,
                ast_path=f"line_{line_num}/empty_catch",
                matched_text=m.group(0)[:200],
                start_line=line_num,
                start_col=m.start() + 1,
            ))
    return findings


# ─── Maintainability (VIGIL-MAINT-007) ──────────────────────────────────────

def _compute_cyclomatic(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Compute cyclomatic complexity of a function."""
    count = 1
    for node in ast.walk(func_node):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                              ast.With, ast.AsyncWith, ast.AsyncFor)):
            count += 1
        elif isinstance(node, ast.BoolOp):
            count += len(node.values) - 1
    return count


def _detect_maintainability_python(tree: ast.AST, source: str, rule: SkillRule) -> List[DetectedFinding]:
    findings: List[DetectedFinding] = []
    lines = source.splitlines()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        func_name = node.name
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        body_lines = end - start

        # Long function check
        if body_lines > 80:
            findings.append(DetectedFinding(
                rule_id=rule.rule_id,
                category=rule.category,
                severity=rule.severity,
                confidence=0.95,
                title=f"Long function: '{func_name}' ({body_lines} lines)",
                rationale=f"Function '{func_name}' has {body_lines} lines, exceeding the 80-line limit. "
                           "Long functions are harder to test and maintain.",
                remediation=rule.remediation_template,
                evidence_kind=EvidenceKind.ast_node,
                ast_path=f"FunctionDef[name={func_name}]",
                matched_text=f"def {func_name}",
                start_line=start,
                start_col=node.col_offset + 1,
                end_line=end,
            ))

        # High cyclomatic complexity
        complexity = _compute_cyclomatic(node)
        if complexity >= 10:
            findings.append(DetectedFinding(
                rule_id=rule.rule_id,
                category=rule.category,
                severity=rule.severity,
                confidence=0.90,
                title=f"High cyclomatic complexity: '{func_name}' (complexity={complexity})",
                rationale=f"Function '{func_name}' has cyclomatic complexity {complexity} >= 10. "
                           "High complexity correlates with defect density.",
                remediation=rule.remediation_template,
                evidence_kind=EvidenceKind.ast_node,
                ast_path=f"FunctionDef[name={func_name}][complexity={complexity}]",
                matched_text=f"def {func_name}",
                start_line=start,
                start_col=node.col_offset + 1,
            ))

        # Large parameter count (excluding self/cls)
        args = node.args
        params = [
            a for a in (args.args + args.posonlyargs + args.kwonlyargs)
            if a.arg not in {"self", "cls"}
        ]
        if len(params) > 7:
            findings.append(DetectedFinding(
                rule_id=rule.rule_id,
                category=rule.category,
                severity=rule.severity,
                confidence=0.85,
                title=f"Too many parameters: '{func_name}' ({len(params)} params)",
                rationale=f"Function '{func_name}' has {len(params)} parameters. "
                           "Functions with more than 7 parameters are difficult to call correctly.",
                remediation=rule.remediation_template,
                evidence_kind=EvidenceKind.ast_node,
                ast_path=f"FunctionDef[name={func_name}][params={len(params)}]",
                matched_text=f"def {func_name}",
                start_line=start,
                start_col=node.col_offset + 1,
            ))

    return findings


# ─── Main Rule Engine Entry Point ────────────────────────────────────────────

class RuleEngine:
    """
    Applies all loaded skill rules to source code.
    Uses Python ast for Python analysis and token-regex for JS/TS.
    ZERO subprocess calls, ZERO code execution on submitted content.
    """

    def __init__(self) -> None:
        self.rules = get_rules()

    def run(self, source: str, language: str) -> Tuple[List[DetectedFinding], Optional[ast.AST]]:
        """
        Run all applicable baseline rules against the source code.
        Returns (findings, python_ast_or_None).
        """
        lang = language.lower()
        findings: List[DetectedFinding] = []
        py_tree: Optional[ast.AST] = None

        # Parse Python AST for Python analysis
        if lang == "python":
            try:
                py_tree = ast.parse(source, mode="exec")
            except SyntaxError:
                # Syntax errors are handled earlier; skip rule analysis
                return findings, None

        for rule_id, rule in self.rules.items():
            if lang not in rule.languages and "python" not in rule.languages and lang not in {"javascript", "typescript"}:
                continue
            if lang not in rule.languages:
                continue

            try:
                new_findings = self._apply_rule(rule, source, lang, py_tree)
                findings.extend(new_findings)
            except Exception as e:
                logger.warning("Rule %s failed: %s", rule_id, e, exc_info=True)

        return findings, py_tree

    def _apply_rule(
        self,
        rule: SkillRule,
        source: str,
        language: str,
        py_tree: Optional[ast.AST],
    ) -> List[DetectedFinding]:
        cat = rule.category

        if cat == "secrets":
            return _detect_secrets(source, language, rule)

        elif cat == "unsafe_eval":
            if language == "python" and py_tree:
                return _detect_unsafe_eval_python(py_tree, rule)
            else:
                return _detect_unsafe_eval_js(source, rule)

        elif cat == "injection":
            if language == "python" and py_tree:
                return _detect_injection_python(py_tree, source, rule)
            else:
                return _detect_injection_js(source, rule)

        elif cat == "deserialization":
            return _detect_deserialization(py_tree or ast.parse(""), source, language, rule)

        elif cat == "weak_crypto":
            return _detect_weak_crypto(py_tree or ast.parse(""), source, language, rule)

        elif cat == "error_handling":
            if language == "python" and py_tree:
                return _detect_error_handling_python(py_tree, rule)
            else:
                return _detect_error_handling_js(source, rule)

        elif cat == "maintainability":
            if language == "python" and py_tree:
                return _detect_maintainability_python(py_tree, source, rule)
            # JS maintainability is lower priority — skip for Phase 1

        return []


def compute_fingerprint(
    rule_id: str,
    ast_path: str,
    matched_text: str,
    evidence_kind: str,
) -> str:
    """Public fingerprint computation function. See Implementation Plan [H3], [C3]."""
    return _compute_fingerprint(rule_id, ast_path, matched_text, evidence_kind)
