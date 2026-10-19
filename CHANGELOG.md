# Changelog

All notable changes to Galliani are recorded here.

This project follows spec-driven development. Changelog entries should reference the specs that motivated the change.

## Unreleased

### Added

- Packaging for the interactive terminal UI (spec 017 R1-R2, Decision 0034): a new optional `tui` extra (`textual>=8.2.8,<9`) and the `galliacli` console script (`galliani.tui.entry:main`; spec 018 R27). The terminal command is `galliacli`; the desktop app keeps `galliani` (winget alias, spec 016 R15), and `python -m galliani` also starts the terminal UI. CI and the Release workflow install the extra, and CI sets `GALLIANI_REQUIRE_TUI=1` so the TUI tests fail instead of skipping. The TUI is not bundled into `Galliani.exe` yet (documented follow-up); install it with `pip install ".[tui]"`.

### Changed

- The terminal console script is renamed from `galliani` to `galliacli` (spec 018 R27, Decision 0035), so it no longer clashes with the desktop app's `galliani` command. `pyproject.toml` `[project.scripts]` now has `galliacli` only; the PyPI package and the `tui` extra keep the name `galliani`. The README has an "Interactive terminal" section with the install options and the Windows PATH note (spec 018 R26), and the release checklist has a `galliacli --version` smoke step.

## 0.2.0 - 2026-10-16

This release hardens what the agent can touch on your computer and what the local server accepts, and it explains clearly what happens when Microsoft Edge WebView2 is missing or broken. `Galliani.exe` is still not code-signed (a certificate is planned), so Windows SmartScreen shows an "unknown publisher" warning on first launch.

**Breaking: API clients must send `X-Requested-With` or `X-App-Token`.** Every state-changing (non-GET) `/api` call now needs one of those headers and a same-origin `Origin`, and the server only answers the host names `127.0.0.1`, `localhost` and `[::1]`. The Galliani app itself is not affected; scripts or third-party tools that call the local API must add the header (spec 012, Decision 0032, `docs/security.md`).

### Added

- Clear message when Microsoft Edge WebView2 is missing on Windows (spec 012 R6-R15, Decision 0031). Before opening its window, the desktop app checks the registry, offline and read-only, with the same rule as pywebview, and never opens a window with the Internet Explorer engine. If WebView2 is missing, a native Yes/No message box (No is the default) offers Microsoft's WebView2 page, `https://developer.microsoft.com/microsoft-edge/webview2/`, which opens in your browser only if you select Yes; Galliani never downloads or runs an installer. The app then exits with code 3; a window that fails to start shows a second message with the `desktop.log` path and exits with code 4. One line goes to the local `desktop.log`, without the app token or window URL; nothing is sent anywhere. `--simulate-missing-webview2` shows the message on any machine, and `--smoke-test` adds an information-only `INFO  webview2:` line that never changes its exit code.
- WebView2 that is installed but fails to initialize no longer leaves an empty window that exits with code 0 (spec 012 R20, Decision 0031). When WebView2 reports the failure before the page has loaded, the app closes the empty window, shows the "could not open its window" message box and exits with code 4; `desktop.log` gets one `webview2_init_failed` line, and pywebview's own failure record, redacted. There is no timeout, so a slow start never shows the box; a start that never reports anything is still not detected (known limitation).
- winget manifest generator, Phase 3 of spec 016 (Decision 0029): `scripts/winget_manifest.py` writes the portable-package manifest for a release, the Release workflow attaches it as `galliani-winget-<version>.zip`, and `packaging/winget/0.1.0/` holds the `v0.1.0` manifest. The release checklist documents the manual submission.
- Release checklist: a manual clean-machine test (`.exe`, winget, Windows 10 without WebView2 with and without `--simulate-missing-webview2`, exit code 3, `desktop.log` path), a list of the steps only the user can do, and a re-run of pytest, the evals and the `docs/security.md` checklist before every minor release (specs 016 R4; 012 R6-R15).

### Changed

