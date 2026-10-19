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

## Decision 0027: Public launch plan (spec 016 approved), Phase 1

Status: Accepted (2026-10-06)

- Spec 016 is approved. It ships in phases: first release, landing page on GitHub Pages, winget, Microsoft Store, and optionally PyPI. Each phase ships on its own.
- **Manual release runs.** `release.yml` also has a `workflow_dispatch` trigger with a required `tag` input, because the `v0.1.0` tag reached GitHub without starting the workflow. A manual run checks out that tag and then behaves like a tag push.
- **Tag check in `scripts/release_tag.py`.** The inline check moved to a tested script. It reads `pyproject.toml` at the tag (`git show <tag>:pyproject.toml`), not from the branch the run started on, so a manual run from `main` checks the tag it will publish, and older tags without the script can still be released. It refuses malformed tags (before calling git), missing tags and mismatched versions with a message naming the tag and the version. The tag reaches scripts only through an environment variable.
- **Pre-releases never become latest.** The publish step sets `make_latest` from the check's `prerelease` output, so `/releases/latest/download/Galliani.exe` always serves the newest stable build.
- The clean-machine, VirusTotal and false-positive steps are manual items in `docs/release-checklist.md` (R4).

## Decision 0028: The landing page is a React app (spec 016 R6 amended), Phase 2

Status: Accepted (2026-10-06)

- **Stack.** At the maintainer's request, spec 016 R6 changes from plain HTML and CSS to React, Vite, Tailwind CSS and Motion, for richer components and animations. The site is still static: `npm run build && npm run check` produces and checks `site/dist/`. Nothing runs on a server.
- **No third-party code at runtime.** The JavaScript bundle, styles, images and video are all served from the site. The built pages set a CSP (`default-src 'self'`, `connect-src https://api.github.com`); the dev server does not, because Vite's hot reload needs inline scripts. Fonts are system fonts (Segoe UI on Windows). Animations follow `prefers-reduced-motion` through `MotionConfig reducedMotion="user"`.
- **Hosting on Vercel (R5 amended).** The site is hosted on Vercel's free Hobby plan at `https://galliani.vercel.app/` instead of GitHub Pages, at the maintainer's request. Vercel's Git integration builds `site/` (`site/vercel.json`) on every push: `main` is production, other branches get previews. The site checks run inside the Vercel build, so a failing check blocks the deploy and the previous site stays live. The GitHub Pages workflow is removed. Vercel serves the site at the root, so the base path defaults to `/` (`SITE_BASE` can set a prefix), and `VITE_SITE_URL` sets the canonical and Open Graph URLs. Vercel Analytics and Speed Insights stay off: the no-telemetry promise covers the website too.
- **Budget.** React and Motion add about 110 KB gzipped. The home page transfers about 200 KB before the video plays (R13 allows 500 KB), and the video is re-encoded from the render to 1280x720 H.264 without audio, about 1.3 MB (R12 allows 8 MB). `site/scripts/check-site.mjs` enforces both, plus allowed external URLs, the CSP, `lang` and `alt`, before deploying.
- **SmartScreen step.** Until a real screenshot is taken on a clean machine, the install section shows a drawn stand-in for the SmartScreen dialog, with a text label.
- **Illustrative demos.** The hero's app window (a prompt is typed, the router scans the models and picks one, cost and savings count up), the agent stepper and the cost bars are animations with example numbers, labelled "Example" or "Illustrative". The app shows the real model and cost for every answer. The model strip lists the models in `config/models.yaml` by name only, with no vendor logos.

## Decision 0029: winget manifest generator, Phase 3

Status: Accepted (2026-10-07)

- **Portable package.** `scripts/winget_manifest.py` writes the three manifest files (version, installer, default locale) for a release tag. The package is `InstallerType: portable`, points at the versioned release URL (never `latest`), carries the `.exe`'s SHA-256 and the command alias `galliani`, and uses manifest schema 1.6.0. It validates the tag, checksum, identifier and date before writing anything, and it has no network access: the checksum comes from the built `.exe` or from the release's `.sha256` file.
- **Release workflow.** After the checksum step, `release.yml` generates the manifest from the built `.exe` and attaches `galliani-winget-<version>.zip` to the release. The workflow does not open the winget-pkgs pull request, because that needs a personal access token (deferred, per spec 016 Non-goals).
- **Committed manifest.** `packaging/winget/0.1.0/` holds the manifest for the first release, built from the published checksum and checked with `winget validate`.
- **Identifier.** `Jotade.Galliani`, from the maintainer's Partner Center publisher name "Jotade" (confirmed 2026-10-07). It cannot change after the first winget-pkgs merge.
- **Publisher field.** The locale manifest uses "Galliani contributors", matching the license notice, until Open Question 3 (copyright holder) is decided.

