---
rule_id: VIGIL-SEC-002
category: unsafe_eval
severity: Critical
languages:
  - python
  - javascript
  - typescript
pattern_type: ast_node
detection_notes: |
  Detects use of dynamic evaluation constructs that execute arbitrary code:
  Python:
    - eval(expr) — evaluates a Python expression string.
    - exec(code) — executes a Python code string or code object.
    - compile(source, ...) followed by eval/exec.
  JavaScript/TypeScript:
    - eval(expr) — evaluates a JS string as code.
    - new Function(args, body) — constructs a function from strings.
    - setTimeout(string, ...) or setInterval(string, ...) where the first argument
      is a string literal or variable rather than a function reference.
    - document.write(userInput) is a related injection pattern; flagged at Medium.
  Match any call expression whose callee matches the above identifiers.
remediation_template: |
  Replace dynamic evaluation with safe alternatives:
  - Python: use ast.literal_eval() for safe expression parsing of literals,
    or restructure to avoid runtime code generation entirely.
  - JavaScript: use JSON.parse() for data deserialization; pass callback functions
    to setTimeout/setInterval instead of strings.
  - If dynamic dispatch is genuinely required, use a strict allowlist of permitted
    operations and validate all inputs against it before dispatch.
references:
  - "https://cwe.mitre.org/data/definitions/95.html"
  - "https://owasp.org/www-community/attacks/Code_Injection"
  - "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/eval"
---

# VIGIL-SEC-002: Unsafe Evaluation (eval/exec/Function)

Dynamic code evaluation creates a direct code injection vector. Any user-controlled or
externally derived input reaching an `eval`/`exec`/`new Function` call results in
arbitrary code execution.

## Detection Logic

### Python
1. AST `Call` node where `func` is a `Name` node with `id` in `{"eval", "exec"}`.
2. AST `Call` node where `func` is an `Attribute` node with `attr` in `{"eval", "exec"}`
   on any object (e.g., `builtins.eval`).

### JavaScript / TypeScript
1. AST `CallExpression` where `callee.name == "eval"`.
2. AST `NewExpression` where `callee.name == "Function"`.
3. AST `CallExpression` where `callee.name` in `{"setTimeout", "setInterval"}` and the
   first argument is a `Literal` (string) or `Identifier` (variable), not a function.

## False-Positive Guidance

`ast.literal_eval` in Python is safe and must NOT be flagged. Only flag `eval` and `exec`.
