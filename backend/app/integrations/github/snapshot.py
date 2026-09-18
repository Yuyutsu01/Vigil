"""
Repository Revision Snapshot: Git Trees API traversal, bounds enforcement, LFS detection (FR-104).
Zero-persistence: files exist only in-memory during review execution.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.integrations.github.client import GitHubClient
from app.integrations.github.policy import is_file_eligible

logger = logging.getLogger(__name__)

# Constants
MAX_FILE_BYTES = 500 * 1024  # 500 KB per file cap
MAX_TOTAL_BYTES = 50 * 1024 * 1024  # 50 MB total review cap
LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


class SnapshotFile:
    """Represents an in-memory source file eligible for analysis."""

    def __init__(
        self,
        path: str,
        content: str,
        language: str,
        size_bytes: int,
        sha: Optional[str] = None,
    ) -> None:
        self.path = path[:1024]
        self.content = content
        self.language = language
        self.size_bytes = size_bytes
        self.sha = sha


def is_git_lfs_pointer(content_bytes: bytes) -> bool:
    """Check if byte sequence starts with Git LFS pointer signature."""
    return content_bytes.strip().startswith(LFS_POINTER_PREFIX)


async def fetch_repository_snapshot(
    client: GitHubClient,
    owner: str,
    repo: str,
    commit_sha: str,
    enabled_languages: List[str],
    ignored_paths: List[str],
    max_files: int = 500,
    directory_filter: Optional[str] = None,
    specific_files: Optional[List[str]] = None,
) -> List[SnapshotFile]:
    """
    Fetch repository snapshot matching policy criteria using Git Trees API.
    Enforces per-file and total size caps, LFS detection, and zero-persistence.
    """
    tree_data = await client.get_tree(owner=owner, repo=repo, commit_sha=commit_sha, recursive=True)
    tree_items = tree_data.get("tree", [])

    specific_set = set(specific_files) if specific_files else None
    dir_prefix = directory_filter.strip("/") + "/" if directory_filter else None

    eligible_entries: List[Dict[str, Any]] = []

    for item in tree_items:
        if item.get("type") != "blob":
            continue

        path = item.get("path", "")

        # Check directory filter if provided
        if dir_prefix and not path.startswith(dir_prefix):
            continue

        # Check specific files list if provided
        if specific_set is not None and path not in specific_set:
            continue

        eligible, lang = is_file_eligible(path, enabled_languages, ignored_paths)
        if not eligible or not lang:
            continue

        size = item.get("size", 0)
        # Skip files exceeding 500 KB or zero size
        if size > MAX_FILE_BYTES or size == 0:
            continue

        item["_detected_lang"] = lang
        eligible_entries.append(item)

        if len(eligible_entries) >= max_files:
            break

    # Now fetch blobs in-memory
    snapshot_files: List[SnapshotFile] = []
    total_bytes = 0

    for item in eligible_entries:
        path = item["path"]
        sha = item["sha"]
        lang = item["_detected_lang"]

        try:
            content_bytes = await client.get_blob_bytes(owner=owner, repo=repo, file_sha=sha)
        except Exception as e:
            logger.warning("Failed to fetch blob for %s (%s): %s", path, sha, e)
            continue

        # LFS check
        if is_git_lfs_pointer(content_bytes):
            logger.info("Skipping Git LFS pointer: %s", path)
            continue

        # Decode as utf-8 (skip binary if decode fails)
        try:
            content_str = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content_str = content_bytes.decode("latin-1")
            except Exception:
                continue

        # Enforce total byte cap
        file_len = len(content_bytes)
        if total_bytes + file_len > MAX_TOTAL_BYTES:
            logger.warning("Total review size exceeded 50MB; truncating file list.")
            break

        total_bytes += file_len
        snapshot_files.append(
            SnapshotFile(
                path=path,
                content=content_str,
                language=lang,
                size_bytes=file_len,
                sha=sha,
            )
        )

    return snapshot_files
