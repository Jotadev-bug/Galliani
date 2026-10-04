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

## Decision 0012: Provider adapters live in `galliani/providers/`

Status: Accepted (2026-10-04)

Concrete provider adapters live in the `galliani/providers/` subpackage and may import provider SDKs or the legacy `app` provider stack. Core modules (`galliani/*.py`) must not import that subpackage or any provider code; `tests/core/test_foundation.py` enforces this. The first adapter, `app_bridge.AppProviderAdapter`, exposes `config/models.yaml` models as Agent Workers. Worker profiles are derived from registry facts, and models without a usable key are marked unavailable so the router falls back instead of failing.

## Decision 0013: Clarification resume

Status: Accepted (2026-10-04)

A task waiting for clarification resumes through `Supervisor.clarify(task_id, answer, constraints=...)`. Answers are appended to `TaskState.clarifications` and passed to planners as user instructions. Constraints may be added, and the original objective is never changed (008 R2). Before a plan exists the task goes `waiting_for_user -> planning`. After a plan exists (for example, after inconclusive verification) the task goes `waiting_for_user -> replanning`, a transition added to the Decision 0007 table, and the plan is revised against the replan budget. If that budget is exhausted the task fails safely.

## Decision 0014: Model-backed planner and verifier

Status: Accepted (2026-10-04)

`ModelPlanner` and `ModelSemanticVerifier` call Agent Workers through `WorkerClient` and route by capability (default `reasoning`). Their prompt/input contracts are documented in their modules. Worker replies are untrusted: hidden-reasoning fields are dropped, plans are schema-checked and validated against limits and the real tool catalog, and a rejected plan gets one bounded repair round. An unreadable or "unsure" verdict is inconclusive, never a pass.

## Decision 0015: CLI wiring layer and workspace toolkit

Status: Accepted (2026-10-04)

`galliani/cli/` is a wiring layer. Like `galliani/providers/`, it may import provider adapters and the legacy `app` configuration; core modules never import it. It connects the model registry, the `AppProviderAdapter`, `ModelPlanner`, `ModelSemanticVerifier` and the workspace toolkit, and it answers approval prompts and clarification questions interactively. Provider keys come from the environment first, then from the OS credential store used by the desktop app.

The workspace toolkit (`galliani/workspace.py`) confines file access to one directory. Its input schemas reject absolute paths and traversal, credential-like files and `.git/` are refused, `list_files`/`read_file` are read-only, and `write_file` is a `write` action that requires approval scoped to the exact path.

Worker cost classes gain `premium` (frontier tier) so the cheapest-capable strategy prefers strong over frontier models. Adapter errors distinguish retryable codes (outage, timeout, rate limit) from codes that are only fallback-eligible (`auth_error`, `insufficient_credits`, `context_overflow`).

## Decision 0016: Lessons from the first live runs

Status: Accepted (2026-10-04)

Live runs against real providers led to these changes:

- Equality criteria (`equals`, `field_equals`) tolerate JSON scalar type mismatches (`"false"` vs `false`, `"3"` vs `3`). String-to-string comparison stays exact. A planner writing a quoted boolean had caused a false verification failure and an unnecessary replan.
- `$ref` paths may be nested and index into lists (`s1.files.0`). A failed lookup names the fields or list length that do exist, so replanning gets accurate evidence.
- A planner question raised during replanning pauses the task in `waiting_for_user` (`replanning -> waiting_for_user` added to the Decision 0007 table) instead of blocking it. The attempt is not charged against the replan budget because no revision was made, and `Supervisor.clarify` resumes it.
- The CLI gives the planner the workspace file listing as context (data) and raises the planner context cap to 4,000 characters, so it stops asking for paths it can see.
- `worker_completed` events carry token usage and a registry-price cost estimate; the CLI prints per-run totals.

## Decision 0017: Workspace-relative paths, actionable tool errors, and `read_files`

Status: Accepted (2026-10-04)

