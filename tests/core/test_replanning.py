"""Spec 008 - Replanning unit tests: retry budget logic, plan revision and resume point."""

from __future__ import annotations

import pytest

from galliani.contracts import Objective
from galliani.planner import Plan, PlanRequest, StaticPlanner
from galliani.replanning import Budgets, FailureSignal, Replanner, ReplanRequest, ReplanStatus, RetryPolicy
from galliani.verification import VerificationRecommendation as Rec
from tests.core.helpers import read_step, summarize_step

R = ReplanStatus


def timeout_signal() -> FailureSignal:
    return FailureSignal(source="execution", step_id="s1", summary="timed out", code="timeout", retryable=True)


@pytest.mark.parametrize("signal,budgets,expected", [
    (timeout_signal(), Budgets(), R.retry),                                   # AC Retry
    (timeout_signal(), Budgets(retries_used=1), R.revised),                   # retry budget exhausted -> replan
    (timeout_signal(), Budgets(retries_used=1, replans_used=1), R.failed),    # AC Stop
    (FailureSignal(source="execution", step_id="s1", summary="bad args", code="invalid_arguments"), Budgets(), R.revised),
    (FailureSignal(source="verification", step_id="s1", summary="x", recommendation=Rec.retry), Budgets(), R.retry),
    (FailureSignal(source="verification", step_id="s1", summary="x", recommendation=Rec.replan), Budgets(), R.revised),
    (FailureSignal(source="verification", step_id="s1", summary="x", recommendation=Rec.stop), Budgets(), R.failed),
])
def test_decide_respects_policy_and_budgets(signal, budgets, expected):
    assert Replanner(StaticPlanner([])).decide(signal, budgets) is expected


def test_zero_budgets_never_loop():
    replanner = Replanner(StaticPlanner([]), RetryPolicy(max_retries_per_step=0, max_replans=0))
    assert replanner.decide(timeout_signal(), Budgets()) is R.failed


def plan_v1() -> Plan:
    return Plan(plan_id="p1", task_id="t1", version=1, steps=[read_step(), summarize_step()])


def plan_request() -> PlanRequest:
    return PlanRequest(objective=Objective(goal="summarize n1"), available_capabilities={"text", "read_note"})


def replan_request(plan: Plan) -> ReplanRequest:
    return ReplanRequest(task_id="t1", current_plan=plan, failed_step=plan.steps[1], evidence=["missing 'budget'"],
                         budgets=Budgets())


# AC: Replan
async def test_revised_plan_version_reason_and_resume_after_verified_steps():
    new_s1 = summarize_step(must_contain="spend")
    replanner = Replanner(StaticPlanner([{"steps": [read_step(), new_s1]}]))
    result = await replanner.replan(replan_request(plan_v1()), plan_request())
    assert result.status is R.revised
    revised = result.revised_plan
    assert revised.version == 2 and revised.revision.previous_plan_id == "p1"
    assert revised.revision.changed_steps == ["s1"] and "missing 'budget'" in revised.revision.reason
    assert result.resume_index == 1  # verified, unchanged s0 is not re-run


async def test_no_alternative_plan_blocks():
    result = await Replanner(StaticPlanner([])).replan(replan_request(plan_v1()), plan_request())
    assert result.status is R.blocked


async def test_invalid_revised_plan_fails():
    oversized = {"steps": [summarize_step(step_id=f"x{i}", refs=()) for i in range(6)]}
    result = await Replanner(StaticPlanner([oversized])).replan(replan_request(plan_v1()), plan_request())
    assert result.status is R.failed and "rejected" in result.reason_summary


async def test_revised_plan_must_keep_the_same_task():
    class OtherTaskPlanner(StaticPlanner):
        async def revise(self, request, *, current_plan, failed_step_id, evidence):
            outcome = await super().revise(request, current_plan=current_plan, failed_step_id=failed_step_id,
                                           evidence=evidence)
            return outcome.model_copy(update={"plan": outcome.plan.model_copy(update={"task_id": "other"})})

    result = await Replanner(OtherTaskPlanner([{"steps": [read_step()]}])).replan(replan_request(plan_v1()), plan_request())
    assert result.status is R.failed
