"""
Integration tests for GitHub repository policy enforcement (FR-104, B5, M1).
Tests policy language filtering, path ignore patterns, max files cap, and review fork/draft PR settings.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.integrations.github.policy import is_file_eligible
from app.integrations.github.scope import resolve_review_scope
from app.integrations.github.snapshot import SnapshotFile
from app.models.repository import (
    IntegrationCredential,
    Repository,
    RepositoryPolicy,
)
from app.models.tenant import Tenant
from app.services.repo_review_service import RepoReviewService


@pytest.mark.asyncio
async def test_policy_language_filtering_enforced():
    """Verify only files matching enabled_languages are analyzed."""
    enabled_languages = ["python"]
    ignored_paths = ["vendor/**"]

    assert is_file_eligible("src/main.py", enabled_languages, ignored_paths)[0] is True
    assert is_file_eligible("src/app.js", enabled_languages, ignored_paths)[0] is False
    assert is_file_eligible("src/Component.tsx", enabled_languages, ignored_paths)[0] is False


@pytest.mark.asyncio
async def test_policy_glob_ignored_paths_enforced():
    """Verify glob patterns in ignored_paths correctly filter files."""
    enabled_languages = ["python", "javascript", "typescript"]
    ignored_paths = ["tests/**", "docs/*", "*.min.js", "vendor/**"]

    assert is_file_eligible("src/service.py", enabled_languages, ignored_paths)[0] is True
    assert is_file_eligible("tests/test_service.py", enabled_languages, ignored_paths)[0] is False
    assert is_file_eligible("tests/unit/test_foo.py", enabled_languages, ignored_paths)[0] is False
    assert is_file_eligible("docs/readme.md", enabled_languages, ignored_paths)[0] is False
    assert is_file_eligible("static/bundle.min.js", enabled_languages, ignored_paths)[0] is False
    assert is_file_eligible("vendor/bundle/pkg.py", enabled_languages, ignored_paths)[0] is False


@pytest.mark.asyncio
async def test_policy_max_files_cap_enforced():
    """Verify scope resolution respects max_files limit from policy."""
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
    cred_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    async with session_maker() as session:
        session.add(Tenant(tenant_id=tenant_id, name="Policy Cap Tenant"))
        await session.commit()

        cred = IntegrationCredential(
            credential_id=cred_id,
            tenant_id=tenant_id,
            provider="github",
            installation_id=444,
            encrypted_private_key_ref="vault://key",
        )
        session.add(cred)

        # Policy sets max_files_per_review = 3
        policy = RepositoryPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            enabled_languages=["python"],
            ignored_paths=[],
            ignored_rules=[],
            max_files_per_review=3,
        )
        session.add(policy)

        repo = Repository(
            repository_id=repo_id,
            tenant_id=tenant_id,
            installation_id=cred_id,
            policy_id=policy_id,
            external_id=444555,
            full_name="vigil-test/policy-cap-repo",
            default_branch="main",
            is_connected=True,
        )
        session.add(repo)
        await session.commit()

    # Re-fetch repo
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    async with session_maker() as session:
        q = (
            select(Repository)
            .options(selectinload(Repository.credential), selectinload(Repository.policy))
            .where(Repository.repository_id == repo_id)
        )
        repo_obj = (await session.execute(q)).scalar_one()

        # Mock resolve_review_scope with 10 files, but policy allows at most 3
        mock_raw_files = [
            SnapshotFile(path=f"file_{i}.py", content=f"x = {i}\n", language="python", size_bytes=10)
            for i in range(10)
        ]

        async def mock_resolve(*args, **kwargs):
            max_f = kwargs.get("max_files", 500)
            return mock_raw_files[:max_f]

        with patch("app.services.repo_review_service.resolve_review_scope", new=mock_resolve), \
             patch("app.services.repo_review_service.run_review_graph") as mock_graph:
            
            mock_state = AsyncMock()
            mock_state.token_usage = 100
            mock_state.iterations = 1
            mock_state.parked_reason = None
            mock_state.final_findings = []
            mock_state.tool_findings = []
            mock_graph.return_value = mock_state

            svc = RepoReviewService(session)
            review_run, repo_review = await svc.execute_repo_review(
                tenant_id=tenant_id,
                repo=repo_obj,
                ref_type="branch",
                ref_value="main",
                scope_mode="full_repo",
            )

            # Assert only 3 files analyzed
            assert repo_review.file_count == 3
            assert mock_graph.call_count == 3


@pytest.mark.asyncio
async def test_policy_empty_files_handling():
    """Verify that scoped review over 0 eligible files completes cleanly."""
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
    cred_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    async with session_maker() as session:
        session.add(Tenant(tenant_id=tenant_id, name="Empty Repo Tenant"))
        await session.commit()

        cred = IntegrationCredential(
            credential_id=cred_id,
            tenant_id=tenant_id,
            provider="github",
            installation_id=111,
            encrypted_private_key_ref="vault://key",
        )
        session.add(cred)

        policy = RepositoryPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            enabled_languages=["python"],
            ignored_paths=["**"],
            ignored_rules=[],
            max_files_per_review=10,
        )
        session.add(policy)

        repo = Repository(
            repository_id=repo_id,
            tenant_id=tenant_id,
            installation_id=cred_id,
            policy_id=policy_id,
            external_id=111222,
            full_name="vigil-test/empty-repo",
            default_branch="main",
            is_connected=True,
        )
        session.add(repo)
        await session.commit()

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.review import ReviewStatus

    async with session_maker() as session:
        q = (
            select(Repository)
            .options(selectinload(Repository.credential), selectinload(Repository.policy))
            .where(Repository.repository_id == repo_id)
        )
        repo_obj = (await session.execute(q)).scalar_one()

        with patch("app.services.repo_review_service.resolve_review_scope", new=AsyncMock(return_value=[])):
            svc = RepoReviewService(session)
            review_run, repo_review = await svc.execute_repo_review(
                tenant_id=tenant_id,
                repo=repo_obj,
                ref_type="branch",
                ref_value="main",
                scope_mode="full_repo",
            )

            assert repo_review.file_count == 0
            assert repo_review.llm_calls == 0
            assert repo_review.tokens_used == 0
            assert review_run.status == ReviewStatus.completed


def test_case_insensitive_path_filtering():
    """Verify that path filtering matches case-insensitively and normalizes backslashes."""
    enabled = ["python"]
    ignored = ["tests/**", "vendor/**"]

    assert is_file_eligible("Tests/Unit/Test_Foo.py", enabled, ignored)[0] is False
    assert is_file_eligible("src\\nested\\module.py", enabled, ignored)[0] is True
    assert is_file_eligible("VENDOR\\lib\\lib.py", enabled, ignored)[0] is False
    assert is_file_eligible("SRC\\APP.PY", enabled, ignored)[0] is True


@pytest.mark.asyncio
async def test_policy_auto_review_toggle_defaults():
    """Verify repository policy default toggle values upon persistence."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    tenant_id = uuid.uuid4()

    async with session_maker() as session:
        session.add(Tenant(tenant_id=tenant_id, name="Defaults Tenant"))
        policy = RepositoryPolicy(
            tenant_id=tenant_id,
            enabled_languages=["python", "javascript", "typescript"],
            ignored_paths=["tests/**"],
            ignored_rules=[],
        )
        session.add(policy)
        await session.commit()
        await session.refresh(policy)

        # Verify default column flags are applied correctly on persistence
        assert policy.auto_review_on_pr is True
        assert policy.auto_review_on_push is False
        assert policy.review_fork_prs is False
        assert policy.review_draft_prs is False

