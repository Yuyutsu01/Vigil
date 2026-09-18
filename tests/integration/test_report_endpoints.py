"""
Integration tests for report export endpoints (FR-102).
Verifies JSON, HTML, and PDF report downloads and tenant isolation.
"""
import uuid
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.finding import Finding, FindingOrigin, Severity
from app.models.review import ReviewRun, ReviewStatus, SourceArtifact
from app.services.auth_service import create_access_token


@pytest.fixture
def mock_review_run():
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    artifact_id = uuid.uuid4()

    artifact = SourceArtifact(
        artifact_id=artifact_id,
        tenant_id=tenant_id,
        content="x = 1",
        checksum="chk",
        language="python",
        size_bytes=5,
    )
    run = ReviewRun(
        run_id=run_id,
        tenant_id=tenant_id,
        artifact_id=artifact_id,
        status=ReviewStatus.completed,
        source_artifact=artifact,
        findings=[
            Finding(
                finding_id=uuid.uuid4(),
                run_id=run_id,
                tenant_id=tenant_id,
                fingerprint="fp111",
                origin=FindingOrigin.rule,
                rule_id="VIGIL-SEC-002",
                category="security",
                severity=Severity.critical,
                confidence=0.9,
                title="Unsafe eval()",
                rationale="Direct code execution",
                remediation="Avoid eval",
            )
        ],
    )
    return run


class MockPipeline:
    def __init__(self, store):
        self.store = store

    def zremrangebyscore(self, key, min_val, max_val):
        return self

    def zadd(self, key, mapping):
        return self

    def zcard(self, key):
        return self

    def expire(self, key, ttl):
        return self

    async def execute(self):
        return [0, 1, 1, True]


class MockRedis:
    def __init__(self):
        self.store = {}
        self.kv = {}

    def pipeline(self, transaction=True):
        return MockPipeline(self.store)

    async def get(self, key):
        return self.kv.get(key)

    async def setex(self, key, ttl, value):
        self.kv[key] = value
        return True


def test_report_download_formats(mock_review_run):
    mock_redis = MockRedis()
    token = create_access_token(
        user_id=uuid.uuid4(),
        tenant_id=mock_review_run.tenant_id,
        role="developer",
    )
    headers = {"Authorization": f"Bearer {token}"}

    async def mock_get_run(db, run_id, tenant_id):
        if run_id == mock_review_run.run_id and tenant_id == mock_review_run.tenant_id:
            return mock_review_run
        return None

    with patch("app.main.create_tables", new=AsyncMock()), \
         patch("app.api.rate_limit.get_redis", return_value=mock_redis), \
         patch("app.api.idempotency.get_redis", return_value=mock_redis), \
         patch("app.api.v1.reviews.get_review_run", side_effect=mock_get_run):

        with TestClient(app) as client:
            run_id = mock_review_run.run_id

            # 1. JSON report download
            resp_json = client.get(f"/v1/reviews/{run_id}/report?format=json", headers=headers)
            assert resp_json.status_code == 200
            assert resp_json.headers["content-type"].startswith("application/json")
            assert "attachment" in resp_json.headers.get("content-disposition", "")
            data = resp_json.json()
            assert data["run_id"] == str(run_id)

            # 2. HTML report download
            resp_html = client.get(f"/v1/reviews/{run_id}/report?format=html", headers=headers)
            assert resp_html.status_code == 200
            assert "text/html" in resp_html.headers["content-type"]
            assert "<!DOCTYPE html>" in resp_html.text

            # 3. PDF report download
            resp_pdf = client.get(f"/v1/reviews/{run_id}/report?format=pdf", headers=headers)
            assert resp_pdf.status_code == 200
            assert resp_pdf.headers["content-type"] == "application/pdf"
            assert resp_pdf.content.startswith(b"%PDF-")

            # 4. Executive summary PDF
            resp_exec = client.get(f"/v1/reviews/{run_id}/report/executive.pdf", headers=headers)
            assert resp_exec.status_code == 200
            assert resp_exec.headers["content-type"] == "application/pdf"
            assert resp_exec.content.startswith(b"%PDF-")


def test_report_download_tenant_isolation(mock_review_run):
    mock_redis = MockRedis()
    other_tenant = uuid.uuid4()
    token_other = create_access_token(
        user_id=uuid.uuid4(),
        tenant_id=other_tenant,
        role="developer",
    )
    headers_other = {"Authorization": f"Bearer {token_other}"}

    async def mock_get_run(db, run_id, tenant_id):
        if run_id == mock_review_run.run_id and tenant_id == mock_review_run.tenant_id:
            return mock_review_run
        return None

    with patch("app.main.create_tables", new=AsyncMock()), \
         patch("app.api.rate_limit.get_redis", return_value=mock_redis), \
         patch("app.api.idempotency.get_redis", return_value=mock_redis), \
         patch("app.api.v1.reviews.get_review_run", side_effect=mock_get_run):

        with TestClient(app) as client:
            resp = client.get(
                f"/v1/reviews/{mock_review_run.run_id}/report?format=json",
                headers=headers_other,
            )
            assert resp.status_code == 404
