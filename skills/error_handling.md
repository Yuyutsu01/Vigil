---
rule_id: VIGIL-QUAL-006
category: error_handling
severity: Low
languages:
  - python
  - javascript
  - typescript
pattern_type: ast_node
detection_notes: |
  Detects problematic error handling patterns that suppress exceptions silently or
  catch all exceptions indiscriminately:

  Python:
    - Bare except clause: `except:` with no exception type specified.
    - Broad exception: `except Exception:` or `except BaseException:` with an empty body
      (just `pass`) or a body containing only a logging call with no re-raise.
    - Empty except body: catch block that only contains `pass`.

  JavaScript/TypeScript:
    - Empty catch block: `catch (e) {}` with an empty body.
    - Catch block containing only a comment.
    - Catch block that reassigns the error to a generic variable and never logs or rethrows.
    - Promise .catch(() => {}) — empty promise rejection handler.
    - Unhandled promise rejection: async function without try/catch around await expressions
      that are not wrapped in a rejection handler (informational only).
remediation_template: |
  Python:
  - Catch specific exception types: `except ValueError as e:` rather than bare `except`.
  - Always log or re-raise: never silently discard exceptions in production code.
  - Use contextlib.suppress() only for intentionally suppressed exceptions, and document why.
  JavaScript/TypeScript:
  - Always handle errors in catch blocks: log, throw, or recover explicitly.
  - Propagate promise rejections: add .catch(err => logger.error(err)) or use async/await with try/catch.
  - Consider a global unhandledRejection handler for remaining cases.
references:
  - "https://cwe.mitre.org/data/definitions/390.html"
  - "https://cwe.mitre.org/data/definitions/391.html"
  - "https://owasp.org/www-project-top-ten/2017/A10_2017-Insufficient_Logging_%26_Monitoring"
---

# VIGIL-QUAL-006: Improper Error Handling

Silent exception swallowing hides bugs, masks security incidents, and makes systems
difficult to debug. Bare `except` clauses in Python can even catch `KeyboardInterrupt`
and `SystemExit`, interfering with process lifecycle.

## Detection Logic

### Python
1. AST `ExceptHandler` node where `type` is `None` (bare `except:`).
2. AST `ExceptHandler` node where `type.id in {"Exception","BaseException"}` and the body
   contains only a `Pass` statement.
3. Any `ExceptHandler` whose body consists solely of `pass`.

### JavaScript / TypeScript
1. AST `CatchClause` node where `body.body` is an empty array `[]`.
2. AST `CatchClause` node where the body contains only comment nodes.
3. `.catch(` call expression where the argument is an arrow function with an empty body.
