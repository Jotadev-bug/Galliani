"""Spec 001 - Agent Core: the Agent Supervisor loop.

objective -> plan -> routing -> action/tool -> observation -> verification -> replan/retry -> done

The supervisor owns every lifecycle decision. Agent Workers, tools and the planner only return
structured results. Every status change goes through `_transition`, which patches Task State and
emits a lifecycle event. A task is marked done only after verification passes. The loop terminates
because every iteration either consumes the action budget or moves to a pausing or terminal status.
"""

from __future__ import annotations

import json

from collections.abc import Awaitable, Callable, Iterable, Mapping
from datetime import timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field

from galliani.adapters import ProviderAdapter
from galliani.contracts import Objective, Sensitivity
from galliani.errors import ContractError
from galliani.execution import ArtifactRef, ExecutionEngine, ExecutionLimits, ExecutionRequest, ExecutionStatus
from galliani.limits import LoopLimits
from galliani.memory import USER_SCOPE, MemoryQuery, MemoryRecord, MemoryStore, keywords_of
from galliani.observability import EventType, Observability, UsageLedger
from galliani.permissions import (
    ApprovalPrompt,
    PermissionLevel,
    PermissionPolicy,
    PermissionRequest,
    PermissionStatus,
)
from galliani.planner import Planner, PlannerError, PlannerStatus, PlanRequest, PlanStep, validate_plan
from galliani.replanning import Budgets, FailureSignal, Replanner, ReplanRequest, ReplanStatus, RetryPolicy
from galliani.router import ModelRouter, RoutingPolicy
from galliani.state import (
    TERMINAL_STATUSES,
    FinalResult,
    ObservationRecord,
    PendingPermission,
    StatePatch,
    TaskState,
    TaskStateStore,
    TaskStatus,
    set_status,
)
from galliani.tools import ToolSystem
from galliani.verification import (
    Criterion,
    VerificationRecommendation,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
    Verifier,
)

S = TaskStatus
MAX_CONTEXT_CHARS = 4_000  # reference data passed to planners
SPEND_ACTION = "extend_budget:"
MAX_JUDGE_SOURCE_CHARS = 8_000  # source data shown to a semantic verifier


class UserPolicy(BaseModel):
    user_id: str = "user"
    routing: RoutingPolicy = Field(default_factory=RoutingPolicy)


class StartTaskRequest(BaseModel):
    """001 `StartTaskRequest`: objective, context, constraints, user policy."""

    objective: Objective
    context: str = ""
    constraints: dict[str, Any] = Field(default_factory=dict)
    user_policy: UserPolicy = Field(default_factory=UserPolicy)
    # Memory scopes this task may read (010 R4): "user" plus, usually, "project:<workspace>".
    memory_scopes: list[str] = Field(default_factory=lambda: [USER_SCOPE])


class SupervisorDecision(BaseModel):
    """001 `SupervisorDecision`, recorded as an observation for every loop decision."""

    next_action: Literal["plan", "execute_step", "verify", "retry_step", "replan", "ask_user", "finish", "block", "fail"]
    reason_summary: str
    required_capability: str | None = None
    state_patch: list[StatePatch] = Field(default_factory=list)


class TaskResult(BaseModel):
    """001 `TaskResult`, plus the pause details a caller needs to resume."""

    task_id: str
    status: TaskStatus
    summary: str
    output: Any = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    verification_result: VerificationResult | None = None
    observations: list[ObservationRecord] = Field(default_factory=list)
    approval_prompt: ApprovalPrompt | None = None
    clarification: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)  # worker calls, tokens, cost_micro_usd (estimate)