## Decision 0030: Microsoft Store packaging scaffold, Phase 4

Status: Accepted (2026-10-07)

- **One-folder build.** `scripts/build_desktop.py --onedir` builds `dist/onedir/Galliani/` for the package, which starts faster and extracts nothing to `%TEMP%` (spec 016 R20). The standalone `.exe` stays `--onefile` and its output paths are unchanged. The build still runs the app's `--smoke-test` before anything is packed.
- **Packaging.** `scripts/build_msix.py` fills `packaging/msix/AppxManifest.template.xml` (a full-trust desktop app: `runFullTrust`, `Windows.FullTrustApplication`, x64, Windows 10 1809 or later), stages the app folder with an `Assets` folder and the manifest, and packs it with `makeappx` from the Windows SDK. The version is `pyproject.toml`'s with a fourth part of `0`, which the Store reserves.
- **Identity is never invented (R19).** `packaging/msix/identity.json` leaves `identity_name` and `publisher` null until Partner Center issues them; `publisher_display_name` is "Jotade". A Store build with null values refuses to run and says where to find them. In CI, `--if-configured` skips the step instead, so the release workflow keeps working until the identity is committed.
- **Signing (R18).** Store builds are left unsigned, because the Store signs them. `--local-test` uses a made-up identity (`Galliani.LocalTest`, `CN=Galliani Local Test`) and signs with a certificate created for the run and deleted from the certificate store right after signing; only its public `.cer` is written to `dist/`. The script never trusts the certificate: the checklist has the maintainer do that by hand, as administrator, and undo it afterwards.
- **Never blocks the `.exe`.** The workflow step is `continue-on-error`, so an MSIX failure leaves the `.exe` release intact (spec 016 Error Handling).
- **Tiles (R21).** `scripts/make_icon.py` also writes `packaging/msix/Assets/` (Square44x44, Square150x150, Wide310x150 on `#121318`, StoreLogo, at scales 100, 125, 150, 200 and 400). They are committed, like the other generated icons.
- **Verified locally (2026-10-07).** `python -m scripts.build_msix --local-test` built the one-folder app, passed its smoke test, packed with `makeappx` and signed with the throwaway certificate, which was gone from the certificate store afterwards. `makeappx` requires the unscaled tile names the manifest declares, so `make_icon` also writes `<Name>.png` (the 200% tile). A package built in a developer environment with extra packages installed (`torch` and others) is far bigger than one built on the clean CI runner, so check the size of the first CI-built package.
- **Not yet verified.** Installing the package and running it from inside the package (R22: the credential store, `%LOCALAPPDATA%` virtualization, the folder picker) is a manual check on a clean machine.

## Decision 0031: A clear message when WebView2 is missing (spec 012 amendment R6-R15)

Status: Accepted (2026-10-15, approved by the user with every default in spec 012 Open Questions 1-6). Spec 012 R6-R15 are Approved for implementation. Amendment to R7, R8 and R10: Accepted (2026-10-15, the user: "approve with defaults", spec 012 Open Question 7). Amendment R20 (WebView2 installed but fails to initialize) and the `PYWEBVIEW_LOG` rule in R13: Accepted (2026-10-15, the user approved every default of spec 012 Open Question 8). R20 clarification (record ignored once `closing` or `closed` is set; formerly proposed R20-A1): folded into R20 as a clarification of approved text (2026-10-15). Amendment R20-A2 (the close request): Proposed, not approved (2026-10-15, spec 012 Open Question 9).

Roadmap item 5 and spec 016 Open Question 5. On Windows 10 machines without the Microsoft Edge WebView2 runtime, pywebview does not fail: it silently falls back to the deprecated Internet Explorer engine (MSHTML), which cannot run the bundled UI. The windowed build has no console, so the user sees a blank or broken window and the only trace is `desktop.log`.

