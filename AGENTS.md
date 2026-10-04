# Galliani Agent Development Rules

These rules apply to Claude Code, Codex, and any AI coding assistant working in this repository.

## Source of Truth

The `specs/` directory is authoritative. When a request conflicts with a spec, pause and ask for the spec to be updated or clarified before implementing behavior.

## Required Workflow

1. Identify the relevant spec files.
2. Read `PROJECT.md`, this file, and every relevant spec before editing.
3. State the implementation scope in terms of spec requirements.
4. Make small, reviewable changes.
5. Add or update tests tied to acceptance criteria.
6. Run the narrowest meaningful verification command.
7. Report changed files and verification results.

## Architecture Rules

- Galliani is the Agent Supervisor and Orchestrator.
- Models are Agent Workers and must not own orchestration policy.
- Providers must remain decoupled behind adapter interfaces.
- Task State is active run state and must remain separate from Memory.
- Tools must be registered capabilities with schemas and permission metadata.
- Verification must be explicit before a task is marked done.
- Replanning must be bounded and observable.
- Hidden reasoning, chain-of-thought, private scratchpads, and provider-native reasoning traces must never be exposed.

## Coding Constraints

- Do not implement code that is not covered by an approved spec.
- Do not add provider-specific assumptions to core modules.
- Do not store secrets, API keys, prompts containing credentials, or private reasoning.
- Do not silently skip failed verification.
- Do not turn Memory into a log of all task events.
- Do not turn Task State into long-term user preference storage.

## Test Expectations

Every behavior change should include at least one of:

- Unit tests for contracts and edge cases.
- Integration tests for the supervisor loop.
- Snapshot or golden tests for stable event payloads.
- Evaluation cases under `evals/` for quality-sensitive behavior.

## Documentation Expectations

Update docs when public behavior, data contracts, lifecycle states, or security expectations change. Architecture decisions belong in `docs/decisions.md` until they are promoted into dedicated ADR files.

## Review Checklist

- The change maps to a numbered requirement.
- The core remains provider-neutral.
- Tool execution is permission-aware.
- Errors are structured and recoverable where possible.
- Observability does not leak hidden reasoning or secrets.
- Tests cover the happy path and at least one failure path.
