"""Spec 002 - Task State: active run state for one task, separate from durable Memory.

All mutation goes through `TaskStateStore.apply` with `StatePatch`es:
- status changes are checked against `TRANSITIONS` (Decision 0007);
- values are sanitized (hidden reasoning dropped, secrets masked) before they are stored;
- every applied batch is appended to an audit log (002 R5);
- `expected_version` gives optimistic concurrency;
- a terminal task is frozen; only audit reads remain.
"""

from __future__ import annotations

import copy
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from galliani.contracts import Objective, Sensitivity, new_id, utcnow
from galliani.errors import ConcurrencyConflict, ContractError, InvalidTransition, TaskNotFound
from galliani.permissions import ApprovalPrompt, ApprovalRecord, PermissionDecision, PermissionRequest
from galliani.planner import Plan
from galliani.redaction import REDACTED, redact
from galliani.verification import VerificationResult


class TaskStatus(str, Enum):
    created = "created"
    planning = "planning"
    executing = "executing"
    verifying = "verifying"
    replanning = "replanning"
    waiting_for_user = "waiting_for_user"
    done = "done"
    blocked = "blocked"
    failed = "failed"
    canceled = "canceled"


S = TaskStatus
TERMINAL_STATUSES = frozenset({S.done, S.failed, S.canceled})

TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    S.created: frozenset({S.planning, S.waiting_for_user, S.failed, S.canceled}),
    S.planning: frozenset({S.executing, S.waiting_for_user, S.blocked, S.failed, S.canceled}),
    S.executing: frozenset({S.verifying, S.replanning, S.waiting_for_user, S.blocked, S.failed, S.canceled}),
    S.verifying: frozenset({S.executing, S.replanning, S.done, S.waiting_for_user, S.blocked, S.failed, S.canceled}),
    S.replanning: frozenset({S.executing, S.blocked, S.failed, S.canceled}),
    S.waiting_for_user: frozenset({S.planning, S.executing, S.replanning, S.blocked, S.failed, S.canceled}),
    S.blocked: frozenset({S.failed, S.canceled}),
    S.done: frozenset(),
    S.failed: frozenset(),
    S.canceled: frozenset(),
}


def can_transition(current: TaskStatus, new: TaskStatus) -> bool:
    return new in TRANSITIONS[current]


class ObservationRecord(BaseModel):
    """002 `ObservationRecord`, plus `kind` and `outcome` so observations are filterable."""

    id: str = Field(default_factory=lambda: new_id("obs"))
    source: str  # e.g. "worker:w1", "tool:read_note", "verifier", "supervisor"
    step_id: str | None = None
    kind: Literal["execution", "verification", "permission", "planning", "replanning", "supervisor"]
    outcome: str
    summary: str
    data_ref: str | None = None  # key into TaskState.outputs
    timestamp: datetime = Field(default_factory=utcnow)
    sensitivity: Sensitivity = Sensitivity.internal


class PendingPermission(BaseModel):
    step_id: str
    request: PermissionRequest
    prompt: ApprovalPrompt


class FinalResult(BaseModel):
    status: TaskStatus
    summary: str
    output_ref: str | None = None
    verification: VerificationResult | None = None


class TaskState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    status: TaskStatus = TaskStatus.created
    objective: Objective
    constraints: dict[str, Any] = Field(default_factory=dict)
    plan: Plan | None = None
    plan_history: list[Plan] = Field(default_factory=list)
    current_step: int = 0
    observations: list[ObservationRecord] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    approvals: list[ApprovalRecord] = Field(default_factory=list)
    permission_decisions: list[PermissionDecision] = Field(default_factory=list)
    pending_permission: PendingPermission | None = None
    clarification: str | None = None  # the open question while waiting_for_user
    clarifications: list[str] = Field(default_factory=list)  # user answers received so far
    retry_counts: dict[str, int] = Field(default_factory=dict)
    replan_count: int = 0
    action_count: int = 0
    result: FinalResult | None = None
    version: int = 0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def current_plan_step(self):
        if self.plan is None or self.current_step >= len(self.plan.steps):
            return None
        return self.plan.steps[self.current_step]

    def latest_output_ref(self, step_id: str) -> str | None:
        for obs in reversed(self.observations):
            if obs.step_id == step_id and obs.kind == "execution" and obs.outcome == "succeeded" and obs.data_ref:
                return obs.data_ref
        return None

    def for_display(self) -> dict[str, Any]:
        """A display-safe view: sensitive observations and their outputs are redacted (002 security)."""
        data = redact(self.model_dump(mode="json"))
        sensitive_refs = set()
        for obs in data["observations"]:
            if obs["sensitivity"] == Sensitivity.sensitive.value:
                obs["summary"] = REDACTED
                if obs.get("data_ref"):
                    sensitive_refs.add(obs["data_ref"])
        for ref in sensitive_refs:
            if ref in data["outputs"]:
                data["outputs"][ref] = REDACTED
        return data


class StatePatch(BaseModel):
    """002 `StatePatch`: operation, path, value, reason_summary."""

    operation: Literal["set", "append", "increment", "put"]
    path: str
    value: Any = None
    reason_summary: str = ""


