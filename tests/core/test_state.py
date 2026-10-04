"""Spec 002 - Task State acceptance criteria and contract tests."""

from __future__ import annotations

import pytest

from galliani.contracts import Objective, Sensitivity
from galliani.errors import ConcurrencyConflict, ContractError, InvalidTransition, TaskNotFound
from galliani.state import (
    TERMINAL_STATUSES,
    TRANSITIONS,
    ObservationRecord,
    StatePatch,
    TaskState,
    TaskStateStore,
    TaskStatus,
    set_status,
)

S = TaskStatus


def make() -> tuple[TaskStateStore, TaskState]:
    store = TaskStateStore()
    return store, store.create(Objective(goal="summarize the note", constraints={"lang": "en"}))


def move(store: TaskStateStore, state: TaskState, *statuses: TaskStatus) -> TaskState:
    for status in statuses:
        state = store.apply(state.task_id, [set_status(status, "test")], expected_version=state.version, actor="supervisor")
    return state


# AC: State Creation
def test_task_state_created_with_status_created_and_no_memory_fields():
    store, state = make()
    assert state.status is S.created
    assert state.constraints == {"lang": "en"}
    assert not any("memory" in name for name in TaskState.model_fields)  # 002 R4: not durable Memory


# AC: Invalid Transition
def test_done_task_cannot_move_to_executing():
    store, state = make()
    state = move(store, state, S.planning, S.executing, S.verifying, S.done)
    with pytest.raises(InvalidTransition):
        move(store, state, S.executing)


@pytest.mark.parametrize("current,new", [(S.created, S.executing), (S.planning, S.done), (S.blocked, S.executing)])
def test_denied_transitions(current, new):
    assert new not in TRANSITIONS[current]


def test_terminal_states_have_no_exits_and_task_is_frozen():
    assert all(not TRANSITIONS[s] for s in TERMINAL_STATUSES)
    store, state = make()
    state = move(store, state, S.canceled)
    with pytest.raises(InvalidTransition):
        store.apply(state.task_id, [StatePatch(operation="increment", path="action_count")],
                    expected_version=state.version, actor="supervisor")
    assert store.get(state.task_id).status is S.canceled  # post-run audit reads still work


# AC: Observation Recording
def test_observation_is_linked_to_its_step():
    store, state = make()
    obs = ObservationRecord(source="tool:read_note", step_id="s1", kind="execution", outcome="succeeded",
                            summary="read 1 note", data_ref="out:s1:1")
    state = store.apply(state.task_id, [
        StatePatch(operation="put", path="outputs.out:s1:1", value="note text"),
        StatePatch(operation="append", path="observations", value=obs),
    ], expected_version=state.version, actor="supervisor")
    assert state.observations[0].step_id == "s1"
    assert state.latest_output_ref("s1") == "out:s1:1"


def test_conflicting_patches_are_rejected():
    store, state = make()
    store.apply(state.task_id, [set_status(S.planning, "a")], expected_version=0, actor="supervisor")
    with pytest.raises(ConcurrencyConflict):
        store.apply(state.task_id, [set_status(S.canceled, "b")], expected_version=0, actor="supervisor")


def test_patch_log_is_append_only_and_auditable():
    store, state = make()
    move(store, state, S.planning, S.executing)
    log = store.history(state.task_id)
    assert [entry.version for entry in log] == [1, 2]
    assert log[1].patches[0].value == "executing"


def test_only_approved_writers_mutate_state():
    store, state = make()
    with pytest.raises(ContractError):
        store.apply(state.task_id, [set_status(S.planning, "x")], expected_version=0, actor="worker")


def test_disallowed_path_and_output_overwrite_rejected():
    store, state = make()
    with pytest.raises(ContractError):
        store.apply(state.task_id, [StatePatch(operation="set", path="task_id", value="x")],
                    expected_version=0, actor="supervisor")
    state = store.apply(state.task_id, [StatePatch(operation="put", path="outputs.r1", value=1)],
                        expected_version=0, actor="supervisor")
    with pytest.raises(ContractError):
        store.apply(state.task_id, [StatePatch(operation="put", path="outputs.r1", value=2)],
                    expected_version=state.version, actor="supervisor")


def test_missing_task_is_not_found():
    with pytest.raises(TaskNotFound):
        TaskStateStore().get("nope")


def test_patch_values_drop_hidden_reasoning_and_mask_secrets():
    store, state = make()
    state = store.apply(state.task_id, [StatePatch(
        operation="put", path="outputs.r1",
        value={"answer": "42", "reasoning": "private chain of thought", "api_key": "abc", "note": "key sk-abcdefghijklmnopqrstuv"},
    )], expected_version=0, actor="supervisor")
    assert state.outputs["r1"] == {"answer": "42", "api_key": "[redacted]", "note": "key [redacted]"}


def test_serialization_round_trip():
    store, state = make()
    state = move(store, state, S.planning)
    assert TaskState.model_validate_json(state.model_dump_json()) == state


def test_sensitive_observations_are_redacted_for_display():
    store, state = make()
    obs = ObservationRecord(source="tool:x", step_id="s1", kind="execution", outcome="succeeded",
                            summary="patient record", data_ref="r1", sensitivity=Sensitivity.sensitive)
    state = store.apply(state.task_id, [
        StatePatch(operation="put", path="outputs.r1", value="private data"),
        StatePatch(operation="append", path="observations", value=obs),
    ], expected_version=0, actor="supervisor")
    view = state.for_display()
    assert view["observations"][0]["summary"] == "[redacted]"
    assert view["outputs"]["r1"] == "[redacted]"


def test_force_fail_moves_corrupt_task_to_failed():
    store, state = make()
    failed = store.force_fail(state.task_id, "internal error")
    assert failed.status is S.failed and failed.result.summary == "internal error"
