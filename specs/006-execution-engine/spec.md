# 006 - Execution Engine

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0006).

        ## Goal

        Define how plan steps are executed through Agent Workers and tools.

        ## Non-goals

        - Owning planning policy.
- Owning routing policy.
- Owning final verification policy.

        ## Requirements

        1. The execution engine must execute one plan step at a time.
2. The execution engine must call the Model Router for model steps.
3. The execution engine must call the Tool System for tool steps.
4. The execution engine must emit observations for every attempted action.
5. The execution engine must respect cancellation and retry limits.

        ## Behavior

        - The supervisor provides the current plan step.
- The execution engine dispatches the step to a worker or tool.
- The execution engine captures output, errors, artifacts, and observations.
- The supervisor receives a structured execution result.

        ## Interfaces and Data Contracts

        - `ExecutionRequest`: task_id, step, state_snapshot, limits.
- `ExecutionResult`: step_id, status, output, observation, artifacts, error, route.
- `ExecutionStatus`: succeeded, failed, blocked, canceled, timed_out.
- `ArtifactRef`: artifact_id, kind, uri, sensitivity, produced_by.

        ## Error Handling

        - Worker errors are normalized as execution errors.
- Tool errors are passed through ToolResult normalization.
- Cancellation stops further side effects where possible.
- Partial results are recorded as observations.

        ## Security

        - Execution must not bypass permissions.
- Execution logs must redact secrets.
- Worker output must be treated as untrusted until verified.

        ## Acceptance Criteria

        ### Model Step

Given a plan step requires model work

When execution runs

Then the router selects a worker and the step returns a structured result.

### Tool Step

Given a plan step requires a tool

When execution runs

Then the tool system validates and executes the call.

### Cancellation

Given a task is canceled

When execution checks state

Then no further actions are started.

        ## Tests

        - Unit tests for dispatch by step kind.
- Integration tests for model and tool execution.
- Timeout and cancellation tests.

        ## Evaluation

        - Step execution success rate.
- Observation coverage for attempted actions.
- Unexpected side-effect count must be zero.

        ## Implementation Tasks

        - [ ] Define execution request/result contracts.
- [ ] Implement step dispatch.
- [ ] Integrate routing and tool system.
- [ ] Emit observations and artifacts.

        ## Dependencies

        Depends on `001-agent-core`, `003-model-router`, `005-tool-system`, and `009-permissions`.
