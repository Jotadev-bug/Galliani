# 007 - Verification

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0006).

        ## Goal

        Define how Galliani decides whether a step or task satisfies its criteria.

        ## Non-goals

        - Replacing tests with model judgment.
- Guaranteeing semantic perfection.
- Exposing verifier hidden reasoning.

        ## Requirements

        1. Verification must run before a task is marked done.
2. Verification must compare results against explicit criteria.
3. Verification must return pass, fail, or inconclusive.
4. Verification must include a public reason summary.
5. Verification must recommend retry, replan, ask_user, or stop when failing.

        ## Behavior

        - The supervisor sends output and criteria to the verifier.
- The verifier checks deterministic criteria first where available.
- The verifier may use a model worker for semantic checks.
- The verifier returns a structured result used by the supervisor.

        ## Interfaces and Data Contracts

        - `VerificationRequest`: task_id, step_id, output_refs, criteria, context_summary.
- `VerificationResult`: status, satisfied_criteria, failed_criteria, reason_summary, recommendation.
- `VerificationStatus`: pass, fail, inconclusive.
- `VerificationRecommendation`: continue, retry, replan, ask_user, stop.

        ## Error Handling

        - Missing criteria returns inconclusive.
- Unavailable verifier returns retryable verification error.
- Contradictory evidence returns fail or ask_user depending on policy.

        ## Security

        - Verifier output must not expose hidden reasoning.
- Verification must not execute tools directly.
- Sensitive artifacts must be referenced, not copied into logs.

        ## Acceptance Criteria

        ### Task Done

Given all final criteria are satisfied

When verification runs

Then the verifier returns pass and the task can be marked done.

### Failure

Given an output misses a required criterion

When verification runs

Then the verifier returns fail with a retry or replan recommendation.

### Inconclusive

Given criteria are insufficient

When verification runs

Then the verifier returns inconclusive and asks for clarification or better criteria.

        ## Tests

        - Unit tests for deterministic criteria.
- Golden tests for semantic verification fixtures.
- Failure tests for missing criteria.

        ## Evaluation

        - Verification precision and recall.
- False done rate must be zero in critical fixtures.
- Inconclusive rate tracked for spec improvement.

        ## Implementation Tasks

        - [x] Define verification contracts.
- [x] Implement deterministic verification hooks.
- [x] Add model-backed verifier boundary.
- [x] Integrate recommendations with replanning.

        ## Dependencies

        Depends on `001-agent-core`, `002-task-state`, and `004-planner`.
