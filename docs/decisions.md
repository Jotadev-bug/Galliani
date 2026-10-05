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

## Decision 0020: One chat screen with Chat and Agent conversations

Status: Accepted (2026-10-04)

The separate Agent page (Decision 0018) is folded into the chat screen. A switch in the composer chooses the kind of the next conversation: **Chat** (one routed model answers, as before) or **Agent** (each message starts a supervised task in a chosen folder). A conversation keeps its kind; switching modes in a non-empty conversation starts a new one.

- Both kinds share the same layout. Agent conversations use a teal accent (`--agent`, `--agent-2`) where chat uses violet: composer border, send button, user bubbles, running spinners, and primary buttons inside task cards.
- In an agent conversation each task is a reply card: approval and question callouts while live; then the result (prose first, tool records collapsed), verification, files saved, the plan, memory used and saved, collapsible activity, and usage. Cards are built only from the 012 view models.
- Later messages in the same agent conversation reuse its folder and pass the earlier tasks' outcomes as context (data). Only one task per conversation may be in progress.
- Card snapshots are kept with the conversation in local storage, so finished tasks survive a reload. A task the server no longer has (the app was closed) is shown as stopped, with its last known state.
- A Memory page (spec 010) lists, adds and forgets notes. Sensitive notes are redacted in the list and never sent to models.
- The semantic verifier now also receives the step's expected output and the source data it used, so it can judge claims about the source instead of answering "unsure".

## Decision 0021: `write_files` for multi-file builds

Status: Accepted (2026-10-05)

A live run asked the agent to build a small web app (`index.html`, `styles.css`, `app.js`). The planner answered `cannot_plan`: with only `write_file`, every file needed a generation step and a write step, so six steps exceeded the 5-step plan limit. No file type was ever blocked. The limit of one file per write call made any build of three or more files impossible. The fix mirrors `read_files` (Decision 0017) and keeps the step limits unchanged (Decision 0008):

- `write_files` (a `write` action that requires approval) writes up to 50 files, 400 KB in total, in one call. It takes either `files: [{path, content}]` or a `bundle`, which is a model step's text where each file starts with a line `=== path/to/file ===`. Text before the first header and a code fence wrapping a whole file are removed, so a model's framing never ends up in the written files. Every path is validated and checked against protected names before any file is written.
- The permission scope is the deepest folder that holds every file. The approval prompt lists each file with its size (009: specific, understandable prompts). One approval covers that call only.
- A tool's `artifact_field` may name a list, so each written file is reported as an artifact.
- The planner prompt says to save generated files with one model step that produces a bundle plus one `write_files` step, never one step pair per file. The same web app now plans in 2 steps.
- `.env.example`, `.env.sample` and `.env.template` are ordinary project files. Other `.env*` files stay protected.

## Decision 0022: Accept-edits mode (spec 014 approved)

Status: Accepted (2026-10-05)

Spec 014 is approved for implementation with its draft defaults. The UI does not remember the mode across app restarts. Overwrites are auto-approved but labelled in the result.

- **Policy.** `EditMode` (`ask` | `accept_edits`) lives in `UserPolicy` and `TaskState`. `PermissionPolicy.evaluate` applies the mode only where a request would otherwise need the user, and only to `write`-level requests whose tool declares `workspace_edit`. A policy rule that denies writes, a missing rule, and an explicit approval all take precedence. An approved write is credited to the approval, not the mode. An earlier approval for another path no longer causes a scope-mismatch denial while the mode is on. The registry refuses `workspace_edit` on any tool that is not `write`-level.
- **Switching while a task runs.** Task State is versioned, so a switch made from the UI during a run would conflict with the loop. `Supervisor.set_edit_mode` updates the task's policy at once and emits `edit_mode_changed`. An idle task records the change in Task State immediately; a running loop records it at the start of its next step, before any permission check.
- **Audit.** Automatic approvals are ordinary `PermissionDecision`s with the audit summary "allowed by accept-edits mode" and a `permission_decided` event (`metadata.auto = true`). No `ApprovalRecord` is created, because no user approved that call. Write tools report `created` or `overwritten` for each file, and the task view lists them as `files_changed` with an `edits_auto_approved` count.
- **UI.** In agent mode the composer has an "Ask before edits" / "Accept edits" toggle next to the folder chip, similar to the edit-mode switch in other coding agents. The choice is kept in memory per conversation and resets for a new conversation or after a restart. Switching it during a live task also switches that task. Write approvals offer "Yes, and accept edits". Running cards show an "Accepting edits" badge, and results mark files as new or overwritten.
- **Evaluation.** `evals/cases/v0_1_accept_edits.yaml` covers the acceptance criteria. Any accept-edits approval of a non-eligible action counts as a permission bypass, and the new blocking gate `unaudited_auto_approvals` must be 0.

## Decision 0023: Dashboard and task-view redesign of the desktop UI

Status: Accepted (2026-10-05)

The desktop UI (spec 012) is restyled after a dashboard and task-view mockup. Every existing function stays: routed chat with preview and routing details, agent tasks with approvals, questions, accept-edits, memory, models, usage, keys and settings. No API or view-model contract changes.