A user's live run failed: the workspace was `docs` and the objective said "docs/". The planner listed `docs` inside `docs`, asked a question, then tried the absolute path `/docs`, and ran out of replan budget. The fix keeps the sandbox and step limits unchanged:

- The CLI context states the workspace root and that every tool path is relative to it (`.` is the root). The planner prompt forbids absolute paths.
- Workspace "not found" errors name what the nearest existing folder contains (protected names hidden), and `invalid_arguments` errors carry the validator's reason (never the input value). Replanning then has usable evidence.
- `read_files` (read-only, size-limited: 30 files, 40 KB each, 200 KB total) reads a folder or an explicit list in one step, so summarizing a folder fits the 5-step plan limit (Decision 0008 unchanged).

## Decision 0018: Desktop UI for the agent (spec 012 approved)

Status: Accepted (2026-10-04)

Spec 012 is approved for v0.1 implementation. The agent UI is added to the existing desktop/web app:

- `galliani/viewmodel.py` (core) builds the 012 contracts (`TaskViewModel`, `EventFeedItem`, `MemoryIndicator`, reusing `ApprovalPrompt`) only from `TaskState.for_display()` and redacted events, so the UI cannot see hidden reasoning or unredacted sensitive data.
- `galliani/web/` is a wiring layer, like `galliani/cli/`. It provides the agent API router mounted into `app/api/routes.py`, which is the only change to the legacy app besides the UI page. Each task gets its own runtime (workspace, keys, budget) and runs as a background task; tasks live in memory and are lost when the app closes.
- The UI follows tasks by long polling (`GET .../events?after=<seq>`), not Server-Sent Events: `EventSource` cannot send the per-launch app token header, and polling makes "stale state with a retry option" (012 error handling) straightforward.
- Because the agent reads and writes files, its API is enabled only in the token-protected desktop app or when `GALLIANI_AGENT_WORKSPACE_ROOT` is set, in which case workspaces must be inside that folder. Otherwise any local program could drive it.
- Memory (spec 010) is still Draft: the memory indicator always shows that nothing was written to durable memory and that the task view is Task State.
- `Supervisor.create` and `Supervisor.run` split `start`, so the UI can open the task view in `created`/`planning` status before the loop finishes (012 AC Start Task).

## Decision 0019: Durable memory (spec 010 approved)

Status: Accepted (2026-10-04)

Spec 010 is approved for v0.1 implementation.

- **Store.** `galliani/memory.py` holds the contracts plus a `MemoryStore` protocol with an in-memory store and a JSON-file store (one file in the app's user data folder, written atomically). Every store refuses content with secret-like values, so secrets are never persisted (010 security). Identical content in the same scope refreshes the record instead of duplicating it; differing records are never merged, and conflicts come back side by side with their provenance (010 error handling).
- **Scopes.** Each record has a scope: `user` (applies to all of the user's tasks) or `project:<absolute workspace path>` (only tasks in that folder). A task retrieves only from `user` plus its own project scope (010 AC Scoped Retrieval).
- **Relevance.** Retrieval is deterministic and model-free. `preference` and `instruction` records in scope are always relevant, because they describe how the user wants work done. `fact` and `note` records must share a keyword with the objective (5-character prefix match, stop words removed). At most 5 records are returned, and the rest are counted in `omitted_count`.
- **Retrieval before planning.** The supervisor retrieves once, before planning (010 behavior). Records reach planners as `PlanRequest.memory`, which is data, never instructions. Task State records only that retrieval happened and which record ids were used, not their content, so Task State and Memory stay separate. If the store is unavailable, the task continues without memory and a diagnostic event is emitted.
- **Writes are explicit.** Users add records directly (Memory page, API), and those writes are allowed after the secret check. An agent can write only through the `remember` tool, a `sensitive` action that always needs the user's approval. The approval prompt shows the exact text to be saved. Provenance names the task and step. Observations are never written to memory automatically (010 AC Separate State), and a denied write is recorded as a task observation, not as memory.
- **Display.** Sensitive records are redacted in events, task views and the Memory page list, which offers deletion.
