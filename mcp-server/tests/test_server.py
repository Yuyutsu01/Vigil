"""
Unit test suite for vigil_mcp server tools and FastMCP registration.
"""
import pytest
import unittest.mock as mock
from vigil_mcp.server import (
    mcp,
    server,
    vigil_health_check,
    vigil_review_code,
    vigil_get_findings,
    vigil_list_repositories,
    vigil_trigger_repo_review,
    vigil_generate_patch,
    vigil_validate_patch,
    vigil_get_agent_tree,
)


def test_mcp_server_instance():
    """Verify FastMCP server instance is exported."""
    assert server is not None
    assert mcp.name == "vigil-mcp"


@pytest.mark.asyncio
async def test_vigil_health_check():
    """Verify health check tool calls backend."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "healthy"}

    with mock.patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await vigil_health_check()
        assert res["status"] == 200
        assert res["data"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_vigil_review_code():
    """Verify review submission tool."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 202
    mock_resp.json.return_value = {"run_id": "test-run-123", "status": "queued"}

    with mock.patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await vigil_review_code(source_code="import os", language="python")
        assert res["run_id"] == "test-run-123"
        assert res["status"] == "queued"


@pytest.mark.asyncio
async def test_vigil_get_findings():
    """Verify findings retrieval tool."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"run_id": "test-run-123", "findings": []}

    with mock.patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await vigil_get_findings("test-run-123")
        assert res["run_id"] == "test-run-123"


@pytest.mark.asyncio
async def test_vigil_list_repositories():
    """Verify list repositories tool."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"full_name": "Yuyutsu01/OpenTerminal"}]

    with mock.patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await vigil_list_repositories()
        assert len(res["repositories"]) == 1


@pytest.mark.asyncio
async def test_vigil_trigger_repo_review():
    """Verify trigger repository review tool."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"review_run_id": "test-run-456"}

    with mock.patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await vigil_trigger_repo_review("repo-123", scope_mode="full_repo")
        assert res["review_run_id"] == "test-run-456"


@pytest.mark.asyncio
async def test_vigil_generate_patch():
    """Verify patch generation tool."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"patch_id": "patch-789", "status": "draft"}

    with mock.patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await vigil_generate_patch("finding-123")
        assert res["patch_id"] == "patch-789"


@pytest.mark.asyncio
async def test_vigil_validate_patch():
    """Verify patch validation tool."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"validation_id": "val-123", "verdict": "passed"}

    with mock.patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await vigil_validate_patch("patch-789")
        assert res["verdict"] == "passed"


@pytest.mark.asyncio
async def test_vigil_get_agent_tree():
    """Verify agent execution tree retrieval."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"run_id": "test-run-123", "stages": []}

    with mock.patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await vigil_get_agent_tree("test-run-123")
        assert res["run_id"] == "test-run-123"
