"""
Vigil MCP Server - Model Context Protocol integration for Vigil Automated Code Review & Security Assistant.
Exposes the complete suite of 8 Vigil security, remediation, and telemetry tools.
"""
from typing import Optional, Dict, Any, List
import os
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("vigil-mcp")
server = mcp  # Expose 'server' symbol so `from vigil_mcp import server` works seamlessly

VIGIL_API_URL = os.environ.get("VIGIL_API_URL", "http://localhost:8000")
VIGIL_API_TOKEN = os.environ.get("VIGIL_API_TOKEN", "")


def _get_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if VIGIL_API_TOKEN:
        headers["Authorization"] = f"Bearer {VIGIL_API_TOKEN}"
    return headers


@mcp.tool()
async def vigil_health_check() -> Dict[str, Any]:
    """Check the health and operational status of the Vigil backend service."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{VIGIL_API_URL}/health", timeout=10.0)
            return {"status": resp.status_code, "data": resp.json()}
        except Exception as e:
            return {"status": "error", "error": str(e)}


@mcp.tool()
async def vigil_review_code(
    source_code: str,
    language: str = "python",
) -> Dict[str, Any]:
    """
    Submit source code for automated multi-agent security and quality review.
    
    Args:
        source_code: The raw source code to analyze.
        language: Programming language ('python', 'javascript', or 'typescript').
    """
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "source_text": source_code,
                "language": language.lower(),
            }
            resp = await client.post(
                f"{VIGIL_API_URL}/v1/reviews",
                json=payload,
                headers=_get_headers(),
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}


@mcp.tool()
async def vigil_get_findings(run_id: str) -> Dict[str, Any]:
    """
    Retrieve review status, metrics, and security findings for a given review run ID.
    
    Args:
        run_id: UUID of the review run.
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{VIGIL_API_URL}/v1/reviews/{run_id}",
                headers=_get_headers(),
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}


@mcp.tool()
async def vigil_list_repositories() -> Dict[str, Any]:
    """List all connected GitHub repositories and their CI/CD status."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{VIGIL_API_URL}/v1/repositories",
                headers=_get_headers(),
                timeout=15.0,
            )
            resp.raise_for_status()
            return {"repositories": resp.json()}
        except Exception as e:
            return {"status": "error", "error": str(e)}


@mcp.tool()
async def vigil_trigger_repo_review(
    repository_id: str,
    ref_type: str = "branch",
    ref_value: str = "main",
    scope_mode: str = "full_repo",
) -> Dict[str, Any]:
    """
    Trigger an automated security scan on a connected GitHub repository.
    
    Args:
        repository_id: UUID of the connected repository.
        ref_type: 'branch', 'tag', or 'commit'.
        ref_value: Branch name or reference value (e.g. 'main').
        scope_mode: 'full_repo' (comprehensive) or 'changed_files' (fast diff scan).
    """
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "ref_type": ref_type,
                "ref_value": ref_value,
                "scope_mode": scope_mode,
            }
            resp = await client.post(
                f"{VIGIL_API_URL}/v1/repositories/{repository_id}/reviews",
                json=payload,
                headers=_get_headers(),
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}


@mcp.tool()
async def vigil_generate_patch(finding_id: str) -> Dict[str, Any]:
    """
    Generate an autonomous surgical unified diff remediation patch for a specific security finding.
    
    Args:
        finding_id: UUID of the security finding to remediate.
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{VIGIL_API_URL}/v1/findings/{finding_id}/patches",
                headers=_get_headers(),
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}


@mcp.tool()
async def vigil_validate_patch(patch_id: str) -> Dict[str, Any]:
    """
    Execute sandbox behavioral validation and regression tests for a candidate patch inside gVisor.
    
    Args:
        patch_id: UUID of the generated candidate patch.
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{VIGIL_API_URL}/v1/patches/{patch_id}/validate",
                headers=_get_headers(),
                timeout=45.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}


@mcp.tool()
async def vigil_get_agent_tree(run_id: str) -> Dict[str, Any]:
    """
    Fetch the 14-stage multi-agent DAG execution tree, status nodes, token metrics, and execution timing.
    
    Args:
        run_id: UUID of the review run.
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{VIGIL_API_URL}/v1/reviews/{run_id}/agent-tree",
                headers=_get_headers(),
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}


def main():
    """Run the FastMCP server over standard stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
