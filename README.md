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
- `specs/016-public-launch/spec.md` - first release, landing page and winget distribution.

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

**Shared memory.** The desktop app and `galliacli` share one memory file on your machine, and you can run them at the same time. Each save or delete locks the file briefly and re-reads it first, so neither app erases or brings back the other's notes, and each sees the other's changes without a restart. If the file stays busy for more than 5 seconds or cannot be read, memory shows as unavailable and you can try again; an unreadable file is never overwritten. Keeping the memory file on a network drive or in a folder synced by a cloud tool (OneDrive and similar) is not supported for use by two apps at once, because file locks are not reliable there (spec 010 Amendment A).

## Interactive terminal

`galliacli` is a full-screen terminal chat for the agent (specs 017 and 018). It needs the optional `tui` extra. The command is `galliacli`; the name `galliani` belongs to the desktop app.

Install, in order of preference:

```bash
# From a clone, recommended: pipx puts the command on PATH (run `pipx ensurepath` once)
pipx install -e ".[tui]"

# Or into a virtual environment
pip install -e ".[tui]"

# Or for your user only
pip install --user -e ".[tui]"
```

Non-editable installs (`pip install "galliani[tui]"`) still lack package data until spec 016 Phase 5, so install from a clone for now.

**Windows PATH.** `pip install --user` puts scripts in `%APPDATA%\Python\Python3XY\Scripts` (for example `Python312\Scripts`), which is not on PATH by default. Add it for your user in PowerShell, then open a new terminal:

```powershell
$scripts = "$env:APPDATA\Python\Python312\Scripts"   # match your Python version
[Environment]::SetEnvironmentVariable("Path", "$([Environment]::GetEnvironmentVariable('Path','User'));$scripts", "User")
```

`python -m galliani` always works, with or without PATH.

Check it, then run it in any project folder (the folder you start in is the workspace):

```bash
galliacli --version
cd path/to/your/project
galliacli
```

On Windows, `where galliacli` shows which copy is on PATH. No installer edits PATH for you.

## Calling the local API

`python -m app.api` serves the web UI and the JSON API at `http://127.0.0.1:8000`. The API only answers on your own machine and refuses anything that looks like a web page acting on your behalf (spec 012 R16-R19, Decision 0032). If you call it from a script, `curl` or a test:

- Every `POST`, `PUT`, `PATCH` and `DELETE` under `/api/` needs a non-empty `X-Requested-With` header (any value, for example `galliani`) or an `X-App-Token`. `GET`, `HEAD` and `OPTIONS` need neither.
- The `Host` header must be `127.0.0.1`, `localhost` or `[::1]`, on any port. Any other host gets `403`.
- If you send an `Origin` header, it must match the server's own address. A plain script does not need to send one.
- A refused call returns `403` with a JSON `{"detail": ...}` and changes nothing.
- Routing calls also need a provider key: set it in the server's environment, or send it in an `x-openrouter-key` header.

```bash
curl -X POST http://127.0.0.1:8000/api/route \
  -H "X-Requested-With: galliani" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Summarize this in one line."}], "mode": "auto"}'
```

The desktop app is stricter: every `/api/` call needs the per-launch app token, which other programs do not get.

## Download

Get it from the website: https://galliani.vercel.app/

Windows builds are published on [GitHub Releases](https://github.com/Jotadev-bug/Galliani/releases/latest). The direct link to the newest stable build is `https://github.com/Jotadev-bug/Galliani/releases/latest/download/Galliani.exe`. You need your own OpenRouter key, which the app keeps in your OS credential store. 

**Windows will warn about an unknown publisher.** The app is not code-signed yet, so Windows SmartScreen shows "Windows protected your PC" with an "unknown publisher" notice the first time you run it. This is expected, and it does not mean the file is damaged. To continue, choose **More info**, then **Run anyway**. A code-signing certificate is planned, which should reduce or remove the warning (Windows also builds trust in a new certificate over time). To check your download first, compare its SHA-256 with the checksum listed in the release notes on GitHub Releases. In PowerShell: `Get-FileHash .\Galliani.exe -Algorithm SHA256`.

Galliani has no accounts and sends no telemetry. The only network calls are the model requests you make with your own key.

## Website

The landing page lives in `site/` (React, Vite, Tailwind, Motion). `npm run dev` in `site/` serves it locally; `npm run build && npm run check` builds it and checks the size, link and accessibility rules from spec 016. Vercel deploys it from `main` (project root directory `site`), and runs the checks in every build.

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
