---
rule_id: VIGIL-SEC-005
category: weak_crypto
severity: Medium
languages:
  - python
  - javascript
  - typescript
pattern_type: ast_node
detection_notes: "Detects legacy or broken cryptographic algorithms such as MD5, SHA-1, DES, 3DES, and RC4 for hashing or encryption."
remediation_template: "Upgrade to modern cryptographic algorithms: SHA-256/SHA-512 for integrity, Argon2id/bcrypt for password hashing, and AES-GCM or ChaCha20-Poly1305 for symmetric encryption."
references:
  - "https://cwe.mitre.org/data/definitions/327.html"
  - "https://cwe.mitre.org/data/definitions/328.html"
---

# VIGIL-SEC-005: Broken or Weak Cryptography

Deprecated hash functions and ciphers are susceptible to collision attacks, preimage computation, and brute-force cracking.

## Detection Logic
1. Calls to `hashlib.md5(...)`, `hashlib.sha1(...)`, `crypto.createHash('md5')`, `crypto.createHash('sha1')`.
2. Symmetric cipher initialization specifying `DES`, `ARC4`, or `Blowfish`.
