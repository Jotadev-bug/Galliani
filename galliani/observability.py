"""Spec 011 - Observability: structured, redacted lifecycle events and derived metrics.

`Observability.emit` redacts every summary and metadata value before any sink sees it, and a failing
sink never raises into task execution (011 AC Telemetry Failure).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError

from galliani.contracts import new_id, utcnow
from galliani.redaction import DEFAULT_POLICY, RedactionPolicy, redact, redact_text


class EventType(str, Enum):
    task_created = "task_created"
    status_changed = "status_changed"
    plan_created = "plan_created"
    plan_rejected = "plan_rejected"
    plan_revised = "plan_revised"
    route_selected = "route_selected"
    route_fallback = "route_fallback"
    route_failed = "route_failed"
    permission_decided = "permission_decided"
    tool_called = "tool_called"
    step_executed = "step_executed"
    verification_completed = "verification_completed"
    retry_scheduled = "retry_scheduled"
    replan_started = "replan_started"
    approval_recorded = "approval_recorded"
    task_finished = "task_finished"
    diagnostic = "diagnostic"


class TraceContext(BaseModel):
    task_id: str
    plan_id: str | None = None
    step_id: str | None = None
    call_id: str | None = None
    parent_event_id: str | None = None


class LifecycleEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("evt"))
    task_id: str
    type: EventType
    timestamp: datetime = Field(default_factory=utcnow)
    public_summary: str
    refs: TraceContext
    metadata: dict[str, Any] = Field(default_factory=dict)


class Metric(BaseModel):
    name: str
    value: float
    unit: str = "count"
    tags: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utcnow)


class EventSink(Protocol):
    def write(self, event: LifecycleEvent) -> None: ...


class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: list[LifecycleEvent] = []

    def write(self, event: LifecycleEvent) -> None:
        self.events.append(event)

    def for_task(self, task_id: str) -> list[LifecycleEvent]:
        return [e for e in self.events if e.task_id == task_id]


class Observability:
    def __init__(self, sinks: Iterable[EventSink] | None = None, policy: RedactionPolicy = DEFAULT_POLICY):
        self.sinks = list(sinks) if sinks is not None else [InMemoryEventSink()]
        self.policy = policy
        self.sink_failures = 0

    def emit(
        self,
        type: EventType,
        task_id: str,
        public_summary: str,
        *,
        plan_id: str | None = None,
        step_id: str | None = None,
        call_id: str | None = None,
        parent_event_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LifecycleEvent | None:
        diagnostics: list[str] = []
        try:
            clean_meta = redact(metadata or {}, self.policy, diagnostics)
            event = LifecycleEvent(
                task_id=task_id,
                type=type,
                public_summary=redact_text(str(public_summary), self.policy),
                refs=TraceContext(task_id=task_id, plan_id=plan_id, step_id=step_id, call_id=call_id,
                                  parent_event_id=parent_event_id),
                metadata=clean_meta if isinstance(clean_meta, dict) else {},
            )
        except (ValidationError, ValueError, TypeError):
            diagnostics.append(f"malformed {getattr(type, 'value', type)} event dropped")
            event = None
        if event is not None:
            self._write(event)
        for message in diagnostics:
            self._write(LifecycleEvent(task_id=task_id, type=EventType.diagnostic, public_summary=message,
                                       refs=TraceContext(task_id=task_id)))
        return event

    def _write(self, event: LifecycleEvent) -> None:
        for sink in self.sinks:
            try:
                sink.write(event)
            except Exception:  # noqa: BLE001 - telemetry must never fail the task
                self.sink_failures += 1


def derive_metrics(events: Iterable[LifecycleEvent]) -> list[Metric]:
    """Loop-health metrics derived from events (011 behavior: metrics are derived from events)."""
    events = list(events)
    counts = Counter(e.type.value for e in events)
    metrics = [Metric(name=f"events.{name}", value=n) for name, n in sorted(counts.items())]
    finished = [e for e in events if e.type is EventType.task_finished]
    for status, n in sorted(Counter(e.metadata.get("status", "unknown") for e in finished).items()):
        metrics.append(Metric(name="tasks.finished", value=n, tags={"status": str(status)}))
    return metrics