- **Launcher, not core.** The check and the message live in the desktop launcher under `app/`. The `galliani/` core, Task State and Memory are untouched; no task exists when the check runs.
- **Same rule as pywebview, checked first.** The launcher applies exactly pywebview's rule (as amended below: the same keys, paths, default view, order, first-number version comparison of at least 86, stop on a malformed value, .NET Framework 4.6.2 or later), read-only and offline, before creating the window and before pywebview's Windows backend is imported. It also refuses to open a window if pywebview still picks a non-Chromium renderer. Reusing pywebview's private check would tie us to an internal API, so the launcher has its own small, tested function, kept honest by the `pywebview>=6.2,<7` pin.
- **A native message box, not a web page.** The message must render without WebView2, so it is a standard Windows Yes/No message box with fixed text (012 R9). No is the default button, so Enter never opens a browser.
- **Link, never download.** The only path forward is Microsoft's official WebView2 page, opened in the user's default browser only after they select Yes. Galliani does not bundle, download, run or elevate any installer, and the URL carries no query string. Bundling the runtime would add well over 100 MB and an update duty; auto-download would break the "nothing happens without the user" rule.
- **Decline means exit cleanly, nothing remembered.** Either answer stops the local server and exits (code 3; code 4 when a detected runtime fails to start the window). There is no retry loop and no "don't ask again"; the next launch checks again.
- **No telemetry.** One line goes to the local `desktop.log` (case, version, answer), without the app token or window URL. Nothing is sent anywhere. This keeps the standing constraints: no telemetry, no accounts, no servers, no paid signing.
- **Testable without uninstalling WebView2.** Detection reads through an injectable registry reader, the flow takes injectable dialog, opener and window factories, and `--simulate-missing-webview2` forces the message on any machine. `--smoke-test` reports the detected version as information only, so CI and release checks keep their meaning.
- **Resolved by the user (2026-10-15)** (012 Open Questions 1-6): the R9 and R12 titles and texts exactly as written; the link is Microsoft's page `https://developer.microsoft.com/microsoft-edge/webview2/`, not the direct bootstrapper; no browser fallback; .NET Framework older than 4.6.2 shows the same R9 message; No stays the default button, with exit codes 3 (runtime missing) and 4 (window failed); `docs/release-checklist.md` gains a manual Windows 10 check and the site FAQ gains a WebView2 entry.
- **Wording revision (2026-10-15, approved by the user after the ui-engineer copy review).** The R9 text now gives the explanation, then asks "Open Microsoft's WebView2 page now?" so that Yes and No answer a question, then says what each button does ("Yes opens ...; No closes Galliani.") instead of "Select Yes/Select No" imperatives; it adds "Nothing was sent anywhere." next to "Nothing has been downloaded or changed on this PC." (matching R13 and the no-telemetry rule). R12 says "Reinstalling or updating it often helps." instead of the unverified "usually fixes this." Titles, icons, buttons, No as default, the single URL, exit codes 3 and 4, and the log path on its own line are unchanged. The "Evergreen Runtime" wording stays. The status stays Accepted; the golden test must be updated to the new strings.
- **Amendment to R7, R8 and R10 (2026-10-15, Accepted; spec 012 R7, R8, R10, "Why R7, R8 and R10 read this way", Open Question 7).** Found while implementing: pywebview 6.2.1 decides its renderer while importing its Windows backend, and when it picks MSHTML that import writes per-user registry values (`HKCU\...\FeatureControl\FEATURE_BROWSER_EMULATION`, and, found later by qa-security, `FEATURE_96DPI_PIXEL`). So the R8 renderer probe cannot run without that write, and showing the R9 box afterwards makes "Nothing has been downloaded or changed on this PC." untrue. The path is reachable because R7 is not pywebview's rule: R7 also reads the native 64-bit HKLM view (pywebview reads only `WOW6432Node` on non-x86 Windows), reads .NET in both views, compares the full version where pywebview compares only the first number, and skips malformed `pv` values where pywebview stops. Proposal: (1) R7 mirrors pywebview's rule exactly (paths, default view, order, first-number comparison, stop on malformed value), and pywebview's Windows backend is not imported before R7 decides; (2) pin `pywebview>=6.2,<7` with a test that fails outside that range; (3) the R8 case, now reachable only if pywebview's rule drifts, shows the R12 box (which claims nothing about changes) and exits with code 4; (4) R10 names pywebview's two writes on the R8 path as a known exception. The R9 and R12 texts stay as approved. Considered and rejected: rewording R9 (weakens a claim that is true on every R9 path once the rule is mirrored, and the text was approved twice); no-op'ing pywebview's private `_set_ie_mode` before probing (removes the writes but patches a private function and fails silently on a rename). Decided by the user on 2026-10-15 with all three defaults: (a) copy the rule exactly, including the first-number-only comparison; (b) R8 shows R12 with exit code 4 and R10 names the two HKCU values; (c) the pin with a test that fails outside the range. Consequence: `app/webview2.py` must be reworked (spec 012 Implementation Tasks); a pywebview upgrade past 6.x needs an R7 re-check and a spec update.
- **`desktop.log` is redacted as a whole (2026-10-15, spec 012 R13 and Security).** pywebview's own `pywebview` logger and any logged or re-raised traceback go through the same filter as the launcher's lines: the exact app token and window URL of the launch are removed, then the shared redactor runs. One filter on the file handler, not per call site, so a new log line cannot bypass it.
- **Amendment: WebView2 installed but fails to initialize (2026-10-15, Accepted; spec 012 R20, "Why R20 reads this way", Open Question 8).** QA found (Medium) that R12 never fires for a damaged WebView2 install. pywebview 6.2.1 `EdgeChrome.on_webview_ready` only logs `WebView2 initialization failed with exception: ...` on the `pywebview` logger when `IsSuccess` is false, and raises nothing. The user gets an empty window, exit code 0, and no R12 box.
  - **Decision.** The launcher attaches a flag-only watcher to the `pywebview` logger while the window starts. When an ERROR record starting with that prefix arrives before the window's `loaded` event, the launcher closes the empty window, shows the unchanged R12 box, logs the new R13 case `webview2_init_failed`, and exits with code 4. There is no timeout, no telemetry and no new network access. A source-text pin test on pywebview's `edgechromium.py`, together with the `<7` pin, makes a reworded message fail CI.
  - **Considered and rejected.** A `shown`/`loaded` timeout: `shown` fires even on failure, and any `loaded` timeout short enough to help would close working apps on slow machines with a "damaged" warning. Accepting the gap as a known limitation: R12 already promises this case. Subscribing to the .NET `CoreWebView2InitializationCompleted` event: it needs a private pywebview attribute and has a race.
  - **Residual.** A start that never reports (a hang) stays undetected and documented. There is no timeout backstop.
  - **Decided by the user (2026-10-15)** with the defaults in spec 012 Open Question 8: option (b), the pywebview failure record; no hang timeout; no new simulation flag (the manual check uses `WEBVIEW2_RUNTIME_PATH` from a source checkout); the R12 text unchanged.
  - **Interaction with logging.** The watcher depends on pywebview's ERROR record reaching the `pywebview` logger's handlers. No setting, flag or environment variable may raise that logger's level above ERROR, or disable logging at ERROR, while the window starts; otherwise R20 would switch off silently.
  - **Implemented (2026-10-15).** `launch_window` attaches the watcher with `watch_init_failure` around its call to `open_window()` (before `webview.create_window`), and removes it when `open_window` returns or raises; `app/desktop.py` supplies the `loaded` check and the `close_window` callback. The manual check now imports `app.desktop` first and `webview` only inside the R8 renderer hook, and points `LOCALAPPDATA` at a temp folder, so pywebview's unredacted stderr handler never appears and the tester's real data folder is not touched (spec 012 Tests).
