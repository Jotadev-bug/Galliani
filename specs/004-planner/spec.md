# 004 - Planner

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0006).

        ## Goal

        Define how Galliani converts a user objective into a verifiable plan.

        ## Non-goals

        - Long-horizon autonomous project management.
- Provider-specific prompt engineering.
- Tool execution.

        ## Requirements

        1. The planner must produce ordered steps.
2. Each step must include purpose, inputs, expected output, required capability, and verification criteria.
3. The planner must distinguish model work from tool work.
4. The planner must keep plans small for v0.1.
5. The planner must produce plans that can be revised by replanning.

        ## Behavior

        - The supervisor sends a normalized objective to the planner.
- The planner returns a plan with one or more steps.
- The plan is stored in Task State.
- The plan may be revised after failed verification or changed constraints.

        ## Interfaces and Data Contracts

        - `PlanRequest`: objective, constraints, available_capabilities, context_summary.
- `Plan`: plan_id, task_id, version, steps, success_criteria.
- `PlanStep`: step_id, kind, purpose, required_capability, input_refs, expected_output, verification_criteria.
- `PlanRevision`: previous_plan_id, reason, changed_steps.

        ## Error Handling

        - Ambiguous objectives return clarification needs.
- Impossible objectives return `cannot_plan` with a public reason.
- Oversized plans are rejected against v0.1 limits.

        ## Security

        - Plans must not include secrets in plain text.
- Plans must not include hidden reasoning.
- Plans derived from untrusted documents must preserve source boundaries.

        ## Acceptance Criteria

        ### Plan Creation

Given a clear objective

When planning runs

Then a bounded plan with verifiable steps is produced.

### Clarification

Given an objective lacks required constraints

When planning runs

Then the planner returns a clarification request.

### Plan Revision

Given verification fails on a step

When replanning runs

Then a revised plan version is created with a reason summary.

        ## Tests

        - Unit tests for plan schema validation.
- Golden tests for representative objectives.
- Failure tests for ambiguous and impossible objectives.

        ## Evaluation

        - Plan validity rate.
- Average steps per v0.1 task.
- Verification criteria coverage.

        ## Implementation Tasks

        - [x] Define Plan and PlanStep schema.
- [x] Define planner prompt/input contract if model-backed.
- [x] Add plan validation.
- [x] Add plan revision metadata.

        ## Dependencies

        Depends on `000-foundation`, `001-agent-core`, and `002-task-state`.
