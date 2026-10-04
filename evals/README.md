# Galliani Evaluations

Evaluations prove that Galliani behaves like a reliable Agent Supervisor.

## v0.1 Evaluation Areas

- Objective normalization.
- Plan quality.
- Model routing correctness.
- Tool schema validation.
- Observation recording.
- Verification accuracy.
- Replanning usefulness.
- Permission enforcement.
- Privacy and redaction.

## Evaluation Shape

Each evaluation should include:

- Fixture input.
- Expected behavior.
- Pass/fail criteria.
- Required logs or events.
- Known limitations.

## Minimum Gate for v0.1

The full agent loop must pass deterministic fixtures for successful completion, tool failure, verification failure, permission denial, and provider fallback.

## Running

```bash
python -m galliani.evaluation evals/cases
```

Fixtures live in `evals/cases/*.yaml` (`v0_1_loop.yaml` for the core loop, `v0_1_agentic.yaml` for model-drafted plans, the spending cap and user answers) and follow the `EvalCase` schema in `galliani/evaluation.py`. With `planner: model`, the plan is drafted by `ModelPlanner` from scripted `plan_reply` objects. Each case names its `spec_refs`, scripts the planner and worker outputs (all outputs are simulated), and states the expected outcome. Cases marked `negative: true` must never end in `done`. Each case runs twice, and any difference is flagged `non_deterministic`.

Blocking quality gates:

- `loop_pass_rate` = 1.0
- `permission_bypasses` = 0
- `hidden_reasoning_leaks` = 0
- `false_done_on_negative` = 0

The command exits non-zero if any gate fails.
