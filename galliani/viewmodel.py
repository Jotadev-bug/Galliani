"""Spec 012 contracts: what a UI may show about a task.

Every view is built from `TaskState.for_display()` (sensitive observations and their outputs redacted,
hidden reasoning dropped) and from already-redacted lifecycle events. A UI therefore cannot show
hidden reasoning (012 R4, security) and only ever sees public summaries and rationales.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from galliani.contracts import Sensitivity
from galliani.memory import MemoryRecord
from galliani.observability import LifecycleEvent
from galliani.permissions import ApprovalPrompt
from galliani.state import TERMINAL_STATUSES, TaskState, TaskStatus

S = TaskStatus

STATUS_LABELS = {
    S.created: "Starting",
    S.planning: "Planning",
    S.executing: "Working",
    S.verifying: "Checking the result",
    S.replanning: "Revising the plan",
    S.waiting_for_user: "Needs your input",
    S.done: "Done",
    S.blocked: "Blocked",
    S.failed: "Failed",
    S.canceled: "Canceled",
}
MEMORY_NOTE = ("Nothing from this task was saved to long-term memory. Everything shown here is this task's "
               "working state and is discarded when the app closes.")
MEMORY_SAVED_NOTE = ("Only the notes listed as saved were written to long-term memory, each with your approval. "
                     "Everything else here is this task's working state and is discarded when the app closes.")

StepState = Literal["pending", "running", "waiting", "verified", "failed", "canceled"]


class StepView(BaseModel):
    step_id: str
    kind: str
    purpose: str
    capability: str
    state: StepState
    attempts: int


class PlanView(BaseModel):
    version: int
    steps: list[StepView]
    revision_reason: str | None = None


class ObservationView(BaseModel):
    id: str
    step_id: str | None
    kind: str
    outcome: str
    summary: str  # "[redacted]" for sensitive observations (012 security: redacted or collapsed)
    sensitive: bool
    timestamp: datetime


class ApprovalView(BaseModel):
    action: str
    scope: str
    status: str
    summary: str


class VerificationView(BaseModel):
    status: str
    reason_summary: str
    satisfied: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    final: bool


class ResultView(BaseModel):
    status: TaskStatus
    summary: str
    output: Any = None
    output_kind: Literal["text", "json"] | None = None
    artifacts: list[dict[str, str]] = Field(default_factory=list)
    verification: VerificationView | None = None
    # When the final output is a tool record (e.g. a file write), the last model-written text, so the
    # user sees the content and not only {"path": ..., "bytes": ...}.
    preview: str | None = None


class MemoryIndicator(BaseModel):
    """012 `MemoryIndicator`: one durable memory record a task wrote. Always empty until spec 010 ships."""

    record_id: str
    summary: str
    provenance: str
    sensitivity: Sensitivity


class MemoryView(BaseModel):
    records: list[MemoryIndicator] = Field(default_factory=list)  # written to durable memory by this task
    used: list[MemoryIndicator] = Field(default_factory=list)  # retrieved as context before planning
    note: str = MEMORY_NOTE


class EventFeedItem(BaseModel):
    """012 `EventFeedItem`: timestamp, type, public_summary, refs (plus a sequence number for polling)."""

    seq: int
    timestamp: datetime
    type: str
    public_summary: str
    refs: dict[str, str] = Field(default_factory=dict)


class TaskViewModel(BaseModel):
    """012 `TaskViewModel`, with the pause details and next options a UI needs."""

    task_id: str
    status: TaskStatus
    status_label: str
    terminal: bool
    objective_summary: str
    plan: PlanView | None = None
    current_step: str | None = None
    observations: list[ObservationView] = Field(default_factory=list)
    approvals: list[ApprovalView] = Field(default_factory=list)
    verification: VerificationView | None = None
    result: ResultView | None = None
    approval_prompt: ApprovalPrompt | None = None
    clarification: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    memory: MemoryView = Field(default_factory=MemoryView)
    next_options: list[str] = Field(default_factory=list)
    updated_at: datetime


def _step_state(index: int, current: int, status: TaskStatus) -> StepState:
    if status is S.done or index < current:
        return "verified"
    if index > current:
        return "pending"
    return {
        S.executing: "running", S.verifying: "running", S.replanning: "running",
        S.waiting_for_user: "waiting", S.failed: "failed", S.blocked: "failed", S.canceled: "canceled",
    }.get(status, "pending")


def _next_options(state: TaskState) -> list[str]:
    if state.status is S.waiting_for_user:
        return ["approve", "deny", "cancel"] if state.pending_permission else ["answer", "cancel"]
    if state.status is S.done:
        return ["new_task"]
    if state.status in (S.failed, S.blocked, S.canceled):
        return ["retry", "edit_and_retry", "new_task"]
    return ["cancel"]


def _memory_view(state: TaskState, data: dict[str, Any], used: Iterable[MemoryRecord]) -> MemoryView:
    written = []
    for obs in data["observations"]:
        if obs["source"] == "tool:remember" and obs["outcome"] == "succeeded" and obs.get("data_ref"):
            out = data["outputs"].get(obs["data_ref"])
            if isinstance(out, dict) and "id" in out:
                written.append(MemoryIndicator(record_id=out["id"], summary=out["content"],
                                               provenance=out["provenance"], sensitivity=out["sensitivity"]))
    used_views = [MemoryIndicator(record_id=r.id, summary=r.display_content(), provenance=r.provenance,
                                  sensitivity=r.sensitivity) for r in used]
    return MemoryView(records=written, used=used_views, note=MEMORY_SAVED_NOTE if written else MEMORY_NOTE)


def build_task_view(
    state: TaskState, *, artifacts: Iterable[dict[str, str]] = (), usage: dict[str, int] | None = None,
    memory_used: Iterable[MemoryRecord] = (),
) -> TaskViewModel:
    data = state.for_display()  # redacted copy: the only source of displayed content
    observations = [
        ObservationView(id=o["id"], step_id=o.get("step_id"), kind=o["kind"], outcome=o["outcome"],
                        summary=o["summary"], sensitive=o["sensitivity"] == Sensitivity.sensitive.value,
                        timestamp=o["timestamp"])
        for o in data["observations"]
    ]

    plan_view = None
    current = None
    if state.plan is not None:
        steps = []
        for i, step in enumerate(state.plan.steps):
            # A permission pause or cancellation is not an attempt: the action did not run.
            attempts = sum(1 for o in state.observations if o.step_id == step.step_id and o.kind == "execution"
                           and o.outcome not in ("blocked", "canceled"))
            steps.append(StepView(step_id=step.step_id, kind=step.kind.value, purpose=step.purpose,
                                  capability=step.required_capability,
                                  state=_step_state(i, state.current_step, state.status), attempts=attempts))
        revision = state.plan.revision.reason if state.plan.revision else None
        plan_view = PlanView(version=state.plan.version, steps=steps, revision_reason=revision)
        step = state.current_plan_step()
        current = step.step_id if step is not None and state.status is not S.done else None

    verification = None
    if state.result is not None and state.result.verification is not None:
        v = state.result.verification
        verification = VerificationView(status=v.status.value, reason_summary=v.reason_summary,
                                        satisfied=v.satisfied_criteria, failed=v.failed_criteria, final=True)
    else:
        last = next((o for o in reversed(observations) if o.kind == "verification"), None)
        if last is not None:
            verification = VerificationView(status=last.outcome, reason_summary=last.summary, final=last.step_id is None)

    result = None
    if state.result is not None:
        output = data["outputs"].get(state.result.output_ref) if state.result.output_ref else None
        kind = None if output is None else "text" if isinstance(output, str) else "json"
        result = ResultView(
            status=state.result.status, summary=data["result"]["summary"], output=output, output_kind=kind,
            artifacts=list(artifacts), verification=verification if state.result.verification else None,
            preview=_model_text_preview(state, data["outputs"]) if kind != "text" else None,
        )

    pending = state.pending_permission
    return TaskViewModel(
        task_id=state.task_id,
        status=state.status,
        status_label=STATUS_LABELS[state.status],
        terminal=state.status in TERMINAL_STATUSES or state.status is S.blocked,
        objective_summary=data["objective"]["goal"][:200],
        plan=plan_view,
        current_step=current,
        observations=observations,
        approvals=[ApprovalView(action=d["action"], scope=d["scope"], status=d["status"], summary=d["audit_summary"])
                   for d in data["permission_decisions"]],
        verification=verification,
        result=result,
        approval_prompt=ApprovalPrompt.model_validate(data["pending_permission"]["prompt"]) if pending else None,
        clarification=data["clarification"] if state.status is S.waiting_for_user else None,
        usage=dict(usage or {}),
        memory=_memory_view(state, data, memory_used),
        next_options=_next_options(state),
        updated_at=state.updated_at,
    )


def _model_text_preview(state: TaskState, outputs: dict[str, Any]) -> str | None:
    if state.plan is None:
        return None
    for step in reversed(state.plan.steps):
        if step.kind.value != "model":
            continue
        ref = state.latest_output_ref(step.step_id)
        text = outputs.get(ref) if ref else None
        if isinstance(text, str) and text.strip():
            return text
    return None


def build_feed(events: Iterable[LifecycleEvent], *, after: int = 0) -> list[EventFeedItem]:
    """Events numbered from 1 in arrival order; only those with seq > `after` are returned."""
    items = []
    for seq, event in enumerate(events, start=1):
        if seq <= after:
            continue
        refs = {k: v for k, v in (("step_id", event.refs.step_id), ("plan_id", event.refs.plan_id),
                                  ("call_id", event.refs.call_id)) if v}
        items.append(EventFeedItem(seq=seq, timestamp=event.timestamp, type=event.type.value,
                                   public_summary=event.public_summary, refs=refs))
    return items
