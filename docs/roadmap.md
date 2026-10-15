# Galliani Roadmap

Updated 2026-10-15. Items are proposals ordered by priority. Each needs an approved spec before code (`AGENTS.md`); the "Spec" column says which. Items marked **needs user decision** change a standing constraint from spec 016 and are not started until the user approves.

State today: `v0.1.0` is published; landing page is live on Vercel; winget manifest generator and MSIX scaffold are done (branch `msix-phase-4`); first winget and Store submissions are still manual and pending.

## Now: finish the launch (spec 016)

| # | Item | Owner | Notes |
|---|---|---|---|
| 1 | Merge `msix-phase-4`; reserve the name in Partner Center and commit `packaging/msix/identity.json` | release-engineer + user | User does the Partner Center steps |
| 2 | Clean-machine test: `.exe`, `winget install --manifest`, `--local-test` MSIX; replace the drawn SmartScreen stand-in with a real screenshot | release-engineer + user | |
| 3 | Submit to `microsoft/winget-pkgs` and the Microsoft Store | user | Store signs the MSIX, so this also removes the SmartScreen warning for Store installs |
| 4 | Security review of agent file access and accept-edits (spec 014) before wide announcement | qa-security | Open Question 6 |
| 5 | WebView2-missing message for Windows 10 | core-engineer + ui-engineer | Needs a requirement in spec 012 first |
| 6 | Branding check (name, logo vs. Google G/Gemini sparkle, Claude mascot in the video) | user | Open Question 4; blocks heavy promotion |

## Next: make it worth using daily (1-2 months)

| # | Item | Owner | Spec |
|---|---|---|---|
| 7 | Claude Code-style interactive CLI, built on `galliani/cli` | tech-lead then core-engineer | New spec 017. **Waits for the user's go-ahead** |
| 8 | Memory completion and UI (spec 010 follow-through) | core-engineer + ui-engineer | 010 |
| 9 | Provider breadth: more adapters (local models via Ollama, direct OpenAI/Google/Anthropic keys) behind the existing adapter interface | core-engineer | 003 amendment |
| 10 | Router quality: eval suite growth, routing explanations, automated `sync_pricing` | core-engineer + qa-security | 003, 013 |
| 11 | Savings report: weekly/monthly local summary and export (CSV) | ui-engineer | 012 amendment |
| 12 | In-app update check (notify only, no auto-update; opt-in so "no telemetry" holds) | core-engineer + release-engineer | New spec; amends 016 non-goals |
| 13 | Crash-safe local diagnostics bundle the user can attach to an issue (redacted) | core-engineer | 011 |

## Later: reach and sustainability (3-6 months)

| # | Item | Owner | Spec |
|---|---|---|---|
| 14 | macOS and Linux builds (PyInstaller + pywebview already portable in principle) | release-engineer | New spec; amends 016 non-goals |
| 15 | PyPI package, trusted publishing (`pipx install galliani`) | release-engineer | 016 Phase 5 |
| 16 | Plugin/tool packs: user-installable registered tools with schemas and permission metadata | tech-lead + core-engineer | 005 extension |
| 17 | Team features: shared routing policies and budget caps as a config file, no server | core-engineer | New spec |
| 18 | Custom domain and docs site | ui-engineer + user | Open Question 2 |

## Monetization options

The project is AGPL, local-first, with no accounts, server or telemetry. That is a selling point for privacy-minded users, so monetization should come from things users choose to pay for, not from data. Ordered by fit and effort:

| Option | Effort | Fit with constraints | Notes |
|---|---|---|---|
| **A. Sponsorship** (GitHub Sponsors, Ko-fi) with a link on the site, README and in-app About | Hours | Fully compatible | Low revenue, zero risk. Do first. |
| **B. Paid Microsoft Store listing or "Supporter" Store edition** (same open-source code, convenience install + auto-updates via Store) | Low once Phase 4 ships | Compatible: source stays AGPL | Common pattern; Store handles billing and updates. Confirm Store policy on charging for open-source builds. |
| **C. Dual licensing / commercial license** for companies that cannot use AGPL | Medium | Compatible, but **needs copyright holder decision** (Open Question 3) and a contributor agreement before accepting outside PRs; lawyer review | Likely the best long-term B2B lever. Decide before taking contributions. |
| **D. Paid support and setup for teams** (SLA, onboarding, custom routing policies) | Medium | Compatible | Needs a legal entity or freelancer setup; sells consulting more than product. |
| **E. Optional paid hosted gateway** (managed key, bundled credits, sync) | High | **Breaks non-goals** (accounts, server, payments) | **Needs user decision.** Adds ops, privacy and compliance burden. Only if A-C show demand. |
| **F. Pro features in a source-available build** (team policies, advanced analytics) | Medium | Conflicts with AGPL unless the owner relicenses own code | Revisit after C is settled. |

Recommended sequence: A now, B at Store launch, decide C before accepting external contributions, measure interest through GitHub stars/issues and download counts from GitHub Releases (no in-app telemetry), then consider D/E.

Success signals to watch without telemetry: release download counts, winget/Store installs, GitHub stars and issues, sponsor count.

## Maintenance cadence

- Patch release (`0.1.x`) for fixes whenever `qa-security` is green.
- Minor release (`0.x.0`) per completed "Next" item, with a `CHANGELOG.md` entry and decision record.
- Re-run evals and the security checklist before every minor release.
- Revisit this roadmap monthly; `product-growth` proposes changes, the user decides.
