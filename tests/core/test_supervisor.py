"""Spec 001 - Agent Core: integration tests for the full objective-to-done loop."""

from __future__ import annotations

import ast
import inspect

import pytest

import galliani.supervisor as supervisor_module
from galliani.contracts import Objective
from galliani.errors import ContractError
from galliani.limits import LoopLimits
from galliani.permissions import PermissionLevel, PermissionPolicy, PermissionStatus
from galliani.router import RoutingPolicy
from galliani.state import TaskStatus
from galliani.supervisor import StartTaskRequest, UserPolicy
from galliani.testing import ScriptedAdapter, ScriptedChatAdapter
from tests.core.helpers import Harness, read_step, summarize_step, tool_step, worker

S = TaskStatus
GOOD = {"output": "Q3 budget: spend is 4% under plan."}
BAD = {"output": "Everything looks fine overall."}
REASONING_MARKER = "PRIVATE-REASONING-MARKER"


def start(goal: str = "Summarize note n1", **kw) -> StartTaskRequest:
    return StartTaskRequest(objective=Objective(goal=goal), **kw)


def two_step_plan(**summarize_kw) -> dict:
    return {"steps": [read_step(), summarize_step(**summarize_kw)],
            "success_criteria": [{"kind": "contains", "value": "under plan"}]}


# AC: Happy Path
async def test_full_loop_objective_to_done():
    h = Harness([two_step_plan()], script={"w1": [GOOD]})
    result = await h.supervisor.start(start())
    assert result.status is S.done
    assert result.output == GOOD["output"]
    assert result.verification_result.status.value == "pass"
    assert h.statuses(result.task_id) == [
        "created", "planning", "executing", "verifying", "executing", "verifying", "done"]
    # the worker received the tool output as data
    assert h.adapter.calls[0].inputs == {"s0": {"text": "Q3 budget review: spend is 4% under plan."}}
    kinds = [(o.kind, o.outcome) for o in result.observations]
    assert ("execution", "succeeded") in kinds and ("verification", "pass") in kinds


# AC: Verification Failure -> retry
async def test_failed_verification_retries_instead_of_done():
    h = Harness([two_step_plan()], script={"w1": [BAD, GOOD]})
    result = await h.supervisor.start(start())
    assert result.status is S.done
    state = h.supervisor.store.get(result.task_id)
    assert state.retry_counts == {"s1": 1} and state.replan_count == 0
    assert len(h.events(result.task_id, "retry_scheduled")) == 1


# AC: Verification Failure -> replan (bad approach), verified steps not re-run
async def test_bad_approach_replans_to_new_plan_version():
    revised = {"steps": [read_step(), summarize_step(must_contain="spend")],
               "success_criteria": [{"kind": "contains", "value": "under plan"}]}
    h = Harness([two_step_plan(on_fail="replan"), revised], script={"w1": [BAD, GOOD]})
    result = await h.supervisor.start(start())
    assert result.status is S.done
    state = h.supervisor.store.get(result.task_id)
    assert state.plan.version == 2 and len(state.plan_history) == 1
    assert state.plan.revision.changed_steps == ["s1"]
    assert h.world.executed == ["read_note"]  # no repeated side effects
    assert "replanning" in h.statuses(result.task_id)
    assert h.events(result.task_id, "plan_revised")[0].metadata["version"] == 2


# 008 AC Stop / 001 negative fixture: never a false done
async def test_budgets_exhausted_fails_safely_never_done():
    h = Harness([two_step_plan(), two_step_plan()], script={"w1": [BAD] * 10})
    result = await h.supervisor.start(start())
    assert result.status is S.failed
    assert "budgets were exhausted" in result.summary
    state = h.supervisor.store.get(result.task_id)
    assert state.replan_count == 1 and state.retry_counts["s1"] == 1
    assert state.action_count <= LoopLimits().max_total_actions


async def test_final_success_criteria_gate_done():
    plan = two_step_plan()
    plan["success_criteria"] = [{"kind": "contains", "value": "never present"}]
    h = Harness([plan], script={"w1": [GOOD] * 5})
    result = await h.supervisor.start(start())
    assert result.status is not S.done


async def test_retryable_tool_timeout_is_retried_and_recorded():
    h = Harness([{"steps": [tool_step("f", "fetch_page", url="https://example.test/q3")]}])
    h.world.pages["https://example.test/q3"] = "Q3 page"
    h.world.flaky_timeouts = 1
    result = await h.supervisor.start(start())
    assert result.status is S.done
    assert h.world.executed == ["fetch_page", "fetch_page"]
    assert h.supervisor.store.get(result.task_id).retry_counts == {"f": 1}


