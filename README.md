# Galliani

Galliani is an Agent Supervisor and orchestration system for spec-driven AI work. It receives a user objective, creates and maintains a plan, routes work to appropriate Agent Workers, executes approved tools, observes results, verifies outcomes, replans or retries when needed, and finishes only when the objective is satisfied.

Galliani is provider-neutral. Models are Agent Workers. Providers are adapters. Tools are explicit capabilities. Memory is not task state. Private reasoning is never exposed.

## v0.1 Objective

```text
objective -> plan -> routing -> action/tool -> observation -> verification -> replan/retry -> done
```

v0.1 must prove the full loop with a small, deterministic core before adding advanced autonomy.

## Principles

1. Specs are the source of truth.
2. The supervisor owns orchestration, not model-specific behavior.
3. Agent Workers receive bounded tasks and return structured results.
4. Providers are interchangeable behind stable contracts.
5. Task State tracks the active run; Memory stores durable user/project knowledge.
6. Tools require explicit schemas, permissions, and observable results.
7. Verification is a first-class step, not an afterthought.
8. Chain-of-thought or hidden reasoning must never be exposed in logs, UI, APIs, or stored artifacts.

## Repository Map

```text
galliani/
|-- README.md
|-- AGENTS.md
|-- PROJECT.md
|-- CHANGELOG.md
|-- CONTRIBUTING.md
|-- LICENSE.md
|-- specs/
|-- docs/
`-- evals/
```

## Specification Index

- `specs/000-foundation/spec.md` - product invariants and shared vocabulary.
- `specs/001-agent-core/spec.md` - supervisor loop and lifecycle.
- `specs/002-task-state/spec.md` - active run state model.
- `specs/003-model-router/spec.md` - worker selection and provider abstraction.
- `specs/004-planner/spec.md` - plan creation and maintenance.
- `specs/005-tool-system/spec.md` - tool registry, execution contracts, and results.
- `specs/006-execution-engine/spec.md` - step execution and orchestration.
- `specs/007-verification/spec.md` - outcome validation.
- `specs/008-replanning/spec.md` - retry and plan revision.
- `specs/009-permissions/spec.md` - user approval and capability boundaries.
- `specs/010-memory/spec.md` - durable memory separated from task state.
- `specs/011-observability/spec.md` - structured logs, events, metrics, and traces.
- `specs/012-desktop-ui/spec.md` - desktop user experience.
- `specs/013-evaluation/spec.md` - quality gates and benchmark methodology.

## Running the v0.1 Core

The provider-neutral supervisor lives in `galliani/`. The older prompt router in `app/` is separate and unchanged.

```bash
python -m pytest tests/core
python -m galliani.evaluation evals/cases
```

The tests and evals are deterministic: they use fixture-driven planners and scripted worker adapters.

To run a real objective against your configured providers (keys from `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or the desktop app's OS credential store):

```bash
python -m galliani.cli "Summarize agent-loop.md in five bullets and save it as summary.md" --workspace docs
```

A model plans the work, the supervisor validates the plan, cheap workers run the bounded steps, and verification gates completion. File writes pause for a y/N approval scoped to the exact path, and a task pauses again if its estimated model spend passes `--budget` (default $0.50). The agent can only touch files inside `--workspace`, which must be an existing folder (here the repo's `docs/`).

Before a release, follow `docs/release-checklist.md`.

## Development Workflow

1. Read the relevant spec.
2. Confirm dependencies and non-goals.
3. Implement the smallest behavior that satisfies acceptance criteria.
4. Add tests named by the spec.
5. Run evaluation where applicable.
6. Update documentation only when behavior changes.

No implementation work should begin without a matching approved spec.
