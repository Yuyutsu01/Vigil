"""
Scoped Review Orchestration: Full repo, changed files, directory, or explicit files (FR-104).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.integrations.github.client import GitHubClient
from app.integrations.github.diff import resolve_compare_diff, resolve_pr_diff
from app.integrations.github.policy import is_file_eligible
from app.integrations.github.snapshot import SnapshotFile, fetch_repository_snapshot, is_git_lfs_pointer

logger = logging.getLogger(__name__)


async def resolve_review_scope(
    client: GitHubClient,
    owner: str,
    repo: str,
    ref_type: str,  # branch, commit, pr, directory
    ref_value: str,
    scope_mode: str,  # full_repo, changed_files, directory, files
    enabled_languages: List[str],
    ignored_paths: List[str],
    max_files: int = 500,
    directory_filter: Optional[str] = None,
    specific_files: Optional[List[str]] = None,
) -> List[SnapshotFile]:
    """
    Resolve scoped files for analysis according to scope_mode and repository policy.
    Returns list of in-memory SnapshotFile objects.
    """
    # 1. Scope mode: changed_files (for pull requests or commit diffs)
    if scope_mode == "changed_files" or ref_type == "pr":
        pull_number = None
        if ref_type == "pr":
            try:
                pull_number = int(ref_value)
            except ValueError:
                pass

        if pull_number is not None:
            diff_files = await resolve_pr_diff(
                client=client,
                owner=owner,
                repo=repo,
                pull_number=pull_number,
                max_files=max_files,
            )
        else:
            # Assume ref_value is base...head or commit
            parts = ref_value.split("...")
            if len(parts) == 2:
                base, head = parts[0], parts[1]
            else:
                base = f"{ref_value}~1"
                head = ref_value

            diff_files = await resolve_compare_diff(
                client=client,
                owner=owner,
                repo=repo,
                base=base,
                head=head,
                max_files=max_files,
            )

        # Filter diff files against repository policy
        eligible_diff = []
        for df in diff_files:
            eligible, lang = is_file_eligible(df.filename, enabled_languages, ignored_paths)
            if eligible and lang:
                eligible_diff.append((df, lang))

        # Fetch contents for eligible changed files
        result_files: List[SnapshotFile] = []
        for df, lang in eligible_diff:
            try:
                # If patch contains the full text or we fetch raw file
                raw_bytes = await client.get_raw_file_content(
                    owner=owner,
                    repo=repo,
                    path=df.filename,
                    ref=ref_value if ref_type != "pr" else (df.sha or "HEAD"),
                )
                if is_git_lfs_pointer(raw_bytes):
                    continue

                content_str = raw_bytes.decode("utf-8", errors="replace")
                result_files.append(
                    SnapshotFile(
                        path=df.filename,
                        content=content_str,
                        language=lang,
                        size_bytes=len(raw_bytes),
                        sha=df.sha,
                    )
                )
            except Exception as e:
                logger.warning("Failed to fetch changed file content for %s: %s", df.filename, e)

            if len(result_files) >= max_files:
                break

        return result_files

    # 2. Scope mode: directory
    if scope_mode == "directory" or directory_filter:
        effective_dir = directory_filter or (ref_value if ref_type == "directory" else None)
        commit_sha = ref_value if ref_type == "commit" else "HEAD"
        return await fetch_repository_snapshot(
            client=client,
            owner=owner,
            repo=repo,
            commit_sha=commit_sha,
            enabled_languages=enabled_languages,
            ignored_paths=ignored_paths,
            max_files=max_files,
            directory_filter=effective_dir,
        )

    # 3. Scope mode: files (explicit list)
    if scope_mode == "files" or specific_files:
        commit_sha = ref_value if ref_type in ("commit", "branch") else "HEAD"
        return await fetch_repository_snapshot(
            client=client,
            owner=owner,
            repo=repo,
            commit_sha=commit_sha,
            enabled_languages=enabled_languages,
            ignored_paths=ignored_paths,
            max_files=max_files,
            specific_files=specific_files,
        )

    # 4. Scope mode: full_repo (default)
    commit_sha = ref_value if ref_type in ("commit", "branch") else "HEAD"
    return await fetch_repository_snapshot(
        client=client,
        owner=owner,
        repo=repo,
        commit_sha=commit_sha,
        enabled_languages=enabled_languages,
        ignored_paths=ignored_paths,
        max_files=max_files,
    )
