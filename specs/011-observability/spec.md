# 011 - Observability

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0006).

        ## Goal

        Define events, logs, metrics, and traces that make Galliani auditable without leaking private reasoning or secrets.

        ## Non-goals

        - Full analytics platform implementation.
- Capturing provider-native hidden reasoning.
- Storing raw secrets for debugging.

        ## Requirements

        1. Every lifecycle transition must emit a structured event.
2. Every model route, tool call, verification result, and replan must be observable.
3. Events must include public summaries and stable identifiers.
4. Sensitive fields must be redacted.
5. Observability must not expose chain-of-thought.

        ## Behavior

        - Components emit events through a shared observability interface.
- Events are correlated by task_id, plan_id, step_id, and call_id where available.
- Metrics are derived from events.
- Debug detail is bounded and redacted.

        ## Interfaces and Data Contracts

        - `LifecycleEvent`: event_id, task_id, type, timestamp, public_summary, refs, metadata.
- `Metric`: name, value, unit, tags, timestamp.
- `TraceContext`: task_id, plan_id, step_id, parent_event_id.
- `RedactionPolicy`: field_patterns, sensitivity_labels, action.

        ## Error Handling

        - Telemetry failure must not crash task execution.
- Malformed events are rejected or sanitized.
- Redaction failure drops the sensitive field and emits a safe diagnostic.

        ## Security

        - No secrets in logs.
- No hidden reasoning in events.
- User-visible audit entries must be understandable and minimal.

        ## Acceptance Criteria

        ### Lifecycle Event

Given a task changes status

When the transition occurs

Then a structured event is emitted.

### Redaction

Given an event contains a sensitive field

When observability processes it

Then the sensitive value is redacted before storage.

### Telemetry Failure

Given event storage is unavailable

When execution continues

Then the task is not failed solely because telemetry failed.

        ## Tests

        - Unit tests for event schema validation.
- Redaction tests with secret fixtures.
- Integration tests for event emission across the full loop.

        ## Evaluation

        - Event coverage per task.
- Redaction success rate.
- Hidden reasoning leak count must be zero.

        ## Implementation Tasks

        - [ ] Define event schema.
- [ ] Define redaction policy.
- [ ] Instrument supervisor, router, tools, verifier, and replanner.
- [ ] Add metrics for v0.1 loop health.

        ## Dependencies

        Depends on all runtime specs, especially `001-agent-core` and `002-task-state`.
