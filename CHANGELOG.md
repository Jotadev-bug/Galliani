# Changelog

All notable changes to Galliani are recorded here.

This project follows spec-driven development. Changelog entries should reference the specs that motivated the change.

## Unreleased

### Security

- Agent file access hardening from the independent security review (specs 005, 009, 014; Decision 0032; findings SEC-1 to SEC-7 in `docs/security.md`). Protected files (`.env`, keys, `.git/`) can no longer be reached on Windows through case changes, trailing dots or spaces, `::$DATA` streams, device names, links, junctions or 8.3 short names, so accept-edits mode cannot plant a git hook and `read_file` cannot read secrets. `tool_called` events no longer carry file contents or memory text. Every state-changing `/api` call now needs an `X-Requested-With` (or desktop `X-App-Token`) header and a same-origin `Origin`, so a web page cannot approve agent writes; other API clients must send the header. "Approve and accept edits" on an ineligible prompt now answers 409. Only the workspace toolkit's own tools may be accept-edits eligible. Evals now run every case against a real workspace folder, and the `permission_bypasses` gate counts any protected or outside file that changed or leaked.
- Fixes from the independent re-review (Decision 0032; SEC-8, SEC-10, SEC-11 in `docs/security.md`). The local server now refuses (403) every request whose `Host` (port ignored) is not `127.0.0.1`, `localhost` or `[::1]`, so a hostile site rebound to 127.0.0.1 (DNS rebinding) cannot start or approve agent tasks, spend the provider key or read memory; the desktop app is unaffected, and a server started with another `--host` only answers those names. Redaction and the memory secret check now recognize GitHub (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`), Google (`AIza`), Slack (`xox[abprs]-`), GitLab (`glpat-`) and Stripe live (`sk_live_`, `rk_live_`) tokens. Writes re-check the path before creating parent folders, so a link swapped in cannot get folders created through it. Hard links to protected files (SEC-9) remain open pending a decision.
- Redaction no longer treats ordinary words ending in "sk" (`task-runner-...`, `disk-cleanup-...`) as `sk-` API keys: the pattern now needs a word boundary on its left. Real `sk-` keys at the start of text or after spaces, quotes, `=` or brackets are still masked (spec 011 R4-R5, spec 010 secret check).
- Redaction now accepts more left contexts for `sk-` keys, so a key is masked unless a letter or digit comes directly before it, and also after URL, string, hex and unicode escapes (`%3D`, `%253D`, `\n`, `\xNN`, `\uXXXX`), while ordinary words ending in "sk" are not, and it recognizes Stripe test keys (`sk_test_`, `rk_test_`) next to the live ones (spec 011 R4-R5, spec 010 secret check).
- `desktop.log` can no longer hold a secret (spec 012, Decision 0031). Every logger and every traceback now passes a redacting filter before it is written. In the windowed build, lines written to stdout are recorded in `desktop.log` as log records, so they are redacted too. `PYWEBVIEW_LOG` is no longer honoured while the app runs, so it cannot raise pywebview's log detail.

### Changed

- The `desktop` extra now pins `pywebview>=6.2,<7` (was `>=5.0`), because the WebView2 check mirrors pywebview 6.2.1's own rule (spec 012 R7). `tests/test_pywebview_pin.py` fails if the installed version or the `pyproject.toml` range leaves the pin; the release checklist requires an R7 re-check before any upgrade outside it.
- Spec 012 amended (R7, R8, R10): WebView2 detection now follows pywebview 6.2.1's rule exactly, and pywebview's Windows backend is not loaded before the check. When the check finds only the legacy engine, the app shows the "could not open its window" message box and exits with code 4.

### Added

- Clear message when Microsoft Edge WebView2 is missing on Windows (spec 012 R6-R15, Decision 0031). Before opening its window, the desktop app checks the registry, offline and read-only, with the same rule as pywebview, and never opens a window with the Internet Explorer engine. If WebView2 is missing, a native Yes/No message box (No is the default) offers Microsoft's WebView2 page, `https://developer.microsoft.com/microsoft-edge/webview2/`, which opens in your browser only if you select Yes; Galliani never downloads or runs an installer. The app then exits with code 3; a window that fails to start shows a second message with the `desktop.log` path and exits with code 4. One line goes to the local `desktop.log`, without the app token or window URL; nothing is sent anywhere. `--simulate-missing-webview2` shows the message on any machine, and `--smoke-test` adds an information-only `INFO  webview2:` line that never changes its exit code.

- Release checklist: a manual clean-machine test (`.exe`, winget, MSIX `--local-test`, Windows 10 without WebView2 with and without `--simulate-missing-webview2`, exit code 3, `desktop.log` path), a list of the steps only the user can do, and a re-run of pytest, the evals and the `docs/security.md` checklist before every minor release (specs 016 R4, R22; 012 R6-R15, approved).
- Microsoft Store packaging scaffold, Phase 4 of spec 016 (Decision 0030): `scripts/build_msix.py` builds `Galliani.msix` from a one-folder build (`build_desktop --onedir`) with `makeappx`, `make_icon` generates the Store tiles, `packaging/msix/` holds the manifest template and the Partner Center identity file, and `--local-test` makes a package signed with a throwaway certificate for testing. The Release workflow builds the package once the identity is committed, and never lets it block the `.exe`. The release checklist documents the Store steps.
- winget manifest generator, Phase 3 of spec 016 (Decision 0029): `scripts/winget_manifest.py` writes the portable-package manifest for a release, the Release workflow attaches it as `galliani-winget-<version>.zip`, and `packaging/winget/0.1.0/` holds the `v0.1.0` manifest. The release checklist documents the manual submission.

## 0.1.0 - 2026-10-06

First public release: `Galliani.exe` on GitHub Releases.

### Added

- Landing page, Phase 2 of spec 016 (Decision 0028): a React, Vite, Tailwind and Motion site in `site/` with download, video, features, install, privacy, open source and FAQ sections, and a privacy page. It is hosted on Vercel at https://galliani.vercel.app/, which builds and checks it on every push.
- Public launch plan, Phase 1 (spec 016, Decision 0027): the Release workflow can be started by hand for an existing tag, the tag check is a tested script (`scripts/release_tag.py`) that reads the version at the tag, pre-releases never become the latest release, and the release checklist adds clean-machine, VirusTotal and false-positive steps before announcing.
- AGPL-3.0 license, CI and a release pipeline (Decision 0026): tests and evals run on every push and pull request, and pushing a `v*` tag builds, smoke-tests and publishes `Galliani.exe` with its checksum on GitHub Releases.
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
