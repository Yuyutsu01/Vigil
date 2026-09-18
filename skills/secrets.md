---
rule_id: VIGIL-SEC-001
category: secrets
severity: Critical
languages:
  - python
  - javascript
  - typescript
pattern_type: token_regex
detection_notes: |
  Detects hardcoded credentials, API keys, private keys, and high-entropy secrets
  embedded in source code. Patterns include:
  1. AWS access key IDs (AKIA[0-9A-Z]{16}).
  2. Generic high-entropy strings assigned to variables named *key*, *secret*, *password*, *token*, *credential*.
  3. PEM-encoded private keys (-----BEGIN PRIVATE KEY----- etc.).
  4. GitHub personal access tokens (ghp_..., gho_..., ghs_...).
  5. JWT-shaped strings in string literals.
  6. Slack/Stripe/Twilio/Sendgrid tokens by prefix pattern.
  Minimum entropy threshold for generic string detection: Shannon entropy >= 4.5 over 20+ char strings.
remediation_template: |
  Move credentials out of source code immediately:
  1. Rotate the exposed credential at the provider.
  2. Store secrets in environment variables, a secrets manager (AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager), or a CI/CD secret store.
  3. Access at runtime via os.environ or a vault SDK, never hardcoded.
  4. Add the secret pattern to your .gitignore pre-commit hook and secret scanning rules.
references:
  - "https://cwe.mitre.org/data/definitions/798.html"
  - "https://owasp.org/www-community/vulnerabilities/Use_of_hard-coded_password"
  - "https://docs.github.com/en/code-security/secret-scanning/about-secret-scanning"
---

# VIGIL-SEC-001: Hardcoded Secrets and Credentials

Hardcoded secrets are one of the most common and highest-severity vulnerabilities. Once committed
to source control, a secret may persist in history even after deletion and can be harvested by
automated scanning tools within minutes of a repository being made public.

## Detection Logic

1. **AWS keys**: Regex `AKIA[0-9A-Z]{16}` in string literals.
2. **Private key blocks**: String literal containing `-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----`.
3. **High-entropy assignment**: Assignment where the right-hand side is a quoted string of length >= 20,
   Shannon entropy >= 4.5, and the left-hand variable name contains any of:
   `key`, `secret`, `password`, `passwd`, `pwd`, `token`, `credential`, `auth`, `api_key`, `apikey`.
4. **Known token prefixes**: `ghp_`, `gho_`, `ghs_`, `sk-` (OpenAI), `xoxb-` (Slack), `rk_live_` / `sk_live_` (Stripe).

## False-Positive Guidance

Exclude test fixture files, `.env.example` templates containing placeholder values like
`your-secret-here`, and files explicitly listed in a `vigil.ignore` allowlist.
