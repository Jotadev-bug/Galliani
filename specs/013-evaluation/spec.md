# 013 - Evaluation

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0006).

        ## Goal

        Define evaluation strategy and quality gates for the v0.1 Galliani loop.

        ## Non-goals

        - Benchmarking every commercial model.
- Replacing unit and integration tests.
- Using private chain-of-thought as an evaluation artifact.

        ## Requirements

        1. Evaluations must map to spec requirements.
2. Evaluations must cover success, failure, permission, fallback, and replan scenarios.
3. Evaluations must report deterministic pass/fail where possible.
4. Evaluations must not store secrets or hidden reasoning.
5. v0.1 must define minimum gates before release.

        ## Behavior

        - Evaluation fixtures define task inputs and expected outcomes.
- The evaluation runner executes or simulates the supervisor loop.
- Results are recorded with linked requirements and failure categories.
- Failures produce actionable follow-up items.

        ## Interfaces and Data Contracts

        - `EvalCase`: id, spec_refs, objective, initial_state, available_workers, available_tools, expected_outcome.
- `EvalResult`: case_id, status, metrics, failure_category, evidence_refs.
- `EvalSuite`: name, cases, required_pass_rate, blockers.
- `QualityGate`: name, threshold, blocking, owner.

        ## Error Handling

        - Invalid fixtures fail fast.
- Runner failures are separated from product failures.
- Non-deterministic outcomes are flagged for manual review.

        ## Security

        - Evaluation logs must redact secrets.
- No hidden reasoning may be used as expected output.
- Fixtures based on external data must preserve trust boundaries.

        ## Acceptance Criteria

        ### Success Fixture

Given a clear objective and available tools

When the eval runs

Then the task reaches done with passing verification.

### Permission Fixture

Given a restricted action is required

When the eval runs

Then the task pauses for approval instead of executing.

### Failure Fixture

Given verification cannot pass

When the eval runs

Then the task retries or replans within budget and then blocks or fails safely.

        ## Tests

        - Fixture validation tests.
- End-to-end evaluation smoke test.
- Regression tests for known failure cases.

        ## Evaluation

        - Minimum pass rate for v0.1 loop fixtures.
- Zero permission bypasses.
- Zero hidden reasoning leaks.
- Zero false done results on negative fixtures.

        ## Implementation Tasks

        - [ ] Define eval case schema.
- [ ] Create v0.1 fixture suite.
- [ ] Define quality gates.
- [ ] Integrate evaluation reporting with changelog or release checklist.

        ## Dependencies

        Depends on all v0.1 specs.
