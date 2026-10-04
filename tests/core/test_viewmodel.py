"""Spec 012 - view-model unit tests."""

from __future__ import annotations

from galliani.contracts import Sensitivity
from galliani.observability import EventType, InMemoryEventSink, Observability
from galliani.state import ObservationRecord, StatePatch, TaskStatus
from galliani.viewmodel import MEMORY_NOTE, build_feed, build_task_view
from tests.core.helpers import Harness, read_step, summarize_step, tool_step
from tests.core.test_supervisor import GOOD, start, two_step_plan

S = TaskStatus


async def test_done_view_has_result_verification_steps_and_memory_indicator():
    h = Harness([two_step_plan()], script={"w1": [GOOD]})
    result = await h.supervisor.start(start())
    view = build_task_view(h.supervisor.store.get(result.task_id), usage=result.usage)
    assert view.status is S.done and view.status_label == "Done" and view.terminal
    assert [s.state for s in view.plan.steps] == ["verified", "verified"]
    assert view.result.output == GOOD["output"] and view.result.output_kind == "text"
    assert view.result.verification.status == "pass" and view.result.verification.final
    assert view.memory.records == [] and view.memory.note == MEMORY_NOTE  # Task State, not Memory (012 R5)
    assert view.next_options == ["new_task"] and view.current_step is None


async def test_waiting_view_carries_the_approval_prompt_and_step_states():
    h = Harness([{"steps": [read_step(), tool_step("d", "delete_file", path="a.txt")]}])
    result = await h.supervisor.start(start())
    view = build_task_view(h.supervisor.store.get(result.task_id))
    assert view.status_label == "Needs your input" and not view.terminal
    assert view.approval_prompt.scope == "a.txt" and view.next_options == ["approve", "deny", "cancel"]
    assert [s.state for s in view.plan.steps] == ["verified", "waiting"] and view.current_step == "d"
    assert view.approvals[-1].status == "needs_user"


async def test_failed_view_shows_safe_summary_and_next_options():
    h = Harness([two_step_plan(), two_step_plan()], script={"w1": [{"output": "nope"}] * 10})
    result = await h.supervisor.start(start())
    view = build_task_view(h.supervisor.store.get(result.task_id))
    assert view.status is S.failed and view.result.summary and view.result.verification is None
    assert view.verification is not None and view.verification.status == "fail"
    assert [s.state for s in view.plan.steps][-1] == "failed"
    assert view.next_options == ["retry", "edit_and_retry", "new_task"]


async def test_sensitive_observations_are_collapsed_and_reasoning_never_shown():
    h = Harness([{"steps": [summarize_step(refs=())]}],
                script={"w1": [{"output": "budget under plan", "reasoning": "PRIVATE-THOUGHT"}]})
    result = await h.supervisor.start(start())
    store = h.supervisor.store
    state = store.get(result.task_id)
    # a sensitive observation added to a fresh task, then viewed
    fresh = store.create(state.objective)
    fresh = store.apply(fresh.task_id, [
        StatePatch(operation="put", path="outputs.r1", value="medical record"),
        StatePatch(operation="append", path="observations", value=ObservationRecord(
            source="tool:x", step_id="s1", kind="execution", outcome="succeeded", summary="patient X record",
            data_ref="r1", sensitivity=Sensitivity.sensitive)),
    ], expected_version=0, actor="supervisor")
    view = build_task_view(fresh)
    assert view.observations[0].summary == "[redacted]" and view.observations[0].sensitive
    assert "PRIVATE-THOUGHT" not in build_task_view(state).model_dump_json()


def test_feed_numbers_events_and_filters_by_seq():
    sink = InMemoryEventSink()
    obs = Observability([sink])
    for i in range(3):
        obs.emit(EventType.tool_called, "t", f"call {i}", step_id="s1")
    feed = build_feed(sink.events, after=1)
    assert [f.seq for f in feed] == [2, 3] and feed[0].refs == {"step_id": "s1"}
    assert feed[0].public_summary == "call 1"


async def test_result_preview_shows_model_text_when_final_output_is_a_tool_record():
    from galliani.permissions import PermissionLevel, PermissionPolicy, PermissionStatus

    policy = PermissionPolicy(rules={**PermissionPolicy().rules, PermissionLevel.write: PermissionStatus.allowed})
    plan = {"steps": [summarize_step(step_id="s1", refs=()),
                      tool_step("w", "write_file", path="out.md", content={"$ref": "s1"})]}
    h = Harness([plan], script={"w1": [GOOD]}, policy=policy)
    result = await h.supervisor.start(start())
    view = build_task_view(h.supervisor.store.get(result.task_id))
    assert view.result.output_kind == "json" and view.result.preview == GOOD["output"]


async def test_permission_pause_is_not_counted_as_an_attempt():
    h = Harness([{"steps": [tool_step("d", "delete_file", path="a.txt")]}])
    h.world.files["a.txt"] = "x"
    paused = await h.supervisor.start(start())
    assert build_task_view(h.supervisor.store.get(paused.task_id)).plan.steps[0].attempts == 0
    done = await h.supervisor.approve(paused.task_id)
    assert build_task_view(h.supervisor.store.get(done.task_id)).plan.steps[0].attempts == 1
