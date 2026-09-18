---
rule_id: VIGIL-SEC-004
category: deserialization
severity: High
languages:
  - python
  - javascript
  - typescript
pattern_type: ast_node
detection_notes: |
  Detects insecure deserialization patterns that can lead to arbitrary code execution:

  Python:
    - pickle.loads(data) — deserializes arbitrary Python objects; can execute code.
    - pickle.load(file) — same risk.
    - cPickle.loads / cPickle.load — deprecated alias, same risk.
    - yaml.load(data) without SafeLoader — PyYAML unsafe load allows Python object tags.
    - yaml.load(data, Loader=yaml.Loader) — explicitly unsafe.
    - marshal.loads() — can execute code via code objects.
    - shelve.open() with untrusted data — wraps pickle.
    - jsonpickle.decode() — executes Python code.

  JavaScript/TypeScript:
    - node-serialize / serialize-javascript deserialize() with untrusted input.
    - vm.runInNewContext / vm.runInThisContext with user data — sandboxed but exploitable.
    - eval(JSON.parse(...)) patterns.
remediation_template: |
  Python:
  - Replace pickle with json, msgpack, or protobuf for data interchange.
  - If YAML is required, always use yaml.safe_load(data) or yaml.load(data, Loader=yaml.SafeLoader).
  - Never deserialize pickle data from untrusted sources. If internal use only, add
    HMAC signature verification before deserialization.
  JavaScript:
  - Use JSON.parse() for data deserialization; avoid eval-based deserializers.
  - Validate deserialized data against a strict JSON schema before use.
references:
  - "https://cwe.mitre.org/data/definitions/502.html"
  - "https://owasp.org/www-project-top-ten/2017/A8_2017-Insecure_Deserialization"
  - "https://pyyaml.org/wiki/PyYAMLDocumentation"
---

# VIGIL-SEC-004: Insecure Deserialization

Insecure deserialization allows attackers to manipulate serialized objects to achieve remote
code execution, privilege escalation, or denial of service. Python's `pickle` and YAML's unsafe
loader are particularly dangerous as they can execute arbitrary Python code during deserialization.

## Detection Logic

### Python
1. AST `Call` node where `func` is `Attribute` with `value.id in {"pickle","cPickle"}` and
   `attr in {"loads","load"}`.
2. AST `Call` node where `func` is `Attribute` with `value.id == "yaml"` and `attr == "load"` —
   regardless of Loader argument (flag and check; SafeLoader use is allowed).
3. AST `Call` node where `func` is `Attribute` with `value.id == "yaml"` and `attr == "load"`
   and keyword `Loader` is `yaml.Loader`, `yaml.FullLoader`, `yaml.UnsafeLoader`, or absent.
4. `marshal.loads` call.
5. `jsonpickle.decode` call.

### JavaScript / TypeScript
1. Import of `node-serialize` or `serialize-javascript` with a decode/deserialize call on
   non-literal data.
