# Galliani Vault Index

Map of Content for the repository, which doubles as the Obsidian vault (vault root = repo root). Start here, then open only what the task needs. Statuses below were read from each spec's `Status` section on 2026-10-19; the spec itself is always the authority.

## Core documents

| Note | What it is |
|---|---|
| [[PROJECT]] | Product definition: what Galliani is and the supervised loop |
| [[AGENTS]] | Rules for every AI assistant: spec-first workflow, architecture rules, review checklist |
| [[ORCHESTRATION]] | How the coordinator dispatches role agents and what each one owns |
| [[docs/roadmap]] | Prioritized plan, monetization options, future work |
| [[docs/decisions]] | Decision records (0001 onward); the "why" behind each spec |
| [[docs/architecture]] | High-level flow and responsibilities |
| [[docs/security]] | Security boundaries, core rules, review results and trust boundaries |

Also useful: [[docs/agent-loop]], [[docs/tool-system]], [[docs/model-routing]], [[docs/routing]], [[docs/release-checklist]], [[docs/benchmark]], [[docs/summary]]. Templates: [[docs/templates/spec-template]], [[docs/templates/adr-template]].

## Specs

`specs/` is authoritative. If a request conflicts with a spec, stop and get the spec changed first.

| # | Title | Status | Purpose | Link |
|---|---|---|---|---|
| 000 | Foundation | Approved (v0.1) | Shared vocabulary, invariants and product boundaries | [[specs/000-foundation/spec\|000]] |
| 001 | Agent Core | Approved (v0.1) | The supervisor loop: plan, route, execute, observe, verify, replan | [[specs/001-agent-core/spec\|001]] |
| 002 | Task State | Approved (v0.1) | Active run state, kept separate from Memory | [[specs/002-task-state/spec\|002]] |
| 003 | Model Router | Approved (v0.1) | Provider-neutral routing from requests to Agent Workers | [[specs/003-model-router/spec\|003]] |
| 004 | Planner | Approved (v0.1) | Turn an objective into a verifiable plan | [[specs/004-planner/spec\|004]] |
| 005 | Tool System | Approved (v0.1) | Register, validate, authorize, run and observe tools | [[specs/005-tool-system/spec\|005]] |
| 006 | Execution Engine | Approved (v0.1) | Run plan steps through workers and tools | [[specs/006-execution-engine/spec\|006]] |
| 007 | Verification | Approved (v0.1) | Decide whether a step or task meets its criteria | [[specs/007-verification/spec\|007]] |
| 008 | Replanning | Approved (v0.1) | Bounded retry and replanning | [[specs/008-replanning/spec\|008]] |
| 009 | Permissions | Approved (v0.1) | Permission checks and user approval flows | [[specs/009-permissions/spec\|009]] |
| 010 | Memory | Approved (v0.1) | Durable memory, separate from Task State | [[specs/010-memory/spec\|010]] |
| 011 | Observability | Approved (v0.1) | Events and logs without leaking reasoning or secrets | [[specs/011-observability/spec\|011]] |
| 012 | Desktop UI | Approved, with approved amendments (WebView2, local API guard) | The desktop app front end | [[specs/012-desktop-ui/spec\|012]] |
| 013 | Evaluation | Approved (v0.1) | Evaluation strategy and quality gates | [[specs/013-evaluation/spec\|013]] |
| 014 | Accept-Edits Mode | Approved, hardened 2026-10-15 | Per-task opt-in to file writes in the workspace without per-write approval | [[specs/014-accept-edits/spec\|014]] |
| 015 | Remotion Video | Draft | Short kinetic marketing video built with Remotion in `video/` | [[specs/015-remotion-video/spec\|015]] |
| 016 | Public Launch | Approved, amended 2026-10-16 (no Store; unsigned until a certificate is bought) | Release, landing page, winget, PyPI, signing | [[specs/016-public-launch/spec\|016]] |
| 017 | Interactive CLI (terminal UI) | Implemented; command is `galliacli` | Claude Code-style full-screen terminal front end | [[specs/017-interactive-cli/spec\|017]] |
| 018 | TUI polish | Implemented, reviewed 2026-10-20 | Look and feel, motion, `/` and `@` completion, easier launch | [[specs/018-tui-polish/spec\|018]] |

## How agents use this vault

1. Read this index first. Do not scan `specs/` or `docs/` wholesale.
2. Read [[AGENTS]] and [[PROJECT]], then load only the specs your task names, plus the decision records they cite.
3. State the scope in terms of spec requirement numbers (R1, R2, ...) before editing.
4. Edit only the paths your role owns ([[ORCHESTRATION]]). Other workers edit the rest in parallel.
5. When a spec and reality disagree, ask for the spec to change. Do not bend it.
6. Update this index when a spec is added or its status changes.

## Naming conventions

- Specs: `specs/NNN-short-name/spec.md`, numbered in order, three digits. One folder per spec.
- Decisions: `## Decision NNNN: title` in [[docs/decisions]], four digits, status Proposed or Accepted.
- Docs: lowercase, hyphenated file names in `docs/`.
- Links: wikilinks with the path from the vault root and no extension, for example `[[docs/roadmap]]` or `[[specs/018-tui-polish/spec|018]]`.
- Terminal command is `galliacli`; the desktop app and winget alias stay `galliani`.

## Where to record what

| What | Where |
|---|---|
| New or changed behavior, requirements, acceptance criteria | A spec in `specs/` |
| Why a design choice was made | [[docs/decisions]] |
| What is planned next, order and owners | [[docs/roadmap]] |
| Public behavior, data contracts, security expectations | [[docs/architecture]], [[docs/security]] |
| What shipped in a version | `CHANGELOG.md` |
| Release steps | [[docs/release-checklist]] |
| Assistant's own durable notes (preferences, corrections) | Claude Code memory, not the repo. This is tooling and unrelated to the product Memory of spec 010 |
