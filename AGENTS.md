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

## Working Memory (Claude Code)

The `claude-memory` plugin (skill `claude-memory:structured-memory`) keeps the assistant's own memory across sessions. This is developer tooling. It is unrelated to Galliani's product Memory (spec 010).

- Recall first: before answering anything about past decisions, user preferences, earlier work or "what we decided", read the memory index (`MEMORY.md`) and load only the matching memory files. Skip it when the answer is already in context.
- Save only what is durable and not recoverable from the repo: user preferences and corrections, project decisions and constraints, pointers to external resources. Update an overlapping memory instead of creating a duplicate.
- Never save what the repo already records (code, `specs/`, `docs/decisions.md`, git history, `CHANGELOG.md`), debugging fixes, or details that only matter in the current session.
- Never save secrets, API keys, tokens, prompts containing credentials, or hidden reasoning.
- Memory is background context. Specs, `AGENTS.md` and the user's current instruction win over it. Check that a remembered file, flag or function still exists before relying on it.
- Subagents do not write memory. They report `Memory:` candidates in their handoff and the main agent decides what to save (see `ORCHESTRATION.md`).

## Review Checklist

- The change maps to a numbered requirement.
- The core remains provider-neutral.
- Tool execution is permission-aware.
- Errors are structured and recoverable where possible.
- Observability does not leak hidden reasoning or secrets.
- Tests cover the happy path and at least one failure path.