- **R20 clarification: the user's own close is not a failure (2026-10-15; spec 012 R20 Signal, "Why R20 reads this way", AC "User Closes First"; formerly proposed R20-A1).** If the user closes the empty window during start, the disposed WebView2 control may still complete with `IsSuccess` false, and pywebview logs the same failure line. R20 then showed the R12 box with exit code 4 for what was only a user close. QA reproduced it on Windows: closing within 0.2 s of `shown` gave the box and exit code 4 in 6 of 6 runs; closing at 0.4 s or later did not. That contradicts R20's approved sentence "If the user closed the empty window before the flag was set, the exit is unchanged (0)".
  - **Decision.** Treated as a clarification of that approved sentence, not a new requirement, so no new approval round: the R20 signal counts only while neither the window's `closing` nor its `closed` event is set (and `loaded` is not set). A matching record after that is ignored; a flag already set before `closing` stays set. The check is injectable like `loaded`; if reading the events fails, the record counts. The R20 Signal bullet and the AC "User Closes First" now say this explicitly.
  - **Cost.** A real damaged-runtime failure reported only after the user already clicked close shows no box on that launch; the next launch reports it.
  - **Status.** core-engineer is fixing the code; the implementation task stays unticked until verification is confirmed, and the R20 qa-security step stays open.
- **Proposed amendment R20-A2: the close request (2026-10-15, PROPOSED, NOT APPROVED; spec 012 "Proposed amendment R20-A2", Open Question 9).** From the code review of the R20 implementation. `close_window` calls pywebview's `Window.destroy()`, which waits up to 20 s for `shown`, while the launcher joins the close thread for only 1 s. So the close can come late, and a "could not be closed" warning can be written after `desktop.log` has closed (to the last-resort stderr handler). It contains only a type name.
  - **Proposal.** Request the close only once `shown` is set and the window is not already closing or closed, keep the 1 s join, add no timeout, and write nothing once the launcher has moved on.
  - **Recommendation.** Approve. It removes a 20 s wait and a write outside R13 without private pywebview attributes. Rejected: a longer join (delays the box and normal exits); catching `WebViewException` alone (keeps the 20 s wait).
  - **Until decided,** R20 (with its clarified signal) stays in force and nothing of R20-A2 is implemented.
