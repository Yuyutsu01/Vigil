"""
Unit tests for the GitHub Client Write Allowlist (FR-105, FR-107, B1, B4).
Verifies that only the 8 permitted endpoints (9 HTTP verb entries) are authorized, and protected branches are blocked.
"""
import pytest
from app.integrations.github.client import GitHubClient, ALLOWED_WRITE_ENDPOINTS


def test_allowlist_matches_permitted_endpoints():
    """Verify all 8 Phase 4 endpoints across 9 HTTP verbs are recognized by _is_write_allowed."""
    client = GitHubClient(installation_id=123)

    # 1. POST git/blobs
    assert client._is_write_allowed("POST", "/repos/org/repo/git/blobs") is True

    # 2. POST git/trees
    assert client._is_write_allowed("POST", "/repos/org/repo/git/trees") is True

    # 3. POST git/commits
    assert client._is_write_allowed("POST", "/repos/org/repo/git/commits") is True

    # 4. POST git/refs
    assert client._is_write_allowed("POST", "/repos/org/repo/git/refs") is True

    # 5 & 6. PATCH / DELETE git/refs/heads/vigil/patch-*
    assert client._is_write_allowed("PATCH", "/repos/org/repo/git/refs/heads/vigil/patch-abcdef12-20260918120000") is True
    assert client._is_write_allowed("DELETE", "/repos/org/repo/git/refs/heads/vigil/patch-abcdef12-20260918120000") is True

    # 7. POST pulls
    assert client._is_write_allowed("POST", "/repos/org/repo/pulls") is True

    # 8. POST pulls/{number}/reviews
    assert client._is_write_allowed("POST", "/repos/org/repo/pulls/42/reviews") is True

    # 9. POST issues/{number}/comments
    assert client._is_write_allowed("POST", "/repos/org/repo/issues/42/comments") is True


def test_allowlist_blocks_unauthorized_endpoints():
    """Verify unauthorized mutation requests return False."""
    client = GitHubClient(installation_id=123)

    # Merging PRs is strictly prohibited
    assert client._is_write_allowed("PUT", "/repos/org/repo/pulls/1/merge") is False

    # Deleting repositories is strictly prohibited
    assert client._is_write_allowed("DELETE", "/repos/org/repo") is False

    # Modifying or deleting protected branches is strictly prohibited
    assert client._is_write_allowed("DELETE", "/repos/org/repo/git/refs/heads/main") is False
    assert client._is_write_allowed("PATCH", "/repos/org/repo/git/refs/heads/main") is False

    # Releases and tags are strictly prohibited
    assert client._is_write_allowed("POST", "/repos/org/repo/releases") is False
    assert client._is_write_allowed("POST", "/repos/org/repo/git/tags") is False


def test_protected_branch_shielding():
    """Verify attempts to mutate protected branches raise ValueError."""
    client = GitHubClient(installation_id=123)

    for branch in ["main", "master", "release/v1.0", "release", "prod", "production", "refs/heads/main"]:
        with pytest.raises(ValueError, match="Modifying protected branch"):
            client._verify_not_protected_branch(branch)

    # Ephemeral patch branches must be allowed
    client._verify_not_protected_branch("vigil/patch-abcdef12-20260918120000")
    client._verify_not_protected_branch("refs/heads/vigil/patch-abcdef12-20260918120000")


@pytest.mark.asyncio
async def test_put_raises_not_implemented():
    """Verify PUT calls raise NotImplementedError."""
    client = GitHubClient(installation_id=123)
    with pytest.raises(NotImplementedError, match="PUT is prohibited"):
        await client.put("/repos/org/repo/pulls/1/merge")