class Supervisor:
    def __init__(
        self,
        *,
        planner: Planner,
        router: ModelRouter,
        adapters: Mapping[str, ProviderAdapter] | Iterable[ProviderAdapter],
        tools: ToolSystem,
        verifier: Verifier | None = None,
        retry_policy: RetryPolicy | None = None,
        limits: LoopLimits | None = None,
        store: TaskStateStore | None = None,
        observability: Observability | None = None,
        memory: MemoryStore | None = None,
    ):
        self.planner = planner
        self.memory = memory
        self.router = router
        self.tools = tools
        self.verifier = verifier or Verifier()
        self.retry_policy = retry_policy or RetryPolicy()
        self.limits = limits or LoopLimits()
        self.store = store or TaskStateStore()
        self.obs = observability or Observability()
        self.ledger = UsageLedger()  # every worker call on this bus (planner, steps, verifier) is counted
        self.obs.sinks.append(self.ledger)
        self.engine = ExecutionEngine(router, adapters, tools, self.obs)
        self.replanner = Replanner(planner, self.retry_policy, self.limits)
        self.actor = "supervisor"
        self._policies: dict[str, UserPolicy] = {}
        self._artifacts: dict[str, list[ArtifactRef]] = {}
        self._cancel_requested: set[str] = set()
        self._memory_scopes: dict[str, list[str]] = {}
        self._memory_context: dict[str, list[MemoryRecord]] = {}  # retrieved records; context, not Task State
        self._running: set[str] = set()

    # ------------------------------------------------------------------ public API

    async def start(self, request: StartTaskRequest) -> TaskResult:
        """Create the task and run the loop until it finishes or pauses."""
        return await self.run(self.create(request).task_id)

    def create(self, request: StartTaskRequest) -> TaskResult:
        """Create the task without running it, so a UI can show it in `created` status (012 AC Start Task)."""
        objective = request.objective.model_copy(update={
            "constraints": {**request.objective.constraints, **request.constraints},
            "context": request.objective.context or request.context,
        })
        state = self.store.create(objective)
        self._policies[state.task_id] = request.user_policy
        self._artifacts[state.task_id] = []
        self._memory_scopes[state.task_id] = list(request.memory_scopes)
        self.obs.emit(EventType.task_created, state.task_id, "task created", metadata={"status": state.status.value})
        if not objective.is_valid():
            state = self._transition(state, S.waiting_for_user, "objective is empty; clarification requested",
                                     [StatePatch(operation="set", path="clarification",
                                                 value="Please describe the objective you want completed.")])
        return self._result(state)

    async def run(self, task_id: str) -> TaskResult:
        """Run a created task. A task that is paused or finished is returned as it is."""
        state = self.store.get(task_id)
        if state.status is not S.created:
            return self._result(state)
        return await self._run(state)

    async def approve(self, task_id: str, *, user_id: str | None = None, ttl: timedelta | None = None) -> TaskResult:
        state = self.store.get(task_id)
        pending = state.pending_permission
        if state.status is not S.waiting_for_user or pending is None:
            raise ContractError(f"task {task_id} has no pending approval")
        user = user_id or self._policy(task_id).user_id
        approval = PermissionPolicy.approval_for(pending.request, user, ttl)
        self.obs.emit(EventType.approval_recorded, task_id, f"{user} approved {approval.action} for scope {approval.scope}",
                      step_id=pending.step_id, metadata={"approval_id": approval.approval_id, "scope": approval.scope})
        state = self._transition(state, S.executing, f"user approved {approval.action}", [
            StatePatch(operation="append", path="approvals", value=approval, reason_summary="user approval"),
            StatePatch(operation="set", path="pending_permission", value=None),
        ])
        return await self._run(state)

    async def deny(self, task_id: str, *, user_id: str | None = None) -> TaskResult:
        state = self.store.get(task_id)
        pending = state.pending_permission
        if state.status is not S.waiting_for_user or pending is None:
            raise ContractError(f"task {task_id} has no pending approval")
        user = user_id or self._policy(task_id).user_id
        state = self._apply(state, [
            StatePatch(operation="set", path="pending_permission", value=None),
            self._observe(pending.step_id, "permission", "denied", f"{user} denied {pending.request.action}"),
        ])
        return self._result(self._finish(state, S.blocked, f"execution blocked: {user} denied {pending.request.action}"))

    async def clarify(self, task_id: str, answer: str, *, constraints: dict[str, Any] | None = None) -> TaskResult:
        """Answer an open clarification and resume (Decision 0013).

        Before a plan exists the task is planned again; otherwise the current plan is revised with the
        answer as evidence, which consumes replan budget. The original objective is never changed.
        """
        state = self.store.get(task_id)
        if state.status is not S.waiting_for_user or state.pending_permission is not None or not state.clarification:
            raise ContractError(f"task {task_id} has no open clarification")
        if not answer.strip() and not constraints:
            raise ContractError("a clarification needs an answer or constraints")
        question = state.clarification
        patches = [
            StatePatch(operation="set", path="clarification", value=None),
            self._observe(None, "supervisor", "clarified", f"user answered: {question}"),
        ]
        if answer.strip():
            patches.append(StatePatch(operation="append", path="clarifications", value=answer.strip()))
        if constraints:
            patches.append(StatePatch(operation="set", path="constraints", value={**state.constraints, **constraints}))
        if state.plan is None:
            state = self._transition(state, S.planning, "clarification received; planning", patches)
            return await self._run(state)

        step = state.current_plan_step() or state.plan.steps[-1]
        budgets = Budgets(retries_used=state.retry_counts.get(step.step_id, 0), replans_used=state.replan_count)
        if budgets.replans_used >= self.retry_policy.max_replans:
            state = self._apply(state, patches)
            return self._result(self._finish(state, S.failed, "clarification received but the replan budget is exhausted"))
        state = self._apply(state, patches)
        evidence = [f"open question: {question}", f"user answer: {answer.strip()}"]
        return await self._run(state, start=lambda st: self._revise(
            st, step, "clarification received; revising plan", budgets, evidence=evidence))

    def cancel(self, task_id: str) -> TaskResult:
        state = self.store.get(task_id)
        if state.terminal:
            return self._result(state)
        self._cancel_requested.add(task_id)
        if task_id not in self._running:  # a running loop applies the cancellation at its next checkpoint
            state = self._finish(state, S.canceled, "task canceled by user")
        return self._result(state)

    def get(self, task_id: str) -> TaskResult:
        return self._result(self.store.get(task_id))

    # ------------------------------------------------------------------ loop

    async def _run(self, state: TaskState,
                   start: Callable[[TaskState], Awaitable[TaskState]] | None = None) -> TaskResult:
        self._running.add(state.task_id)
        try:
            if start is not None:
                state = await start(state)
            state = await self._loop(state)
        except Exception as e:  # noqa: BLE001 - corrupt or unexpected state fails safely (002)
            state = self.store.force_fail(state.task_id, f"internal error ({type(e).__name__}); task stopped safely")
            self.obs.emit(EventType.status_changed, state.task_id, "task failed after an internal error",
                          metadata={"to": S.failed.value})
            self.obs.emit(EventType.task_finished, state.task_id, state.result.summary, metadata={"status": S.failed.value})
        finally:
            self._running.discard(state.task_id)
        return self._result(state)

    async def _loop(self, state: TaskState) -> TaskState:
        while True:
            if state.task_id in self._cancel_requested and not state.terminal:
                return self._finish(state, S.canceled, "task canceled by user")
            if state.status in (S.created, S.planning):
                state = await self._plan(state)
            elif state.status is S.executing:
                state = await self._execute_current(state)
            else:  # waiting_for_user, blocked and terminal statuses end this run
                return state

    async def _plan(self, state: TaskState) -> TaskState:
        if state.status is not S.planning:
            state = self._transition(state, S.planning, "planning started")
        if state.task_id not in self._memory_context:
            state = self._retrieve_memory(state)
        request = self._plan_request(state)
        attempts = 0
        while True:
            try:
                outcome = await self.planner.plan(request, task_id=state.task_id)
                break
            except PlannerError as e:
                if e.retryable and attempts < self.retry_policy.max_retries_per_step:
                    attempts += 1
                    self.obs.emit(EventType.retry_scheduled, state.task_id, f"retrying planner: {e.safe_summary}")
                    continue
                return self._finish(state, S.blocked, f"planning failed: {e.safe_summary}")

        if outcome.status is PlannerStatus.needs_clarification:
            return self._transition(state, S.waiting_for_user, "planner needs clarification", [
                StatePatch(operation="set", path="clarification", value=outcome.public_reason),
            ])
        if outcome.status is PlannerStatus.cannot_plan or outcome.plan is None:
            return self._finish(state, S.blocked, f"cannot plan: {outcome.public_reason}")
        plan = outcome.plan
        errors = validate_plan(plan, self.limits, request.available_capabilities)
        if errors:
            self.obs.emit(EventType.plan_rejected, state.task_id, "; ".join(errors), plan_id=plan.plan_id)
            return self._finish(state, S.blocked, f"plan rejected: {'; '.join(errors)}")

        state = self._apply(state, [
            StatePatch(operation="set", path="plan", value=plan, reason_summary="initial plan"),
            StatePatch(operation="set", path="current_step", value=0),
            self._decision(None, "plan", f"plan v{plan.version} with {len(plan.steps)} step(s)"),
        ])
        self.obs.emit(EventType.plan_created, state.task_id, f"plan v{plan.version} with {len(plan.steps)} step(s)",
                      plan_id=plan.plan_id, metadata={"steps": self._outline(plan), "version": plan.version})
        return self._transition(state, S.executing, "plan ready; executing")

    async def _execute_current(self, state: TaskState) -> TaskState:
        step = state.current_plan_step()
        assert state.plan is not None and step is not None
        if state.action_count >= self.limits.max_total_actions:
            return self._finish(state, S.failed, f"action budget of {self.limits.max_total_actions} exhausted")
        state, stop = self._check_spend(state, step)
        if stop:
            return state

        result = await self.engine.execute(
            ExecutionRequest(
                task_id=state.task_id, plan_id=state.plan.plan_id, step=step, state_snapshot=state,
                limits=ExecutionLimits(remaining_actions=self.limits.max_total_actions - state.action_count),
                routing_policy=self._policy(state.task_id).routing,
            ),
            is_canceled=lambda: state.task_id in self._cancel_requested,
        )
        patches = [
            StatePatch(operation="increment", path="action_count", reason_summary=f"executed {step.step_id}"),
            StatePatch(operation="append", path="observations", value=result.observation),
        ]
        if result.output_ref is not None:
            patches.insert(0, StatePatch(operation="put", path=f"outputs.{result.output_ref}", value=result.output))
        if result.permission is not None:
            patches.append(StatePatch(operation="append", path="permission_decisions", value=result.permission))
        state = self._apply(state, patches)
        self._artifacts[state.task_id].extend(result.artifacts)
        self.obs.emit(EventType.step_executed, state.task_id, result.observation.summary, plan_id=state.plan.plan_id,
                      step_id=step.step_id, metadata={"status": result.status.value, "worker": result.worker_id,
                                                      "attempted_workers": result.attempted_workers,
                                                      "error": result.error.code if result.error else None})

        if result.status is ExecutionStatus.canceled:
            return self._finish(state, S.canceled, "task canceled by user")
        if result.status is ExecutionStatus.blocked:
            if result.permission and result.permission.status is PermissionStatus.needs_user and result.permission_request:
                pending = PendingPermission(step_id=step.step_id, request=result.permission_request,
                                            prompt=PermissionPolicy.prompt_for(result.permission_request, result.permission))
                return self._transition(state, S.waiting_for_user, f"waiting for approval: {result.permission.audit_summary}", [
                    StatePatch(operation="set", path="pending_permission", value=pending),
                ])
            return self._finish(state, S.blocked, f"execution blocked: {result.error.safe_summary if result.error else 'denied'}")
        if result.status in (ExecutionStatus.failed, ExecutionStatus.timed_out):
            assert result.error is not None
            return await self._handle_failure(state, step, FailureSignal(
                source="execution", step_id=step.step_id, summary=result.error.safe_summary,
                code=result.error.code, retryable=result.error.retryable,
            ))

        state = self._transition(state, S.verifying, f"verifying {step.step_id}")
        state, verification = await self._verify(state, step.step_id, [result.output_ref], step.verification_criteria,
                                                 self._verification_context(state, step))
        if verification.status is VerificationStatus.pass_:
            if state.current_step + 1 < len(state.plan.steps):
                state = self._apply(state, [StatePatch(operation="set", path="current_step", value=state.current_step + 1)])
                return self._transition(state, S.executing, f"{step.step_id} verified; next step")
            return await self._verify_task(state, step)
        return await self._on_verification_failure(state, step, verification)

    async def _verify_task(self, state: TaskState, last_step: PlanStep) -> TaskState:
        """Final, task-level verification (001 R6, 007 R1) before the task may be marked done."""
        assert state.plan is not None
        final_ref = state.latest_output_ref(last_step.step_id)
        if state.plan.success_criteria:
            state, verification = await self._verify(state, None, [final_ref], state.plan.success_criteria,
                                                     state.objective.goal)
            if verification.status is not VerificationStatus.pass_:
                return await self._on_verification_failure(state, last_step, verification)
        else:
            verified = [o.step_id for o in state.observations if o.kind == "verification" and o.outcome == "pass"]
            verification = VerificationResult(
                status=VerificationStatus.pass_, satisfied_criteria=[f"step {s} verified" for s in dict.fromkeys(verified)],
                reason_summary=f"all {len(state.plan.steps)} step(s) passed verification",
                recommendation=VerificationRecommendation.continue_,
            )
        return self._finish(state, S.done, f"objective completed and verified: {verification.reason_summary}",
                            verification=verification, output_ref=final_ref)

    async def _verify(self, state: TaskState, step_id: str | None, refs: list[str | None], criteria: list[Criterion],
                      context: str) -> tuple[TaskState, VerificationResult]:
        request = VerificationRequest(task_id=state.task_id, step_id=step_id, output_refs=[r for r in refs if r],
                                      criteria=criteria, context_summary=context)
        verification = await self.verifier.verify(request, state.outputs)
        state = self._apply(state, [StatePatch(operation="append", path="observations", value=ObservationRecord(
            source="verifier", step_id=step_id, kind="verification", outcome=verification.status.value,
            summary=verification.reason_summary,
        ))])
        self.obs.emit(EventType.verification_completed, state.task_id, verification.reason_summary,
                      plan_id=state.plan.plan_id if state.plan else None, step_id=step_id,
                      metadata={"status": verification.status.value, "recommendation": verification.recommendation.value,
                                "failed_criteria": verification.failed_criteria, "final": step_id is None})
        return state, verification

    async def _on_verification_failure(self, state: TaskState, step: PlanStep, verification: VerificationResult) -> TaskState:
        if verification.recommendation is VerificationRecommendation.ask_user:
            return self._transition(state, S.waiting_for_user, "verification inconclusive; clarification needed", [
                StatePatch(operation="set", path="clarification", value=verification.reason_summary),
            ])
        return await self._handle_failure(state, step, FailureSignal(
            source="verification", step_id=step.step_id, summary=verification.reason_summary,
            recommendation=verification.recommendation,
        ))

    async def _handle_failure(self, state: TaskState, step: PlanStep, signal: FailureSignal) -> TaskState:
        """Bounded retry/replan (008). Failed actions stay recorded; nothing is hidden."""
        assert state.plan is not None
        budgets = Budgets(retries_used=state.retry_counts.get(step.step_id, 0), replans_used=state.replan_count)
        decision = self.replanner.decide(signal, budgets)

        if decision is ReplanStatus.retry:
            summary = (f"retrying {step.step_id} (retry {budgets.retries_used + 1}/"
                       f"{self.retry_policy.max_retries_per_step}): {signal.summary}")
            patches = [
                StatePatch(operation="increment", path=f"retry_counts.{step.step_id}", reason_summary=summary),
                self._decision(step.step_id, "retry_step", summary),
            ]
            self.obs.emit(EventType.retry_scheduled, state.task_id, summary, plan_id=state.plan.plan_id,
                          step_id=step.step_id, metadata={"source": signal.source, "code": signal.code})
            if state.status is S.executing:
                return self._apply(state, patches)
            return self._transition(state, S.executing, summary, patches)

        if decision is ReplanStatus.revised:
            return await self._revise(state, step, f"replanning after {step.step_id} failed: {signal.summary}", budgets)

        return self._finish(state, S.failed, f"stopped after {step.step_id} failed and budgets were exhausted "
                                              f"(retries {budgets.retries_used}, replans {budgets.replans_used}): "
                                              f"{signal.summary}")

    async def _revise(self, state: TaskState, step: PlanStep, summary: str, budgets: Budgets,
                      evidence: list[str] | None = None) -> TaskState:
        """Install a revised plan version (008 R5) or stop safely when no safe path remains."""
        assert state.plan is not None
        state = self._transition(state, S.replanning, summary, [
            StatePatch(operation="increment", path="replan_count", reason_summary=summary),
            self._decision(step.step_id, "replan", summary),
        ])
        self.obs.emit(EventType.replan_started, state.task_id, summary, plan_id=state.plan.plan_id, step_id=step.step_id)
        if evidence is None:
            evidence = [o.summary for o in state.observations if o.step_id == step.step_id][-3:]
        outcome = await self.replanner.replan(
            ReplanRequest(task_id=state.task_id, current_plan=state.plan, failed_step=step, evidence=evidence,
                          constraints=state.constraints, budgets=budgets),
            self._plan_request(state),
        )
        if outcome.status is ReplanStatus.revised and outcome.revised_plan is not None:
            revised = outcome.revised_plan
            state = self._apply(state, [
                StatePatch(operation="append", path="plan_history", value=state.plan),
                StatePatch(operation="set", path="plan", value=revised, reason_summary=outcome.reason_summary),
                StatePatch(operation="set", path="current_step", value=outcome.resume_index),
                self._observe(step.step_id, "replanning", "revised", outcome.reason_summary),
            ])
            self.obs.emit(EventType.plan_revised, state.task_id, outcome.reason_summary, plan_id=revised.plan_id,
                          step_id=step.step_id, metadata={
                              "version": revised.version,
                              "steps": self._outline(revised),
                              "previous_plan_id": revised.revision.previous_plan_id if revised.revision else None,
                              "changed_steps": revised.revision.changed_steps if revised.revision else [],
                              "resume_index": outcome.resume_index})
            return self._transition(state, S.executing, f"executing revised plan v{revised.version}")
        if outcome.clarification:
            return self._transition(state, S.waiting_for_user, "replanning needs the user's answer", [
                StatePatch(operation="increment", path="replan_count", value=-1,
                           reason_summary="no revision was made; the replan is not charged"),
                StatePatch(operation="set", path="clarification", value=outcome.clarification),
            ])
        status = S.blocked if outcome.status is ReplanStatus.blocked else S.failed
        return self._finish(state, status, outcome.reason_summary)

    # ------------------------------------------------------------------ helpers

    def _check_spend(self, state: TaskState, step: PlanStep) -> tuple[TaskState, bool]:
        """Costly-action gate (009 R3): past the spending limit, continuing needs explicit approval.

        Each approval is a distinct `extend_budget:<n>` action, so an earlier approval never covers a
        later extension. Returns the (possibly updated) state and whether the loop must stop.
        """
        cap = self.limits.max_cost_usd
        if cap is None:
            return state, False
        spent = self.ledger.totals(state.task_id).get("cost_micro_usd", 0) / 1_000_000
        grants = sum(1 for a in state.approvals if a.action.startswith(SPEND_ACTION))
        limit = cap * (1 + grants)
        if spent < limit:
            return state, False
        request = PermissionRequest(
            task_id=state.task_id, action=f"{SPEND_ACTION}{grants + 1}", resource="model usage",
            scope=f"budget/{grants + 1}", risk_level=PermissionLevel.costly,
            reason_summary=(f"estimated spend ${spent:.4f} reached the ${limit:.2f} limit; "
                            f"approving allows up to ${limit + cap:.2f}"),
        )
        decision = self.tools.policy.evaluate(request, state.approvals)
        state = self._apply(state, [StatePatch(operation="append", path="permission_decisions", value=decision)])
        self.obs.emit(EventType.permission_decided, state.task_id, decision.audit_summary, step_id=step.step_id,
                      metadata={"status": decision.status.value, "scope": request.scope, "spent_usd": round(spent, 4)})
        if decision.status is PermissionStatus.allowed:
            return state, False
        if decision.status is PermissionStatus.needs_user:
            pending = PendingPermission(step_id=step.step_id, request=request,
                                        prompt=PermissionPolicy.prompt_for(request, decision))
            return self._transition(state, S.waiting_for_user, f"spending limit reached: {request.reason_summary}", [
                StatePatch(operation="set", path="pending_permission", value=pending),
            ]), True
        return self._finish(state, S.blocked,
                            f"spending limit reached and extension denied: {request.reason_summary}"), True

    @staticmethod
    def _outline(plan) -> list[dict[str, str]]:
        """Public plan outline for events: what each step does, never how a model reasoned about it."""
        return [{"id": st.step_id, "kind": st.kind.value, "capability": st.required_capability, "purpose": st.purpose}
                for st in plan.steps]

    def _policy(self, task_id: str) -> UserPolicy:
        return self._policies.get(task_id) or UserPolicy()

    @staticmethod
    def _verification_context(state: TaskState, step: PlanStep) -> str:
        """What a semantic judge needs: the expected output and the source data the step worked from."""
        context = f"Expected output: {step.expected_output}"
        sources = {ref: state.outputs.get(state.latest_output_ref(ref) or "") for ref in step.input_refs}
        if sources:
            data = json.dumps(sources, ensure_ascii=False, default=str)
            context += f"\nSource data the step was given:\n{data[:MAX_JUDGE_SOURCE_CHARS]}"
        return context

    def _retrieve_memory(self, state: TaskState) -> TaskState:
        """010 behavior: retrieve scoped, relevant memory once before planning. Task State records only the
        ids used; an unavailable store never blocks the task (010 error handling)."""
        self._memory_context[state.task_id] = []
        if self.memory is None:
            return state
        query = MemoryQuery(task_id=state.task_id, scope=self._memory_scopes.get(state.task_id, [USER_SCOPE]),
                            keywords=keywords_of(f"{state.objective.goal} {' '.join(state.clarifications)}"))
        try:
            result = self.memory.query(query)
        except Exception as e:  # noqa: BLE001 - memory is optional for execution
            self.obs.emit(EventType.diagnostic, state.task_id,
                          f"memory unavailable ({type(e).__name__}); continuing without it")
            return state
        self._memory_context[state.task_id] = result.records
        ids = [r.id for r in result.records]
        self.obs.emit(EventType.memory_retrieved, state.task_id, result.retrieval_summary,
                      metadata={"record_ids": ids, "omitted": result.omitted_count})
        if not ids:
            return state
        return self._apply(state, [self._observe(None, "memory", "retrieved",
                                                 f"used {len(ids)} saved memory record(s): {', '.join(ids)}")])

    def memory_used(self, task_id: str) -> list[MemoryRecord]:
        return list(self._memory_context.get(task_id, []))

    def _plan_request(self, state: TaskState) -> PlanRequest:
        return PlanRequest(
            objective=state.objective,
            constraints=state.constraints,
            available_capabilities=self.router.capabilities() | set(self.tools.registry.names()),
            context_summary=state.objective.context[:MAX_CONTEXT_CHARS],
            clarifications=state.clarifications,
            # Sensitive records stay on this machine: they are not sent to model workers.
            memory=[{"id": r.id, "type": r.type, "content": r.content}
                    for r in self._memory_context.get(state.task_id, []) if r.sensitivity is not Sensitivity.sensitive],
        )

    def _apply(self, state: TaskState, patches: list[StatePatch]) -> TaskState:
        return self.store.apply(state.task_id, patches, expected_version=state.version, actor=self.actor)

    def _transition(self, state: TaskState, new: TaskStatus, reason: str, extra: list[StatePatch] | None = None) -> TaskState:
        old = state.status
        state = self._apply(state, [set_status(new, reason), *(extra or [])])
        self.obs.emit(EventType.status_changed, state.task_id, f"{old.value} -> {new.value}: {reason}",
                      plan_id=state.plan.plan_id if state.plan else None,
                      metadata={"from": old.value, "to": new.value})
        if new in TERMINAL_STATUSES or new is S.blocked:
            self.obs.emit(EventType.task_finished, state.task_id, reason, metadata={"status": new.value})
        return state

    def _finish(self, state: TaskState, status: TaskStatus, summary: str, *,
                verification: VerificationResult | None = None, output_ref: str | None = None) -> TaskState:
        result = FinalResult(status=status, summary=summary, output_ref=output_ref, verification=verification)
        action = {S.done: "finish", S.blocked: "block"}.get(status, "fail")
        return self._transition(state, status, summary, [
            StatePatch(operation="set", path="result", value=result),
            self._decision(None, action, summary),
        ])

    @staticmethod
    def _observe(step_id: str | None, kind: str, outcome: str, summary: str) -> StatePatch:
        return StatePatch(operation="append", path="observations", value=ObservationRecord(
            source="supervisor", step_id=step_id, kind=kind, outcome=outcome, summary=summary))

    @classmethod
    def _decision(cls, step_id: str | None, action: str, summary: str) -> StatePatch:
        decision = SupervisorDecision(next_action=action, reason_summary=summary)
        return cls._observe(step_id, "supervisor", decision.next_action, decision.reason_summary)

    def _result(self, state: TaskState) -> TaskResult:
        result = state.result
        if result is not None:
            summary = result.summary
        elif state.status is S.waiting_for_user:
            summary = state.clarification or (state.pending_permission.prompt.action_summary
                                              if state.pending_permission else "waiting for user")
        else:
            summary = f"task is {state.status.value}"
        output_ref = result.output_ref if result else None
        return TaskResult(
            task_id=state.task_id,
            status=state.status,
            summary=summary,
            output=state.outputs.get(output_ref) if output_ref else None,
            artifacts=list(self._artifacts.get(state.task_id, [])),
            verification_result=result.verification if result else None,
            observations=state.observations,
            approval_prompt=state.pending_permission.prompt if state.pending_permission else None,
            clarification=state.clarification if state.status is S.waiting_for_user else None,
            usage=self.ledger.totals(state.task_id),
        )