- **Shell.** An icon rail replaces the sidebar: Home, All conversations, Memory, Models, Usage, API Keys, Settings, and the OpenRouter credit. The conversation list moves to a drawer that the header's panel button opens. The global routing bar is removed. The routing mode lives in the composer, and each answer's model chip expands that answer's routing details.
- **Home.** Welcome text, the composer (Chat | Agent, folder, edit mode), suggestions, the four most recent conversations with their status, and totals (tasks completed, spent, saved).
- **Conversation view.** A header shows the title, status, duration and cost, with Stop while a task runs and Copy result after it ends. Tabs: Overview, Plan, Activity, Files and Settings for agent conversations; Overview, Routing and Settings for chats.
- **Running task.** "Agent progress" is a stepper: understanding the objective, planning, each plan step, then reviewing and finishing. A "Model & tools" card shows the current model, taken from the router's public `route_selected` rationale, and the tools in the plan. Approval and question prompts appear right under the progress, next to the composer. Their accessible markup is unchanged.
- **Finished task: compact final response.** The Overview shows the outcome, file cards for `files_changed` or artifacts, verification, and memory. It does not repeat the whole output:
  - When the task saved files, the model text written into them is not shown again.
  - A text output is clamped, with "Show more".
  - Every fenced code block is folded into a collapsed "language · N lines" row.
  - The raw tool record (JSON) is only in the Files tab.
  Spec 012's "Done" criterion still holds: final result, verification summary and artifacts are visible. The full content stays reachable, but it is never dumped by default.
- Suggested next steps under the final response only fill the composer. They never send anything.

## Decision 0024: Showcase video in `video/`

Status: Accepted (2026-10-05)

The first Remotion explainer for spec 015 (kinetic text, 28 beats, wipes) was too busy. It is replaced, at the user's request, with a quiet product showcase that sets spec 015 aside:

- One continuous 28-second shot at 1920x1080 with a smooth camera. It snaps in (up to 1.5x) while typing and while the tasks load, eases between focus points, and does not zoom during the logo reveal, ending on the new mark: a G and a star, cut out of the logo tile in `video/public/galliani-mark*.png`. The G draws itself and the robot becomes the star. There are no cuts or transitions, and every movement is a smooth eased move.
- Dark background and greyscale UI only. The chat bar appears and a prompt is typed and sent. The agent card plans four steps, runs them (including a write approval), verifies, and shows the resulting file.
- There is no explanatory copy. The UI itself is the message. A tiny greyscale robot wanders the chat, curious about each moment.
- Model choice and cost are part of the core UI. The agent card header always shows the current model and running cost. A routing panel weighs Haiku 4.5, Sonnet 5.5 and Opus 5.5 for the coding step and picks Sonnet 5.5. The finished task leads with model, cost and savings tiles. The figures come from the published per-token prices and illustrative token counts.
- The Claude mascot (our own pixel-style SVG, the only color in the video) pops out of the chosen model and high-fives the robot. Public use of Anthropic's marks should follow Anthropic's brand guidelines.
- Timing, copy and the robot's path live in `video/src/timeline.ts`. The logo pieces are the only assets, and the render is deterministic.

Spec 015 still describes the old explainer. Its requirements on copy beats, concept coverage, duration (35-55 s) and vertical-first output no longer apply to this video. Update or retire the spec before relying on it.

## Decision 0025: The logo tile is the app icon, and the UI palette follows it

Status: Accepted (2026-10-06)

The new logo (`assets/logo.png`: a silver G and star on a graphite rounded tile) replaces the blue-to-violet SVG "G" everywhere:

- `scripts/make_icon.py` derives every icon from `assets/logo.png`: `assets/galliani.ico` and `assets/galliani.icns` for the desktop build, `assets/galliani.png`, and `app/web/logo.png` (128 px). The desktop build runs it before packaging, as before.
- The web UI uses `app/web/logo.png` as its favicon and rail logo. The server serves it at `/logo.png`. Like `/`, it needs no app token, because a favicon request cannot send one.
- The palette moves from blue and violet to the logo's graphite and silver. The dark theme's background is the tile color (`#121318`). The accent is silver in the dark theme and graphite in the light theme, and primary buttons and the send button use the G's silver gradient (dark) or a graphite gradient (light). Links keep their underline because the accent is close to the text color.
- Status colors (good, warn, bad), the agent's teal (Decision 0020, slightly desaturated) and the vendor marks stay in color, because they carry meaning. Chat no longer uses violet.

## Decision 0026: AGPL-3.0 license and a free release pipeline

Status: Accepted (2026-10-06)

- **License.** Galliani is licensed under the GNU AGPL-3.0 or later, replacing the reserved placeholder in `LICENSE.md`. It is an approved open-source license, so the project qualifies for free open-source code signing. Anyone who offers a modified Galliani as a network service must publish their changes, which protects a future hosted version and paid credits. The full text is in `LICENSE`, unmodified from gnu.org.
- **CI.** `.github/workflows/ci.yml` runs the tests and the deterministic evals on Windows (the platform the app ships on) for every push to `main` and every pull request.
- **Releases.** `.github/workflows/release.yml` runs on a `v*` tag. It checks that the tag matches `pyproject.toml`, runs the tests, builds `Galliani.exe` with `scripts/build_desktop.py`, and fails unless the binary's `--smoke-test` passes. It then publishes the `.exe` and its SHA-256 on GitHub Releases. GitHub attaches the tagged source, which is how the binary's source is offered under the AGPL. Hosting and builds cost nothing for a public repository.
- **Signing.** Builds are unsigned for now. The release notes explain the SmartScreen "Run anyway" step and the checksum. Signing will be added as a workflow step once the project is accepted by an open-source signing program.
- The desktop smoke test also checks that the logo is bundled (`/logo.png`, Decision 0025).
