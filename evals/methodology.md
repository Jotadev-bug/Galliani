# Evaluation Methodology

Galliani evaluations combine deterministic contract tests with scenario-based quality checks.

## Evaluation Principles

1. Test behavior, not implementation details.
2. Tie each scenario to a spec requirement.
3. Record enough evidence to debug failures.
4. Avoid storing secrets or hidden reasoning.
5. Keep v0.1 fixtures small and repeatable.

## Scenario Format

Each scenario should define:

- Objective.
- Initial Task State.
- Available workers.
- Available tools.
- Permission policy.
- Expected observations.
- Expected verification result.
- Expected final state.

## Metrics

- Completion rate.
- Verification precision.
- Verification recall.
- Replan success rate.
- Tool error recovery rate.
- Permission violation count.
- Provider fallback correctness.

## Reporting

Evaluation reports should include pass/fail status, linked spec requirements, failure category, and recommended follow-up.
