"""
Multi-Agent Orchestration Layer (FR-108).
Coordinates specialist agents across parallel subtrees, synchronization barriers,
static permission boundaries, deterministic triage arbitration, and aggregate budget controls.

Key invariants:
- Immutable context snapshots: agents cannot mutate review input.
- Subtree 1 parallel fan-out (A11, A3, A4, A12) bounded by 30s barrier timeout.
- Unhandled agent errors are caught, logged, and audited; review completes as 'partial'.
- Static permissions enforced: unauthorized capabilities raise PermissionDeniedError.
- Deterministic Triage (A5) is the supreme arbiter: baseline rule findings cannot be suppressed by A10.
- Subtree 2 sequential pipeline (A6 -> A13 -> A7). Shell safety verified before sandbox execution.
- Cumulative token budget capped at 200,000 tokens; exceeding marks status as 'budget_paused'.
- OpenTelemetry instrumentation: root span 'vigil.orchestration_run', child spans 'vigil.agent.{agent_name}'.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.capabilities import (
    capability_llm_quality,
    capability_llm_security,
    capability_parse,
    capability_run_adapters,
    capability_run_rules,
    capability_triage,
)
from app.agents.dataflow_agent import DataflowInput, DataflowOutput, run_dataflow_agent
from app.agents.dependency_agent import DependencyRiskInput, DependencyRiskOutput, run_dependency_agent
from app.agents.executive_summary_agent import ExecutiveSummaryInput, ExecutiveSummaryOutput, run_executive_summary_agent
from app.agents.llm_provider import ModelProvider, get_provider
from app.agents.patch_agent import PatchAgent, PatchDraft
from app.agents.permissions import assert_permission, PermissionDeniedError
from app.agents.risk_scoring_agent import RiskScoringInput, RiskScoringOutput, SanitizedPrecedent, run_risk_scoring_agent
from app.agents.state import ReviewGraphState
from app.agents.test_generation_agent import (
    TestGenerationInput,
    TestGenerationOutput,
    run_test_generation_agent,
    validate_test_command_safety,
)
from app.agents.validation_agent import ValidationAgent, ValidationVerdict
from app.config import Settings, get_settings
from app.models.finding import FindingOrigin
from app.models.orchestration import AgentCoordinationRun, AgentTaskExecution
from app.models.repository import RepositoryPolicy
from app.models.review import AuditAction
from app.rules.engine import DetectedFinding
from app.sandbox.runtime import NoOpSandboxRuntime, SandboxRuntime
from app.services.audit_service import record_audit_event
from app.telemetry import create_span

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReviewContextSnapshot:
    """
    Immutable snapshot of the review input and parameters.
    Guarantees that parallel specialist agents cannot mutate the review environment.
    """
    run_id: uuid.UUID
    tenant_id: uuid.UUID
    source_code: str
    language: str
    manifest_files: Dict[str, str] = field(default_factory=dict)
    lock_files: Dict[str, str] = field(default_factory=dict)
    candidate_sinks: List[Dict[str, Any]] = field(default_factory=list)
    patch_diff: Optional[str] = None
    target_file_path: Optional[str] = None
    framework_hints: List[str] = field(default_factory=list)
    allowed_ci_commands: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AgentExecutionRecord:
    """Detailed execution record and telemetry for an individual specialist agent."""
    task_id: uuid.UUID
    agent_name: str
    status: str  # running | completed | failed | timeout | skipped
    tokens_consumed: int = 0
    duration_ms: int = 0
    error_message: Optional[str] = None
    partial_output: Optional[Any] = None


@dataclass
class OrchestrationResult:
    """Aggregated output of a multi-agent orchestration execution."""
    coordination_id: uuid.UUID
    review_run_id: uuid.UUID
    tenant_id: uuid.UUID
    status: str  # running | completed | partial | failed | budget_paused
    total_tokens_consumed: int = 0
    total_wall_clock_ms: int = 0
    failed_agents: List[str] = field(default_factory=list)
    task_executions: Dict[str, AgentExecutionRecord] = field(default_factory=dict)
    final_findings: List[DetectedFinding] = field(default_factory=list)
    dependency_output: Optional[DependencyRiskOutput] = None
    dataflow_output: Optional[DataflowOutput] = None
    risk_scoring_output: Optional[RiskScoringOutput] = None
    patch_draft: Optional[PatchDraft] = None
    test_generation_output: Optional[TestGenerationOutput] = None
    validation_verdict: Optional[ValidationVerdict] = None
    executive_summary_output: Optional[ExecutiveSummaryOutput] = None


from app.agents.capabilities import _convert_tool_finding, _convert_llm_finding, _SEVERITY_ORDER
from app.models.finding import EvidenceKind


def _to_detected_finding(f_item: Any) -> DetectedFinding:
    if isinstance(f_item, DetectedFinding):
        return f_item
    if isinstance(f_item, dict):
        raw_sev = f_item.get("severity", "Medium")
        if hasattr(raw_sev, "value"):
            raw_sev = raw_sev.value
        sev_str = str(raw_sev).capitalize()
        if sev_str not in {"Critical", "High", "Medium", "Low", "Info"}:
            sev_str = "Medium"
        return DetectedFinding(
            rule_id=f_item.get("rule_id", "UNKNOWN-001"),
            category=f_item.get("category", "security"),
            severity=sev_str,
            confidence=float(f_item.get("confidence", 0.8)),
            title=f_item.get("title", f_item.get("message", "Finding")),
            rationale=f_item.get("rationale", ""),
            remediation=f_item.get("remediation", ""),
            evidence_kind=EvidenceKind.token_regex,
            ast_path=f_item.get("source_file_path", f_item.get("file_path", "unknown")),
            matched_text=f_item.get("title", "")[:200],
            start_line=f_item.get("start_line", 1),
            origin=FindingOrigin.agent,
            tool_name=f_item.get("tool_name", "specialist_agent"),
        )
    return _convert_tool_finding(f_item)


class MultiAgentOrchestrator:
    """
    Coordinates multi-agent reviews per FR-108 and FR-109 specifications.
    """

    def __init__(
        self,
        provider: Optional[ModelProvider] = None,
        db: Optional[AsyncSession] = None,
        settings: Optional[Settings] = None,
        barrier_timeout: float = 30.0,
        token_budget: Optional[int] = None,
        deadline_seconds: float = 90.0,
        redis_client: Optional[Any] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or get_provider(
            self.settings.llm_provider,
            model_name=self.settings.llm_model_name,
            api_key=self.settings.openai_api_key or self.settings.anthropic_api_key,
        )
        self.db = db
        self.barrier_timeout = barrier_timeout
        self.token_budget = (
            token_budget
            if token_budget is not None
            else getattr(self.settings, "aggregate_review_token_budget", 200_000)
        )
        self.deadline_seconds = deadline_seconds
        self.redis = redis_client

    async def _is_killswitch_active(self) -> bool:
        """
        Checks Redis for emergency kill switch vigil:killswitch:multi_agent (IC10).
        If active, skips all Phase 5 specialist agents (A10-A14).
        """
        try:
            redis = self.redis
            if redis is None:
                from app.redis_client import get_redis
                redis = get_redis()
            killswitch_key = getattr(self.settings, "killswitch_key", "vigil:killswitch:multi_agent")
            value = await redis.get(killswitch_key)
            if value is None:
                return False
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            return str(value).lower().strip() in {"true", "1", "yes", "on"}
        except Exception as e:
            logger.warning("Kill switch check failed: %s. Defaulting to active=False.", e)
            return False

    async def _run_phase1_4_pipeline_only(
        self,
        snapshot: ReviewContextSnapshot,
        base_state: ReviewGraphState,
        coordination_id: uuid.UUID,
        result: OrchestrationResult,
        enable_patch: bool = False,
        sandbox_runtime: Optional[SandboxRuntime] = None,
    ) -> OrchestrationResult:
        """
        Fallback execution path when emergency kill switch is active (IC10).
        Skips all specialist agents (A10-A14) and runs Phase 1-4 pipeline only.
        """
        from app.rules.engine import compute_fingerprint

        combined_findings: List[DetectedFinding] = list(base_state.rule_findings)
        for tf in base_state.tool_findings:
            combined_findings.append(_to_detected_finding(tf))

        # A3: Security reasoning
        async def _task_a3():
            assert_permission("security", "allow_llm")
            st = ReviewGraphState(
                run_id=snapshot.run_id,
                tenant_id=snapshot.tenant_id,
                source_code=snapshot.source_code,
                language=snapshot.language,
                parse_successful=True,
                rule_findings=list(base_state.rule_findings),
            )
            return await capability_llm_security(st, self.provider)

        # A4: Quality review
        async def _task_a4():
            assert_permission("quality", "allow_llm")
            st = ReviewGraphState(
                run_id=snapshot.run_id,
                tenant_id=snapshot.tenant_id,
                source_code=snapshot.source_code,
                language=snapshot.language,
                parse_successful=True,
            )
            return await capability_llm_quality(st, self.provider)

        sec_res = await self._execute_agent_task(
            "security", _task_a3, coordination_id, snapshot.tenant_id, result, estimated_tokens=8000, required_permission="allow_llm"
        )
        qual_res = await self._execute_agent_task(
            "quality", _task_a4, coordination_id, snapshot.tenant_id, result, estimated_tokens=6000, required_permission="allow_llm"
        )

        if isinstance(sec_res, ReviewGraphState):
            for lf in sec_res.llm_security_findings:
                combined_findings.append(_convert_llm_finding(lf, cap_severity=False))

        if isinstance(qual_res, ReviewGraphState):
            for lf in qual_res.llm_quality_findings:
                combined_findings.append(_convert_llm_finding(lf, cap_severity=True))

        # A5: Deterministic Triage
        seen = {}
        for f in combined_findings:
            fp = compute_fingerprint(
                f.rule_id or "unknown",
                f.ast_path or "",
                f.matched_text or "",
                f.evidence_kind.value if hasattr(f.evidence_kind, "value") else str(f.evidence_kind),
            )
            if fp not in seen:
                seen[fp] = f

        triaged = list(seen.values())
        triaged.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), -f.confidence))
        result.final_findings = triaged

        # Subtree 2: Patch & Validation (Phase 4), bypassing A13 Test Gen
        if enable_patch and result.final_findings and result.status != "budget_paused":
            target_finding = result.final_findings[0]

            async def _task_a6():
                assert_permission("patch", "allow_llm")
                patch_agent = PatchAgent(provider=self.provider, settings=self.settings)
                return await patch_agent.draft_patch(
                    finding=target_finding,
                    source_code=snapshot.source_code,
                    file_path=snapshot.target_file_path or "main.py",
                )

            patch_res = await self._execute_agent_task(
                "patch", _task_a6, coordination_id, snapshot.tenant_id, result, estimated_tokens=6000, required_permission="allow_llm"
            )
            if isinstance(patch_res, PatchDraft):
                result.patch_draft = patch_res

            if result.patch_draft and result.status != "budget_paused":
                async def _task_a7():
                    assert_permission("validation", "allow_sandbox")
                    v_runtime = sandbox_runtime or NoOpSandboxRuntime()
                    val_agent = ValidationAgent(runtime=v_runtime, settings=self.settings)
                    return await val_agent.run_validation(
                        patch_candidate=result.patch_draft,
                        source_files={snapshot.target_file_path or "main.py": snapshot.source_code},
                        allowed_ci_commands=snapshot.allowed_ci_commands,
                        commands_to_run=[],
                    )

                val_res = await self._execute_agent_task(
                    "validation", _task_a7, coordination_id, snapshot.tenant_id, result, estimated_tokens=0, required_permission="allow_sandbox"
                )
                if isinstance(val_res, ValidationVerdict):
                    result.validation_verdict = val_res

        result.status = "completed"
        return result

    async def _record_audit(
        self,
        tenant_id: uuid.UUID,
        action: AuditAction,
        target_type: str,
        target_id: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Helper to write audit events if a database session is active."""
        if self.db:
            try:
                await record_audit_event(
                    self.db,
                    tenant_id=tenant_id,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    metadata=meta or {},
                )
            except Exception as e:
                logger.warning("Failed to record audit event %s: %s", action, e)

    async def _execute_agent_task(
        self,
        agent_name: str,
        coro_factory: Callable[[], Coroutine[Any, Any, Any]],
        coordination_id: uuid.UUID,
        tenant_id: uuid.UUID,
        result: OrchestrationResult,
        estimated_tokens: int = 0,
        required_permission: Optional[str] = None,
    ) -> Any:
        """
        Executes a single agent task with telemetry, permission checks, budget guarding,
        and database task tracking.
        """
        task_id = uuid.uuid4()
        task_rec = AgentExecutionRecord(
            task_id=task_id,
            agent_name=agent_name,
            status="running",
        )
        result.task_executions[agent_name] = task_rec

        # 1. Permission boundary check
        if required_permission:
            try:
                assert_permission(agent_name, required_permission)
            except PermissionDeniedError as e:
                task_rec.status = "failed"
                task_rec.error_message = str(e)
                result.failed_agents.append(agent_name)
                await self._record_audit(
                    tenant_id=tenant_id,
                    action=AuditAction.AGENT_PERMISSION_DENIED,
                    target_type="AgentTask",
                    target_id=str(task_id),
                    meta={"agent": agent_name, "error": str(e)},
                )
                raise

        # 2. Cumulative budget check
        if result.total_tokens_consumed >= self.token_budget:
            task_rec.status = "skipped"
            task_rec.error_message = "budget_paused"
            result.status = "budget_paused"
            await self._record_audit(
                tenant_id=tenant_id,
                action=AuditAction.AGENT_BUDGET_EXCEEDED,
                target_type="AgentTask",
                target_id=str(task_id),
                meta={
                    "agent": agent_name,
                    "budget_limit": self.token_budget,
                    "consumed": result.total_tokens_consumed,
                },
            )
            return None

        # 3. Execution with OpenTelemetry child span
        span_attrs = {
            "agent_name": agent_name,
            "task_id": str(task_id),
            "coordination_id": str(coordination_id),
        }
        await self._record_audit(
            tenant_id=tenant_id,
            action=AuditAction.AGENT_EXECUTION_STARTED,
            target_type="AgentTask",
            target_id=str(task_id),
            meta={"agent": agent_name},
        )

        start_time = time.perf_counter()
        with create_span(f"vigil.agent.{agent_name}", span_attrs):
            try:
                out = await coro_factory()
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                task_rec.duration_ms = duration_ms
                task_rec.status = "completed"
                task_rec.tokens_consumed = estimated_tokens
                result.total_tokens_consumed += estimated_tokens

                # Check if this consumption pushed us over the budget
                if result.total_tokens_consumed >= self.token_budget:
                    result.status = "budget_paused"
                    await self._record_audit(
                        tenant_id=tenant_id,
                        action=AuditAction.AGENT_BUDGET_EXCEEDED,
                        target_type="AgentTask",
                        target_id=str(task_id),
                        meta={
                            "agent": agent_name,
                            "budget_limit": self.token_budget,
                            "consumed": result.total_tokens_consumed,
                        },
                    )

                await self._record_audit(
                    tenant_id=tenant_id,
                    action=AuditAction.AGENT_EXECUTION_COMPLETED,
                    target_type="AgentTask",
                    target_id=str(task_id),
                    meta={"agent": agent_name, "duration_ms": duration_ms, "tokens": estimated_tokens},
                )
                return out

            except asyncio.CancelledError:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                task_rec.duration_ms = duration_ms
                task_rec.status = "timeout"
                task_rec.error_message = "barrier_timeout"
                result.failed_agents.append(agent_name)
                result.status = "partial"
                await self._record_audit(
                    tenant_id=tenant_id,
                    action=AuditAction.AGENT_EXECUTION_FAILED,
                    target_type="AgentTask",
                    target_id=str(task_id),
                    meta={"agent": agent_name, "reason": "barrier_timeout"},
                )
                raise

            except Exception as e:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                task_rec.duration_ms = duration_ms
                task_rec.status = "failed"
                task_rec.error_message = str(e)
                result.failed_agents.append(agent_name)
                result.status = "partial"
                await self._record_audit(
                    tenant_id=tenant_id,
                    action=AuditAction.AGENT_EXECUTION_FAILED,
                    target_type="AgentTask",
                    target_id=str(task_id),
                    meta={"agent": agent_name, "error": str(e)},
                )
                logger.error("Agent %s failed: %s", agent_name, e, exc_info=True)
                return None

    async def run(
        self,
        snapshot: ReviewContextSnapshot,
        policy: Optional[RepositoryPolicy] = None,
        enable_patch: bool = False,
        sandbox_runtime: Optional[SandboxRuntime] = None,
        historical_precedents: Optional[List[SanitizedPrecedent]] = None,
    ) -> OrchestrationResult:
        """
        Executes the full multi-agent orchestration DAG per FR-108.
        """
        wall_clock_start = time.perf_counter()
        coordination_id = uuid.uuid4()

        result = OrchestrationResult(
            coordination_id=coordination_id,
            review_run_id=snapshot.run_id,
            tenant_id=snapshot.tenant_id,
            status="running",
        )

        root_span_attrs = {
            "coordination_id": str(coordination_id),
            "review_run_id": str(snapshot.run_id),
            "tenant_id": str(snapshot.tenant_id),
        }

        with create_span("vigil.orchestration_run", root_span_attrs):
            try:
                # ── Step 1: Base Parse & Baseline Rules (A1 & A2) ───────────
                base_state = ReviewGraphState(
                    run_id=snapshot.run_id,
                    tenant_id=snapshot.tenant_id,
                    source_code=snapshot.source_code,
                    language=snapshot.language,
                )
                base_state = await capability_parse(base_state)
                if not base_state.parse_successful:
                    result.status = "failed"
                    return result

                base_state = await capability_run_rules(base_state)
                base_state = await capability_run_adapters(base_state)

                # ── Kill Switch Check (IC10) ──────────────────────────────────
                if await self._is_killswitch_active():
                    logger.warning(
                        "Kill switch active: skipping all specialist agents. coordination_id=%s",
                        coordination_id,
                    )
                    return await self._run_phase1_4_pipeline_only(
                        snapshot=snapshot,
                        base_state=base_state,
                        coordination_id=coordination_id,
                        result=result,
                        enable_patch=enable_patch,
                        sandbox_runtime=sandbox_runtime,
                    )

                # ── Step 2: Subtree 1 Parallel Fan-Out (A11, A3, A4, A12) ────
                # Dependency matrix: check toggles from policy
                run_a11 = policy.enable_dependency_risk if policy else True
                run_a3 = True  # Security reasoning
                run_a4 = True  # Quality review
                run_a12 = policy.enable_dataflow_investigation if policy else True

                # Construct tasks for Subtree 1
                async def _task_a11():
                    assert_permission("dependency_risk", "allow_llm")
                    dep_input = DependencyRiskInput(
                        manifest_files=snapshot.manifest_files,
                        lock_files=snapshot.lock_files,
                    )
                    return await run_dependency_agent(dep_input)

                async def _task_a3():
                    assert_permission("security", "allow_llm")
                    st = ReviewGraphState(
                        run_id=snapshot.run_id,
                        tenant_id=snapshot.tenant_id,
                        source_code=snapshot.source_code,
                        language=snapshot.language,
                        parse_successful=True,
                        rule_findings=list(base_state.rule_findings),
                    )
                    return await capability_llm_security(st, self.provider)

                async def _task_a4():
                    assert_permission("quality", "allow_llm")
                    st = ReviewGraphState(
                        run_id=snapshot.run_id,
                        tenant_id=snapshot.tenant_id,
                        source_code=snapshot.source_code,
                        language=snapshot.language,
                        parse_successful=True,
                    )
                    return await capability_llm_quality(st, self.provider)

                async def _task_a12():
                    assert_permission("dataflow", "allow_llm")
                    sinks = snapshot.candidate_sinks
                    if not sinks:
                        # Auto-extract call expressions from source code as candidate sinks
                        import ast
                        sinks = []
                        try:
                            tree = ast.parse(snapshot.source_code)
                            for node in ast.walk(tree):
                                if isinstance(node, ast.Call):
                                    func_name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                                    if func_name in {"eval", "exec", "system", "run", "execute"}:
                                        sinks.append({
                                            "sink_symbol": func_name,
                                            "line_number": getattr(node, "lineno", 1),
                                            "expression": f"{func_name}(...)",
                                        })
                        except Exception:
                            pass

                    df_input = DataflowInput(
                        source_code=snapshot.source_code,
                        language=snapshot.language,
                        candidate_sinks=sinks,
                    )
                    return await run_dataflow_agent(df_input)

                # Wrap tasks in agent executors
                futures = {}
                if run_a11:
                    futures["dependency_risk"] = asyncio.create_task(
                        self._execute_agent_task(
                            "dependency_risk",
                            _task_a11,
                            coordination_id,
                            snapshot.tenant_id,
                            result,
                            estimated_tokens=4000,
                            required_permission="allow_llm",
                        )
                    )
                if run_a3:
                    futures["security"] = asyncio.create_task(
                        self._execute_agent_task(
                            "security",
                            _task_a3,
                            coordination_id,
                            snapshot.tenant_id,
                            result,
                            estimated_tokens=8000,
                            required_permission="allow_llm",
                        )
                    )
                if run_a4:
                    futures["quality"] = asyncio.create_task(
                        self._execute_agent_task(
                            "quality",
                            _task_a4,
                            coordination_id,
                            snapshot.tenant_id,
                            result,
                            estimated_tokens=6000,
                            required_permission="allow_llm",
                        )
                    )
                if run_a12:
                    futures["dataflow"] = asyncio.create_task(
                        self._execute_agent_task(
                            "dataflow",
                            _task_a12,
                            coordination_id,
                            snapshot.tenant_id,
                            result,
                            estimated_tokens=16000,
                            required_permission="allow_llm",
                        )
                    )

                # Wait for Subtree 1 parallel completion with 30s barrier timeout
                pending = set(futures.values())
                done = set()
                try:
                    done, pending = await asyncio.wait(
                        pending,
                        timeout=self.barrier_timeout,
                        return_when=asyncio.ALL_COMPLETED,
                    )
                except Exception as e:
                    logger.error("Subtree 1 execution exception: %s", e)

                # Handle barrier timeout: cancel lingering tasks
                if pending:
                    for task in pending:
                        task.cancel()
                    # Await cancellations gracefully
                    await asyncio.gather(*pending, return_exceptions=True)
                    result.status = "partial"

                # Extract Subtree 1 results
                dep_res = futures.get("dependency_risk").result() if "dependency_risk" in futures and futures["dependency_risk"].done() and not futures["dependency_risk"].cancelled() else None
                sec_res = futures.get("security").result() if "security" in futures and futures["security"].done() and not futures["security"].cancelled() else None
                qual_res = futures.get("quality").result() if "quality" in futures and futures["quality"].done() and not futures["quality"].cancelled() else None
                df_res = futures.get("dataflow").result() if "dataflow" in futures and futures["dataflow"].done() and not futures["dataflow"].cancelled() else None

                if isinstance(dep_res, DependencyRiskOutput):
                    result.dependency_output = dep_res
                if isinstance(df_res, DataflowOutput):
                    result.dataflow_output = df_res

                # Aggregate findings from Subtree 1
                combined_findings: List[DetectedFinding] = list(base_state.rule_findings)

                from app.agents.capabilities import _convert_tool_finding, _convert_llm_finding
                from app.models.finding import EvidenceKind

                def _to_detected_finding(f_item: Any) -> DetectedFinding:
                    if isinstance(f_item, DetectedFinding):
                        return f_item
                    if isinstance(f_item, dict):
                        raw_sev = f_item.get("severity", "Medium")
                        if hasattr(raw_sev, "value"):
                            raw_sev = raw_sev.value
                        sev_str = str(raw_sev).capitalize()
                        if sev_str not in {"Critical", "High", "Medium", "Low", "Info"}:
                            sev_str = "Medium"
                        return DetectedFinding(
                            rule_id=f_item.get("rule_id", "UNKNOWN-001"),
                            category=f_item.get("category", "security"),
                            severity=sev_str,
                            confidence=float(f_item.get("confidence", 0.8)),
                            title=f_item.get("title", f_item.get("message", "Finding")),
                            rationale=f_item.get("rationale", ""),
                            remediation=f_item.get("remediation", ""),
                            evidence_kind=EvidenceKind.token_regex,
                            ast_path=f_item.get("source_file_path", f_item.get("file_path", "unknown")),
                            matched_text=f_item.get("title", "")[:200],
                            start_line=f_item.get("start_line", 1),
                            origin=FindingOrigin.agent,
                            tool_name=f_item.get("tool_name", "specialist_agent"),
                        )
                    return _convert_tool_finding(f_item)

                for tf in base_state.tool_findings:
                    combined_findings.append(_to_detected_finding(tf))

                # From A11 Dependency Risk
                if result.dependency_output:
                    for rf in result.dependency_output.findings:
                        combined_findings.append(_to_detected_finding(rf))

                # From A3 Security
                if isinstance(sec_res, ReviewGraphState):
                    for lf in sec_res.llm_security_findings:
                        combined_findings.append(_convert_llm_finding(lf, cap_severity=False))

                # From A4 Quality
                if isinstance(qual_res, ReviewGraphState):
                    for lf in qual_res.llm_quality_findings:
                        combined_findings.append(_convert_llm_finding(lf, cap_severity=True))

                # From A12 Dataflow
                if result.dataflow_output:
                    for df_find in result.dataflow_output.validated_findings:
                        combined_findings.append(_to_detected_finding(df_find))

                # ── Step 3: Governed Learning & Risk Scoring (A10) ──────────
                run_a10 = policy.enable_specialist_risk_scoring if policy else True
                precedents = historical_precedents or []

                if run_a10 and result.status != "budget_paused":
                    # Convert combined_findings to RawFinding format for A10 input
                    from app.schemas.finding import RawFinding
                    raw_findings_for_a10 = [
                        RawFinding(
                            tool_name=f.tool_name or (f.origin.value if hasattr(f, "origin") else "agent"),
                            rule_id=f.rule_id,
                            severity_raw=f.severity,
                            message=f.title,
                            file_path=f.ast_path,
                            start_line=f.start_line,
                        )
                        for f in combined_findings
                    ]

                    async def _task_a10():
                        assert_permission("risk_scoring", "allow_llm")
                        rs_input = RiskScoringInput(
                            findings=raw_findings_for_a10,
                            historical_dispositions=precedents,
                            repository_context=snapshot.metadata,
                        )
                        return await run_risk_scoring_agent(rs_input, provider=self.provider)

                    rs_res = await self._execute_agent_task(
                        "risk_scoring",
                        _task_a10,
                        coordination_id,
                        snapshot.tenant_id,
                        result,
                        estimated_tokens=12000,
                        required_permission="allow_llm",
                    )
                    if isinstance(rs_res, RiskScoringOutput):
                        result.risk_scoring_output = rs_res

                # ── Step 4: Deterministic Triage (A5) ───────────────────────
                # Deterministic Triage is supreme arbiter (AC-108.5).
                # Build suppression map from A10 suggestions
                suppressions = set()
                score_adjustments = {}
                if result.risk_scoring_output:
                    for item in result.risk_scoring_output.scored_items:
                        score_adjustments[str(item.finding_id)] = item.adjusted_confidence
                        if item.suggested_action == "suppress":
                            suppressions.add(str(item.finding_id))

                # Deduplicate and sort findings, enforcing AC-108.5
                from app.rules.engine import compute_fingerprint
                from app.agents.capabilities import _SEVERITY_ORDER
                seen = {}
                for f in combined_findings:
                    fid = getattr(f, "rule_id", "unknown")
                    # AC-108.5: Deterministic Triage overrides A10 suppression on baseline rules!
                    # Rule origin findings (e.g. VIGIL-SEC-001) are strictly preserved!
                    is_baseline_rule = (
                        getattr(f, "origin", None) == FindingOrigin.rule
                        or (f.rule_id and f.rule_id.startswith("VIGIL-SEC-"))
                        or (f.rule_id and f.rule_id.startswith("VIGIL-"))
                    )

                    if fid in suppressions and not is_baseline_rule:
                        # Non-baseline finding suppressed by advisory scoring
                        continue

                    # Adjust confidence if advisory score provided
                    if fid in score_adjustments:
                        f.confidence = score_adjustments[fid]

                    fp = compute_fingerprint(
                        f.rule_id or "unknown",
                        f.ast_path or "",
                        f.matched_text or "",
                        f.evidence_kind.value if hasattr(f.evidence_kind, "value") else str(f.evidence_kind),
                    )
                    if fp not in seen:
                        seen[fp] = f

                triaged = list(seen.values())
                triaged.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), -f.confidence))
                result.final_findings = triaged

                # ── Step 5: Subtree 2 Sequential Pipeline (A6 -> A13 -> A7) ─
                # Strictly sequential per AC-108.1b
                if enable_patch and result.final_findings and result.status != "budget_paused":
                    target_finding = result.final_findings[0]

                    # Step 5a: Patch Agent (A6)
                    async def _task_a6():
                        assert_permission("patch", "allow_llm")
                        patch_agent = PatchAgent(provider=self.provider, settings=self.settings)
                        return await patch_agent.draft_patch(
                            finding=target_finding,
                            source_code=snapshot.source_code,
                            file_path=snapshot.target_file_path or "main.py",
                        )

                    patch_res = await self._execute_agent_task(
                        "patch",
                        _task_a6,
                        coordination_id,
                        snapshot.tenant_id,
                        result,
                        estimated_tokens=6000,
                        required_permission="allow_llm",
                    )
                    if isinstance(patch_res, PatchDraft):
                        result.patch_draft = patch_res

                    # Step 5b: Test Generation Agent (A13)
                    # Requires patch diff from A6
                    if result.patch_draft and result.status != "budget_paused":
                        async def _task_a13():
                            assert_permission("test_generation", "allow_llm")
                            tg_input = TestGenerationInput(
                                patch_diff=result.patch_draft.diff_unified,
                                target_file_path=snapshot.target_file_path or "main.py",
                                framework_hints=snapshot.framework_hints,
                            )
                            return await run_test_generation_agent(tg_input, provider=self.provider)

                        tg_res = await self._execute_agent_task(
                            "test_generation",
                            _task_a13,
                            coordination_id,
                            snapshot.tenant_id,
                            result,
                            estimated_tokens=8000,
                            required_permission="allow_llm",
                        )
                        if isinstance(tg_res, TestGenerationOutput):
                            result.test_generation_output = tg_res

                    # Step 5c: Validation Agent (A7)
                    # Validates patch and generated tests in sandbox
                    if result.patch_draft and result.status != "budget_paused":
                        # Validate test command safety before invoking sandbox (AC-108.6)
                        cmds = []
                        if result.test_generation_output:
                            cmds = result.test_generation_output.test_commands
                            for c in cmds:
                                validate_test_command_safety(c)

                        async def _task_a7():
                            assert_permission("validation", "allow_sandbox")
                            v_runtime = sandbox_runtime or NoOpSandboxRuntime()
                            val_agent = ValidationAgent(runtime=v_runtime, settings=self.settings)
                            return await val_agent.run_validation(
                                patch_candidate=result.patch_draft,
                                source_files={snapshot.target_file_path or "main.py": snapshot.source_code},
                                allowed_ci_commands=snapshot.allowed_ci_commands,
                                commands_to_run=cmds,
                            )

                        val_res = await self._execute_agent_task(
                            "validation",
                            _task_a7,
                            coordination_id,
                            snapshot.tenant_id,
                            result,
                            estimated_tokens=0,
                            required_permission="allow_sandbox",
                        )
                        if isinstance(val_res, ValidationVerdict):
                            result.validation_verdict = val_res

                # ── Step 6: Executive Summary Agent (A14) ───────────────────
                # Always executes even if earlier agents failed or were skipped ([M4])
                run_a14 = policy.enable_executive_summary if policy else True
                if run_a14:
                    async def _task_a14():
                        assert_permission("executive_summary", "allow_llm")
                        from app.schemas.finding import RawFinding
                        exec_findings = [
                            RawFinding(
                                tool_name=f.tool_name or (f.origin.value if hasattr(f, "origin") else "agent"),
                                rule_id=f.rule_id,
                                severity_raw=f.severity,
                                message=f.title,
                                file_path=f.ast_path,
                                start_line=f.start_line,
                            )
                            for f in result.final_findings
                        ]
                        exec_input = ExecutiveSummaryInput(
                            final_findings=exec_findings,
                            review_metadata=snapshot.metadata,
                            agent_execution_summary={
                                "failed_agents": result.failed_agents,
                                "total_tasks": len(result.task_executions),
                                "status": result.status,
                            },
                        )
                        return await run_executive_summary_agent(exec_input, provider=self.provider)

                    exec_res = await self._execute_agent_task(
                        "executive_summary",
                        _task_a14,
                        coordination_id,
                        snapshot.tenant_id,
                        result,
                        estimated_tokens=10000,
                        required_permission="allow_llm",
                    )
                    if isinstance(exec_res, ExecutiveSummaryOutput):
                        result.executive_summary_output = exec_res

                # ── Step 7: Final Status Determination ──────────────────────
                if result.status != "budget_paused" and result.status != "partial":
                    if result.failed_agents:
                        result.status = "partial"
                    else:
                        result.status = "completed"

            except Exception as e:
                logger.error("MultiAgentOrchestrator error: %s", e, exc_info=True)
                result.status = "failed"

            finally:
                wall_clock_ms = int((time.perf_counter() - wall_clock_start) * 1000)
                result.total_wall_clock_ms = wall_clock_ms

                # Persist coordination run and task records if database session is active
                if self.db:
                    try:
                        coord_run = AgentCoordinationRun(
                            coordination_id=result.coordination_id,
                            review_run_id=result.review_run_id,
                            tenant_id=result.tenant_id,
                            status=result.status,
                            total_tokens_consumed=result.total_tokens_consumed,
                            total_wall_clock_ms=result.total_wall_clock_ms,
                            failed_agents=result.failed_agents,
                        )
                        self.db.add(coord_run)

                        for rec in result.task_executions.values():
                            task_exec = AgentTaskExecution(
                                task_id=rec.task_id,
                                coordination_id=result.coordination_id,
                                agent_name=rec.agent_name,
                                status=rec.status,
                                tokens_consumed=rec.tokens_consumed,
                                duration_ms=rec.duration_ms,
                                error_message=rec.error_message,
                                partial_output=rec.partial_output,
                            )
                            self.db.add(task_exec)

                        await self.db.flush()
                    except Exception as e:
                        logger.warning("Failed to persist coordination run records: %s", e)

        return result