# AC: Blocked Task (missing permission -> waiting for user approval)
async def test_missing_permission_pauses_for_user_approval():
    h = Harness([{"steps": [tool_step("d", "delete_file", path="reports/old.txt")]}])
    h.world.files["reports/old.txt"] = "x"
    result = await h.supervisor.start(start("Delete reports/old.txt"))
    assert result.status is S.waiting_for_user
    assert result.approval_prompt.scope == "reports/old.txt"
    assert "delete_file" in result.approval_prompt.action_summary
    assert "delete_file" not in h.world.executed

    resumed = await h.supervisor.approve(result.task_id)
    assert resumed.status is S.done
    assert h.world.executed == ["delete_file"] and "reports/old.txt" not in h.world.files
    state = h.supervisor.store.get(result.task_id)
    assert [a.scope for a in state.approvals] == ["reports/old.txt"]
    assert [d.status for d in state.permission_decisions] == [PermissionStatus.needs_user, PermissionStatus.allowed]
    assert state.retry_counts == {}  # approval does not consume retry budget


async def test_user_denial_blocks_execution():
    h = Harness([{"steps": [tool_step("d", "delete_file", path="a.txt")]}])
    result = await h.supervisor.start(start("Delete a.txt"))
    denied = await h.supervisor.deny(result.task_id)
    assert denied.status is S.blocked and "denied" in denied.summary
    assert h.world.executed == []
    with pytest.raises(ContractError):
        await h.supervisor.approve(result.task_id)


async def test_policy_denial_blocks_without_asking():
    policy = PermissionPolicy(rules={PermissionLevel.destructive: PermissionStatus.denied})
    h = Harness([{"steps": [tool_step("d", "delete_file", path="a.txt")]}], policy=policy)
    result = await h.supervisor.start(start("Delete a.txt"))
    assert result.status is S.blocked and h.world.executed == []


# Router failure: fallback routing, or blocked
async def test_provider_failure_falls_back_to_compatible_worker():
    h = Harness([two_step_plan()], workers=[worker("w1"), worker("w2", cost="medium")],
                script={"w1": [{"error": "provider_unavailable"}], "w2": [GOOD]})
    result = await h.supervisor.start(start())
    assert result.status is S.done
    fallback = h.events(result.task_id, "route_fallback")
    assert fallback and fallback[0].metadata == {"from": "w1", "to": "w2", "reason": "provider_unavailable"}


async def test_no_route_blocks_when_no_alternative_plan():
    plan = {"steps": [summarize_step(refs=())]}
    plan["steps"][0]["required_capability"] = "text"
    h = Harness([plan], workers=[worker("w1")])
    result = await h.supervisor.start(start(user_policy=UserPolicy(routing=RoutingPolicy(denied_providers={"scripted"}))))
    assert result.status is S.blocked
    assert h.events(result.task_id, "route_failed")[0].metadata["code"] == "route_denied"


# Planner failures
async def test_planner_failure_blocks_and_retryable_planner_error_is_retried_once():
    h = Harness([{"error": "planner down"}])
    assert (await h.supervisor.start(start())).status is S.blocked
    h = Harness([{"error": "flaky", "retryable": True}, two_step_plan()], script={"w1": [GOOD]})
    assert (await h.supervisor.start(start())).status is S.done


async def test_cannot_plan_and_oversized_plan_block():
    assert (await Harness([{"cannot_plan": "no tool reaches that system"}]).supervisor.start(start())).status is S.blocked
    oversized = {"steps": [summarize_step(step_id=f"s{i}", refs=()) for i in range(6)]}
    h = Harness([oversized])
    result = await h.supervisor.start(start())
    assert result.status is S.blocked and "limit" in result.summary
    assert h.events(result.task_id, "plan_rejected")


async def test_invalid_objective_and_missing_constraints_ask_for_clarification():
    result = await Harness([two_step_plan()]).supervisor.start(start("   "))
    assert result.status is S.waiting_for_user and result.clarification
    h = Harness([two_step_plan()], required_constraints=["audience"])
    result = await h.supervisor.start(start())
    assert result.status is S.waiting_for_user and "audience" in result.clarification


async def test_inconclusive_verification_asks_user():
    plan = {"steps": [summarize_step(refs=())]}
    plan["steps"][0]["verification_criteria"] = [{"kind": "semantic", "value": "is persuasive"}]
    result = await Harness([plan], script={"w1": [GOOD]}).supervisor.start(start())
    assert result.status is S.waiting_for_user and "better criteria" in result.clarification


