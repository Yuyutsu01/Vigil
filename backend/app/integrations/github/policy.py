"""
Repository Policy Service: path filtering, language matching, and case normalization (FR-103, FR-104, M4).
"""
from __future__ import annotations

import fnmatch
import os
import posixpath
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.repository import RepositoryPolicy

# Standard extension to language mapping
EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
}

DEFAULT_POLICY_CONFIG = {
    "enabled_languages": ["python", "javascript", "typescript"],
    "ignored_paths": [
        "vendor/**",
        "node_modules/**",
        ".git/**",
        "dist/**",
        "build/**",
        "tests/**",
        "*.min.js",
        "*.bundle.js",
        "package-lock.json",
        "yarn.lock",
        "poetry.lock",
    ],
    "ignored_rules": [],
    "max_files_per_review": 500,
    "auto_review_on_push": False,
    "auto_review_on_pr": True,
    "review_fork_prs": False,
    "review_draft_prs": False,
}


def normalize_path(path: str) -> str:
    """Normalize path separators to forward slash and normalize case on Windows (M4)."""
    clean = path.replace("\\", "/").strip("/")
    if os.name == "nt":
        return clean.lower()
    return clean


def is_path_ignored(path: str, ignored_patterns: List[str]) -> bool:
    """Check if file path matches any ignored glob pattern with OS-specific case rules (M4)."""
    norm_path = normalize_path(path)
    for pattern in ignored_patterns:
        norm_pattern = normalize_path(pattern)
        # Match against full relative path and basename
        if fnmatch.fnmatch(norm_path, norm_pattern):
            return True
        if fnmatch.fnmatch(posixpath.basename(norm_path), norm_pattern):
            return True
    return False


def detect_language(path: str) -> Optional[str]:
    """Detect language from file path extension."""
    norm = normalize_path(path)
    _, ext = posixpath.splitext(norm)
    return EXT_TO_LANG.get(ext)


def is_file_eligible(
    path: str,
    enabled_languages: List[str],
    ignored_patterns: List[str],
) -> tuple[bool, Optional[str]]:
    """
    Determine if a file is eligible for review under repository policy.
    Returns (eligible: bool, language: Optional[str]).
    """
    if is_path_ignored(path, ignored_patterns):
        return False, None

    lang = detect_language(path)
    if not lang:
        return False, None

    enabled_lower = [l.lower() for l in enabled_languages]
    if lang.lower() not in enabled_lower:
        return False, None

    return True, lang


async def get_or_create_default_policy(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> RepositoryPolicy:
    """Retrieve or create default RepositoryPolicy for tenant."""
    query = select(RepositoryPolicy).where(RepositoryPolicy.tenant_id == tenant_id).limit(1)
    result = await session.execute(query)
    policy = result.scalar_one_or_none()

    if policy is None:
        policy = RepositoryPolicy(
            tenant_id=tenant_id,
            enabled_languages=DEFAULT_POLICY_CONFIG["enabled_languages"],
            ignored_paths=DEFAULT_POLICY_CONFIG["ignored_paths"],
            ignored_rules=DEFAULT_POLICY_CONFIG["ignored_rules"],
            max_files_per_review=DEFAULT_POLICY_CONFIG["max_files_per_review"],
            auto_review_on_push=DEFAULT_POLICY_CONFIG["auto_review_on_push"],
            auto_review_on_pr=DEFAULT_POLICY_CONFIG["auto_review_on_pr"],
            review_fork_prs=DEFAULT_POLICY_CONFIG["review_fork_prs"],
            review_draft_prs=DEFAULT_POLICY_CONFIG["review_draft_prs"],
        )
        session.add(policy)
        await session.flush()

    return policy
