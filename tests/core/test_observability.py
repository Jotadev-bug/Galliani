"""Spec 011 - Observability acceptance criteria."""

from __future__ import annotations

from galliani.observability import EventType, InMemoryEventSink, LifecycleEvent, Observability, derive_metrics


class BrokenSink:
    def write(self, event: LifecycleEvent) -> None:
        raise OSError("disk full")


# AC: Lifecycle Event (schema + stable identifiers)
def test_emit_produces_structured_event_with_refs():
    sink = InMemoryEventSink()
    obs = Observability([sink])
    event = obs.emit(EventType.status_changed, "task_1", "planning -> executing", plan_id="p1", step_id="s1",
                     metadata={"from": "planning", "to": "executing"})
    assert sink.events == [event]
    assert event.event_id.startswith("evt_")
    assert event.refs.task_id == "task_1" and event.refs.plan_id == "p1" and event.refs.step_id == "s1"


# AC: Redaction
def test_sensitive_values_redacted_before_storage():
    sink = InMemoryEventSink()
    Observability([sink]).emit(
        EventType.tool_called, "t", "called with key sk-abcdefghijklmnopqrstuvwx",
        metadata={"api_key": "abc123", "args": {"password": "hunter2", "path": "notes/a.txt"},
                  "auth": "Bearer abcdefghijklmnopqrstuvwxyz", "usage": {"input_tokens": 12}},
    )
    event = sink.events[0]
    assert "sk-" not in event.public_summary
    assert event.metadata["api_key"] == "[redacted]"
    assert event.metadata["args"] == {"password": "[redacted]", "path": "notes/a.txt"}
    assert "abcdefghijklmnop" not in event.metadata["auth"]
    assert event.metadata["usage"] == {"input_tokens": 12}


def test_hidden_reasoning_never_reaches_events():
    sink = InMemoryEventSink()
    Observability([sink]).emit(EventType.route_selected, "t", "selected w1",
                               metadata={"thinking": "secret plan", "nested": {"chain_of_thought": "x", "ok": 1}})
    dumped = sink.events[0].model_dump_json()
    assert "secret plan" not in dumped and "chain_of_thought" not in dumped


# AC: Telemetry Failure
def test_broken_sink_does_not_raise():
    good = InMemoryEventSink()
    obs = Observability([BrokenSink(), good])
    obs.emit(EventType.task_created, "t", "created")
    assert obs.sink_failures == 1
    assert len(good.events) == 1


def test_unredactable_field_dropped_with_safe_diagnostic():
    class Weird:
        def __str__(self):
            raise RuntimeError("boom")

    sink = InMemoryEventSink()
    Observability([sink]).emit(EventType.tool_called, "t", "x", metadata={"ok": 1, "bad": Weird()})
    assert sink.events[0].metadata == {"ok": 1}
    assert sink.events[1].type is EventType.diagnostic


def test_metrics_derived_from_events():
    sink = InMemoryEventSink()
    obs = Observability([sink])
    obs.emit(EventType.retry_scheduled, "t", "retry")
    obs.emit(EventType.task_finished, "t", "done", metadata={"status": "done"})
    metrics = {(m.name, tuple(m.tags.items())): m.value for m in derive_metrics(sink.events)}
    assert metrics[("events.retry_scheduled", ())] == 1
    assert metrics[("tasks.finished", (("status", "done"),))] == 1
