# Architecture Decisions

This file records decisions until they are promoted to dedicated ADR files.

## Decision 0001: Galliani is the Agent Supervisor

Status: Accepted

Galliani owns planning, routing, execution, observation, verification, and replanning. Models are Agent Workers and do not own orchestration policy.

## Decision 0002: Providers are adapters

Status: Accepted

Provider integrations must be isolated behind provider-neutral contracts. Core modules cannot depend on provider-native response structures.

## Decision 0003: Task State and Memory are separate

Status: Accepted

Task State represents active execution. Memory represents explicit durable knowledge. Runtime observations are not memory unless promoted by policy.

## Decision 0004: No chain-of-thought exposure

Status: Accepted

Galliani may expose concise rationales, summaries, decisions, and audit records. It must not expose hidden reasoning, chain-of-thought, or private scratchpads.

## Decision 0005: v0.1 proves the loop

Status: Accepted

v0.1 prioritizes the objective-to-done loop over breadth of providers, tools, or UI polish.

## Decision 0006: v0.1 specs approved for implementation

Status: Accepted (2026-10-04)

Specs 000-009, 011, and 013 are approved for v0.1 implementation. Specs 010 (Memory) and 012 (Desktop UI) remain Draft; v0.1 implements only the `MemoryRecord` contract named in 000 and no memory store or UI.

## Decision 0007: Task lifecycle transition table

Status: Accepted (2026-10-04)

Spec 001 lists seven statuses and spec 002 lists ten. The runtime uses the ten statuses from 002. A missing approval or clarification moves a task to `waiting_for_user`; an explicit permission denial or an unrecoverable planning failure moves it to `blocked`. `done`, `failed`, and `canceled` are terminal; `blocked` may only move to `failed` or `canceled`. The transition table lives in `galliani/state.py` and is the single source of allowed transitions.

## Decision 0008: v0.1 loop budgets

Status: Accepted (2026-10-04)

PROJECT.md requires "one bounded retry or replan". Defaults: `max_retries_per_step=1`, `max_replans=1`, `max_plan_steps=5`, `max_total_actions=10`. All are configurable per supervisor. Exhausting the retry and replan budgets fails the task with a safe summary.

## Decision 0009: Runtime package and schema mechanism

Status: Accepted (2026-10-04)

The provider-neutral supervisor lives in the top-level `galliani/` package. It must not import `app/` or any provider SDK. The pre-existing `app/` prompt router is left untouched. Tool input and output schemas are pydantic models, which avoids a new JSON Schema dependency.

## Decision 0010: Tool validation runs before the permission check

Status: Accepted (2026-10-04)

`docs/security.md` orders schema validation before the permission check, while spec 005 lists permission first. Validation has no side effects and the permission scope is derived from validated arguments, so the tool system validates first and then checks permission. In both orders, a tool never runs unless both checks pass.

## Decision 0011: Permission pause and resume

Status: Accepted (2026-10-04)

When a tool needs user approval, the task moves to `waiting_for_user` with an `ApprovalPrompt`. `Supervisor.approve` records a least-privilege `ApprovalRecord` (exactly the requested action and scope) and resumes the same step without consuming retry budget. `Supervisor.deny` moves the task to `blocked`.
