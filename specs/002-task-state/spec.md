# 002 - Task State

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0006).

        ## Goal

        Define active runtime state for a task without conflating it with durable Memory.

        ## Non-goals

        - Long-term user preference storage.
- Semantic memory retrieval.
- Analytics warehouse design.

        ## Requirements

        1. Task State must represent one active task lifecycle.
2. Task State must contain current objective, plan, step index, observations, approvals, retries, and final status.
3. Task State must not store chain-of-thought.
4. Task State must not become durable Memory by default.
5. Task State updates must be append-friendly and auditable.

        ## Behavior

        - Task State is initialized when a task starts.
- Each supervisor decision applies a state patch.
- Observations are attached to the relevant step.
- Finalization freezes the task status while allowing post-run audit reads.

        ## Interfaces and Data Contracts

        - `TaskState`: task_id, status, objective, constraints, plan, current_step, observations, approvals, retry_counts, result.
- `StatePatch`: operation, path, value, reason_summary.
- `ObservationRecord`: id, source, step_id, summary, data_ref, timestamp, sensitivity.
- `TaskStatus`: created, planning, executing, verifying, replanning, waiting_for_user, done, blocked, failed, canceled.

        ## Error Handling

        - Invalid state transitions are rejected with a contract error.
- Missing task IDs return not found.
- Conflicting updates require optimistic concurrency handling.
- Corrupt state moves the task to `failed` with safe diagnostics.

        ## Security

        - Sensitive observations must be labeled and redacted before display.
- State patches must not contain secrets or hidden reasoning.
- Only approved components may mutate Task State.

        ## Acceptance Criteria

        ### State Creation

Given a valid objective

When a task starts

Then Task State is created with status `created` and no durable Memory write.

### Observation Recording

Given a tool returns a result

When the execution engine records an observation

Then the observation is linked to the current step.

### Invalid Transition

Given a task is `done`

When a component tries to move it to `executing`

Then the transition is rejected.

        ## Tests

        - Unit tests for allowed and denied transitions.
- Contract tests for TaskState serialization.
- Concurrency test for conflicting state patches.

        ## Evaluation

        - State consistency across full-loop fixtures.
- Audit completeness score for lifecycle events.
- Redaction checks for sensitive observations.

        ## Implementation Tasks

        - [x] Define TaskState schema.
- [x] Define status transition table.
- [x] Create state patch validation.
- [x] Add observation and approval records.

        ## Dependencies

        Depends on `000-foundation` and supports `001-agent-core`.
