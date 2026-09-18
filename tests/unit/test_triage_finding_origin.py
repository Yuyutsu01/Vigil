"""
Unit tests for finding origin persistence: tool vs rule vs agent (B4.4).
Verifies:
- tool-origin finding -> Finding.origin == 'tool'
- rule-origin finding -> Finding.origin == 'rule'
- agent-origin finding -> Finding.origin == 'agent'
- tool finding persists tool_name, tool_version, and raw_evidence_ref
- rule/agent findings have tool_name=None, tool_version=None, raw_evidence_ref=None
"""
import sys
import uuid
from pathlib import Path
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.database import Base
from app.models.finding import EvidenceKind, Finding, FindingOrigin, Severity
from app.models.review import ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import Tenant
from app.models.tool_finding import ToolFinding
from app.rules.engine import DetectedFinding
from app.services.review_service import _persist_findings


@pytest.mark.asyncio
async def test_finding_origin_persistence():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id = uuid.uuid4()
        run_id = uuid.uuid4()
        artifact_id = uuid.uuid4()
        tool_finding_id = uuid.uuid4()

        tenant = Tenant(tenant_id=tenant_id, name="Origin Test Tenant")
        from datetime import datetime, timezone
        artifact = SourceArtifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            content="print(1)",
            checksum="chk",
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
        tool_record = ToolFinding(
            tool_finding_id=tool_finding_id,
            run_id=run_id,
            tenant_id=tenant_id,
            tool_name="semgrep",
            tool_version="1.90.0",
            rule_id="semgrep-001",
            severity_raw="ERROR",
            message="Semgrep vulnerability",
            file_path="app.py",
            start_line=1,
            start_col=1,
            end_line=1,
            end_col=10,
            raw_evidence={"tool": "semgrep"},
        )
        session.add_all([tenant, artifact, run, tool_record])
        await session.commit()

        # 1. Create three detected findings: rule, tool, agent
        rule_finding = DetectedFinding(
            rule_id="VIGIL-SEC-001",
            category="security",
            severity="Critical",
            confidence=0.99,
            title="Rule Title",
            rationale="Rule Rationale",
            remediation="Rule Fix",
            evidence_kind=EvidenceKind.token_regex,
            ast_path="line_1",
            matched_text="secret_key = 1",
            origin=FindingOrigin.rule,
            tool_name="should_be_cleared_for_rule",
            tool_version="v1",
        )

        tool_finding = DetectedFinding(
            rule_id="semgrep-001",
            category="security",
            severity="High",
            confidence=0.85,
            title="Tool Title",
            rationale="Tool Rationale",
            remediation="Tool Fix",
            evidence_kind=EvidenceKind.ast_node,
            ast_path="line_1",
            matched_text="eval(input)",
            origin=FindingOrigin.tool,
            tool_name="semgrep",
            tool_version="1.90.0",
            raw_evidence_ref=tool_finding_id,
        )

        agent_finding = DetectedFinding(
            rule_id="LLM-SEC-001",
            category="security",
            severity="Medium",
            confidence=0.70,
            title="Agent Title",
            rationale="Agent Rationale",
            remediation="Agent Fix",
            evidence_kind=EvidenceKind.llm_reasoning,
            ast_path="line_1/reasoning",
            matched_text="potential injection",
            origin=FindingOrigin.agent,
            tool_name="should_be_cleared_for_agent",
            tool_version="v1",
        )

        tool_map = {("semgrep", "semgrep-001"): tool_finding_id}

        await _persist_findings(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            detected=[rule_finding, tool_finding, agent_finding],
            tool_finding_map=tool_map,
        )
        await session.commit()

        stmt = select(Finding).where(Finding.run_id == run_id).order_by(Finding.confidence.desc())
        result = await session.execute(stmt)
        saved = result.scalars().all()
        assert len(saved) == 3

        # Rule finding assertions
        saved_rule = next(f for f in saved if f.origin == FindingOrigin.rule)
        assert saved_rule.origin == FindingOrigin.rule
        assert saved_rule.tool_name is None
        assert saved_rule.tool_version is None
        assert saved_rule.raw_evidence_ref is None

        # Tool finding assertions
        saved_tool = next(f for f in saved if f.origin == FindingOrigin.tool)
        assert saved_tool.origin == FindingOrigin.tool
        assert saved_tool.tool_name == "semgrep"
        assert saved_tool.tool_version == "1.90.0"
        assert saved_tool.raw_evidence_ref == tool_finding_id

        # Agent finding assertions
        saved_agent = next(f for f in saved if f.origin == FindingOrigin.agent)
        assert saved_agent.origin == FindingOrigin.agent
        assert saved_agent.tool_name is None
        assert saved_agent.tool_version is None
        assert saved_agent.raw_evidence_ref is None

    await engine.dispose()