- **`PYWEBVIEW_LOG` is ignored (2026-10-15, Accepted with R20; spec 012 R13, Security, AC "PYWEBVIEW_LOG Ignored").** While the app runs, the launcher sets the `pywebview` logger's level itself: DEBUG with `--debug`, otherwise INFO. The `PYWEBVIEW_LOG` environment variable has no effect, whatever its value. Reasons: a user value such as `CRITICAL` would hide the record R20 depends on, and a value such as `DEBUG` would put more pywebview detail into `desktop.log` than the app's own level allows. Every pywebview record still reaches `desktop.log` only through the R13 redacting filter. This reverses the earlier implementation, which followed pywebview's rule (a valid `PYWEBVIEW_LOG` name wins); its two tests and the CHANGELOG line saying it "is honoured again" must be updated. Considered and rejected: honouring `PYWEBVIEW_LOG` but clamping it to ERROR or below (keeps an extra, undocumented knob on what reaches `desktop.log`, for no user need; `--debug` already covers debugging).
## Decision 0032: Agent file access hardening (security review SEC-1..SEC-7)

Status: Accepted (2026-10-15, approved by the user). Implements behavior already required by specs 005, 009 and 014; findings and tests in `docs/security.md` ("Agent File Access Threat Model") and `tests/core/test_security_review.py`. The local API contract (CSRF guard and `Host` allowlist) is now spec 012 R16-R19; the Windows path rules, the `workspace_edit` confinement and the `tool_called` metadata are written into spec 014 (R3, Security).

