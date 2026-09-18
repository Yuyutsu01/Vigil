---
rule_id: VIGIL-MAINT-007
category: maintainability
severity: Low
languages:
  - python
  - javascript
  - typescript
pattern_type: ast_node
detection_notes: |
  Detects maintainability smells that increase technical debt and defect risk:

  Long Functions:
    - Python: FunctionDef or AsyncFunctionDef with more than 80 lines of body code
      (excluding blank lines and comment-only lines).
    - JavaScript/TypeScript: FunctionDeclaration, FunctionExpression, ArrowFunctionExpression,
      MethodDefinition with a body spanning more than 80 lines.

  High Cyclomatic Complexity:
    - Cyclomatic complexity is computed as: 1 + (number of branching points).
    - Branching points counted: if/elif/else, for, while, try/except, with (Python);
      if/else, for, while, do-while, switch case, catch, ternary (JS/TS).
    - Flag functions with cyclomatic complexity >= 10.

  Deeply Nested Logic:
    - Flag code blocks with nesting depth >= 4 (4 levels of indented control flow).

  Large Parameter Lists:
    - Functions with more than 7 parameters.
remediation_template: |
  Long Functions:
  - Apply the Single Responsibility Principle: extract cohesive blocks into named helper functions.
  - Functions should do one thing and do it well.
  High Complexity:
  - Flatten conditionals using early returns (guard clauses).
  - Extract complex conditions into well-named boolean functions.
  - Replace complex switch/if-chains with polymorphism or a dispatch table.
  Nesting:
  - Invert conditions to reduce nesting (fail fast / guard clause pattern).
  - Extract nested loops into functions.
  Large Parameter Lists:
  - Group related parameters into a data class / options object / NamedTuple.
references:
  - "https://en.wikipedia.org/wiki/Cyclomatic_complexity"
  - "https://refactoring.guru/refactoring"
  - "https://martinfowler.com/bliki/TooManyParameters.html"
---

# VIGIL-MAINT-007: Maintainability Smells

Large, complex functions are a leading indicator of defect density. Research consistently
shows that functions exceeding ~40-80 lines or cyclomatic complexity >= 10 have
significantly higher defect rates.

## Detection Logic

### Long Function
- Count non-blank, non-comment lines between the function start and end.
- Flag if line count > 80.

### Cyclomatic Complexity
- Start at 1 per function.
- Add 1 for each: `if`, `elif`, `for`, `while`, `with`, `except` clause, `and`/`or` in condition,
  `case` arm (Python 3.10+ match), ternary operator.
- Flag if complexity >= 10.

### Deep Nesting
- Track indentation depth. Flag any block at depth >= 4 within a single function.

### Parameter Count
- Count formal parameters (excluding `self`, `cls`). Flag if count > 7.
