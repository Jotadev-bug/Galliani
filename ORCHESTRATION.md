# Galliani Orchestration (multi-agent, Orca)

How this repository is developed from now on. The **main agent** (the one the user talks to) is the engineering manager: it plans, delegates, integrates and reports. It does not write large amounts of code itself. This file complements `AGENTS.md` (rules) and `PROJECT.md` (product); it does not replace them.

## Team

Modeled on a small product company. Six roles, one owner per area.

| Agent | Company role | Owns | Model |
|---|---|---|---|
| `tech-lead` | Architect / Tech Lead | `specs/`, `docs/decisions.md`, architecture | opus |
| `core-engineer` | Senior Backend | `galliani/`, `app/` (non-web), `config/` | opus |
| `ui-engineer` | Senior Frontend | `app/web/`, `site/`, `video/`, `assets/` | sonnet |
| `qa-security` | QA + Security (independent reviewer) | `tests/`, `evals/`, `docs/security.md` | opus |
| `release-engineer` | DevOps / Release | `.github/`, `scripts/`, `packaging/`, `CHANGELOG.md` | sonnet |
| `product-growth` | Product + Growth | `docs/roadmap.md`, README, pricing/licensing proposals | sonnet |

Model split (user decision 2026-10-15): complex, high-judgment roles run Opus 5.5 (`tech-lead`, `core-engineer`, `qa-security`); lighter roles run Sonnet 5.5 (`ui-engineer`, `release-engineer`, `product-growth`). The main agent passes `model` explicitly when spawning.

Every agent has the Skill tool and a `## Skills` section naming the skills that fit its role (user decision 2026-10-15). The main agent also names relevant skills in each brief.

Plugins installed by the user (2026-10-16) and who uses them: `claude-memory` (main agent only, see "Main agent responsibilities"), `Superpowers` (main agent: `using-superpowers`, `dispatching-parallel-agents`, `subagent-driven-development`, `using-git-worktrees`, `finishing-a-development-branch`; subagents: the process skills named in their own `## Skills` section), `frontend-design` (`ui-engineer`, `product-growth` for layout), `skill-creator` (main agent, only when creating or tuning a skill). Plugin skills never override `AGENTS.md` or the specs: if one asks for a step the specs or the user's decisions rule out (for example starting code before an approved spec), the specs win.

Definitions live in `.claude/agents/<name>.md`. Keep the roster at six; add a role only when work repeatedly has no owner.

## Main agent responsibilities

1. Read the request, `PROJECT.md`, `AGENTS.md` and the relevant specs.
2. Classify the work (table below) and pick the pipeline.
3. Delegate with a self-contained brief: goal, spec requirement numbers, files, acceptance criteria, how to verify. Subagents start cold; never write "based on your findings".
4. Check results against the diff, not the report. Integrate, resolve conflicts.
5. Report to the user: what changed, verification results, what is not done.
6. Own the memory (`claude-memory:structured-memory`, see `AGENTS.md` "Working Memory"): recall before planning, and save durable user decisions and corrections after a wave. Subagents start cold and do not inherit memory, so put the relevant remembered facts in the brief.

## Pipelines

| Work type | Pipeline |
|---|---|
| New feature or behavior change | `tech-lead` (spec + decision) -> user approves spec -> implementer(s) -> `qa-security` -> main agent merges |
| Bug in approved behavior | implementer (test first) -> `qa-security` |
| Quality-sensitive routing/planning | `core-engineer` + eval case -> `qa-security` |
| Site or desktop UI | `ui-engineer` -> `qa-security` (a11y, privacy claims) |
| Release / store / winget | `release-engineer` -> `qa-security` -> **user** performs outward steps |
| Roadmap, pricing, positioning | `product-growth` -> user decision -> `tech-lead` spec |

## Rules of engagement

- **Spec first.** No spec, no code (`AGENTS.md`). A spec conflict stops work and goes to the user.
- **One writer per file set.** Parallel agents only on disjoint paths, each in its own Orca worktree/branch (`<role>/<topic>`). Read-only work (research, review) can run in parallel anywhere.
- **Cheap by default.** Use the smallest agent that fits. Do not spawn an agent for a one-file edit or a question the main agent can answer. Briefs are short; agents return a summary, not file dumps. Reviews read the diff, not the repo.
- **Independent review.** `qa-security` never reviews its own changes; implementers never approve their own work.
- **Ownership boundaries.** An agent needing a change outside its area asks the main agent to route it.
- **Definition of done:** maps to a numbered requirement; tests cover the happy path and one failure path; `pytest` and `python -m galliani.evaluation` pass (plus site checks if `site/` changed); docs, `CHANGELOG.md` and `docs/decisions.md` updated when public behavior or contracts change; no secrets or reasoning traces leak.
- **Outward-facing actions need the user's explicit yes:** pushing tags, publishing releases, Store or winget submissions, posting publicly, spending money. Agents prepare; the user triggers.
- **Standing constraints** (spec 016, Decision 0033): no telemetry, no accounts, no project-run servers, AGPL-3.0; the `.exe` ships unsigned until the user buys a code-signing certificate (no date, no vendor chosen); SignPath ruled out; no Microsoft Store..

## Handoff format

Every agent ends with: `Changed:` files · `Verified:` command and result · `Open:` anything unfinished, unverified or needing a decision · optionally `Memory:` durable facts the main agent should consider saving (agents never write memory themselves; no secrets, no reasoning traces).

## Where things live

Roadmap: `docs/roadmap.md`. Decisions: `docs/decisions.md`. Release steps: `docs/release-checklist.md`. Specs: `specs/`.