- **Contract: CSRF guard on the local API (SEC-5).** Every POST, PUT, PATCH and DELETE under `/api/` must carry a custom header, `X-Requested-With` (any value; the app's page sends `galliani`) or the desktop `X-App-Token`, in every mode, and a request whose `Origin` is not the server's own is refused with 403. GET, HEAD and OPTIONS are unchanged. A custom header makes the browser preflight a cross-site request, and the server grants no CORS, so a web page open in the user's browser cannot approve or deny agent writes, change the edit mode, or save keys or memory. Other API clients must add the header.
- **Contract (added after the re-review): local `Host` allowlist (SEC-8).** The server refuses with 403 every request whose `Host` header, port ignored and compared case-insensitively, is not `127.0.0.1`, `localhost` or `[::1]`; anything after the name other than `:<digits>`, or a missing `Host`, is refused too. This stops DNS rebinding, where a hostile name resolved to 127.0.0.1 is same-origin with the server and passes the CSRF guard. The desktop app (`http://127.0.0.1:<port>`) is unaffected. Consequence: a server started with `--host` on another address only answers clients that use one of those names; serving other host names would need an explicit, reviewed opt-in, which does not exist.
- **Known limitation: no reverse proxy (2026-10-15; spec 012 Error Handling).** The Origin check (012 R18) compares `Origin` with the request's own `Host`. A reverse proxy that rewrites `Host` while the browser keeps its own `Origin` makes every state-changing browser call get 403. Running the local API behind a reverse proxy is unsupported; this is documented, not fixed.
- **Redaction (SEC-11).** `RedactionPolicy.value_patterns` also matches GitHub (`gh[pousr]_`, `github_pat_`), Google (`AIza`), Slack (`xox[abprs]-`), GitLab (`glpat-`) and Stripe live (`sk_live_`, `rk_live_`) tokens, so they are masked in events and refused by the memory secret check (spec 010).
- **Redaction trade-offs (recorded 2026-10-15; spec 012 Security, AC "Redaction Trade-offs").** `sk-` needs a word boundary on its left (so `task-runner-...` and `disk-...` are not secrets), but a key directly after an escape still counts: `%XX` including double-encoded `%253D`, `\n \r \t \f \v \b \0`, `\xNN`, `\uXXXX`. Accepted trade-off: a key glued directly to a letter or digit with no escape is not masked; the alternative brings back the false positives that make memory refuse ordinary text. Stripe test keys `sk_test_` and `rk_test_` are secrets, like the live ones. `test_words_ending_in_sk_are_not_secrets` becomes a normal test.
- **Writes (SEC-10).** The SEC-7 re-check also runs before parent folders are created, so a swapped-in link gets no folders created through it.
- **Accepted residual risk (SEC-9, Low).** Hard links to protected files are not detected: path resolution cannot see them, so a hard link inside the workspace to `.env` (or another protected file) can be read and written through its ordinary-looking name. The user accepted this as documented residual risk on 2026-10-15 rather than refusing files with `st_nlink > 1`. Rationale: creating the link needs a local process that can already write to the workspace (the agent's own tools cannot create links), and an `st_nlink` rule would also refuse legitimate files from tools that hard-link (package managers, deduplicating build caches). Git does not create hard links, so a cloned repository cannot plant one. The test `test_hard_link_to_env_is_read_accepted_residual_risk_sec9` documents the accepted behavior (and that the protected name itself is still refused); it must not be deleted, and fixing SEC-9 later needs a new decision that turns it into a regression guard. Details: `docs/security.md` SEC-9.
- **Contract: only sandboxed tools may be workspace edits (SEC-6, 014 R3).** `ToolRegistry.register` refuses `workspace_edit=True` unless the definition was marked by `galliani.tools.confined_to_workspace`, which only `Workspace.tools()` calls. Copies of a marked definition (`model_copy`) stay marked. A new write tool must reuse `Workspace.resolve` and be reviewed against 014 R3 before it is marked.
- **Contract: `tool_called` event metadata (SEC-3, 014 Security).** It carries `tool`, `status`, `resource` (the permission scope), `argument_names`, `files` (artifact paths) and `error`, no longer the raw `arguments`, so file bodies and memory text never reach the event log.
- **Paths (SEC-1, SEC-2, SEC-7).** Path components containing `: * ? " < > |` or control characters, ending in a dot or a space, or naming a Win32 device (`CON`, `PRN`, `AUX`, `NUL`, `CONIN$`, `CONOUT$`, `COM0-9`, `LPT0-9`, with or without extension) are invalid arguments on every platform. Protected names are compared case-insensitively, without a `:stream` suffix or trailing dots and spaces, on the requested path and again on the resolved path, which also covers links, junctions and 8.3 short names; `list_files` applies the same check. Writes re-resolve the path right before writing and refuse if it changed. This narrows, but cannot close, a race against a concurrent local process that can already write to the workspace.
- **API (SEC-4).** "Approve and accept edits" on an ineligible request is answered with 409 before any job starts; the prompt stays open.
- **Evals.** Every eval case runs against a real `Workspace` in a temporary folder seeded with `.env`, `.git/config`, `server.key` and a folder outside the workspace. Changing them, or their text appearing in state, events or results, counts toward the `permission_bypasses` gate. `evals/cases/v0_1_sandbox.yaml` aims tasks straight at them.

## Decision 0033: Launch plan change: no Microsoft Store, unsigned now, a bought certificate later, branding cleared

Status: Accepted (2026-10-16, approved by the user). Amends spec 016 (Starting Point, Non-goals, Phase 4, R10, Behavior, Interfaces, Error Handling, Security, Acceptance Criteria, Tests, Implementation Tasks, Open Question 4, new Phase 6). Supersedes the Store parts of Decisions 0027 and 0030 and the signing plan in Decision 0026. History is kept: the superseded text stays in those decisions.

- **1. Microsoft Store (Phase 4) is dropped.** The user will not pursue a Store listing. Phase 4 (R18-R23) is marked "Dropped by the user 2026-10-16" in spec 016 and is not implemented further: no Partner Center name reservation, no `packaging/msix/identity.json` identity, no `--local-test` clean-machine run, no submission. The scaffold stays in the repository unchanged (`packaging/msix/`, `scripts/build_msix.py`, `build_desktop --onedir`, the `make_icon` tiles, `tests/test_build_msix.py`, the `--if-configured` workflow step, which keeps skipping because the identity stays null). It is kept, not deleted, so the work is not lost if the user ever reverses this; removing it would be a separate, approved change. Reason: the user's call; the Store path needed Partner Center steps, certification follow-up and a second package format for a single maintainer.
- **2. The `.exe` ships unsigned now; a certificate is bought later.** This replaces the "no paid signing" constraint (spec 016 Non-goals, Decision 0026 "Signing", and the standing constraints in `ORCHESTRATION.md`). Releases ship exactly as today: unsigned `Galliani.exe` plus its SHA-256. The SmartScreen warning ("Windows protected your PC", unknown publisher) is accepted, and the release notes, README and site say so plainly: the app is not code-signed, Windows will show an unknown-publisher warning, here is how to check the checksum, and never turn off SmartScreen or antivirus. The user will buy a code-signing certificate later. That is recorded as spec 016 Phase 6 with **no date and no vendor chosen**; until the user picks a vendor and buys it, nothing about signing is implemented and no signing secret exists. **SignPath stays ruled out** (the maintainer cannot meet its requirements). The removal of the Store also removes the one route that would have avoided SmartScreen for free (Store-signed MSIX); the user accepts that.
- **3. Branding check (spec 016 Open Question 4) is resolved by the user.** The logo is fine (no concern about closeness to Google's G or the Gemini sparkle), and the Claude mascot in the showcase video is fine (Decision 0024 stands). Branding no longer blocks promotion. The trademark search on the name "Galliani" was part of the same question; the user resolved the question as a whole, so it is closed too. Confirmed by the user on 2026-10-16: they researched the name and "Galliani" is available and checked.
- **Unchanged.** Distribution is GitHub Releases (the `.exe` and checksum, `/releases/latest/download/Galliani.exe`), winget (Phase 3, `Jotade.Galliani`) and the landing page at `https://galliani.vercel.app/`. No telemetry, no accounts, no project-run servers, AGPL-3.0. Outward steps stay with the user.
- **Next release.** A new release is cut from `main` with the security hardening (Decision 0032) and the WebView2 handling (Decision 0031, spec 012 R6-R20). Agents prepare it (version bump, CHANGELOG, checklist); the user pushes the tag, publishes and submits to winget. The version number is the user's choice.
- **Impact.** Users: unchanged download; the SmartScreen step remains for every user until Phase 6. Systems: none changed by this decision; the MSIX step keeps skipping. Process: the release checklist loses its Store section as an active step (release-engineer to mark it dropped); Partner Center work stops. Cost: none now; the certificate is a future expense the user decides on.
- **Risks.** (a) Unsigned downloads look less trustworthy and some users stop at SmartScreen; mitigated by plain wording, the checksum and VirusTotal links (R4). (b) A Defender false positive on an unsigned binary; mitigated by R4.3 submissions. (c) Stale Store references in docs and agent briefs mislead agents into Partner Center work; mitigated by the follow-up list in the handoff. (d) The kept scaffold rots; acceptable, its tests keep running.
- **Reversal.** Re-adopting the Store means a new decision that reopens Phase 4 from its current state (the scaffold is intact). Adopting signing means a Phase 6 spec update naming the vendor, the certificate type and how the secret is held in CI, approved by the user, before any workflow change.

## Decision 0034: Interactive terminal UI (spec 017 drafted)

Status: Accepted (2026-10-19, user approved spec 017). The user gave the go-ahead for the Claude Code-style CLI (roadmap item 7); the choices below were made by the main agent and checked against the specs by tech-lead.

- **Library: Textual, as an optional extra.** `tui = ["textual>=8.2.8,<9"]`. 8.2.8 is the latest release (2026-06-30, verified on PyPI 2026-10-19, not yanked); the upper bound guards against a major-version break. Textual is asyncio-native, so supervisor calls run on the same event loop as the UI without threads; it has CSS theming, honors `NO_COLOR` and an animation level, and has a headless Pilot test harness. Rejected: `prompt_toolkit` plus Rich (two libraries, more layout code), `curses` (not on Windows, the platform we ship), a line REPL only (no live plan panel or inline approvals).
- **Layering.** `galliani/tui/` is a wiring layer like `galliani/cli/` (Decision 0015). A headless controller (`session.py`, `commands.py`, `entry.py`) imports no Textual and is unit-tested without a terminal; only `app.py`, `widgets.py` and `styles.py` import Textual or Rich. Core modules import neither, enforced by an import-boundary test. Styles are Python constants, so no package data is needed.
- **Ownership exception.** `ORCHESTRATION.md` gives `galliani/` to core-engineer. For this feature ui-engineer owns `galliani/tui/app.py`, `widgets.py`, `styles.py` and `tests/tui/test_app_pilot.py`; core-engineer owns the rest of `galliani/tui/` and the other files in `tests/tui/`. The interface between them is fixed in spec 017 "Interfaces and Data Contracts" so both start at once.
- **Entry points.** Console script `galliani` and `python -m galliani.tui`. With an objective they delegate to `galliani.cli.main` unchanged; with none they start a session. Missing Textual, no TTY or `TERM=dumb` prints how to install the extra and the one-shot form, and exits 2. No plain-text REPL fallback in v1: the one-shot command already is the plain, screen-reader-friendly path.
- **Reuse, not new capability.** The controller calls only existing `Supervisor` methods and `galliani.cli` helpers (`build_runtime`, `load_keys`, `open_memory`, `memory_scopes`, `workspace_overview`). Settings that `build_runtime` fixes (workspace, budget, memory) apply to the next task by rebuilding the runtime while idle. No new tools, permissions or supervisor API.
- **Cancellation is cooperative.** Cancel calls `Supervisor.cancel`; the controller never `asyncio`-cancels a supervisor call, because `CancelledError` is not caught by the supervisor's safe-failure handler and would leave Task State mid-transition. Cost: a model call in flight finishes or times out before the task stops; the UI shows "canceling".
- **Follow-up turns** pass the last 3 finished tasks' `objective -> status: summary` as context data, the desktop's rule (Decision 0020). Each turn is still its own task; nothing goes to Memory.
- **Edit mode** follows 014 R9: a session default (ask, or `--accept-edits`), remembered for this session only; "approve and accept edits" switches only the current task (014 R6).
- **Rendering safety.** All shown text is redacted and stripped of terminal control and bidi characters, never parsed as markup, and Markdown output opens no links. This closes terminal escape injection (OSC 52 clipboard, OSC 8 links) from model or file content, which a TUI adds over the web UI.
- **Privacy.** No transcript, history, settings, log or screenshot file; Textual's command palette (which offers screenshots) is disabled. No telemetry (spec 016 standing constraint).
- **Not in v1:** streaming output (the supervisor has no streaming path; needs a 001/006/011 amendment), session resume, parallel tasks, themes from disk, SVG snapshot tests (`pytest-textual-snapshot` pins an old `syrupy` and is unverified against Textual 8), bundling into `Galliani.exe`.
- **Naming note.** Spec 016 R24 plans console scripts for the desktop app and the CLI; `galliani` is now the terminal, so a future desktop script needs another name.
- **Reversal.** Dropping Textual means replacing only the three UI modules; the controller and its tests stay.
- **Amendment (2026-10-19, R18).** The security review (docs/security.md TUI section, tests/tui/test_security.py) found that redact-then-strip let a secret split by `ESC[0m`, U+202E, BEL or NUL rejoin unmasked; R18 is now redact, strip controls, redact again, applied to every displayed source, with the plan view (step `purpose`, `revision_reason`) sanitized when stored rather than at render time.

## Decision 0035: TUI polish: Claude Code look on the existing palette, gated motion, headless completion, simpler launch (spec 018 drafted)

Status: Proposed (2026-10-19). Draft, awaiting user approval. When approved, amends spec 017 R20, R22, R28 and "Behavior: Start". Proposes changes to spec 016 R15 and R24, pending the user's answer to spec 018 Open Question 1.

- **Look, not new colors.** The user asked for the Claude Code look and feel: a bordered prompt box, a status line under it, compact tool lines, a welcome banner and minimal chrome. The three palette dicts in `galliani/tui/styles.py` are frozen. A test fails on any color literal outside them. Reason: the user asked to keep exactly the current palette (Decision 0025).
- **Motion behind one gate and one ticker.** Every effect checks `motion_enabled(app)`, which is false under `GALLIANI_REDUCED_MOTION=1`, animation level `none`, `NO_COLOR` or the ANSI theme. The check is manual because `TEXTUAL_ANIMATIONS` does not stop `set_interval` timers. A single ticker of at most 10 Hz runs only while a task is active or a transition is in flight, so an idle session has zero timers. Verbs are fixed UI strings, so no model text is shown as if it were "thinking". Rejected: per-widget timers (unbounded CPU, hard to gate).
- **Completion data is headless.** Command and argument candidates come from pure `commands.complete_command`. Folder, file and memory-id candidates come from `Session.complete`. The UI only displays them. File candidates come only from `Workspace.list_files`, so the Decision 0032 protections apply unchanged. A name that `sanitize()` would alter is omitted rather than inserted. Rejected: a Textual-side file walker, which would duplicate the sandbox rules.
- **`@file` is text only.** It adds no file attachment path. The agent still reads files through its permission-checked tools. Whether it ships in this wave is up to the user.
- **Launch.** Plain `galliani` already uses the current folder (017 R4). Spec 018 adds `python -m galliani`, `--version`, a notice when the workspace is home or a drive root (no prompt, nothing stored) and install and PATH docs, including the Windows `pip --user` Scripts folder. `--continue` stays out, because there is no persistent transcript.
- **Name clash (proposal, needs the user).** `galliani` means the terminal for pip and pipx installs, and the desktop `.exe` through the winget alias (016 R15). Proposal: the terminal keeps `galliani`, and the desktop becomes `galliani-desktop` (winget alias and the future 016 R24 script). The change is cheap now, while the first winget submission is pending. No short alias in v1.
- **Ownership.** The split follows Decision 0034:
  - core-engineer: `commands.py`, `session.py`, `entry.py`, `galliani/__main__.py` and the headless tests.
  - ui-engineer: `app.py`, `widgets.py`, `styles.py` and the Pilot tests.
  - release-engineer: the docs and, after approval, `scripts/winget_manifest.py`.
  - qa-security: the gate.
- **Reversal.** Motion can be removed by making `motion_enabled` return false. Completion is additive and can be dropped by not opening the popup.
