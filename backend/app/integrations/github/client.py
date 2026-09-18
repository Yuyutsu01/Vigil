"""
Read-Only Async GitHub API Client with SSRF Protection, Rate Limit Backoff, and Write Blocking (FR-103, FR-104, B7).
"""
from __future__ import annotations

import asyncio
import base64
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.integrations.github.app_auth import (
    get_installation_access_token,
    invalidate_installation_token,
)

logger = logging.getLogger(__name__)

ALLOWED_GITHUB_HOSTS = {"api.github.com"}

# ── Phase 4 GitHub Write Allowlist (FR-105, FR-107, B1, B4) ───────────────────
# Exactly 8 distinct endpoint paths across 9 HTTP verb entries.
ALLOWED_WRITE_ENDPOINTS: Dict[re.Pattern, Set[str]] = {
    re.compile(r"^/repos/[^/]+/[^/]+/git/blobs$"): {"POST"},
    re.compile(r"^/repos/[^/]+/[^/]+/git/trees$"): {"POST"},
    re.compile(r"^/repos/[^/]+/[^/]+/git/commits$"): {"POST"},
    re.compile(r"^/repos/[^/]+/[^/]+/git/refs$"): {"POST"},
    re.compile(r"^/repos/[^/]+/[^/]+/git/refs/heads/vigil/patch-[^/]+$"): {"PATCH", "DELETE"},
    re.compile(r"^/repos/[^/]+/[^/]+/pulls$"): {"POST"},
    re.compile(r"^/repos/[^/]+/[^/]+/pulls/\d+/reviews$"): {"POST"},
    re.compile(r"^/repos/[^/]+/[^/]+/issues/\d+/comments$"): {"POST"},
}

PROTECTED_BRANCH_PATTERNS = [
    re.compile(r"^refs/heads/(main|master|release/.*|release|prod|production)$"),
    re.compile(r"^(main|master|release/.*|release|prod|production)$"),
]



def validate_github_url(url: str, allowed_netloc: Optional[str] = None) -> str:
    """
    SSRF protection: verify target URL host belongs to allowed GitHub API domains.
    If allowed_netloc is provided, verifies match against that host;
    otherwise enforces membership in ALLOWED_GITHUB_HOSTS.
    """
    parsed = urlparse(url)
    target = parsed.netloc
    if allowed_netloc:
        if target != allowed_netloc:
            raise ValueError(
                f"SSRF blocked: URL host '{target}' does not match allowed GitHub API host '{allowed_netloc}'"
            )
    if target not in ALLOWED_GITHUB_HOSTS:
        raise ValueError(
            f"SSRF blocked: URL host '{target}' is not in allowed GitHub hosts {ALLOWED_GITHUB_HOSTS}"
        )
    return url


