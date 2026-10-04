"""Spec 004 - model-backed planner: prompt/input contract, untrusted output handling, revision."""

from __future__ import annotations

import json

from galliani.contracts import Objective
from galliani.model_planner import ModelPlanner, extract_json
from galliani.observability import InMemoryEventSink, Observability
from galliani.router import ModelRouter
from galliani.state import TaskStatus
from galliani.supervisor import StartTaskRequest, Supervisor
from galliani.testing import FixtureWorld, ScriptedAdapter, fixture_tool_registry
from galliani.tools import ToolSystem
from galliani.workers import WorkerClient
from tests.core.helpers import read_step, summarize_step, worker

S = TaskStatus
GOOD = {"output": "Q3 budget: spend is 4% under plan."}


def reply(**body) -> dict:
    return {"output": json.dumps({"status": "planned", "reason": "ok", **body})}


PLAN = reply(steps=[read_step(), summarize_step()], success_criteria=[{"kind": "contains", "value": "under plan"}])


class Rig:
    def __init__(self, planner_replies: list[dict], worker_replies: list[dict] | None = None, **planner_kw):
        self.world = FixtureWorld(notes={"n1": "Q3 budget review: spend is 4% under plan."})
        self.adapter = ScriptedAdapter("scripted", {"planner": planner_replies, "w1": worker_replies or [GOOD]})
        router = ModelRouter([worker("w1"), worker("planner", cost="high", caps=("text", "reasoning"))])
        obs = Observability([InMemoryEventSink()])
        tools = fixture_tool_registry(self.world)
        self.supervisor = Supervisor(
            planner=ModelPlanner(WorkerClient(router, [self.adapter], obs), tools, **planner_kw),
            router=router, adapters=[self.adapter], tools=ToolSystem(tools), observability=obs,
        )

    def planner_calls(self):
        return [c for c in self.adapter.calls if c.worker_id == "planner"]

    async def run(self, goal: str = "Summarize note n1"):
        return await self.supervisor.start(StartTaskRequest(objective=Objective(goal=goal)))


def test_extract_json_tolerates_fences_and_text():
    assert extract_json('Here:\n```json\n{"a": {"b": 1}}\n```') == {"a": {"b": 1}}


async def test_model_plan_drives_full_loop():
    rig = Rig([PLAN])
    result = await rig.run()
    assert result.status is S.done
    [call] = rig.planner_calls()
    assert call.inputs["objective"] == "Summarize note n1"
    assert {t["name"] for t in call.inputs["tools"]} >= {"read_note", "delete_file"}
    assert call.inputs["capabilities"] == ["reasoning", "text"]  # tools listed separately
    assert '"status"' in call.instruction and "Never invent tools" in call.instruction


async def test_hidden_reasoning_in_plan_reply_is_discarded():
    body = json.loads(PLAN["output"])
    body["reasoning"] = "SECRET-PLANNER-THOUGHTS"
    body["steps"][0]["thinking"] = "more"
    rig = Rig([{"output": "```json\n" + json.dumps(body) + "\n```"}])
    result = await rig.run()
    assert result.status is S.done
    state = rig.supervisor.store.get(result.task_id)
    assert "SECRET-PLANNER-THOUGHTS" not in state.model_dump_json()


async def test_invalid_reply_gets_one_repair_round_with_errors():
    invented = reply(steps=[{**read_step(), "required_capability": "rm_rf",
                             "tool": {"tool_name": "rm_rf", "arguments": {}}}])
    rig = Rig([{"output": "not json"}, invented, PLAN, PLAN])
    result = await rig.run()
    assert result.status is S.done
    calls = rig.planner_calls()
    assert "not valid JSON" in calls[1].instruction
    # second draft invented a tool -> planner error (retryable) -> supervisor retries the planner once
    assert len(calls) == 3 and "unavailable capability rm_rf" not in calls[2].instruction


async def test_persistently_invalid_plans_block_safely():
    rig = Rig([{"output": "nope"}] * 4)
    result = await rig.run()
    assert result.status is S.blocked and "invalid plan" in result.summary
    assert len(rig.planner_calls()) == 4  # (1 + 1 repair) x (1 + 1 supervisor retry): bounded


async def test_oversized_model_plan_is_rejected():
    big = reply(steps=[summarize_step(step_id=f"s{i}", refs=()) for i in range(6)])
    rig = Rig([big] * 4)
    assert (await rig.run()).status is S.blocked


async def test_clarification_and_cannot_plan_outcomes():
    rig = Rig([{"output": json.dumps({"status": "needs_clarification", "reason": "Which quarter?"})}])
    result = await rig.run()
    assert result.status is S.waiting_for_user and result.clarification == "Which quarter?"
    rig = Rig([{"output": json.dumps({"status": "cannot_plan", "reason": "No tool reaches the ERP."})}])
    result = await rig.run()
    assert result.status is S.blocked and "ERP" in result.summary


async def test_clarification_answer_reaches_the_next_plan():
    rig = Rig([{"output": json.dumps({"status": "needs_clarification", "reason": "Which note?"})}, PLAN])
    paused = await rig.run("Summarize the budget note")
    result = await rig.supervisor.clarify(paused.task_id, "note n1")
    assert result.status is S.done
    assert rig.planner_calls()[1].inputs["clarifications"] == ["note n1"]


async def test_revision_sends_current_plan_failed_step_and_evidence():
    first = json.loads(PLAN["output"])
    first["steps"][1]["verification_criteria"] = [{"kind": "contains", "value": "budget", "on_fail": "replan"}]
    rig = Rig([{"output": json.dumps(first)}, PLAN], worker_replies=[{"output": "Looks fine."}, GOOD])
    result = await rig.run()
    assert result.status is S.done
    revise_call = rig.planner_calls()[1]
    assert "REVISION" in revise_call.instruction
    assert revise_call.inputs["failed_step_id"] == "s1"
    assert revise_call.inputs["current_plan"]["version"] == 1
    assert any("budget" in e for e in revise_call.inputs["evidence"])
    state = rig.supervisor.store.get(result.task_id)
    assert state.plan.version == 2 and rig.world.executed == ["read_note"]


async def test_planner_worker_unavailable_blocks():
    rig = Rig([{"error": "provider_unavailable"}] * 2)
    result = await rig.run()
    assert result.status is S.blocked and "planning" in result.summary