class AppliedPatch(BaseModel):
    version: int
    actor: str
    timestamp: datetime = Field(default_factory=utcnow)
    patches: list[StatePatch]


_SETTABLE = {"status", "plan", "current_step", "pending_permission", "clarification", "constraints", "result"}
_APPENDABLE = {"observations", "approvals", "permission_decisions", "plan_history", "clarifications"}
_COUNTERS = {"replan_count", "action_count"}
_KEYED_COUNTERS = {"retry_counts"}
_KEYED_PUT = {"outputs"}


def set_status(status: TaskStatus, reason: str) -> StatePatch:
    return StatePatch(operation="set", path="status", value=status.value, reason_summary=reason)


class TaskStateStore:
    """In-memory Task State store. Only `writers` may mutate state (002 security)."""

    def __init__(self, writers: frozenset[str] = frozenset({"supervisor"})):
        self.writers = writers
        self._states: dict[str, TaskState] = {}
        self._log: dict[str, list[AppliedPatch]] = {}

    def create(self, objective: Objective, *, task_id: str | None = None) -> TaskState:
        task_id = task_id or new_id("task")
        if task_id in self._states:
            raise ContractError(f"task {task_id} already exists")
        clean = Objective.model_validate(redact(objective))
        state = TaskState(task_id=task_id, objective=clean, constraints=dict(clean.constraints))
        self._states[task_id] = state
        self._log[task_id] = []
        return state.model_copy(deep=True)

    def get(self, task_id: str) -> TaskState:
        try:
            return self._states[task_id].model_copy(deep=True)
        except KeyError:
            raise TaskNotFound(f"task {task_id} not found") from None

    def history(self, task_id: str) -> list[AppliedPatch]:
        if task_id not in self._log:
            raise TaskNotFound(f"task {task_id} not found")
        return copy.deepcopy(self._log[task_id])

    def apply(self, task_id: str, patches: list[StatePatch], *, expected_version: int, actor: str) -> TaskState:
        if actor not in self.writers:
            raise ContractError(f"{actor} may not mutate Task State")
        current = self._states.get(task_id)
        if current is None:
            raise TaskNotFound(f"task {task_id} not found")
        if current.version != expected_version:
            raise ConcurrencyConflict(
                f"task {task_id} is at version {current.version}, patch expected {expected_version}"
            )
        if current.terminal:
            raise InvalidTransition(f"task {task_id} is {current.status.value} and frozen")

        data = current.model_dump(mode="json")
        clean_patches: list[StatePatch] = []
        for patch in patches:
            clean = patch.model_copy(update={"value": redact(patch.value), "reason_summary": redact(patch.reason_summary)})
            self._apply_one(data, clean)
            clean_patches.append(clean)

        data["version"] = current.version + 1
        data["updated_at"] = utcnow().isoformat()
        try:
            new_state = TaskState.model_validate(data)
        except ValidationError as e:
            raise ContractError(f"patch produced an invalid Task State ({e.error_count()} errors)") from None
        self._states[task_id] = new_state
        self._log[task_id].append(AppliedPatch(version=new_state.version, actor=actor, patches=clean_patches))
        return new_state.model_copy(deep=True)

    def force_fail(self, task_id: str, safe_summary: str) -> TaskState:
        """Move a task whose state can no longer be trusted to `failed` (002 corrupt-state handling)."""
        current = self._states.get(task_id)
        if current is None:
            raise TaskNotFound(f"task {task_id} not found")
        if current.terminal:
            return current.model_copy(deep=True)
        failed = current.model_copy(update={
            "status": TaskStatus.failed,
            "result": FinalResult(status=TaskStatus.failed, summary=safe_summary),
            "version": current.version + 1,
            "updated_at": utcnow(),
        })
        self._states[task_id] = failed
        self._log[task_id].append(AppliedPatch(
            version=failed.version, actor="store",
            patches=[set_status(TaskStatus.failed, safe_summary)],
        ))
        return failed.model_copy(deep=True)

    @staticmethod
    def _apply_one(data: dict[str, Any], patch: StatePatch) -> None:
        head, _, key = patch.path.partition(".")
        op = patch.operation
        if op == "set" and patch.path in _SETTABLE:
            if patch.path == "status":
                try:
                    new, cur = TaskStatus(patch.value), TaskStatus(data["status"])
                except ValueError:
                    raise ContractError(f"unknown status {patch.value!r}") from None
                if not can_transition(cur, new):
                    raise InvalidTransition(f"cannot move from {cur.value} to {new.value}")
            data[patch.path] = patch.value
        elif op == "append" and patch.path in _APPENDABLE:
            data[patch.path].append(patch.value)
        elif op == "increment" and patch.path in _COUNTERS:
            data[patch.path] += int(patch.value or 1)
        elif op == "increment" and head in _KEYED_COUNTERS and key:
            data[head][key] = data[head].get(key, 0) + int(patch.value or 1)
        elif op == "put" and head in _KEYED_PUT and key:
            if key in data[head]:
                raise ContractError(f"{patch.path} already exists; outputs are append-only")
            data[head][key] = patch.value
        else:
            raise ContractError(f"operation {op} is not allowed on {patch.path}")
