# 012 - Desktop UI

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0018).

        ## Goal

        Define the desktop experience for starting, monitoring, approving, and reviewing Galliani tasks.

        ## Non-goals

        - Building a full visual design system.
- Exposing internal hidden reasoning.
- Replacing developer documentation.

        ## Requirements

        1. The UI must let the user submit an objective.
2. The UI must show task status, plan steps, observations, approvals, verification, and final result.
3. The UI must clearly request permission when needed.
4. The UI must show public rationales without chain-of-thought.
5. The UI must distinguish Task State from durable Memory.

        ## Behavior

        - A user starts a task from an objective input.
- The task view updates as lifecycle events arrive.
- Approval prompts pause the task until answered.
- Final results include verification status and artifacts.

        ## Interfaces and Data Contracts

        - `TaskViewModel`: task_id, status, objective_summary, plan, current_step, observations, approvals, verification, result.
- `ApprovalPrompt`: prompt_id, action_summary, risk_summary, allowed_choices, scope.
- `EventFeedItem`: timestamp, type, public_summary, refs.
- `MemoryIndicator`: record_id, summary, provenance, sensitivity.

        ## Error Handling

        - Disconnected event stream shows stale state and retry option.
- Permission denial explains that execution is blocked.
- Failed tasks show safe error summaries and next options.

        ## Security

        - The UI must not display hidden reasoning.
- Sensitive observations must be redacted or collapsed.
- Approval prompts must describe scope before the user consents.

        ## Acceptance Criteria

        ### Start Task

Given the user enters an objective

When they submit it

Then a task view opens with created or planning status.

### Approval

Given a restricted tool is needed

When the task reaches the permission boundary

Then the UI shows a clear approval prompt and pauses execution.

### Done

Given verification passes

When the task completes

Then the UI shows final result, verification summary, and artifacts.

        ## Tests

        - View-model unit tests.
- UI integration tests for lifecycle states.
- Accessibility checks for approval prompts.

        ## Evaluation

        - Task comprehension review.
- Approval prompt clarity review.
- No hidden reasoning visible in UI snapshots.

        ## Implementation Tasks

        - [x] Define task view model.
- [x] Define approval prompt model.
- [x] Map lifecycle events to UI feed items.
- [x] Design final result and verification display.

        ## Dependencies

        Depends on `001-agent-core`, `002-task-state`, `009-permissions`, and `011-observability`.
