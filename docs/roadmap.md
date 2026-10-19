# Galliani Roadmap

Updated 2026-10-19. Items are proposals ordered by priority. Each needs an approved spec before code (`AGENTS.md`); the "Spec" column says which. Items marked **needs user decision** change a standing constraint from spec 016 and are not started until the user approves.

State today: `v0.1.0` is published and `0.2.0` is being prepared (cut from `main` by release-engineer). Security hardening and WebView2 handling are merged (PR #7). The landing page is live on Vercel and the winget manifest generator is done. The first winget submission is still pending (user). The `.exe` ships unsigned for now. The Microsoft Store is dropped and SignPath stays ruled out.

## Now: finish the launch (spec 016)

| # | Item | Owner | Notes |
|---|---|---|---|
| 1 | Clean-machine test of the `.exe` and `winget install --manifest`; replace the drawn SmartScreen stand-in with a real "unknown publisher" screenshot | release-engineer + user | The warning is expected while the app is unsigned |
| 2 | Submit to `microsoft/winget-pkgs` | user | Pending |
| 3 | Security review of agent file access and accept-edits (spec 014) | qa-security | Hardening merged in PR #7 |
| 4 | WebView2-missing message for Windows 10 | core-engineer + ui-engineer | Handling merged in PR #7; manual check on a real Windows 10 machine is pending (user) |

Branding (name, logo, Claude mascot) was checked by the user and is no longer a blocker.

## Future: code signing (on the user's call, no date)

| # | Item | Owner | Notes |
|---|---|---|---|
| 5 | Buy and apply a code-signing certificate | user + release-engineer | No date or vendor chosen. Removes the "unknown publisher" warning once reputation allows. SignPath stays ruled out |
| 6 | Compare certificate options: OV vs EV, price, how fast each removes the SmartScreen warning | product-growth | Run only when the user asks. Cite sources for prices and SmartScreen behavior |

## Next: make it worth using daily (1-2 months)

| # | Item | Owner | Spec |
|---|---|---|---|
| 7 | Claude Code-style interactive CLI, built on `galliani/cli` | tech-lead then core-engineer | New spec 017. Spec 017 merged (PR #11, #12); spec 018 approved 2026-10-19, implementation in progress. Polish after user trial (Claude Code look with the existing palette, motion, slash and `@` completion, easier launch; terminal command renamed `galliacli`): spec 018, approved 2026-10-19, implementation in progress. Follow-ups after it are in "Future work" below |
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

## Future work: after the TUI wave (ordered)

"The TUI wave" is specs 017 and 018 landing on `main`. Everything here is a proposal for the user to approve; none of it starts without an approved spec (`AGENTS.md`). Order is the recommended sequence, not a promise of dates. Each row names the owner agent, what must be true first, and the spec it needs. The "no telemetry, no accounts, no server" constraints from spec 016 apply to every item. Posting, spending money and submitting to third parties are always done by the user.

### Features

| Order | Item | Owner | Prerequisite | Spec |
|---|---|---|---|---|
| F1 | Name and package the entry points: desktop script keeps `galliani`, terminal is `galliacli`; package data so `galliacli` works from a non-editable install (spec 018 R27, 017 Open Item 4) | release-engineer, with core-engineer | Spec 018 implementation merged | 016 R24 and Phase 5 (PyPI) |
| F2 | Shared `memory.json`: desktop and a TUI session can run at once and writes are last-writer-wins (017 Open Item 5). Decide between a file lock, merge-on-write or accepting it, and say so in the docs | tech-lead, then core-engineer | None. Do it before the CLI is announced widely | 010 amendment |
| F3 | TUI in the `.exe`, or a separate terminal binary (017 Open Item 1) | tech-lead (amend scope), then release-engineer | F1, so the console scripts and package data are settled | New spec, amends 016 and 017 |
| F4 | Streaming output in the TUI and desktop. Supervisor and adapters return whole worker outputs today (017 Open Item 2), so this touches the core | tech-lead, then core-engineer, then ui-engineer | Spec 018 merged; F2 not required. Needs adapter-by-adapter feasibility check | Amendments to 001, 006, 011 |
| F5 | Session resume (`galliacli -c`), persistent transcript and prompt history. Lifts 017 and 018 non-goals | tech-lead, then core-engineer + ui-engineer | F2 decided (same storage and privacy rules); a decision on what is stored, where, and how it is redacted. Never store hidden reasoning or secrets | New spec |

Recommended order: F1, F2, F3, F4, F5. F1 and F2 are small and unblock the launch work below; F3 follows once packaging is stable; F4 and F5 are the larger bets and can swap if users ask for resume before streaming.

### Advertising and launch

No spend and no posting without the user. Drafts live in the repo for review; the user publishes.

| Order | Item | Owner | Prerequisite | Spec |
|---|---|---|---|---|
| L1 | README: document `galliacli`, install paths that really work today, and the unsigned-build note | product-growth | Spec 018 merged (names and flags final) | 016 R25 |
| L2 | Winget submission to `microsoft/winget-pkgs` (existing roadmap item 2) | user | Clean-machine test (item 1) | 016 Phase 3 |
| L3 | Landing page update: a terminal section (screenshot or short clip), install steps, honest scope. Copy by product-growth, implementation by ui-engineer | product-growth (copy), ui-engineer (build) | L1; F1 if the page promises a one-line install, otherwise say "from source" | 016 Phase 2 amendment |
| L4 | Announcement copy: short post and longer write-up, in English, no invented metrics or competitor claims | product-growth drafts; user posts | L1, L3 and V1 approved | None (copy only) |

Success is read without telemetry: release downloads, GitHub stars and issues, sponsors.

### Video: "Galliani in your terminal" (CLI update)

A modern, minimalistic, impactful motion-graphics video that shows the CLI update. It extends the existing Remotion project in `video/` (spec 015) and reuses the brand: near-black surfaces (`#0A0A0B`, `#141416`, `#1C1C1F`), light text (`#EDEDEF`, `#8B8B92`), orange accent `#D97757` from the mark, and the TUI status colors (good `#5ec49a`, warn `#e0b04f`, agent `#4cc2bd`). Inter for headlines, Cascadia Mono for terminal text. No new colors, no external assets, no voice, burned-in captions only so it works muted.

| Order | Item | Owner | Prerequisite | Spec |
|---|---|---|---|---|
| V0 | Amend spec 015: it fixes 35-55 s and vertical-first for the explainer, so a 20-30 s CLI-update cut needs its own composition requirement | tech-lead | User agrees to the video | 015 amendment |
| V1 | Script and storyboard approval (outline below), plus captions text | product-growth | V0 | 015 |
| V2 | Remotion composition `GallianiCli` in `video/`, built from scene data like the showcase (`timeline.ts`), reusing `galliani-mark.png` | ui-engineer | V1 approved. TUI visuals final (spec 018 merged) so what is shown is real | 015 |
| V3 | Review stills and a preview; **the user approves before any final render or publish** | user | V2 | 015 |
| V4 | Final render (16:9 1920x1080, 30 fps like the showcase; optional 9:16 cut). Publishing is the user's | ui-engineer renders; user publishes | V3 approved | 015 |

Storyboard outline (about 25 s at 30 fps, 16:9; each beat 1-3 s, kinetic type, hard cuts and short pushes, no slow fades):

| Time | Beat | On screen | Caption |
|---|---|---|---|
| 0-3 s | Hook | Black. The orange mark snaps in, then a blinking prompt `>` | Galliani now runs in your terminal. |
| 3-7 s | Launch | `galliacli` typed in a Cascadia Mono line; the TUI banner opens (built from real TUI frames) | One command. |
| 7-12 s | Objective to plan | An objective is typed; plan steps appear one by one with check states | Type a goal. Watch the plan. |
| 12-16 s | Routing and savings | A model chip is picked per step; cost counter ticks down in `#5ec49a` | The cheapest capable model, every step. |
| 16-20 s | Commands | `/` opens the completion popup, then `@` completes a file path | Slash commands. `@` files. |
| 20-23 s | Control | An approval prompt appears and is answered inline | You approve what matters. |
| 23-25 s | Close | Verified, then Done. The mark and `galliacli` on black | Local. No telemetry. Free. |

Copy rules from spec 015 carry over: short headlines, no filler, no "magic", no claim of unrestricted autonomy, no chain-of-thought shown, no real keys or logs on screen. The "Free" and "No telemetry" captions are claims, so check them against the README and the privacy page before V3. Do not show streaming or session resume; they are not built yet.

## Monetization options

The project is AGPL, local-first, with no accounts, server or telemetry. That is a selling point for privacy-minded users, so monetization should come from things users choose to pay for, not from data. Ordered by fit and effort:

| Option | Effort | Fit with constraints | Notes |
|---|---|---|---|
| **A. Sponsorship** (GitHub Sponsors, Ko-fi) with a link on the site, README and in-app About | Hours | Fully compatible | Low revenue, zero risk. Do first. |
| ~~B. Paid Microsoft Store edition~~ | n/a | Dropped | Superseded 2026-10-16: the Microsoft Store is no longer part of the plan. |
| **C. Dual licensing / commercial license** for companies that cannot use AGPL | Medium | Compatible, but **needs copyright holder decision** (Open Question 3) and a contributor agreement before accepting outside PRs; lawyer review | Likely the best long-term B2B lever. Decide before taking contributions. |
| **D. Paid support and setup for teams** (SLA, onboarding, custom routing policies) | Medium | Compatible | Needs a legal entity or freelancer setup; sells consulting more than product. |
| **E. Optional paid hosted gateway** (managed key, bundled credits, sync) | High | **Breaks non-goals** (accounts, server, payments) | **Needs user decision.** Adds ops, privacy and compliance burden. Only if A-C show demand. |
| **F. Pro features in a source-available build** (team policies, advanced analytics) | Medium | Conflicts with AGPL unless the owner relicenses own code | Revisit after C is settled. |

Recommended sequence: A now, decide C before accepting external contributions, measure interest through GitHub stars/issues and download counts from GitHub Releases (no in-app telemetry), then consider D/E.

Success signals to watch without telemetry: release download counts, GitHub stars and issues, sponsor count. winget install counts may not be visible to the project (unverified), so do not rely on them.

## Maintenance cadence

- Patch release (`0.1.x`) for fixes whenever `qa-security` is green.
- Minor release (`0.x.0`) per completed "Next" item, with a `CHANGELOG.md` entry and decision record.
- Re-run evals and the security checklist before every minor release.
- Revisit this roadmap monthly; `product-growth` proposes changes, the user decides.
