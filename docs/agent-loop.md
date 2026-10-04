# Agent Loop

The v0.1 loop is intentionally small and explicit.

```text
objective -> plan -> routing -> action/tool -> observation -> verification -> replan/retry -> done
```

## Step 1: Objective

The user provides a goal. The supervisor normalizes it into a task with constraints, context, and completion expectations.

## Step 2: Plan

The planner creates ordered steps. Each step must have a purpose, inputs, expected outputs, and verification criteria.

## Step 3: Routing

The model router selects an Agent Worker for model work or identifies that a tool execution is required.

## Step 4: Action or Tool

The execution engine runs the selected action. Model calls and tool calls both return structured results.

## Step 5: Observation

The supervisor records what happened in Task State as an observation. Observations are runtime evidence, not durable memory by default.

## Step 6: Verification

The verifier checks whether the step or task is complete.

## Step 7: Replan or Retry

If verification fails, the supervisor may retry, adjust the plan, ask the user, or stop safely.

## Step 8: Done

A task can be marked done only after verification passes or the user explicitly accepts the result.

## Loop Limits

v0.1 should include clear maximums for retries, replans, tool failures, and total steps to avoid uncontrolled execution.

Implemented defaults (Decision 0008): `max_retries_per_step=1`, `max_replans=1`, `max_plan_steps=5`, `max_total_actions=10`. Every loop iteration either consumes one action or moves the task to a pausing or terminal status, so the loop always terminates.

## Implementation (v0.1)

The loop lives in `galliani/supervisor.py`. Each loop stage maps to one module:

| Loop stage | Module | Spec |
|---|---|---|
| objective, lifecycle | `supervisor.py`, `state.py` | 001, 002 |
| plan | `planner.py` (`StaticPlanner`, `validate_plan`) | 004 |
| routing | `router.py`, `adapters.py` | 003 |
| action/tool | `execution.py`, `tools.py`, `permissions.py` | 006, 005, 009 |
| observation | `ObservationRecord` in `state.py`, events in `observability.py` | 002, 011 |
| verification | `verification.py` | 007 |
| replan/retry | `replanning.py` | 008 |

Lifecycle (Decision 0007): `created -> planning -> executing -> verifying -> (executing | replanning | done)`. A missing approval or clarification pauses the task in `waiting_for_user`; `Supervisor.approve` / `Supervisor.deny` resume or block it. `done`, `failed`, and `canceled` are terminal.

Two planners implement the same `Planner` protocol: `StaticPlanner` (deterministic fixtures) and `ModelPlanner` (an Agent Worker drafts JSON; the supervisor validates it). Semantic criteria can be judged by `ModelSemanticVerifier`. Deterministic criteria always run without a model.

A task paused for clarification resumes with `Supervisor.clarify` (Decision 0013): it re-plans if no plan exists yet, and otherwise revises the current plan.

A retry re-runs the same step. A replan installs a new plan version and resumes after the already verified, unchanged steps, so completed side effects are not repeated.