- The Release workflow's release text now states plainly that the unsigned `.exe` triggers a SmartScreen "Unknown publisher" warning, how to continue (More info, then Run anyway), where the SHA-256 is, that a certificate is planned, and never suggests turning SmartScreen off (spec 016 R25, Decision 0033). The optional MSIX step is renamed to say it is unused; the release checklist points to Decision 0033.
- Microsoft Store distribution is dropped (spec 016 R18-R23 no longer apply; user decision of 2026-10-16). `Galliani.exe` ships unsigned from GitHub Releases and winget; a code-signing certificate comes later. The MSIX scaffold (`scripts/build_msix.py`, `packaging/msix/`) stays in the repository but is unused: its identity file is empty, so the Release workflow skips it.
- The `desktop` extra now pins `pywebview>=6.2,<7` (was `>=5.0`), because the WebView2 check mirrors pywebview 6.2.1's own rule (spec 012 R7). `tests/test_pywebview_pin.py` fails if the installed version or the `pyproject.toml` range leaves the pin; the release checklist requires an R7 re-check before any upgrade outside it.
- Spec 012 amended (R7, R8, R10): WebView2 detection follows pywebview 6.2.1's rule exactly (an empty `REG_NONE` `pv` value now stops the search as it does in pywebview), and pywebview's Windows backend is not loaded before the check. When the check finds only the legacy engine, the app shows the "could not open its window" message box and exits with code 4.
- `PYWEBVIEW_LOG` is now ignored while the app runs: the app sets pywebview's log level itself (DEBUG with `--debug`, otherwise INFO), because the WebView2 failure check (R20) depends on pywebview's ERROR record (spec 012 R13, Decision 0031).
- "Approve and accept edits" on an ineligible prompt now answers 409, and only the workspace toolkit's own tools may be accept-edits eligible (spec 014).
- Evals now run every case against a real workspace folder, and the `permission_bypasses` gate counts any protected or outside file that changed or leaked (spec 013).

### Security

- Agent file access hardening from the independent security review (specs 005, 009, 014; Decision 0032; findings SEC-1 to SEC-7 in `docs/security.md`). Protected files (`.env`, keys, `.git/`) can no longer be reached on Windows through case changes, trailing dots or spaces, `::$DATA` streams, device names, links, junctions or 8.3 short names, so accept-edits mode cannot plant a git hook and `read_file` cannot read secrets. `tool_called` events no longer carry file contents or memory text. Every state-changing `/api` call needs an `X-Requested-With` (or desktop `X-App-Token`) header and a same-origin `Origin`, so a web page cannot approve agent writes.
- Fixes from the independent re-review (Decision 0032; SEC-8, SEC-10, SEC-11). The local server refuses (403) every request whose `Host` (port ignored) is not `127.0.0.1`, `localhost` or `[::1]`, so a hostile site rebound to 127.0.0.1 (DNS rebinding) cannot start or approve agent tasks, spend the provider key or read memory; the desktop app is unaffected, and a server started with another `--host` only answers those names. Writes re-check the path before creating parent folders, so a link swapped in cannot get folders created through it. Hard links to protected files (SEC-9) remain open pending a decision and are accepted residual risk for this release.
- Redaction (spec 011 R4-R5, spec 010 secret check; Decision 0032). It now recognizes GitHub (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`), Google (`AIza`), Slack (`xox[abprs]-`), GitLab (`glpat-`) and Stripe (`sk_live_`, `rk_live_`, `sk_test_`, `rk_test_`) tokens. An `sk-` or Stripe key is masked unless a letter or digit comes directly before it, including after URL, string, hex and unicode escapes (`%3D`, `%253D`, `\n`, `\xNN`, `\uXXXX`) and ANSI colour codes (`ESC[32m`, in the raw, `\x1b`, `\033`, `\u001b` and `\e` forms). Ordinary words and identifiers such as `task-runner-...`, `disk-cleanup-...` or `network_test_connectivitycheck` are no longer masked or refused by memory.
- `desktop.log` can no longer hold a secret (spec 012, Decision 0031). Every logger and every traceback passes a redacting filter before it is written, and in the windowed build, lines written to stdout are recorded as log records, so they are redacted too. The log now starts before the app picks its port, and the app waits briefly for the local server to stop before the log closes, so an early failure and the server's shutdown lines are recorded (redacted) instead of lost.

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
