---
rule_id: VIGIL-SEC-003
category: injection
severity: High
languages:
  - python
  - javascript
  - typescript
pattern_type: ast_node
detection_notes: |
  Detects SQL injection and OS command injection patterns:

  SQL Injection (Python):
    - String formatting/concatenation used to build SQL queries passed to cursor.execute(),
      cursor.executemany(), or connection.execute(). Detects f-strings, % formatting,
      and + concatenation in SQL arguments.

  SQL Injection (JavaScript/TypeScript):
    - Template literals or string concatenation in calls to query(), execute(), run(),
      db.query(), pool.query(), knex.raw(), sequelize.query() where the first argument
      is not a parameterized placeholder string.

  OS Command Injection (Python):
    - subprocess.call([..., shell=True]), subprocess.run([..., shell=True]),
      subprocess.Popen([..., shell=True]) — shell=True with variable interpolation.
    - os.system(expr) where expr is not a string literal.
    - os.popen(expr) — any usage.

  OS Command Injection (JavaScript/TypeScript):
    - child_process.exec(expr) where expr is not a pure string literal.
    - child_process.execSync(expr) similarly.
    - shell: true in child_process.spawn options.
remediation_template: |
  SQL Injection:
  - Always use parameterized queries or prepared statements.
    Python: cursor.execute("SELECT * FROM t WHERE id = %s", (user_id,))
    Node.js: db.query("SELECT * FROM t WHERE id = $1", [userId])
  - Use an ORM with parameter binding (SQLAlchemy, Prisma, TypeORM).
  OS Command Injection:
  - Avoid shell=True. Use subprocess.run(["cmd", arg], shell=False).
  - Validate and allowlist all inputs used in command arguments.
  - Prefer library-level APIs over shell commands where possible.
references:
  - "https://cwe.mitre.org/data/definitions/89.html"
  - "https://cwe.mitre.org/data/definitions/78.html"
  - "https://owasp.org/www-project-top-ten/2017/A1_2017-Injection"
---

# VIGIL-SEC-003: SQL and OS Command Injection

Injection vulnerabilities arise when untrusted data is incorporated into commands or queries
without proper escaping or parameterization. They consistently rank #1 in the OWASP Top 10.

## Detection Logic

### Python SQL Injection
1. AST `Call` node where `func.attr` in `{"execute", "executemany"}` AND the first argument
   is a `JoinedStr` (f-string), `BinOp` with `op=Add` (concatenation), or `%`-formatted string.

### Python OS Injection
1. `subprocess.*` calls with keyword argument `shell=True`.
2. `os.system` call with a non-literal argument.
3. Any `os.popen` call.

### JS/TS SQL Injection
1. `CallExpression` to `query`, `execute`, `run`, `raw` where the argument
   contains a `TemplateLiteral` or `BinaryExpression` with `+`.

### JS/TS OS Injection
1. `child_process.exec` or `child_process.execSync` with a `TemplateLiteral` or concatenated
   string as the first argument.
2. `spawn` options object containing `shell: true`.
