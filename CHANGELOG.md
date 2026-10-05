# Changelog

All notable changes to Galliani are recorded here.

This project follows spec-driven development. Changelog entries should reference the specs that motivated the change.

## Unreleased

### Added

- New logo as the app icon and in-app logo (Decision 0025): the icons and favicon are generated from `assets/logo.png`, and the UI palette moves from blue and violet to the logo's graphite and silver.
- Showcase video (Decision 0024): `video/` Remotion project. It is a 28-second greyscale, single-shot product showcase: a coding prompt is routed to Sonnet 5.5 (the Claude mascot high-fives the robot), with the model and cost always visible, savings against Opus 5.5 at the end, and the new logo.
- Desktop UI redesign (spec 012, Decision 0023): icon rail, Home dashboard with recent tasks and totals, conversation header with tabs (Overview, Plan, Activity, Files, Settings), an agent progress stepper with model and tools, and a compact final response that folds code and does not repeat file contents.
- Initial spec-driven documentation structure.
- v0.1 orchestration objective: objective, plan, routing, action/tool, observation, verification, replan/retry, done.
- Root project guidance for Agent Supervisor architecture.
- Specs for foundation, agent core, task state, model router, planner, tool system, execution engine, verification, replanning, permissions, memory, observability, desktop UI, and evaluation.
- Architecture and workflow documentation.
- `galliani/` runtime implementing the v0.1 loop (specs 000-009, 011, 013): Task State with transition table and audited patches (002), redacted lifecycle events (011), permission policy with least-privilege approvals (009), schema-validated tool system (005), provider-neutral router and adapter boundary (003), deterministic planner and plan validation (004), deterministic verifier (007), execution engine with fallback and cancellation (006), bounded retry/replan (008), and the supervisor loop with approve/deny/cancel (001).
- `tests/core/`: unit and integration tests mapped to spec acceptance criteria.
- `evals/cases/v0_1_loop.yaml` and `python -m galliani.evaluation`: v0.1 fixtures and blocking quality gates (013).
- Decisions 0006-0011 in `docs/decisions.md`.
- Provider bridge `galliani/providers/app_bridge.py`: `config/models.yaml` models become Agent Workers (Decision 0012).
- `ModelPlanner` and `ModelSemanticVerifier` (specs 004, 007; Decision 0014).
- `Supervisor.clarify` to resume after a clarification question (Decision 0013).
- Workspace toolkit and `python -m galliani.cli` with interactive approvals (Decision 0015).
- CLI `--events FILE` (redacted JSON Lines event log), plan outline and per-run usage/cost summary.
- Per-task spending cap: `LoopLimits.max_cost_usd` / CLI `--budget`; extending it needs approval (spec 009 R3).
- Agentic eval fixtures `evals/cases/v0_1_agentic.yaml` (model planner, untrusted plans, spending cap, user answers) and `docs/release-checklist.md` (spec 013).
- Desktop UI for the agent (spec 012, Decision 0018): Agent page with objective form and folder picker, live plan and activity, approval and question cards, verified result with files written, memory indicator, reconnect banner; `/api/agent/*` with long polling; `galliani/viewmodel.py` view models built only from redacted state.
- Durable memory (spec 010, Decision 0019): JSON store in the app data folder, `user` and per-folder scopes, deterministic scoped retrieval before planning, approval-gated `remember` tool, secrets never persisted, memory API, eval gates `unauthorized_memory_writes` and `secret_memory_persistence`.
- Chat and Agent conversations in one chat screen (Decision 0020): composer switch, teal accent for agent conversations, task reply cards, per-conversation folder, Memory page; semantic verifier gets source data.
- `write_files` workspace tool (Decision 0021, specs 005/009): several files of any type in one step and one approval, from a file list or a model-generated `=== path ===` bundle, so multi-file builds fit the 5-step plan limit; `.env.example`-style templates are no longer protected.
- Accept-edits mode (spec 014, Decision 0022): opt-in per task, workspace file writes run without a prompt while every other restricted action still asks. Composer toggle, "Yes, and accept edits" on write approvals, task badge, and new/overwritten labels in the UI; `--accept-edits` and the `a` answer in the CLI; `edit_mode` in the agent API; eval fixtures and the `unaudited_auto_approvals` gate.
- Remotion explainer video spec (spec 015): vertical-first, fast kinetic typography video brief for explaining Galliani's supervisor loop, Agent Workers, provider adapters, Task State vs Memory, verification, retry/replan, and no chain-of-thought exposure.

### Fixed

- Workspace-relative path guidance, actionable tool errors and a `read_files` tool after a failed user run (Decision 0017).
- Findings from the first live provider runs (Decision 0016): JSON-tolerant equality criteria, nested/indexed `$ref` paths with descriptive failures, replanning questions pause instead of block, workspace listing given to the planner.

### Changed

- Project direction clarified around provider-neutral Agent Worker routing.

### Security

- Documented the rule that hidden reasoning and chain-of-thought must not be exposed.
