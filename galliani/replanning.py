"""Spec 008 - Replanning: bounded retry and plan revision on explicit failure signals.

`decide` applies the retry policy to a `FailureSignal`; `replan` asks the planner for a revised plan for
the same objective, validates it, and computes where execution resumes so already verified steps with
unchanged definitions are not re-run (no repeated side effects).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from galliani.contracts import new_id
from galliani.limits import LoopLimits
from galliani.planner import Plan, Planner, PlannerError, PlannerStatus, PlanRequest, PlanRevision, PlanStep, validate_plan
from galliani.verification import VerificationRecommendation


class RetryPolicy(BaseModel):
    max_retries_per_step: int = Field(default=1, ge=0)
    max_replans: int = Field(default=1, ge=0)
    retryable_errors: set[str] = Field(default_factory=lambda: {
        "timeout", "provider_unavailable", "rate_limited", "malformed_response",
    })


class FailureSignal(BaseModel):
    source: Literal["execution", "verification"]
    step_id: str
    summary: str
    code: str | None = None
    retryable: bool = False
    recommendation: VerificationRecommendation | None = None


class ReplanStatus(str, Enum):
    retry = "retry"
    revised = "revised"
    blocked = "blocked"
    failed = "failed"


class Budgets(BaseModel):
    retries_used: int = 0
    replans_used: int = 0


class ReplanRequest(BaseModel):
    task_id: str
    current_plan: Plan
    failed_step: PlanStep
    evidence: list[str]
    constraints: dict = Field(default_factory=dict)
    budgets: Budgets


class ReplanResult(BaseModel):
    status: ReplanStatus
    revised_plan: Plan | None = None
    reason_summary: str
    retry_decision: bool = False
    resume_index: int = 0


class Replanner:
    def __init__(self, planner: Planner, policy: RetryPolicy | None = None, limits: LoopLimits | None = None):
        self.planner = planner
        self.policy = policy or RetryPolicy()
        self.limits = limits or LoopLimits()

    def decide(self, signal: FailureSignal, budgets: Budgets) -> ReplanStatus:
        """Retry, replan (`revised` means a revision should be requested) or stop."""
        if signal.recommendation is VerificationRecommendation.stop:
            return ReplanStatus.failed
        if signal.source == "execution":
            wants_retry = signal.retryable and (signal.code in self.policy.retryable_errors)
        else:
            wants_retry = signal.recommendation is VerificationRecommendation.retry
        if wants_retry and budgets.retries_used < self.policy.max_retries_per_step:
            return ReplanStatus.retry
        if budgets.replans_used < self.policy.max_replans:
            return ReplanStatus.revised
        return ReplanStatus.failed

    async def replan(self, request: ReplanRequest, plan_request: PlanRequest) -> ReplanResult:
        current = request.current_plan
        try:
            outcome = await self.planner.revise(plan_request, current_plan=current,
                                                failed_step_id=request.failed_step.step_id, evidence=request.evidence)
        except PlannerError as e:
            return ReplanResult(status=ReplanStatus.failed, reason_summary=f"replanning failed: {e.safe_summary}")
        # No safe path remains: block (the user may change constraints) rather than fail (008 behavior).
        if outcome.status is PlannerStatus.needs_clarification:
            return ReplanResult(status=ReplanStatus.blocked, reason_summary=f"replanning needs input: {outcome.public_reason}")
        if outcome.status is not PlannerStatus.planned or outcome.plan is None:
            return ReplanResult(status=ReplanStatus.blocked, reason_summary=f"no revised plan: {outcome.public_reason}")

        revised = outcome.plan
        if revised.task_id != current.task_id:
            return ReplanResult(status=ReplanStatus.failed, reason_summary="revised plan targets a different task")
        errors = validate_plan(revised, self.limits, plan_request.available_capabilities)
        if errors:
            return ReplanResult(status=ReplanStatus.failed, reason_summary=f"revised plan rejected: {'; '.join(errors)}")

        old_steps = {s.step_id: s for s in current.steps}
        failed_index = next(i for i, s in enumerate(current.steps) if s.step_id == request.failed_step.step_id)
        verified = {s.step_id for s in current.steps[:failed_index]}
        resume = 0
        for step in revised.steps:
            if step.step_id in verified and old_steps[step.step_id] == step:
                resume += 1
            else:
                break
        changed = [s.step_id for s in revised.steps if old_steps.get(s.step_id) != s]
        reason = f"step {request.failed_step.step_id} failed: {request.evidence[-1] if request.evidence else 'no evidence'}"
        revised = revised.model_copy(update={
            "plan_id": revised.plan_id or new_id("plan"),
            "version": max(revised.version, current.version + 1),
            "revision": PlanRevision(previous_plan_id=current.plan_id, reason=reason, changed_steps=changed),
        })
        return ReplanResult(status=ReplanStatus.revised, revised_plan=revised, resume_index=resume,
                            reason_summary=f"plan revised to v{revised.version}; {len(changed)} step(s) changed; {reason}")
