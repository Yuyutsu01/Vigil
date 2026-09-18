"""
Integration test for raw_evidence_ref foreign key constraint (B3).
Verifies that deleting a ToolFinding cascades ON DELETE SET NULL on Finding.raw_evidence_ref.
"""
import sys
import uuid
from pathlib import Path
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.database import Base
from app.models.finding import Finding, FindingOrigin, Severity
from app.models.review import ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import Tenant
from app.models.tool_finding import ToolFinding


@pytest.mark.asyncio
async def test_tool_finding_fk_on_delete_set_null():
    # Use SQLite in-memory with foreign keys enabled
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Enable SQLite foreign key enforcement
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id = uuid.uuid4()
        run_id = uuid.uuid4()
        artifact_id = uuid.uuid4()
        tool_finding_id = uuid.uuid4()
        finding_id = uuid.uuid4()

        tenant = Tenant(
            tenant_id=tenant_id,
            name="FK Test Tenant",
        )
        from datetime import datetime, timezone
        artifact = SourceArtifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            content="print(1)",
            checksum="chk123",
            language="python",
            size_bytes=8,
            retention_until=datetime.now(timezone.utc),
        )
        run = ReviewRun(
            run_id=run_id,
            tenant_id=tenant_id,
            artifact_id=artifact_id,
            status=ReviewStatus.completed,
            requested_by=uuid.uuid4(),
        )
        tool_finding = ToolFinding(
            tool_finding_id=tool_finding_id,
            run_id=run_id,
            tenant_id=tenant_id,
            tool_name="bandit",
            tool_version="1.9.4",
            rule_id="B101",
            severity_raw="LOW",
            message="Test assert finding",
            file_path="source.py",
            start_line=1,
            start_col=1,
            end_line=1,
            end_col=10,
            raw_evidence={"code": "assert True"},
        )
        finding = Finding(
            finding_id=finding_id,
            run_id=run_id,
            tenant_id=tenant_id,
            fingerprint="fp_fk_test",
            origin=FindingOrigin.tool,
            tool_name="bandit",
            tool_version="1.9.4",
            raw_evidence_ref=tool_finding_id,
            rule_id="B101",
            category="security",
            severity=Severity.low,
            confidence=0.9,
            title="Assert used",
            rationale="Assert used in production",
            remediation="Replace with proper check",
        )

        session.add(tenant)
        await session.flush()
        session.add(artifact)
        await session.flush()
        session.add(run)
        await session.flush()
        session.add(tool_finding)
        await session.flush()
        session.add(finding)
        await session.commit()

        # Verify finding exists and points to tool_finding_id
        stmt = select(Finding).where(Finding.finding_id == finding_id)
        result = await session.execute(stmt)
        saved_finding = result.scalar_one()
        assert saved_finding.raw_evidence_ref == tool_finding_id

        # Delete the ToolFinding record
        await session.delete(tool_finding)
        await session.commit()
        session.expire_all()

        # Query finding again in a new transaction
        stmt = select(Finding).where(Finding.finding_id == finding_id)
        result = await session.execute(stmt)
        updated_finding = result.scalar_one()

        # B3 Verification: raw_evidence_ref must be set to NULL (not raise error or leave dangling FK)
        assert updated_finding.raw_evidence_ref is None

    await engine.dispose()
