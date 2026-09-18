"""
A9. PR Review Agent (LLM) — generates draft pull request review summaries and inline comments.
Enforces diff hunk line mapping, 4 KB comment limits, audit signatures, and cost caps.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from app.agents.llm_provider import ModelProvider, get_provider
from app.agents.prompt_loader import format_pr_review_prompt
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class DraftCommentOutput(BaseModel):
    """Inline comment proposal targeting a specific file and line."""

    path: str
    line: int
    body: str


class PRReviewDraftOutput(BaseModel):
    """Overall review output containing executive summary and line-level comments."""

    summary_markdown: str = ""
    comments: List[DraftCommentOutput] = Field(default_factory=list)


def extract_diff_modified_lines(pr_diff: str) -> Dict[str, Set[int]]:
    """
    Parse unified diff text to identify lines modified or added in the new file.
    Returns mapping of file path -> set of modified line numbers.
    """
    modified_lines: Dict[str, Set[int]] = {}
    current_file = None
    current_line = 0

    hunk_header_re = re.compile(r"^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@")

    for line in pr_diff.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            if current_file not in modified_lines:
                modified_lines[current_file] = set()
            continue

        if not current_file:
            continue

        hunk_match = hunk_header_re.match(line)
        if hunk_match:
            current_line = int(hunk_match.group(1))
            continue

        if line.startswith("+") and not line.startswith("+++"):
            modified_lines[current_file].add(current_line)
            current_line += 1
        elif line.startswith(" "):
            current_line += 1
        # lines starting with '-' are deletions and do not advance new file line counter

    return modified_lines


class PRReviewAgent:
    """Agent A9: LLM-powered governed PR review draft generation."""

    def __init__(
        self,
        provider: Optional[ModelProvider] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or get_provider(self.settings.llm_provider)

    async def generate_draft(
        self,
        pr_diff: str,
        findings: List[Any],
        review_id: str,
        cost_guard: Optional[Dict[str, float]] = None,
    ) -> PRReviewDraftOutput:
        """
        Generate draft review summary and inline comments.
        Enforces budget caps, diff hunk line constraints, and signature lines.
        """
        # 1. Budget cap enforcement
        if cost_guard is not None:
            accumulated_cost = cost_guard.get("total_cost_usd", 0.0)
            accumulated_tokens = cost_guard.get("total_tokens", 0)
            if (
                accumulated_cost >= self.settings.pr_review_generation_max_cost_usd
                or accumulated_tokens >= self.settings.pr_review_generation_max_tokens
            ):
                raise RuntimeError(
                    f"PR review generation halted: budget exhausted (cost=${accumulated_cost:.2f}, "
                    f"tokens={accumulated_tokens})"
                )

        # 2. Serialize findings
        findings_data = []
        for f in findings:
            if isinstance(f, dict):
                findings_data.append(f)
            else:
                findings_data.append({
                    "rule_id": getattr(f, "rule_id", ""),
                    "title": getattr(f, "title", ""),
                    "severity": getattr(f, "severity", ""),
                    "start_line": getattr(f, "start_line", None),
                    "rationale": getattr(f, "rationale", ""),
                    "file_path": getattr(f, "file_path", getattr(f, "path", "")),
                })
        findings_json = json.dumps(findings_data, indent=2)

        # 3. Format prompt
        prompt, prompt_version = format_pr_review_prompt(pr_diff, findings_json)

        # 4. Invoke LLM provider
        raw_output = await self.provider.generate_structured(prompt, PRReviewDraftOutput)
        if not isinstance(raw_output, PRReviewDraftOutput):
            raw_output = PRReviewDraftOutput(
                summary_markdown="Vigil Governed PR Review draft.",
                comments=[],
            )

        # Update cost tracking
        if cost_guard is not None:
            cost_guard["total_cost_usd"] = cost_guard.get("total_cost_usd", 0.0) + 0.015
            cost_guard["total_tokens"] = cost_guard.get("total_tokens", 0) + 1200

        # 5. Extract modified line sets for diff hunk gating
        modified_lines_by_file = extract_diff_modified_lines(pr_diff)

        # 6. Filter, validate, and append signatures
        signature = f"\n\n---\n*Reported by Vigil Governed PR Review [Review #{review_id[:8]}]*"
        valid_comments: List[DraftCommentOutput] = []

        for c in raw_output.comments:
            clean_path = c.path.lstrip("/")
            # Diff hunk line gating: ensure line is modified in diff
            file_mods = modified_lines_by_file.get(clean_path, set())
            if not file_mods:
                # check if diff path matches ending
                for k, v in modified_lines_by_file.items():
                    if k.endswith(clean_path) or clean_path.endswith(k):
                        file_mods = v
                        clean_path = k
                        break

            # If modified line information exists, comment must target modified line
            if file_mods and c.line not in file_mods:
                logger.warning(
                    "Dropping comment on %s:%d: line is not in PR diff hunks",
                    clean_path,
                    c.line,
                )
                continue

            # Length cap check
            body = c.body
            if len(body) > self.settings.pr_comment_max_chars:
                body = body[: self.settings.pr_comment_max_chars - 64] + " ...[truncated]"

            # Append signature
            body_with_sig = body + signature
            valid_comments.append(
                DraftCommentOutput(
                    path=clean_path,
                    line=c.line,
                    body=body_with_sig,
                )
            )

        # Format executive summary with signature
        summary = raw_output.summary_markdown or "Vigil automated review completed."
        summary_with_sig = summary + signature

        return PRReviewDraftOutput(
            summary_markdown=summary_with_sig,
            comments=valid_comments,
        )
