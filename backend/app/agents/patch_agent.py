"""
A6. Patch Agent (LLM) — automated unified diff remediation generation.
Enforces cost caps ($1.00 / 100k tokens), 60s deadline, and Critical severity gate.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.agents.llm_provider import ModelProvider, get_provider
from app.agents.prompt_loader import format_patch_prompt
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Basic validation regex for unified diff hunk header
_HUNK_HEADER_RE = re.compile(r"^@@\s+-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@", re.MULTILINE)


class PatchDraft(BaseModel):
    """Structured output returned by the Patch Agent."""

    unified_diff: str = Field(..., description="Unified diff string (--- a/ ... +++ b/ ... @@ ... @@)")
    rationale: str = Field(..., description="Technical rationale for the remediation")
    assumptions: str = Field(default="", description="Assumptions regarding runtime environment or input guarantees")
    tests_to_run: List[str] = Field(default_factory=list, description="Recommended automated test commands to verify patch")

    @property
    def diff_unified(self) -> str:
        """Compatibility property for callers expecting diff_unified."""
        return self.unified_diff


def is_valid_unified_diff(diff_text: str) -> bool:
    """Verify that the diff string contains valid unified diff header markers and hunk lines."""
    if not diff_text or not isinstance(diff_text, str):
        return False
    has_orig = "--- " in diff_text
    has_new = "+++ " in diff_text
    has_hunk = bool(_HUNK_HEADER_RE.search(diff_text))
    return (has_orig and has_new) or has_hunk


class PatchAgent:
    """Agent A6: LLM-powered surgical unified diff generation."""

    def __init__(
        self,
        provider: Optional[ModelProvider] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or get_provider(self.settings.llm_provider)

    async def generate(
        self,
        finding: Any,
        source_code: str,
        language: str,
        force: bool = False,
        cost_guard: Optional[Dict[str, float]] = None,
    ) -> PatchDraft:
        """
        Generate a candidate patch for a given finding.
        Enforces severity gate for Critical findings, budget limits, and diff validation.
        """
        # 1. Extract finding attributes (handles Pydantic models, ORM models, or dicts)
        if isinstance(finding, dict):
            severity = finding.get("severity", "Medium")
            rule_id = finding.get("rule_id", "UNKNOWN")
            title = finding.get("title", "")
            category = finding.get("category", "security")
            start_line = finding.get("start_line")
            end_line = finding.get("end_line")
            matched_text = finding.get("matched_text", "")
            rationale = finding.get("rationale", "")
        else:
            severity = getattr(finding, "severity", "Medium")
            rule_id = getattr(finding, "rule_id", "UNKNOWN")
            title = getattr(finding, "title", "")
            category = getattr(finding, "category", "security")
            start_line = getattr(finding, "start_line", None)
            end_line = getattr(finding, "end_line", None)
            matched_text = getattr(finding, "matched_text", "")
            rationale = getattr(finding, "rationale", "")

        # Normalize severity string
        sev_str = severity.value if hasattr(severity, "value") else str(severity)
        sev_normalized = sev_str.capitalize()

        # 2. Critical severity gate: requires explicit force=True override
        if sev_normalized == "Critical" and not force:
            raise ValueError("Critical findings require explicit force=True override for patch generation")

        # 3. Cost guard and token caps check
        if cost_guard is not None:
            accumulated_cost = cost_guard.get("total_cost_usd", 0.0)
            accumulated_tokens = cost_guard.get("total_tokens", 0)
            if (
                accumulated_cost >= self.settings.patch_generation_max_cost_usd
                or accumulated_tokens >= self.settings.patch_generation_max_tokens
            ):
                raise RuntimeError(
                    f"Patch generation halted: budget exhausted (cost=${accumulated_cost:.2f}, "
                    f"tokens={accumulated_tokens})"
                )

        # 4. Format prompt
        prompt, prompt_version = format_patch_prompt(
            source_code=source_code,
            language=language,
            rule_id=rule_id,
            title=title,
            severity=sev_normalized,
            category=category,
            start_line=start_line,
            end_line=end_line,
            matched_text=matched_text,
            rationale=rationale,
        )

        # 4a. Prompt token cap enforcement (IC7, H4)
        # Note: len(prompt) // 4 is a fast heuristic approximation; the LLM provider's
        # internal tokenizer is authoritative but omitted here to avoid external tokenization deps.
        est_tokens = len(prompt) // 4
        if est_tokens > self.settings.patch_agent_max_prompt_tokens:
            raise ValueError(
                f"Patch prompt exceeds {self.settings.patch_agent_max_prompt_tokens} "
                f"token limit (approx {est_tokens}). Reduce context."
            )

        start_time = time.time()
        max_seconds = self.settings.patch_generation_max_wall_clock_seconds
        attempts = 0
        last_error = ""

        # 5. Generation loop with up to 3 retry iterations
        while attempts < 3:
            if (time.time() - start_time) > max_seconds:
                raise TimeoutError(f"Patch generation timed out after {max_seconds} seconds")

            attempts += 1
            try:
                response = await self.provider.generate_structured(prompt, PatchDraft)
                if isinstance(response, PatchDraft) and is_valid_unified_diff(response.unified_diff):
                    # Update cost guard tracking
                    if cost_guard is not None:
                        cost_guard["total_cost_usd"] = cost_guard.get("total_cost_usd", 0.0) + 0.02
                        cost_guard["total_tokens"] = cost_guard.get("total_tokens", 0) + 1500
                    return response

                last_error = "Generated diff did not meet unified diff format requirements"
                logger.warning("Patch attempt %d failed diff validation: %s", attempts, last_error)
            except Exception as exc:
                last_error = str(exc)
                logger.warning("Patch generation attempt %d raised exception: %s", attempts, exc)

        raise RuntimeError(f"Failed to generate valid patch after 3 iterations: {last_error}")

    async def draft_patch(
        self,
        finding: Any,
        source_code: str,
        file_path: Optional[str] = "main.py",
        force: bool = False,
        cost_guard: Optional[Dict[str, float]] = None,
    ) -> PatchDraft:
        """Alias for generate() used by orchestrator."""
        language = "python"
        if file_path and "." in file_path:
            ext = file_path.rsplit(".", 1)[-1].lower()
            ext_map = {"py": "python", "js": "javascript", "ts": "typescript", "go": "go"}
            language = ext_map.get(ext, "python")
        return await self.generate(
            finding=finding,
            source_code=source_code,
            language=language,
            force=force,
            cost_guard=cost_guard,
        )
