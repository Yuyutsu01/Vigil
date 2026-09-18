"""
Unit tests for repository review aggregate budget and real usage tracking (B2).
Verifies that repo review accumulates real token usage and iterations from
LangGraph state, halts at cost cap, and sets budget_paused_reason to cost_cap_exceeded.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.state import ReviewGraphState
from app.config import get_settings
from app.database import Base
from app.integrations.github.snapshot import SnapshotFile
from app.models.repository import (
    IntegrationCredential,
    Repository,
    RepositoryPolicy,
    RepositoryReview,
)
from app.models.review import ReviewRun, ReviewStatus
from app.models.tenant import Tenant
from app.services.repo_review_service import RepoReviewService


@pytest.mark.asyncio
async def test_repo_review_stops_at_cost_cap_and_reflects_real_tokens(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    cred_id = uuid.uuid4()

    settings = get_settings()
    # Force low cost cap of $0.50
    monkeypatch.setattr(settings, "repo_review_max_cost_usd", 0.50)
    monkeypatch.setattr(settings, "llm_cost_per_1k_input_tokens", 0.003)

    # 10 mock files
    mock_files = [
        SnapshotFile(
            path=f"src/file_{i}.py",
            content=f"# File {i} content\nx = {i}\n",
            language="python",
            size_bytes=30,
        )
        for i in range(10)
    ]

    # Mock run_review_graph to return state with token_usage=100_000 and iterations=10
    async def mock_run_review_graph(run_id, tenant_id, source_code, language, provider):
        state = ReviewGraphState(
            run_id=run_id,
            tenant_id=tenant_id,
            source_code=source_code,
            language=language,
        )
        state.token_usage = 100_000
        state.iterations = 10
        state.final_findings = []
        return state

    async with session_maker() as session:
        # Seed Tenant first
        session.add(Tenant(tenant_id=tenant_id, name="Budget Tenant"))
        await session.commit()

        cred = IntegrationCredential(
            credential_id=cred_id,
            tenant_id=tenant_id,
            provider="github",
            installation_id=888,
            encrypted_private_key_ref="vault://key",
        )
        session.add(cred)
        policy_id = uuid.uuid4()
        policy = RepositoryPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            enabled_languages=["python"],
            ignored_paths=[],
            ignored_rules=[],
            max_files_per_review=100,
        )
        session.add(policy)

        repo = Repository(
            repository_id=repo_id,
            tenant_id=tenant_id,
            installation_id=cred_id,
            policy_id=policy_id,
            external_id=888999,
            full_name="vigil-org/budget-test-repo",
            default_branch="main",
            is_connected=True,
        )
        session.add(repo)
        await session.commit()

        # Re-fetch repo with relationships loaded
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        q = (
            select(Repository)
            .options(selectinload(Repository.credential), selectinload(Repository.policy))
            .where(Repository.repository_id == repo_id)
        )
        repo_obj = (await session.execute(q)).scalar_one()

        svc = RepoReviewService(session)

        with patch("app.services.repo_review_service.resolve_review_scope", new=AsyncMock(return_value=mock_files)), \
             patch("app.services.repo_review_service.run_review_graph", new=mock_run_review_graph):

            review_run, repo_review = await svc.execute_repo_review(
                tenant_id=tenant_id,
                repo=repo_obj,
                ref_type="branch",
                ref_value="main",
                scope_mode="full_repo",
                requested_by=user_id,
            )

            # Assert review stopped at cost cap
            assert repo_review.budget_paused_reason == "cost_cap_exceeded"
            assert review_run.status == ReviewStatus.budget_paused

            # Assert real tokens accumulated (2 files processed * 100_000 = 200_000, cost = $0.60 >= $0.50 cap)
            assert repo_review.tokens_used == 200_000
            assert repo_review.llm_calls == 20
            # Tokens are NOT file_size // 4 (~7 tokens per file)
            assert repo_review.tokens_used > 1000
