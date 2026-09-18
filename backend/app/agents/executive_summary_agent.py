"""
A14: Executive Summary Agent (FR-108, D1, D5, M4).
Produces high-level narrative risk summaries and composite risk scoring for completed or partial reviews.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.agents.llm_provider import ModelProvider, get_provider
from app.agents.permissions import assert_permission
from app.agents.policy import invoke_llm_with_policy

logger = logging.getLogger(__name__)


class ExecutiveSummaryInput(BaseModel):
    final_findings: List[Any] = Field(default_factory=list)
    review_metadata: Dict[str, Any] = Field(default_factory=dict)
    agent_execution_summary: Dict[str, Any] = Field(default_factory=dict)


class ExecutiveSummaryOutput(BaseModel):
    executive_summary: str
    primary_risk_areas: List[str] = Field(default_factory=list)
    remediation_roadmap: List[str] = Field(default_factory=list)
    composite_risk_score: float = 0.0


class ExecutiveSummaryAgent:
    """
    A14 Specialist Agent synthesizing strategic findings into executive summaries.
    """

    def __init__(self, provider: Optional[ModelProvider] = None):
        from app.config import get_settings
        settings = get_settings()
        self.provider = provider or get_provider(
            settings.llm_provider,
            model_name=settings.llm_model_name,
            api_key=settings.openai_api_key or settings.anthropic_api_key,
        )

    async def generate(
        self,
        input_data: ExecutiveSummaryInput,
        run_id: Optional[uuid.UUID] = None,
        tenant_id: Optional[uuid.UUID] = None,
    ) -> ExecutiveSummaryOutput:
        return await self.generate_summary(input_data, run_id=run_id, tenant_id=tenant_id)

    async def generate_summary(
        self,
        input_data: ExecutiveSummaryInput,
        run_id: Optional[uuid.UUID] = None,
        tenant_id: Optional[uuid.UUID] = None,
    ) -> ExecutiveSummaryOutput:
        # Enforce static permission envelope (D5)
        assert_permission("executive_summary", "allow_llm")

        # IC6: Skip LLM call on empty findings
        if not input_data.final_findings:
            return ExecutiveSummaryOutput(
                executive_summary="No findings detected in this review.",
                primary_risk_areas=[],
                remediation_roadmap=[],
                composite_risk_score=0.0,
            )

        exec_summary = input_data.agent_execution_summary
        if "failed_agents" in exec_summary and isinstance(exec_summary["failed_agents"], list):
            failed_agents = exec_summary["failed_agents"]
            total_agents = exec_summary.get("total_tasks", len(failed_agents) + 1)
        else:
            failed_agents = [
                agent for agent, status in exec_summary.items() if status in {"failed", "timeout"}
            ]
            total_agents = len(exec_summary)

        completed_agents = max(0, total_agents - len(failed_agents))

        partial_prefix = ""
        if failed_agents and total_agents > 0:
            partial_prefix = f"Partial review: {completed_agents} of {total_agents} agents completed. "

        def _get_val(f, key, default=""):
            if hasattr(f, key):
                return getattr(f, key)
            if isinstance(f, dict):
                return f.get(key, default)
            return default

        findings_count = len(input_data.final_findings)
        critical_count = sum(
            1 for f in input_data.final_findings
            if str(_get_val(f, "severity", _get_val(f, "severity_raw", ""))).lower() == "critical"
        )
        high_count = sum(
            1 for f in input_data.final_findings
            if str(_get_val(f, "severity", _get_val(f, "severity_raw", ""))).lower() == "high"
        )

        # Compute composite risk score (0.0 - 10.0 scale)
        raw_score = (critical_count * 3.0) + (high_count * 1.5) + (findings_count * 0.2)
        composite_score = min(10.0, round(raw_score, 1))

        # Risk areas
        categories = list({
            str(_get_val(f, "category", "security")) for f in input_data.final_findings
        })
        primary_risks = categories[:3] if categories else ["None identified"]

        roadmap = [
            f"Remediate {critical_count} critical findings immediately" if critical_count else "Maintain current security baselines",
            f"Review {high_count} high-severity findings prior to production deployment" if high_count else "Audit dependency lockfiles",
        ]

        system_prompt = "You are the Vigil Executive Summary Agent (A14). Produce an executive overview of the code scan."
        user_prompt = f"Findings summary: {findings_count} total ({critical_count} critical, {high_count} high). Risks: {categories}."

        narrative = f"{partial_prefix}Review identified {findings_count} issues across {len(categories)} categories. Composite risk score: {composite_score}/10."
        if self.provider:
            try:
                structured = await self.provider.generate_structured(
                    f"{system_prompt}\n\n{user_prompt}",
                    ExecutiveSummaryOutput,
                )
                if isinstance(structured, ExecutiveSummaryOutput):
                    # Ensure partial failure prefix is maintained if partial
                    if partial_prefix and not structured.executive_summary.startswith("Partial review:"):
                        structured.executive_summary = f"{partial_prefix}{structured.executive_summary}"
                    return structured
            except Exception:
                pass

        return ExecutiveSummaryOutput(
            executive_summary=narrative,
            primary_risk_areas=primary_risks,
            remediation_roadmap=roadmap,
            composite_risk_score=composite_score,
        )


async def run_executive_summary_agent(
    inp: ExecutiveSummaryInput,
    provider: Optional[ModelProvider] = None,
    run_id: Optional[uuid.UUID] = None,
    tenant_id: Optional[uuid.UUID] = None,
) -> ExecutiveSummaryOutput:
    """Async entrypoint for A14 Executive Summary Agent."""
    agent = ExecutiveSummaryAgent(provider=provider)
    return await agent.generate_summary(inp, run_id=run_id, tenant_id=tenant_id)
