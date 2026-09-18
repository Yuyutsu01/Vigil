"""
Pydantic schemas for GitHub repository connection, policy, and scoped review (FR-103, FR-104).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
import uuid

from pydantic import BaseModel, Field


class RepositoryPolicySchema(BaseModel):
    policy_id: Optional[uuid.UUID] = None
    enabled_languages: List[str] = Field(default_factory=lambda: ["python", "javascript", "typescript"])
    ignored_paths: List[str] = Field(default_factory=list)
    ignored_rules: List[str] = Field(default_factory=list)
    max_files_per_review: int = 500
    auto_review_on_push: bool = False
    auto_review_on_pr: bool = True
    review_fork_prs: bool = False
    review_draft_prs: bool = False

    model_config = {"from_attributes": True}


class RepositoryPolicyUpdate(BaseModel):
    enabled_languages: Optional[List[str]] = None
    ignored_paths: Optional[List[str]] = None
    ignored_rules: Optional[List[str]] = None
    max_files_per_review: Optional[int] = None
    auto_review_on_push: Optional[bool] = None
    auto_review_on_pr: Optional[bool] = None
    review_fork_prs: Optional[bool] = None
    review_draft_prs: Optional[bool] = None


class RepositoryResponse(BaseModel):
    repository_id: uuid.UUID
    tenant_id: uuid.UUID
    provider: str
    external_id: int
    full_name: str
    default_branch: str
    is_connected: bool
    policy: Optional[RepositoryPolicySchema] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectURLResponse(BaseModel):
    install_url: str
    state: str


class TriggerRepoReviewRequest(BaseModel):
    ref_type: str = "branch"  # branch, commit, pr, directory
    ref_value: str = "main"
    scope_mode: str = "full_repo"  # full_repo, changed_files, directory, files
    directory_filter: Optional[str] = None
    specific_files: Optional[List[str]] = None


class CostPreviewResponse(BaseModel):
    file_count: int
    total_bytes: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    cost_cap_usd: float
    exceeds_cap: bool


class RepositoryReviewResponse(BaseModel):
    repository_review_id: uuid.UUID
    repository_id: uuid.UUID
    review_run_id: uuid.UUID
    ref_type: str
    ref_value: str
    scope_mode: str
    file_count: int
    status: str
    budget_paused_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
