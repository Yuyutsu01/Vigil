"""
Secret redaction service.
Strips credential-shaped strings from log messages and audit metadata
before emission. [A8]

NEVER stores redacted values — only their absence.
"""
from __future__ import annotations

import logging
import re
from typing import Any

# Patterns to redact (ordered by specificity)
_REDACT_PATTERNS = [
    # AWS Access Key
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # GitHub tokens
    re.compile(r"gh[pos]_[A-Za-z0-9]{35,}"),
    # OpenAI keys
    re.compile(r"sk-[A-Za-z0-9]{48}"),
    # Slack tokens
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]+"),
    # Stripe live keys
    re.compile(r"(rk|sk)_live_[A-Za-z0-9]+"),
    # PEM private key
    re.compile(r"-----BEGIN\s+(RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END", re.DOTALL),
    # Bearer tokens (long base64 strings after Bearer)
    re.compile(r"Bearer\s+[A-Za-z0-9\-_=.+/]{32,}"),
    # Generic high-entropy strings >= 32 chars in quotes
    re.compile(r"""(['"])[A-Za-z0-9+/=_\-]{32,}\1"""),
]

_REPLACEMENT = "[REDACTED]"


def redact(text: str) -> str:
    """Return a copy of `text` with secret-shaped strings replaced by [REDACTED]."""
    for pattern in _REDACT_PATTERNS:
        text = pattern.sub(_REPLACEMENT, text)
    return text


def redact_dict(data: dict) -> dict:
    """Recursively redact a dictionary (for sanitizing audit metadata)."""
    result = {}
    for k, v in data.items():
        if isinstance(v, str):
            result[k] = redact(v)
        elif isinstance(v, dict):
            result[k] = redact_dict(v)
        elif isinstance(v, list):
            result[k] = [redact(i) if isinstance(i, str) else i for i in v]
        else:
            result[k] = v
    return result


class RedactionFilter(logging.Filter):
    """
    A logging.Filter that redacts secret-shaped strings from log records.
    Attach to any logger or handler to ensure zero secret leakage.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    redact(str(a)) if isinstance(a, str) else a for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: redact(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
        return True
