"""
Security tests: Strict write-blocking enforcement on GitHub client (FR-103, Phase 3 invariant).
Any attempt to write (POST/PUT/PATCH/DELETE) to GitHub API must raise NotImplementedError.
"""
import pytest

from app.integrations.github.client import GitHubClient


@pytest.mark.asyncio
async def test_all_write_methods_raise_not_implemented():
    client = GitHubClient(
        installation_id=12345,
        private_key_ref="env://NON_EXISTENT_KEY",
    )

    with pytest.raises(NotImplementedError, match="Phase 4 feature: GitHub writes are disabled in Phase 3"):
        await client.post("/repos/org/repo/releases", json={"tag_name": "v1.0.0"})

    with pytest.raises(NotImplementedError, match="Phase 4 feature: GitHub writes are disabled in Phase 3"):
        await client.put("/repos/org/repo/contents/file.txt", json={})

    with pytest.raises(NotImplementedError, match="Phase 4 feature: GitHub writes are disabled in Phase 3"):
        await client.patch("/repos/org/repo", json={"name": "new-name"})

    with pytest.raises(NotImplementedError, match="Phase 4 feature: GitHub writes are disabled in Phase 3"):
        await client.delete("/repos/org/repo/branches/test")

    with pytest.raises(NotImplementedError, match="PR merge is not on the Phase 4 GitHub write allowlist"):
        await client.merge_pull_request("org", "repo", 42)

