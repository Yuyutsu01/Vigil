"""
Diff Resolution: Commit Compare and PR File Listings with Pagination and Filtering (FR-104, B6).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.integrations.github.client import GitHubClient

logger = logging.getLogger(__name__)


class DiffFile:
    """Represents a changed file in a PR or commit comparison."""

    def __init__(
        self,
        filename: str,
        status: str,
        patch: Optional[str] = None,
        sha: Optional[str] = None,
        raw_url: Optional[str] = None,
    ) -> None:
        # Truncate path > 1024 chars (B6)
        self.filename = filename[:1024]
        self.status = status  # added, modified, removed, renamed
        self.patch = patch
        self.sha = sha
        self.raw_url = raw_url


async def resolve_pr_diff(
    client: GitHubClient,
    owner: str,
    repo: str,
    pull_number: int,
    max_files: Optional[int] = None,
) -> List[DiffFile]:
    """
    Paginate through PR changed files and filter out removed or binary files (B6).
    Caps files at GITHUB_DIFF_MAX_FILES.
    """
    settings = get_settings()
    effective_max = min(max_files or 1000, settings.github_diff_max_files)

    diff_files: List[DiffFile] = []
    page = 1
    per_page = 100

    while len(diff_files) < effective_max:
        raw_files = await client.list_pull_files(
            owner=owner,
            repo=repo,
            pull_number=pull_number,
            page=page,
            per_page=per_page,
        )
        if not raw_files:
            break

        for item in raw_files:
            filename = item.get("filename", "")
            status = item.get("status", "")

            # Filter removed files
            if status == "removed":
                continue

            # Skip binary files or submodules (identified by missing patch or binary marker)
            patch = item.get("patch")
            if item.get("changes") == 0 and patch is None:
                continue

            diff_files.append(
                DiffFile(
                    filename=filename,
                    status=status,
                    patch=patch,
                    sha=item.get("sha"),
                    raw_url=item.get("raw_url"),
                )
            )

            if len(diff_files) >= effective_max:
                break

        if len(raw_files) < per_page:
            break
        page += 1

    return diff_files


async def resolve_compare_diff(
    client: GitHubClient,
    owner: str,
    repo: str,
    base: str,
    head: str,
    max_files: Optional[int] = None,
) -> List[DiffFile]:
    """
    Resolve changed files between two commits or branches using compare API (B6).
    """
    settings = get_settings()
    effective_max = min(max_files or 1000, settings.github_diff_max_files)

    data = await client.compare_commits(owner=owner, repo=repo, base=base, head=head)
    files = data.get("files", [])

    diff_files: List[DiffFile] = []
    for item in files:
        filename = item.get("filename", "")
        status = item.get("status", "")

        if status == "removed":
            continue

        patch = item.get("patch")
        if item.get("changes") == 0 and patch is None:
            continue

        diff_files.append(
            DiffFile(
                filename=filename,
                status=status,
                patch=patch,
                sha=item.get("sha"),
                raw_url=item.get("raw_url"),
            )
        )

        if len(diff_files) >= effective_max:
            break

    return diff_files