async def test_action_budget_bounds_the_loop():
    plan = {"steps": [summarize_step(step_id=f"s{i}", refs=()) for i in range(3)]}
    result = await Harness([plan], script={"w1": [GOOD] * 3}, limits=LoopLimits(max_total_actions=2)).supervisor.start(start())
    assert result.status is S.failed and "action budget" in result.summary


async def test_cancellation_stops_further_actions():
    h = Harness([{"steps": [tool_step("w", "write_file", path="a.txt", content="x"),
                            tool_step("d", "delete_file", path="a.txt")]}],
                policy=PermissionPolicy(rules={PermissionLevel.write: PermissionStatus.allowed,
                                               PermissionLevel.destructive: PermissionStatus.allowed}))
    original = h.supervisor.tools.registry.get("write_file").handler

    def write_then_cancel(args):
        h.supervisor.cancel(next(iter(h.supervisor._running)))
        return original(args)

    h.supervisor.tools.registry.get("write_file").handler = write_then_cancel
    result = await h.supervisor.start(start())
    assert result.status is S.canceled
    assert h.world.executed == ["write_file"]  # delete never started


async def test_cancel_paused_task():
    h = Harness([{"steps": [tool_step("d", "delete_file", path="a.txt")]}])
    result = await h.supervisor.start(start())
    assert h.supervisor.cancel(result.task_id).status is S.canceled


async def test_unexpected_internal_error_fails_safely():
    class ExplodingVerifier:
        async def verify(self, request, outputs):
            raise RuntimeError("secret internal detail")

    h = Harness([two_step_plan()], script={"w1": [GOOD]}, verifier=ExplodingVerifier())
    result = await h.supervisor.start(start())
    assert result.status is S.failed and "secret internal detail" not in result.summary


async def test_telemetry_failure_does_not_fail_task():
    class BrokenSink:
        def write(self, event):
            raise OSError("event store down")

    h = Harness([two_step_plan()], script={"w1": [GOOD]}, sinks=[BrokenSink()])
    assert (await h.supervisor.start(start())).status is S.done
    assert h.supervisor.obs.sink_failures > 0


# 011 R1: every lifecycle transition emits a structured event
async def test_every_status_change_has_an_event():
    h = Harness([two_step_plan()], script={"w1": [BAD, GOOD]})
    result = await h.supervisor.start(start())
    status_patches = [p for entry in h.supervisor.store.history(result.task_id) for p in entry.patches
                      if p.path == "status"]
    assert len(status_patches) == len(h.events(result.task_id, "status_changed"))
    types = {e.type.value for e in h.events(result.task_id)}
    assert {"task_created", "plan_created", "route_selected", "tool_called", "verification_completed",
            "retry_scheduled", "task_finished"} <= types


# PROJECT.md: providers can be swapped without changing supervisor behavior
@pytest.mark.parametrize("adapter_cls", [ScriptedAdapter, ScriptedChatAdapter])
async def test_provider_swap_keeps_behavior(adapter_cls):
    adapter = adapter_cls("scripted", {"w1": [BAD, GOOD]})
    h = Harness([two_step_plan()], adapters=[adapter])
    result = await h.supervisor.start(start())
    assert result.status is S.done and result.output == GOOD["output"]
    assert h.statuses(result.task_id) == ["created", "planning", "executing", "verifying", "executing", "verifying",
                                          "executing", "verifying", "done"]


# 000 AC Privacy Boundary / 001 security: no hidden reasoning or secrets anywhere
async def test_no_hidden_reasoning_or_secrets_leak_anywhere():
    secret = "sk-" + "a" * 30
    script = {"w1": [{"output": f"budget under plan, key {secret}", "reasoning": REASONING_MARKER,
                      "structured": None}]}
    h = Harness([two_step_plan(must_contain="budget")], script=script)
    result = await h.supervisor.start(start())
    state = h.supervisor.store.get(result.task_id)
    blobs = [result.model_dump_json(), state.model_dump_json(),
             *[e.model_dump_json() for e in h.events(result.task_id)],
             *[entry.model_dump_json() for entry in h.supervisor.store.history(result.task_id)]]
    for blob in blobs:
        assert REASONING_MARKER not in blob and secret not in blob and '"reasoning"' not in blob


# 010 AC Separate State: the supervisor has no Memory dependency, so nothing is written to Memory
def test_supervisor_does_not_depend_on_memory():
    tree = ast.parse(inspect.getsource(supervisor_module))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "galliani.memory" not in imported


