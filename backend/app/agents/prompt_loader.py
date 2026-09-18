"""
Prompt loader: loads versioned markdown prompts and computes SHA-256 hashes.
Prompts live in prompts/*.md — never hardcoded in Python strings.
See Implementation Plan [H2].
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parents[3] / "prompts"

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

_cache: Dict[str, Tuple[str, str]] = {}  # name -> (content, sha256_hash)


def _strip_frontmatter(content: str) -> str:
    """Remove YAML front-matter if present (prompts may have it for metadata)."""
    return _FRONTMATTER_RE.sub("", content, count=1).strip()


def load_prompt(name: str, prompts_dir: Path = PROMPTS_DIR) -> Tuple[str, str]:
    """
    Load a prompt by name (e.g. 'security_reasoning').
    Returns (prompt_text, sha256_hex).
    Results are cached after first load.
    """
    if name in _cache:
        return _cache[name]

    path = prompts_dir / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    content = _strip_frontmatter(raw)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    _cache[name] = (content, digest)
    logger.info("Loaded prompt '%s' (sha256=%s...)", name, digest[:12])
    return content, digest


def get_prompt_version(name: str) -> str:
    """Return the SHA-256 hash of the named prompt file (truncated to 16 hex chars for storage)."""
    _, digest = load_prompt(name)
    return digest[:16]


def format_security_prompt(source_code: str, language: str, existing_rule_ids: list[str]) -> Tuple[str, str]:
    """Load and format the security_reasoning prompt. Returns (filled_prompt, prompt_version)."""
    template, version = load_prompt("security_reasoning")
    filled = template.replace("{source_code}", source_code)
    filled = filled.replace("{language}", language)
    filled = filled.replace("{existing_rule_ids}", ", ".join(existing_rule_ids) if existing_rule_ids else "none")
    return filled, version


def format_quality_prompt(source_code: str, language: str) -> Tuple[str, str]:
    """Load and format the quality_review prompt. Returns (filled_prompt, prompt_version)."""
    template, version = load_prompt("quality_review")
    filled = template.replace("{source_code}", source_code)
    filled = filled.replace("{language}", language)
    return filled, version
