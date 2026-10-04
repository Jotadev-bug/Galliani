"""Spec 006 - Execution Engine acceptance criteria."""

from __future__ import annotations

from galliani.contracts import Objective
from galliani.execution import ExecutionEngine, ExecutionLimits, ExecutionRequest, ExecutionStatus
from galliani.observability import InMemoryEventSink, Observability
from galliani.planner import PlanStep
from galliani.router import ModelRouter
from galliani.state import TaskStateStore
from galliani.testing import FixtureWorld, ScriptedAdapter, fixture_tool_registry
from galliani.tools import ToolSystem
from tests.core.helpers import read_step, summarize_step, worker


def setup(script=None, workers=None):
    world = FixtureWorld(notes={"n1": "budget note"})
    adapter = ScriptedAdapter("scripted", script or {})
    sink = InMemoryEventSink()
    engine = ExecutionEngine(ModelRouter(workers or [worker("w1")]), [adapter],
                             ToolSystem(fixture_tool_registry(world)), Observability([sink]))
    state = TaskStateStore().create(Objective(goal="g"))
    return engine, adapter, world, sink, state


def request(state, step: dict, remaining: int = 5) -> ExecutionRequest:
    return ExecutionRequest(task_id=state.task_id, plan_id="p1", step=PlanStep.model_validate(step),
                            state_snapshot=state, limits=ExecutionLimits(remaining_actions=remaining))


# AC: Model Step
async def test_model_step_routes_to_worker_and_returns_structured_result():
    engine, adapter, _, sink, state = setup({"w1": [{"output": "budget is fine"}]})
    result = await engine.execute(request(state, summarize_step(refs=())))
    assert result.status is ExecutionStatus.succeeded
    assert result.worker_id == "w1" and result.route.worker_id == "w1"
    assert result.output == "budget is fine" and result.output_ref
    assert result.observation.step_id == "s1" and result.observation.source == "worker:w1"
    assert [e.type.value for e in sink.events] == ["route_selected"]


# AC: Tool Step
async def test_tool_step_validates_and_executes_through_tool_system():
    engine, adapter, world, sink, state = setup()
    result = await engine.execute(request(state, read_step()))
    assert result.status is ExecutionStatus.succeeded and result.output == {"text": "budget note"}
    assert world.executed == ["read_note"] and adapter.calls == []
    assert "tool_called" in [e.type.value for e in sink.events]


async def test_invalid_tool_arguments_fail_without_running():
    engine, _, world, _, state = setup()
    step = read_step()
    step["tool"]["arguments"] = {"wrong": 1}
    result = await engine.execute(request(state, step))
    assert result.status is ExecutionStatus.failed and result.error.code == "invalid_arguments"
    assert world.executed == []


# AC: Cancellation
async def test_canceled_task_starts_no_action():
    engine, adapter, world, _, state = setup()
    result = await engine.execute(request(state, summarize_step(refs=())), is_canceled=lambda: True)
    assert result.status is ExecutionStatus.canceled
    assert adapter.calls == [] and world.executed == []


async def test_fallback_on_provider_error_and_every_attempt_observed():
    engine, adapter, _, sink, state = setup(
        {"w1": [{"error": "provider_unavailable"}], "w2": [{"output": "budget ok"}]},
        workers=[worker("w1"), worker("w2", cost="medium")],
    )
    result = await engine.execute(request(state, summarize_step(refs=())))
    assert result.status is ExecutionStatus.succeeded and result.worker_id == "w2"
    assert result.attempted_workers == ["w1", "w2"]
    assert "route_fallback" in [e.type.value for e in sink.events]


async def test_worker_timeout_maps_to_timed_out():
    engine, _, _, _, state = setup({"w1": [{"error": "timeout"}]})
    result = await engine.execute(request(state, summarize_step(refs=())))
    assert result.status is ExecutionStatus.timed_out and result.error.retryable


async def test_non_fallback_error_stops_fallback_walk():
    engine, adapter, _, _, state = setup({"w1": [{"error": "invalid_request"}]},
                                         workers=[worker("w1"), worker("w2", cost="medium")])
    result = await engine.execute(request(state, summarize_step(refs=())))
    assert result.status is ExecutionStatus.failed and result.attempted_workers == ["w1"]


async def test_missing_input_and_budget_exhaustion():
    engine, adapter, _, _, state = setup()
    result = await engine.execute(request(state, summarize_step(refs=("s0",))))
    assert result.error.code == "missing_input" and adapter.calls == []
    result = await engine.execute(request(state, summarize_step(refs=()), remaining=0))
    assert result.error.code == "budget_exhausted" and adapter.calls == []


async def test_no_route_is_a_structured_failure():
    engine, _, _, sink, state = setup()
    step = summarize_step(refs=())
    step["required_capability"] = "vision"
    result = await engine.execute(request(state, step))
    assert result.status is ExecutionStatus.failed and result.error.code == "no_route"
    assert sink.events[0].type.value == "route_failed"
