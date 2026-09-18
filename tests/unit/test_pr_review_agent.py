"""
Unit tests for Agent A9 (PR Review Agent).
Verifies diff hunk line mapping, 4,096 character length capping, and audit signature appending.
"""
import pytest
from app.agents.pr_review_agent import PRReviewAgent, PRReviewDraftOutput, extract_diff_modified_lines
from app.agents.llm_provider import ModelProvider


class CustomPRReviewProvider(ModelProvider):
    """Custom provider returning specific draft comments for boundary testing."""

    def __init__(self, long_comment: bool = False, comment_line: int = 10):
        self.long_comment = long_comment
        self.comment_line = comment_line

    @property
    def provider_name(self) -> str:
        return "mock_pr_review"

    async def generate_structured(self, prompt: str, schema):
        body = "A" * 5000 if self.long_comment else "Consider parameterizing this SQL query."
        return schema(
            summary_markdown="### Review Summary\n\nCode looks solid.",
            comments=[
                {
                    "path": "backend/app/main.py",
                    "line": self.comment_line,
                    "body": body,
                }
            ],
        )


def test_extract_diff_modified_lines():
    """Verify parsing of unified diff hunks into modified line sets."""
    sample_diff = (
        "--- a/backend/app/main.py\n"
        "+++ b/backend/app/main.py\n"
        "@@ -10,3 +10,4 @@\n"
        " context_line_1\n"
        "+added_line_11\n"
        "+added_line_12\n"
        " context_line_13\n"
    )
    mod_lines = extract_diff_modified_lines(sample_diff)
    assert "backend/app/main.py" in mod_lines
    # Lines 11 and 12 are additions (+)
    assert 11 in mod_lines["backend/app/main.py"]
    assert 12 in mod_lines["backend/app/main.py"]
    assert 10 not in mod_lines["backend/app/main.py"]  # context line


@pytest.mark.asyncio
async def test_pr_review_agent_signature_and_diff_gating():
    """Verify comments on modified lines receive signature, while unmodified lines are filtered."""
    sample_diff = (
        "--- a/backend/app/main.py\n"
        "+++ b/backend/app/main.py\n"
        "@@ -1,4 +1,5 @@\n"
        " line1\n"
        "+line2\n"
        " line3\n"
    )

    # Provider returning comment on line 2 (modified)
    prov_valid = CustomPRReviewProvider(comment_line=2)
    agent_valid = PRReviewAgent(provider=prov_valid)
    out = await agent_valid.generate_draft(pr_diff=sample_diff, findings=[], review_id="11112222-3333-4444-5555-666677778888")

    assert len(out.comments) == 1
    assert out.comments[0].line == 2
    assert "Reported by Vigil Governed PR Review" in out.comments[0].body
    assert "Reported by Vigil Governed PR Review" in out.summary_markdown

    # Provider returning comment on line 1 (context line, not modified)
    prov_invalid = CustomPRReviewProvider(comment_line=1)
    agent_invalid = PRReviewAgent(provider=prov_invalid)
    out_filtered = await agent_invalid.generate_draft(pr_diff=sample_diff, findings=[], review_id="11112222-3333-4444-5555-666677778888")

    # Comment on unmodified line must be dropped
    assert len(out_filtered.comments) == 0


@pytest.mark.asyncio
async def test_pr_comment_length_capping():
    """Verify comments exceeding 4,096 characters are truncated."""
    sample_diff = (
        "--- a/backend/app/main.py\n"
        "+++ b/backend/app/main.py\n"
        "@@ -1,2 +1,3 @@\n"
        "+line1\n"
    )
    long_prov = CustomPRReviewProvider(long_comment=True, comment_line=1)
    agent = PRReviewAgent(provider=long_prov)

    out = await agent.generate_draft(pr_diff=sample_diff, findings=[], review_id="11112222")
    assert len(out.comments) == 1
    # Body with signature must remain within reasonable bounds and note truncation
    assert "[truncated]" in out.comments[0].body
    assert len(out.comments[0].body) <= 4096 + 100
