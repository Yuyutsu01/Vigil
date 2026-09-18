"""
Evaluation Runner: executes corpus test cases through Vigil and persists metrics.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_review_graph
from app.agents.llm_provider import MockProvider
from app.evaluation.corpus import CorpusLoader
from app.evaluation.metrics import MetricSummary, compute_metrics
from app.models.evaluation import EvaluationRun

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Orchestrates evaluation runs across disk corpora."""

    def __init__(self, loader: Optional[CorpusLoader] = None):
        self.loader = loader or CorpusLoader()

    async def run_suite(
        self,
        suite: str = "all",
        triggered_by: Optional[uuid.UUID] = None,
        db: Optional[AsyncSession] = None,
    ) -> Tuple[EvaluationRun, MetricSummary]:
        """Execute evaluation suite, compute metrics, and persist run record."""
        started_at = datetime.now(timezone.utc)
        test_cases = self.loader.load_suite(suite)

        eval_records = []
        dummy_tenant = uuid.UUID("00000000-0000-0000-0000-000000000099")

        for tc in test_cases:
            run_id = uuid.uuid4()
            state = await run_review_graph(
                run_id=run_id,
                tenant_id=dummy_tenant,
                source_code=tc.source_code,
                language=tc.language,
                provider=MockProvider(),
            )

            detected_rules = [f.rule_id for f in state.final_findings if f.rule_id]
            eval_records.append(
                {
                    "name": tc.name,
                    "is_vulnerable": tc.is_vulnerable,
                    "expected_rule_ids": tc.expected_rule_ids,
                    "detected_rule_ids": detected_rules,
                    "findings": state.final_findings,
                }
            )

        metrics = compute_metrics(eval_records)
        completed_at = datetime.now(timezone.utc)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        from app.telemetry import create_span
        with create_span(
            f"evaluation.run.{suite}",
            {
                "suite": suite,
                "duration_ms": duration_ms,
                "samples_count": len(test_cases),
                "f1": metrics.f1,
            },
        ):
            pass

        eval_run = EvaluationRun(
            evaluation_run_id=uuid.uuid4(),
            suite=suite,
            started_at=started_at,
            completed_at=completed_at,
            precision=metrics.precision,
            recall=metrics.recall,
            f1=metrics.f1,
            per_rule_breakdown={
                "summary": {
                    "total_samples": metrics.total_samples,
                    "true_positives": metrics.true_positives,
                    "false_positives": metrics.false_positives,
                    "false_negatives": metrics.false_negatives,
                    "true_negatives": metrics.true_negatives,
                    "evidence_completeness": metrics.evidence_completeness,
                },
                "rules": metrics.per_rule_breakdown,
            },
            triggered_by=triggered_by,
        )

        if db is not None:
            db.add(eval_run)
            await db.commit()

        return eval_run, metrics
