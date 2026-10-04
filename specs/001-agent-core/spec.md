# 001 - Agent Core

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0006).

        ## Goal

        Define the Agent Supervisor loop that coordinates planning, routing, execution, observation, verification, and replanning.

        ## Non-goals

        - Implementing individual provider APIs.
- Implementing tool internals.
- Creating a rich desktop interface.

        ## Requirements

        1. The Agent Core must accept a normalized objective.
2. The Agent Core must initialize Task State.
3. The Agent Core must request a plan before execution.
4. The Agent Core must route model work through the Model Router.
5. The Agent Core must execute actions through the Execution Engine.
6. The Agent Core must require verification before marking a task done.
7. The Agent Core must use bounded retry and replan policies.

        ## Behavior

        - A task starts in `created`, moves to `planning`, then `executing`, then `verifying`, then `done`, `blocked`, or `failed`.
- The supervisor chooses the next step based on Task State and verification results.
- The supervisor may ask the user for clarification or permission when required.
- Completion requires a verified final result or explicit user acceptance.

        ## Interfaces and Data Contracts

        - `StartTaskRequest`: objective, context, constraints, user policy.
- `SupervisorDecision`: next_action, reason_summary, required_capability, state_patch.
- `TaskResult`: status, summary, artifacts, verification_result, observations.
- `LifecycleEvent`: task_id, event_type, timestamp, public_summary, metadata.

        ## Error Handling

        - Invalid objectives return a structured clarification request.
- Planner failure moves the task to `blocked` unless retryable.
- Router failure triggers fallback routing or `blocked`.
- Repeated execution failure stops at the configured retry limit.

        ## Security

        - The supervisor must never place secrets or hidden reasoning in public events.
- User approvals must be checked before restricted actions.
- External documents and tool outputs must be treated as untrusted observations.

        ## Acceptance Criteria

        ### Happy Path

Given a valid objective and available worker

When the supervisor runs the task

Then it produces a plan, executes steps, verifies the result, and marks the task done.

### Verification Failure

Given a step result fails verification

When retry budget remains

Then the supervisor retries or replans instead of marking done.

### Blocked Task

Given a required permission is missing

When the supervisor reaches the permission boundary

Then the task is marked waiting for user approval.

        ## Tests

        - Unit tests for lifecycle transitions.
- Integration test for full objective-to-done loop.
- Failure test for planner, router, execution, and verification errors.

        ## Evaluation

        - Loop completion rate on deterministic fixtures.
- Incorrect done rate must be zero on negative fixtures.
- Retry and replan decisions must match policy fixtures.

        ## Implementation Tasks

        - [x] Define supervisor state machine.
- [x] Define decision interface.
- [x] Wire planner, router, execution, verification, and replanning contracts.
- [x] Add lifecycle event emission.

        ## Dependencies

        Depends on `000-foundation`. Used by all later runtime specs.