# Decision 0013: clarification resume
async def test_clarify_missing_constraint_then_plan_and_finish():
    h = Harness([two_step_plan()], script={"w1": [GOOD]}, required_constraints=["audience"])
    paused = await h.supervisor.start(start())
    result = await h.supervisor.clarify(paused.task_id, "", constraints={"audience": "execs"})
    assert result.status is S.done
    state = h.supervisor.store.get(result.task_id)
    assert state.constraints == {"audience": "execs"} and state.objective.goal == "Summarize note n1"
    assert h.statuses(result.task_id)[:4] == ["created", "planning", "waiting_for_user", "planning"]


async def test_clarify_after_inconclusive_verification_revises_plan():
    vague = {"steps": [summarize_step(refs=())]}
    vague["steps"][0]["verification_criteria"] = [{"kind": "semantic", "value": "good enough"}]
    concrete = {"steps": [summarize_step(refs=())]}
    h = Harness([vague, concrete], script={"w1": [GOOD, GOOD]})
    paused = await h.supervisor.start(start())
    assert paused.status is S.waiting_for_user
    result = await h.supervisor.clarify(paused.task_id, "It must mention the budget.")
    assert result.status is S.done
    state = h.supervisor.store.get(result.task_id)
    assert state.plan.version == 2 and state.clarifications == ["It must mention the budget."]
    assert "replanning" in h.statuses(result.task_id)


async def test_clarify_requires_open_question_and_respects_replan_budget():
    from galliani.replanning import RetryPolicy

    h = Harness([two_step_plan()], script={"w1": [GOOD]})
    done = await h.supervisor.start(start())
    with pytest.raises(ContractError):
        await h.supervisor.clarify(done.task_id, "anything")

    vague = {"steps": [summarize_step(refs=())]}
    vague["steps"][0]["verification_criteria"] = [{"kind": "semantic", "value": "good enough"}]
    h = Harness([vague], script={"w1": [GOOD]}, retry=RetryPolicy(max_replans=0))
    paused = await h.supervisor.start(start())
    result = await h.supervisor.clarify(paused.task_id, "be specific")
    assert result.status is S.failed and "replan budget" in result.summary


async def test_question_during_replanning_pauses_and_resumes_without_charging_budget():
    plan = two_step_plan(on_fail="replan")
    h = Harness([plan, {"clarify": "Should the summary mention cloud costs?"}, two_step_plan()],
                script={"w1": [BAD, GOOD]})
    paused = await h.supervisor.start(start())
    assert paused.status is S.waiting_for_user and "cloud costs" in paused.clarification
    assert h.supervisor.store.get(paused.task_id).replan_count == 0  # no revision happened yet
    result = await h.supervisor.clarify(paused.task_id, "No, budget only.")
    assert result.status is S.done
    state = h.supervisor.store.get(result.task_id)
    assert state.replan_count == 1 and state.plan.version == 2


# 009 R3: costly actions need explicit approval -> per-task spending cap
def three_model_steps() -> dict:
    return {"steps": [summarize_step(step_id=f"s{i}", refs=()) for i in range(3)]}


PRICEY = {**GOOD, "cost_micro_usd": 6_000}  # $0.006 per call


async def test_spending_cap_pauses_and_approval_extends_it():
    h = Harness([three_model_steps()], script={"w1": [PRICEY] * 3}, limits=LoopLimits(max_cost_usd=0.01))
    paused = await h.supervisor.start(start())
    assert paused.status is S.waiting_for_user
    assert paused.approval_prompt.scope == "budget/1" and "$0.0120" in paused.approval_prompt.action_summary
    assert paused.usage["calls"] == 2 and paused.usage["cost_micro_usd"] == 12_000
    result = await h.supervisor.approve(paused.task_id)
    assert result.status is S.done and result.usage["calls"] == 3
    state = h.supervisor.store.get(result.task_id)
    assert [a.action for a in state.approvals] == ["extend_budget:1"] and state.retry_counts == {}


async def test_denied_budget_extension_blocks():
    h = Harness([three_model_steps()], script={"w1": [PRICEY] * 3}, limits=LoopLimits(max_cost_usd=0.01))
    paused = await h.supervisor.start(start())
    result = await h.supervisor.deny(paused.task_id)
    assert result.status is S.blocked and len(h.adapter.calls) == 2


async def test_policy_may_preallow_costly_actions_and_no_cap_means_no_check():
    policy = PermissionPolicy(rules={**PermissionPolicy().rules, PermissionLevel.costly: PermissionStatus.allowed})
    h = Harness([three_model_steps()], script={"w1": [PRICEY] * 3}, limits=LoopLimits(max_cost_usd=0.01), policy=policy)
    assert (await h.supervisor.start(start())).status is S.done
    h = Harness([three_model_steps()], script={"w1": [PRICEY] * 3})
    result = await h.supervisor.start(start())
    assert result.status is S.done and result.usage["cost_micro_usd"] == 18_000
