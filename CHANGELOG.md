# Changelog

All notable changes to Galliani are recorded here.

This project follows spec-driven development. Changelog entries should reference the specs that motivated the change.

## Unreleased

### Added

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

### Fixed

- Workspace-relative path guidance, actionable tool errors and a `read_files` tool after a failed user run (Decision 0017).
- Findings from the first live provider runs (Decision 0016): JSON-tolerant equality criteria, nested/indexed `$ref` paths with descriptive failures, replanning questions pause instead of block, workspace listing given to the planner.

### Changed

- Project direction clarified around provider-neutral Agent Worker routing.

### Security

- Documented the rule that hidden reasoning and chain-of-thought must not be exposed.
