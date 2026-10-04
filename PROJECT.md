# Galliani Project Definition

## Product Summary

Galliani is an Agent Supervisor for orchestrating AI work across models, providers, tools, and verification strategies. It turns a user objective into a controlled execution loop:

```text
objective -> plan -> routing -> action/tool -> observation -> verification -> replan/retry -> done
```

## v0.1 Mission

Deliver a small, reliable orchestration core that can:

1. Accept a user objective.
2. Normalize it into a task.
3. Produce a plan.
4. Select an Agent Worker through a model router.
5. Execute a model or tool action.
6. Capture an observation.
7. Verify the result.
8. Retry or replan when verification fails.
9. Finish with an auditable final result.

## System Roles

### User

Provides objectives, approvals, constraints, and final acceptance.

### Agent Supervisor

Galliani owns orchestration. It manages task lifecycle, planning, routing, permissions, execution, observation, verification, and replanning.

### Agent Worker

A model invocation selected by the router for a bounded task. Workers return structured outputs and do not control global policy.

### Provider Adapter

A provider-specific integration that exposes stable model execution capabilities without leaking provider details into core orchestration.

### Tool

A registered external capability with a schema, permission level, execution contract, and structured result.

## Boundaries

Galliani does:

- Orchestrate work.
- Track active task state.
- Route model requests.
- Execute approved tools.
- Observe and verify outcomes.
- Store explicit durable memory where allowed.

Galliani does not:

- Expose chain-of-thought.
- Treat providers as core architecture.
- Assume one model family.
- Store every task event as memory.
- Mark work done without verification.
- Execute unsafe tools without permission.

## v0.1 Success Criteria

- A task can complete the full loop from objective to done.
- A failed verification can trigger one bounded retry or replan.
- Model routing is explainable without exposing private reasoning.
- Providers can be swapped without changing supervisor behavior.
- Task State and Memory are represented by separate contracts.
- Tool calls are schema-validated and permission-checked.
- Logs and UI are useful without leaking secrets or hidden reasoning.

## Spec Ownership

Specs are numbered to reflect dependency order, not implementation order. Lower-numbered specs define contracts that higher-numbered specs rely on.

## Release Policy

v0.1 is pre-production. Breaking changes are allowed while specs are draft, but approved specs should be changed deliberately and recorded in `docs/decisions.md`.
