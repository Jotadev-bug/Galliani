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
|-- LICENSE
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
- `specs/014-accept-edits/spec.md` - opt-in mode that auto-approves workspace file writes.
- `specs/015-remotion-video/spec.md` - fast Remotion explainer video for Galliani.
- `specs/016-public-launch/spec.md` - first release, landing page, winget and Microsoft Store distribution.

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

In the desktop app (`python -m app.desktop`), switch the message box from **Chat** to **Agent**, pick a folder, and type a task. The agent's reply shows the plan, live activity, approvals and the verified result. The **Memory** page lists what the agent remembers between tasks; it only saves a note when you approve it.

## Download

Windows builds are published on [GitHub Releases](https://github.com/Jotadev-bug/Galliani/releases/latest). The direct link to the newest stable build is `https://github.com/Jotadev-bug/Galliani/releases/latest/download/Galliani.exe`. You need your own OpenRouter key, which the app keeps in your OS credential store. Builds are not code-signed yet, so on first launch Windows SmartScreen may warn: choose **More info**, then **Run anyway**. Each release lists the SHA-256 of the `.exe`.

## Releasing

Before a release, follow `docs/release-checklist.md`. Then bump `version` in `pyproject.toml`, commit, and push the matching tag on its own:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The `Release` workflow (`.github/workflows/release.yml`) runs the tests, builds `Galliani.exe`, runs its smoke test, and publishes the `.exe` with its checksum on GitHub Releases. Tags with a suffix, such as `v0.2.0-beta.1`, publish as pre-releases and never become the latest release. If a tag push does not start the workflow, run it by hand from **Actions > Release > Run workflow** with the tag name. The `CI` workflow runs the tests and evals on every push to `main` and every pull request.

## Development Workflow

1. Read the relevant spec.
2. Confirm dependencies and non-goals.
3. Implement the smallest behavior that satisfies acceptance criteria.
4. Add tests named by the spec.
5. Run evaluation where applicable.
6. Update documentation only when behavior changes.

No implementation work should begin without a matching approved spec.

## License

Copyright (C) 2026 Galliani contributors.

Galliani is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. It is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See [`LICENSE`](LICENSE) for the full text.
