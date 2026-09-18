"""
Security test for Specialist Agent Permission Boundaries (FR-108, Principle of Least Privilege).

Concept:
Every specialist agent in Vigil runs with a statically declared, immutable permission set (AgentPermissions).
Agents must NOT be allowed to perform operations outside their strict authorization envelope:
- Risk Scoring (A10), Dependency Risk (A11), Dataflow (A12), and Executive Summary (A14) cannot execute containers.
- Dependency Risk (A11) cannot access external networks (offline only).
- Read-only analysis agents cannot write to the filesystem.
Attempting an unauthorized action raises PermissionDeniedError and records AGENT_PERMISSION_DENIED in audit logs.
"""
from __future__ import annotations

import json
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.permissions import (
    AgentPermissions,
    PermissionDeniedError,
    SPECIALIST_PERMISSIONS,
    assert_permission,
)
from app.database import Base
from app.models.review import AuditAction, AuditEvent


def test_permission_matrix_least_privilege_invariants():
    """Verify static permission invariants across all registered agents."""
    # 1. Verify all expected specialist agents exist in permissions registry
    expected_agents = {
        "security",
        "quality",
        "patch",
        "validation",
        "pr_review",
        "risk_scoring",
        "dependency_risk",
        "dataflow",
        "test_generation",
        "executive_summary",
    }
    assert expected_agents.issubset(set(SPECIALIST_PERMISSIONS.keys()))

    # 2. Assert sandbox/container execution is forbidden for all agents except validation and test_generation
    for agent_name, perms in SPECIALIST_PERMISSIONS.items():
        if agent_name in {"validation", "test_generation"}:
            assert perms.allow_sandbox is True
        else:
            assert perms.allow_sandbox is False, f"Agent {agent_name} should not have sandbox permission!"

    # 3. Assert network access is forbidden for dependency_risk (offline manifest analysis only)
    dep_perms = SPECIALIST_PERMISSIONS["dependency_risk"]
    assert dep_perms.allow_network is False

    # 4. Assert filesystem write is forbidden for analysis agents
    read_only_agents = ["risk_scoring", "dependency_risk", "dataflow", "executive_summary"]
    for agent_name in read_only_agents:
        assert SPECIALIST_PERMISSIONS[agent_name].allow_fs_write is False


def test_assert_permission_raises_and_prevents_unauthorized_action():
    """Verify assert_permission raises PermissionDeniedError on unauthorized actions."""
    # A10 Risk Scoring cannot execute sandbox
    with pytest.raises(PermissionDeniedError) as exc_info:
        assert_permission("risk_scoring", "allow_sandbox")
    assert "does not have 'allow_sandbox' permission" in str(exc_info.value)

    # A11 Dependency Risk cannot access network
    with pytest.raises(PermissionDeniedError) as exc_info:
        assert_permission("dependency_risk", "allow_network")
    assert "does not have 'allow_network' permission" in str(exc_info.value)

    # A14 Executive Summary cannot write to filesystem
    with pytest.raises(PermissionDeniedError) as exc_info:
        assert_permission("executive_summary", "allow_fs_write")
    assert "does not have 'allow_fs_write' permission" in str(exc_info.value)

    # Allowed actions succeed without error
    assert_permission("risk_scoring", "allow_llm")
    assert_permission("validation", "allow_sandbox")


@pytest.mark.asyncio
async def test_permission_violation_triggers_audit_event():
    """Verify that orchestrator logs AGENT_PERMISSION_DENIED on unauthorized operation."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        from app.services.audit_service import record_audit_event
        tenant_id = uuid.uuid4()
        task_id = str(uuid.uuid4())

        # Simulate orchestrator recording permission violation
        await record_audit_event(
            session,
            tenant_id=tenant_id,
            action=AuditAction.AGENT_PERMISSION_DENIED,
            target_type="AgentTask",
            target_id=task_id,
            metadata={"agent": "risk_scoring", "attempted": "allow_container_exec"},
        )
        await session.commit()

        # Verify audit event persisted
        stmt = select(AuditEvent).where(AuditEvent.action == AuditAction.AGENT_PERMISSION_DENIED)
        res = await session.execute(stmt)
        audits = res.scalars().all()
        assert len(audits) == 1
        meta = json.loads(audits[0].metadata_json or "{}")
        assert meta["agent"] == "risk_scoring"
        assert meta["attempted"] == "allow_container_exec"
