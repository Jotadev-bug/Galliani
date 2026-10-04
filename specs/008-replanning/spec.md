# 008 - Replanning

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0006).

        ## Goal

        Define bounded retry and replanning behavior when execution or verification does not satisfy the objective.

        ## Non-goals

        - Unlimited autonomous loops.
- Complex multi-day planning.
- Changing user objectives without confirmation.

        ## Requirements

        1. Replanning must be triggered by explicit failure signals.
2. Replanning must preserve the original objective unless the user changes it.
3. Retries and replans must be bounded.
4. Each replan must record a public reason summary.
5. Replanning must update Task State with a new plan version.

        ## Behavior

        - The supervisor receives a failure or inconclusive verification result.
- Retry policy decides whether to retry the same step.
- If retry is not appropriate, replanning produces a revised plan.
- If no safe path remains, the task becomes blocked or failed.

        ## Interfaces and Data Contracts

        - `ReplanRequest`: task_id, current_plan, failed_step, evidence, constraints, budgets.
- `ReplanResult`: status, revised_plan, reason_summary, retry_decision.
- `RetryPolicy`: max_retries_per_step, max_replans, retryable_errors.
- `ReplanStatus`: retry, revised, blocked, failed.

        ## Error Handling

        - Retry budget exhaustion prevents further retries.
- Replan budget exhaustion blocks or fails the task.
- Conflicting user constraints require user clarification.

        ## Security

        - Replanning must not weaken permission requirements.
- Replanning must not hide failed actions.
- Replanning summaries must not include chain-of-thought.

        ## Acceptance Criteria

        ### Retry

Given a retryable tool timeout occurs

When retry budget remains

Then the supervisor retries the step and records the retry.

### Replan

Given verification fails due to a bad approach

When replanning runs

Then a revised plan version is created.

### Stop

Given all budgets are exhausted

When another failure occurs

Then the task is marked blocked or failed with a safe summary.

        ## Tests

        - Unit tests for retry budget logic.
- Integration tests for failed verification to replan.
- Tests for budget exhaustion behavior.

        ## Evaluation

        - Replan success rate.
- Average replans per task.
- Unbounded loop count must be zero.

        ## Implementation Tasks

        - [x] Define retry policy.
- [x] Define replan contracts.
- [x] Integrate verification recommendations.
- [x] Add plan versioning behavior.

        ## Dependencies

        Depends on `004-planner`, `007-verification`, and `002-task-state`.
