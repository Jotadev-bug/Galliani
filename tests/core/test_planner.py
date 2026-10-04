"""Spec 004 - Planner acceptance criteria."""

from __future__ import annotations

import pytest

from galliani.contracts import Objective
from galliani.limits import LoopLimits
from galliani.planner import Plan, PlannerError, PlannerStatus, PlanRequest, StaticPlanner, validate_plan

MODEL_STEP = {
    "step_id": "s1", "kind": "model", "purpose": "summarize", "required_capability": "text",
    "expected_output": "a summary", "instruction": "Summarize the note.",
    "verification_criteria": [{"kind": "min_length", "value": 5}],
}
TOOL_STEP = {
    "step_id": "s0", "kind": "tool", "purpose": "read the note", "required_capability": "read_note",
    "expected_output": "note text", "tool": {"tool_name": "read_note", "arguments": {"note_id": "n1"}},
    "verification_criteria": [{"kind": "field_present", "field": "text"}],
}


def request(**constraints) -> PlanRequest:
    return PlanRequest(objective=Objective(goal="summarize note n1", constraints=constraints),
                       constraints=constraints, available_capabilities={"text", "read_note"})


# AC: Plan Creation
async def test_clear_objective_produces_bounded_verifiable_plan():
    planner = StaticPlanner([{"steps": [TOOL_STEP, {**MODEL_STEP, "input_refs": ["s0"]}]}])
    outcome = await planner.plan(request(), task_id="t1")
    assert outcome.status is PlannerStatus.planned
    plan = outcome.plan
    assert plan.task_id == "t1" and plan.version == 1
    assert [s.kind.value for s in plan.steps] == ["tool", "model"]  # model vs tool work distinguished
    assert validate_plan(plan, LoopLimits(), {"text", "read_note"}) == []


# AC: Clarification
async def test_missing_required_constraint_returns_clarification():
    planner = StaticPlanner([{"steps": [MODEL_STEP]}], required_constraints=["audience"])
    outcome = await planner.plan(request(), task_id="t1")
    assert outcome.status is PlannerStatus.needs_clarification and "audience" in outcome.public_reason


async def test_impossible_objective_returns_cannot_plan():
    outcome = await StaticPlanner([{"cannot_plan": "no tool can reach that system"}]).plan(request(), task_id="t")
    assert outcome.status is PlannerStatus.cannot_plan and outcome.public_reason


# AC: Plan Revision
async def test_revision_increments_version():
    planner = StaticPlanner([{"steps": [MODEL_STEP]}, {"steps": [MODEL_STEP]}])
    first = (await planner.plan(request(), task_id="t")).plan
    revised = (await planner.revise(request(), current_plan=first, failed_step_id="s1", evidence=["x"])).plan
    assert revised.version == 2 and revised.plan_id != first.plan_id


async def test_malformed_plan_and_planner_errors_are_structured():
    with pytest.raises(PlannerError):
        await StaticPlanner([{"steps": [{"step_id": "x"}]}]).plan(request(), task_id="t")
    with pytest.raises(PlannerError) as e:
        await StaticPlanner([{"error": "model down", "retryable": True}]).plan(request(), task_id="t")
    assert e.value.retryable


def plan_of(*steps: dict) -> Plan:
    return Plan(plan_id="p", task_id="t", version=1, steps=list(steps))


def test_oversized_plan_rejected():
    steps = [{**MODEL_STEP, "step_id": f"s{i}"} for i in range(6)]
    assert any("limit" in e for e in validate_plan(plan_of(*steps), LoopLimits(max_plan_steps=5)))


def test_validation_catches_missing_criteria_unknown_capability_bad_refs_and_secrets():
    errors = validate_plan(plan_of(
        {**MODEL_STEP, "verification_criteria": []},
        {**MODEL_STEP, "step_id": "s2", "required_capability": "vision", "input_refs": ["later"]},
        {**MODEL_STEP, "step_id": "s3", "instruction": "use key sk-abcdefghijklmnopqrstuvwx"},
    ), LoopLimits(), {"text"})
    joined = " | ".join(errors)
    assert "no verification criteria" in joined
    assert "unavailable capability vision" in joined
    assert "consumes later" in joined
    assert "secret" in joined


def test_tool_step_must_name_its_tool():
    errors = validate_plan(plan_of({**TOOL_STEP, "required_capability": "other"}), LoopLimits())
    assert any("must name its tool" in e for e in errors)


def test_plan_steps_reject_hidden_reasoning_fields():
    with pytest.raises(ValueError):
        plan_of({**MODEL_STEP, "reasoning": "private"})