class GitHubClient:
    """
    Read-only GitHub API client enforcing strict read-only guarantees (Phase 3).
    All mutation endpoints (POST/PUT/PATCH/DELETE) raise NotImplementedError.
    """

    def __init__(
        self,
        installation_id: int = 0,
        private_key_ref: str = "",
        base_url: Optional[str] = None,
        app_jwt: Optional[str] = None,
    ) -> None:
        self.installation_id = installation_id
        self.private_key_ref = private_key_ref
        settings = get_settings()
        self.base_url = (base_url or getattr(settings, "github_api_base", None) or settings.github_api_base_url).rstrip("/")
        self._allowed_netloc = urlparse(self.base_url).netloc
        self.app_jwt = app_jwt

    def _validate_url(self, url: str) -> str:
        """SSRF protection: verify target host matches configured GitHub API base."""
        full_url = url if url.startswith("http") else f"{self.base_url}/{url.lstrip('/')}"
        validate_github_url(full_url, allowed_netloc=self._allowed_netloc)
        return full_url

    async def _post_app_jwt(
        self, endpoint: str, body: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """
        Execute an authenticated POST using GitHub App JWT (RS256).
        Used exclusively for installation access token exchange (read-only token issuance).
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        validate_github_url(url)
        headers = {
            "Authorization": f"Bearer {self.app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Vigil-Security-Assistant/1.0",
        }
        async with httpx.AsyncClient() as client:
            return await client.post(url, headers=headers, json=body or {}, timeout=10.0)  # ALLOWED_WRITE: /app/installations/\d+/access_tokens

    def _is_write_allowed(self, method: str, endpoint: str) -> bool:
        norm_path = "/" + endpoint.lstrip("/")
        m = method.upper()
        for pattern, allowed_methods in ALLOWED_WRITE_ENDPOINTS.items():
            if m in allowed_methods and pattern.match(norm_path):
                return True
        return False

    def _verify_not_protected_branch(self, ref_name: str) -> None:
        for p in PROTECTED_BRANCH_PATTERNS:
            if p.match(ref_name):
                raise ValueError(f"Operation blocked: Modifying protected branch '{ref_name}' is prohibited")

    async def _post_allowed_write(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """
        Guard method enforcing the Phase 4 write allowlist and protected branch shielding (B1, B4).
        """
        if not self._is_write_allowed(method, endpoint):
            raise NotImplementedError(
                f"Operation blocked: Not in Phase 4 GitHub write allowlist ({method} {endpoint}). "
                "Phase 4 feature: GitHub writes are disabled in Phase 3"
            )

        if json_data and "ref" in json_data:
            self._verify_not_protected_branch(str(json_data["ref"]))
        if "refs/heads/" in endpoint:
            branch_part = endpoint.split("refs/heads/")[-1]
            self._verify_not_protected_branch(branch_part)

        return await self._request(method=method, endpoint=endpoint, json_data=json_data)

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retries: int = 1,
    ) -> httpx.Response:
        """Internal dispatch with token refresh retry and rate-limit backoff."""
        m = method.upper()
        if m in ("POST", "PUT", "PATCH", "DELETE") and not self._is_write_allowed(m, endpoint):
            raise NotImplementedError(
                f"Operation blocked: Not in Phase 4 GitHub write allowlist ({m} {endpoint}). "
                "Phase 4 feature: GitHub writes are disabled in Phase 3"
            )

        url = self._validate_url(endpoint)

        token = await get_installation_access_token(
            installation_id=self.installation_id,
            private_key_ref=self.private_key_ref,
        )

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Vigil-Security-Assistant/1.0",
        }

        if extra_headers:
            headers.update(extra_headers)

        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=20.0,
            )

        # Check rate limit headers
        remaining = resp.headers.get("x-ratelimit-remaining")
        if remaining is not None and int(remaining) == 0:
            reset_epoch = int(resp.headers.get("x-ratelimit-reset", time.time() + 60))
            sleep_sec = min(reset_epoch - int(time.time()), 60)
            if sleep_sec > 0:
                logger.warning("GitHub rate limit reached; backing off for %d seconds", sleep_sec)
                await asyncio.sleep(sleep_sec)

        # Handle 401 token expiry
        if resp.status_code == 401 and retries > 0:
            logger.info("Received 401 from GitHub; invalidating cached token and retrying...")
            await invalidate_installation_token(self.installation_id)
            token = await get_installation_access_token(
                installation_id=self.installation_id,
                private_key_ref=self.private_key_ref,
                force_refresh=True,
            )
            headers["Authorization"] = f"Bearer {token}"
            async with httpx.AsyncClient() as client:
                resp = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=20.0,
                )
            if resp.status_code == 401:
                raise RuntimeError("github_auth_failed: Second 401 received from GitHub")

        return resp

    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Execute a read-only GET request."""
        return await self._request("GET", endpoint, params=params, extra_headers=headers)

    async def get_pull_diff(self, owner: str, repo: str, pull_number: int) -> str:
        """Fetch unified diff for a pull request (Accept: application/vnd.github.v3.diff)."""
        resp = await self.get(
            f"/repos/{owner}/{repo}/pulls/{pull_number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to get diff for PR #{pull_number} in {owner}/{repo}: {resp.status_code} {resp.text}")
        return resp.text


    async def post(self, endpoint: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        """Execute an allowed POST mutation."""
        return await self._post_allowed_write("POST", endpoint, json_data=json)  # ALLOWED_WRITE: /repos/[^/]+/[^/]+/git/blobs

    async def patch(self, endpoint: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        """Execute an allowed PATCH mutation."""
        return await self._post_allowed_write("PATCH", endpoint, json_data=json)  # ALLOWED_WRITE: /repos/[^/]+/[^/]+/git/refs/heads/vigil/patch-[^/]+

    async def delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        """Execute an allowed DELETE mutation."""
        return await self._post_allowed_write("DELETE", endpoint, json_data=None)  # ALLOWED_WRITE: /repos/[^/]+/[^/]+/git/refs/heads/vigil/patch-[^/]+

    async def put(self, *args: Any, **kwargs: Any) -> Any:
        """PUT requests (e.g. merging PRs) are strictly prohibited in Phase 4."""
        raise NotImplementedError(
            "Operation blocked: Not in Phase 4 GitHub write allowlist (PUT is prohibited). "
            "Phase 4 feature: GitHub writes are disabled in Phase 3"
        )

    async def merge_pull_request(self, *args: Any, **kwargs: Any) -> Any:
        """Phase 4 explicitly forbids merging PRs from Vigil."""
        raise NotImplementedError(
            "Operation blocked: PR merge is not on the Phase 4 "
            "GitHub write allowlist and will never be added."
        )

    # ── Phase 4 Git Data API Operations (FR-105) ───────────────────────────
    async def create_blob(self, owner: str, repo: str, content: str, encoding: str = "utf-8") -> str:
        """Create a git blob and return its SHA (B1)."""
        payload = {"content": content, "encoding": encoding}
        resp = await self.post(f"/repos/{owner}/{repo}/git/blobs", json=payload)  # ALLOWED_WRITE: /repos/[^/]+/[^/]+/git/blobs
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create blob in {owner}/{repo}: {resp.status_code} {resp.text}")
        return resp.json()["sha"]

    async def create_tree(self, owner: str, repo: str, base_tree: str, tree: List[Dict[str, Any]]) -> str:
        """Create a git tree on top of base_tree and return its SHA."""
        payload = {"base_tree": base_tree, "tree": tree}
        resp = await self.post(f"/repos/{owner}/{repo}/git/trees", json=payload)  # ALLOWED_WRITE: /repos/[^/]+/[^/]+/git/trees
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create tree in {owner}/{repo}: {resp.status_code} {resp.text}")
        return resp.json()["sha"]

    async def create_commit(self, owner: str, repo: str, message: str, tree: str, parents: List[str]) -> str:
        """Create a git commit and return its SHA."""
        payload = {"message": message, "tree": tree, "parents": parents}
        resp = await self.post(f"/repos/{owner}/{repo}/git/commits", json=payload)  # ALLOWED_WRITE: /repos/[^/]+/[^/]+/git/commits
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create commit in {owner}/{repo}: {resp.status_code} {resp.text}")
        return resp.json()["sha"]

    async def get_ref(self, owner: str, repo: str, ref: str) -> Dict[str, Any]:
        """Fetch a git reference (e.g. 'heads/main' or 'heads/vigil/patch-...')."""
        clean_ref = ref.removeprefix("refs/")
        resp = await self.get(f"/repos/{owner}/{repo}/git/ref/{clean_ref}")
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to get ref {ref} in {owner}/{repo}: {resp.status_code} {resp.text}")
        return resp.json()

    async def create_ref(self, owner: str, repo: str, ref: str, sha: str) -> Dict[str, Any]:
        """Create an ephemeral patch branch reference."""
        payload = {"ref": ref, "sha": sha}
        resp = await self.post(f"/repos/{owner}/{repo}/git/refs", json=payload)  # ALLOWED_WRITE: /repos/[^/]+/[^/]+/git/refs
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create ref {ref} in {owner}/{repo}: {resp.status_code} {resp.text}")
        return resp.json()

    async def update_ref(self, owner: str, repo: str, ref: str, sha: str, force: bool = False) -> Dict[str, Any]:
        """Update an ephemeral patch branch reference."""
        clean_ref = ref.removeprefix("refs/")
        payload = {"sha": sha, "force": force}
        resp = await self.patch(f"/repos/{owner}/{repo}/git/refs/{clean_ref}", json=payload)  # ALLOWED_WRITE: /repos/[^/]+/[^/]+/git/refs/heads/vigil/patch-[^/]+
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to update ref {ref} in {owner}/{repo}: {resp.status_code} {resp.text}")
        return resp.json()

    async def delete_ref(self, owner: str, repo: str, ref: str) -> None:
        """Delete an ephemeral patch branch reference on rollback."""
        clean_ref = ref.removeprefix("refs/")
        resp = await self.delete(f"/repos/{owner}/{repo}/git/refs/{clean_ref}")  # ALLOWED_WRITE: /repos/[^/]+/[^/]+/git/refs/heads/vigil/patch-[^/]+
        if resp.status_code not in (200, 204):
            raise RuntimeError(f"Failed to delete ref {ref} in {owner}/{repo}: {resp.status_code} {resp.text}")

    async def create_pull(self, owner: str, repo: str, title: str, head: str, base: str, body: str, draft: bool = True) -> Dict[str, Any]:
        """Open a draft remediation pull request."""
        payload = {"title": title, "head": head, "base": base, "body": body, "draft": draft}
        resp = await self.post(f"/repos/{owner}/{repo}/pulls", json=payload)  # ALLOWED_WRITE: /repos/[^/]+/[^/]+/pulls
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create PR in {owner}/{repo}: {resp.status_code} {resp.text}")
        return resp.json()

    async def create_pull_review(self, owner: str, repo: str, pull_number: int, body: str, event: str = "COMMENT", comments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Submit a pull request review."""
        payload: Dict[str, Any] = {"body": body, "event": event}
        if comments:
            payload["comments"] = comments
        resp = await self.post(f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews", json=payload)  # ALLOWED_WRITE: /repos/[^/]+/[^/]+/pulls/\d+/reviews
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to submit review for PR #{pull_number} in {owner}/{repo}: {resp.status_code} {resp.text}")
        return resp.json()

    async def create_issue_comment(self, owner: str, repo: str, issue_number: int, body: str) -> Dict[str, Any]:
        """Post a comment to a PR / issue."""
        payload = {"body": body}
        resp = await self.post(f"/repos/{owner}/{repo}/issues/{issue_number}/comments", json=payload)  # ALLOWED_WRITE: /repos/[^/]+/[^/]+/issues/\d+/comments
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to post comment to issue #{issue_number} in {owner}/{repo}: {resp.status_code} {resp.text}")
        return resp.json()


    # ── Higher-level Read operations ───────────────────────────────────────
    async def list_installation_repositories(self) -> List[Dict[str, Any]]:
        """List repositories accessible to this installation."""
        resp = await self.get("/installation/repositories")
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to list installation repositories: {resp.status_code} {resp.text}")
        data = resp.json()
        return data.get("repositories", [])

    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch repository metadata."""
        resp = await self.get(f"/repos/{owner}/{repo}")
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to get repository {owner}/{repo}: {resp.status_code} {resp.text}")
        return resp.json()

    async def get_tree(self, owner: str, repo: str, commit_sha: str, recursive: bool = True) -> Dict[str, Any]:
        """Fetch Git tree for a commit SHA."""
        params = {"recursive": "1"} if recursive else {}
        resp = await self.get(f"/repos/{owner}/{repo}/git/trees/{commit_sha}", params=params)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to get tree for {owner}/{repo}@{commit_sha}: {resp.status_code} {resp.text}")
        return resp.json()

    async def get_blob_bytes(self, owner: str, repo: str, file_sha: str) -> bytes:
        """Fetch Git blob by SHA and decode base64."""
        resp = await self.get(f"/repos/{owner}/{repo}/git/blobs/{file_sha}")
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to get blob {file_sha}: {resp.status_code}")
        data = resp.json()
        encoding = data.get("encoding", "base64")
        content_str = data.get("content", "")
        if encoding == "base64":
            return base64.b64decode(content_str)
        return content_str.encode("utf-8")

    async def get_raw_file_content(self, owner: str, repo: str, path: str, ref: str) -> bytes:
        """Fetch raw file content by path and git ref."""
        headers = {
            "Accept": "application/vnd.github.raw+json",
        }
        resp = await self.get(f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}?ref={ref}")
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch content for {path}@{ref}: {resp.status_code}")
        data = resp.json()
        # GitHub contents API returns base64 for file
        if isinstance(data, dict) and data.get("encoding") == "base64":
            return base64.b64decode(data.get("content", ""))
        elif isinstance(data, dict) and "content" in data:
            return data["content"].encode("utf-8")
        return resp.content

    async def compare_commits(self, owner: str, repo: str, base: str, head: str) -> Dict[str, Any]:
        """Compare two commits/branches."""
        resp = await self.get(f"/repos/{owner}/{repo}/compare/{base}...{head}")
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to compare {base}...{head}: {resp.status_code} {resp.text}")
        return resp.json()

    async def list_pull_files(
        self, owner: str, repo: str, pull_number: int, page: int = 1, per_page: int = 100
    ) -> List[Dict[str, Any]]:
        """List files changed in a pull request with pagination."""
        resp = await self.get(
            f"/repos/{owner}/{repo}/pulls/{pull_number}/files",
            params={"page": page, "per_page": per_page},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to list files for PR #{pull_number}: {resp.status_code} {resp.text}")
        return resp.json()
