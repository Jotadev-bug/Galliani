# 016 - Public Launch

## Status

Approved (2026-10-06, Decision 0027). Phase 1 is implemented first. The license and release pipeline it builds on are already in place (Decision 0026).

Amended 2026-10-16 (Decision 0033, approved by the user): Phase 4 (Microsoft Store) is dropped; the `.exe` ships unsigned, with the SmartScreen warning stated plainly, until the user buys a code-signing certificate (Phase 6, no date, no vendor chosen); Open Question 4 (branding) is resolved. Distribution is GitHub Releases, winget and the landing page.

## Goal

Let anyone find, download and try the Galliani desktop app for free, with as little friction as possible and with honest instructions for the security warning an unsigned app gets, at no cost to the project beyond the maintainer's time until the user decides to buy a code-signing certificate (Phase 6).

(Superseded 2026-10-16, Decision 0033: "...with as little friction and as few security warnings as possible, at no cost to the project beyond the maintainer's time.")

## Starting Point (2026-10-06)

- The repo `Jotadev-bug/Galliani` is public and licensed under AGPL-3.0-or-later.
- `.github/workflows/ci.yml` runs the tests and evals on Windows. It passes on `main`.
- `.github/workflows/release.yml` builds, smoke-tests and publishes `Galliani.exe` with its SHA-256 when a `v*` tag is pushed.
- Tag `v0.1.0` exists on GitHub, but **no release exists and the Release workflow never ran for it**. GitHub lists only two CI runs. The likely cause is that the tag reached GitHub without a tag push event that triggers workflows (for example, it was pushed together with other refs, or before the workflow was registered).
- Builds are unsigned. SignPath was ruled out because the maintainer cannot meet its requirements. Paid signing is out of scope for now. (Updated 2026-10-16, Decision 0033: builds stay unsigned for now and the user will buy a code-signing certificate later, Phase 6; SignPath stays ruled out.)
- The showcase video is already rendered locally at `video/out/galliani-showcase.mp4` (1920x1080, 30 fps), with a poster frame at `video/out/galliani-showcase-poster.png`. `video/out/` is git-ignored.
- The PyPI name `galliani` was unclaimed on 2026-10-06.

## Non-goals

- ~~Paid code signing (Azure Trusted Signing, Certum) or SignPath.~~ Superseded 2026-10-16 (Decision 0033): signing the `.exe` now. Releases ship unsigned until the user buys a certificate (Phase 6). SignPath remains a non-goal.
- A Microsoft Store listing or MSIX distribution (Phase 4 dropped by the user 2026-10-16, Decision 0033). The scaffold in `packaging/msix/` is kept but not pursued.
- A macOS or Linux desktop build. The page says Windows only for now.
- A hosted web version, accounts, paid credits, or any server the project runs.
- Analytics, tracking pixels, cookies, or telemetry, on the site or in the app.
- Auto-update inside the app.
- ~~Automating Microsoft Store submissions (the `msstore` CLI needs an Azure AD app). The first Store submissions are manual.~~ Superseded 2026-10-16: there are no Store submissions (Phase 4 dropped).
- Changing app behavior beyond what this spec names (a missing-WebView2 message is not a requirement here; it is an approved amendment to `012-desktop-ui`, R6-R15, Decision 0031).

## Requirements

The work is split into phases. Each phase ships on its own.

### Phase 1: First release

1. The Release workflow can also be started by hand: add a `workflow_dispatch` trigger with a required `tag` input. A manual run checks out that tag and behaves exactly like a tag push, including the version check. The published release uses that tag.
2. `v0.1.0` is published as a GitHub Release with `Galliani.exe` and `Galliani.exe.sha256`, either by deleting and re-pushing the tag alone (`git push origin v0.1.0`) or by a manual run from R1.
3. The direct link `https://github.com/Jotadev-bug/Galliani/releases/latest/download/Galliani.exe` downloads the newest stable `.exe`. Pre-releases never become "latest".
4. Before announcing a release, the maintainer:
   1. downloads the `.exe` on a clean Windows 10 or 11 machine (or a fresh Windows Sandbox), runs it past SmartScreen, adds a key, and sends one chat message and one agent task,
   2. uploads the `.exe` to VirusTotal and keeps the report link,
   3. if Microsoft Defender or another major engine flags it, submits it as a false positive (Microsoft's submission portal is free) and notes the submission in the release notes.

   This is a manual checklist item in `docs/release-checklist.md`. It is not automated.

### Phase 2: Landing page

5. A static site lives in `site/` and is deployed to Vercel (free Hobby plan) by Vercel's Git integration, with `site` as the project's root directory. Pushes to `main` deploy production; other branches get preview deployments. It is served at `https://galliani.vercel.app/` until a custom domain is chosen (amended 2026-10-06, Decision 0028).
6. The site is a static React app built with Vite, Tailwind CSS and Motion (amended 2026-10-06, Decision 0028). Vercel builds it (`site/vercel.json`) and serves it as static files; nothing runs on a server. No external font or third-party script is loaded at runtime: every asset, including the JavaScript bundle, is served from the site itself. Animations respect `prefers-reduced-motion`.
7. The home page contains, in order:
   1. **Hero:** the logo (`assets/logo.png`), the name, a one-line pitch ("Picks the right model for every message, and shows what you saved"), a primary **Download for Windows** button that links to the R3 URL, and the current version and file size under it.
   2. **Video:** the showcase video, muted, with controls and the poster frame, not autoplaying with sound. A text summary sits next to it for people who don't play it.
   3. **What it does:** three short blocks covering Chat (routes each message to the cheapest capable model), Agent (plans, uses tools in a folder you choose, asks before writing, verifies the result), and Cost (shows the model, the cost and the savings for every answer).
   4. **Install:** numbered steps that cover downloading, the SmartScreen "More info" then "Run anyway" step (with a screenshot), getting an OpenRouter key (with a link to openrouter.ai/keys), and pasting it in. Also the checksum command and, once Phase 3 ships, `winget install` as an alternative.
   5. **Privacy:** keys are stored in the OS credential store and only sent to the provider; requests are logged only on the user's machine; no telemetry. A link to the full privacy page (R10).
   6. **Open source:** AGPL-3.0, a link to the repo, and how to report issues.
   7. **FAQ:** what a typical task costs, why Windows warns, whether a Mac version exists, which models it uses, and what the agent can and cannot touch.
   8. **Footer:** license, repo link, privacy page link, and copyright.
8. The version and file size in R7.1 come from the GitHub Releases API (`/repos/Jotadev-bug/Galliani/releases/latest`), fetched in the browser. If the request fails or is rate-limited, the button still works, and the version line falls back to a link to the releases page. The page never shows a broken or empty value.
9. The site uses the app's graphite and silver palette (Decision 0025) as CSS custom properties. It has dark and light themes that follow `prefers-color-scheme`, a favicon from `app/web/logo.png`, and Open Graph and Twitter card tags with a 1200x630 share image made from the logo and the poster frame.
10. A privacy page (`site/privacy.html`) states, in plain language, what the app stores locally (the request log, memory, settings), what it sends and to whom (prompts to OpenRouter or the chosen provider, using the user's key), and that the project collects nothing. ~~The Microsoft Store listing in Phase 4 links to this page.~~ (Superseded 2026-10-16: Phase 4 dropped. The winget manifest links to this page, R15.)
11. The site works from 360 px wide upwards, with no horizontal scrolling. It meets WCAG 2.1 AA for contrast, keyboard use and focus visibility. The video has a text alternative, and every image has alt text.
12. The video file served by the site is at most 8 MB (an H.264 MP4 re-encoded from the render, plus an optional WebM). It loads with `preload="none"` or `preload="metadata"`.
13. The home page's total transfer before the video plays is at most 500 KB.

### Phase 3: winget

14. A winget manifest for each release is kept in `packaging/winget/<version>/`, using the current winget manifest schema (version, installer and default-locale files).
15. The package is portable: `InstallerType: portable`, the versioned release URL (`.../releases/download/vX.Y.Z/Galliani.exe`, never `latest`), the `.exe`'s SHA-256, the command alias `galliani`, `License: AGPL-3.0-or-later`, and the repo, license and privacy page URLs.
16. The Release workflow generates the manifest for the tag it publishes, from the built `.exe`'s checksum, and attaches it to the release as a zip, so the maintainer can submit it without editing by hand. It does not open the winget-pkgs pull request itself (that needs a personal access token, which is deferred).
17. `docs/release-checklist.md` documents the manual submission: validate locally with `winget validate`, install from the manifest with `winget install --manifest`, then open a pull request to `microsoft/winget-pkgs`.

### Phase 4: Microsoft Store (MSIX) - Dropped by the user 2026-10-16

**Dropped by the user 2026-10-16 (Decision 0033).** R18-R23 are not pursued and are no longer acceptance criteria for the launch. The scaffold already built for them (Decision 0030: `packaging/msix/`, `scripts/build_msix.py`, `build_desktop --onedir`, the `make_icon` tiles and their tests, and the release workflow's `--if-configured` step, which keeps skipping because `packaging/msix/identity.json` stays null) is kept unchanged so the work is not lost; it is not extended, and no Partner Center step is taken. Reopening Phase 4 needs a new decision approved by the user. The requirements below are kept as history.

18. The Release workflow can also produce `Galliani.msix` on the Windows runner, using `makeappx` from the Windows SDK. The package is a full-trust desktop app (`runFullTrust`, `Windows.FullTrustApplication`). Store packages are signed by Microsoft. For local testing only, the workflow or a script may sign with a throwaway self-signed certificate that is never published or committed.
19. The package identity (`Identity Name`, `Publisher`, `PublisherDisplayName`) comes from Partner Center after the maintainer reserves the name. It is kept as non-secret config in `packaging/msix/` and is not invented before then.
20. MSIX builds use PyInstaller's one-folder mode instead of `--onefile` (faster start and no extraction to `%TEMP%`). The standalone `.exe` from Phase 1 stays `--onefile`.
21. `scripts/make_icon.py` also generates the MSIX visual assets from `assets/logo.png`: Square44x44, Square150x150, Wide310x150 (logo centered on the tile color `#121318`), and StoreLogo 50x50, plus the scale variants the manifest declares.
22. The app works unchanged inside the package: the OS credential store, the user data folder under `%LOCALAPPDATA%` (which MSIX virtualizes), the folder picker, and the bundled web UI. The package's smoke test (the same `--smoke-test` checks) passes before submission.
23. `docs/release-checklist.md` documents the manual Store steps: create the free individual developer account and verify identity, reserve "Galliani", fill in the listing (description, screenshots, the privacy URL from R10, age rating), upload the `.msix`, and submit for certification.

### Phase 5 (optional): PyPI

24. Only if developers are a meaningful share of users: publish `galliani` to PyPI from the Release workflow using PyPI trusted publishing (no stored token). This needs packaging changes first: `[project.scripts]` entry points for the desktop app and CLI, and `config/` and `app/web/` included as package data so a non-editable install runs. `pipx install galliani` must start the app and pass the smoke test.

### Unsigned releases now, Phase 6 (future, no date): code signing

Added 2026-10-16 (Decision 0033, approved by the user).

25. **Unsigned, stated plainly (applies now).** Until Phase 6 ships, `Galliani.exe` is published unsigned, exactly as built today. The release notes, the README and the site's Install step and FAQ say plainly that the app is not code-signed, that Windows SmartScreen will show "Windows protected your PC" with an unknown publisher, and how to continue (**More info**, then **Run anyway**) and how to check the SHA-256. They never tell users to disable SmartScreen or antivirus (Security). "Not code-signed yet" is acceptable wording, because a certificate is planned; promising a date or a vendor is not.
26. **Phase 6: a bought code-signing certificate (future; no date, no vendor chosen).** The user will buy a code-signing certificate later. Nothing in this phase is specified or implemented until the user chooses a vendor and buys it. At that point this spec is amended (with the user's approval) to name the vendor and certificate type, how the private key or signing credential is held (never committed or logged; Security), the workflow step that signs `Galliani.exe` before its checksum is computed, how the winget manifest checksum follows, and the wording changes to R25. SignPath stays ruled out.

## Behavior

- **Releasing** stays one action: bump `version` in `pyproject.toml`, push a matching tag. The workflow produces the `.exe`, its checksum and the winget manifest zip (Phase 3). The maintainer then runs the manual checklist items (R4, R17). (Superseded 2026-10-16: "and, once enabled, the `.msix` (Phase 4)" and R23; Phase 4 dropped. The kept MSIX step still runs and skips.)
- **The download button** always points at the latest stable `.exe`. It never depends on the API call in R8.
- **The site** is redeployed only from `main`, so the published page always matches committed content.

## Interfaces and Data Contracts

- `.github/workflows/release.yml`: triggers `push: tags: [v*]` and `workflow_dispatch` with input `tag` (string, required, matching `^v\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$`).
- Release assets: `Galliani.exe`, `Galliani.exe.sha256`, `galliani-winget-<version>.zip` (Phase 3). ~~`Galliani.msix` (Phase 4, when enabled).~~ (Phase 4 dropped 2026-10-16; no `.msix` is published.)
- `site/vercel.json`: Vite framework, build command `npm run build && npm run check`, output `dist`. Environment variable `VITE_SITE_URL` (the public URL with a trailing slash) sets the canonical and Open Graph URLs; `SITE_BASE` (default `/`) sets the path prefix.
- `site/`: a Vite project (`package.json`, `index.html`, `privacy.html`, `src/`, `public/` for the logo, favicon, share image, video, poster and SmartScreen screenshot). `npm run build` writes the deployable site to `site/dist/`.
- `packaging/winget/<version>/`: `<Id>.yaml`, `<Id>.installer.yaml`, `<Id>.locale.en-US.yaml`.
- `packaging/msix/`: `AppxManifest.xml` template, identity config, generated visual assets. Kept, not pursued (Phase 4 dropped 2026-10-16).

## Error Handling

- A manual Release run with a tag that does not exist, or does not match `pyproject.toml`, fails before building, with a message naming the tag and the version.
- If the smoke test fails, nothing is published (unchanged from Decision 0026).
- If MSIX packaging fails, the `.exe` release still publishes, and the job reports the MSIX failure clearly. MSIX is not allowed to block the main download. (Still true for the kept scaffold step after Phase 4 was dropped.)
- If the Vercel build or the site checks fail, the deployment is not promoted and the previous site stays live.
- The site's API fallback is described in R8.

## Security

- Workflows use the minimum permissions each needs (`contents: write` for releases). The Vercel project must not enable Vercel Analytics, Speed Insights or any other injected script (see Non-goals). No long-lived secrets are added in this spec.
- No signing certificate, private key or Partner Center credential is ever committed or logged. The local-test MSIX certificate is generated per run and discarded. This also binds the future Phase 6 certificate (R26).
- The site loads no third-party code, so it has no supply-chain or tracking exposure. It sets a strict Content Security Policy meta tag (`default-src 'self'`, plus `connect-src https://api.github.com` for R8).
- Release notes and the site never tell users to disable SmartScreen or antivirus. They only explain the one-time "Run anyway" step for this app.
- The privacy page must match what the app actually does. If app behavior around data changes, the page is updated in the same change.

## Acceptance Criteria

### Manual Release Run

Given tag `v0.1.0` matches `pyproject.toml`
When the maintainer starts the Release workflow by hand with `tag = v0.1.0`
Then a release `v0.1.0` is published with `Galliani.exe` and `Galliani.exe.sha256`.

### Mismatched Tag Refused

Given `pyproject.toml` says `0.1.0`
When the Release workflow runs for `v0.2.0`
Then it fails before building and publishes nothing.

### Latest Download Link

Given a stable release and a newer pre-release exist
When a user opens `/releases/latest/download/Galliani.exe`
Then they get the stable release's `.exe`.

### Landing Page Download

Given the site is deployed
When a visitor clicks **Download for Windows**
Then the latest stable `Galliani.exe` downloads, even if the GitHub API is unavailable.

### Version Fallback

Given the GitHub API request fails
When the home page loads
Then the version line links to the releases page instead of showing an empty or broken value.

### No Third-Party Requests

Given the home page is loaded in a browser with the network panel open
When the page finishes loading and the video is not played
Then every request goes to the site's own origin or `api.github.com`, and the total transfer is at most 500 KB.

### Small Screens and Themes

Given a 360 px wide viewport in light mode and in dark mode
When the home page is viewed
Then nothing scrolls horizontally, and text and controls meet WCAG AA contrast.

### winget Install

Given the manifest generated for a release
When the maintainer runs `winget validate` and `winget install --manifest <folder>` on a clean machine
Then validation passes, Galliani installs, and `galliani` starts the app.

### Unsigned Warning Stated Plainly

Given an unsigned release (before Phase 6)
When a user reads the release notes, the README's install section, or the site's Install step and FAQ
Then each says the app is not code-signed and Windows SmartScreen will warn about an unknown publisher, explains **More info**, then **Run anyway**, and the checksum, and none tells the user to disable SmartScreen or antivirus.

### MSIX Smoke Test (dropped 2026-10-16, Phase 4; kept as history, not a launch criterion)

Given a locally signed `Galliani.msix`
When it is installed on a clean machine and started with `--smoke-test`
Then every smoke check passes, and a saved key survives an app restart.

## Tests

- A workflow-level test is not practical. Instead, verify R1 and R2 with a real manual run, and keep the tag/version check in a small Python script under `scripts/` with unit tests for matching, mismatching and pre-release tags.
- Unit tests for the winget manifest generator: the fields from R15, the versioned URL, and the checksum.
- Unit tests for the new `make_icon.py` outputs: every MSIX asset exists at the declared size.
- Site checks run on the built `site/dist/` in every Vercel build, before deploying: HTML validity, no external URLs in `src` or `href` except the allowed links (repo, releases, OpenRouter, license), every image has `alt`, and asset sizes are within R12 and R13.
- Manual checks from the acceptance criteria for the clean-machine installs (R4, winget). (The MSIX check was dropped with Phase 4 on 2026-10-16; the `make_icon` and `build_msix` unit tests keep running for the kept scaffold.)
- R25: a site check (in `site/scripts/check-site.mjs`) that the built home page states the app is not code-signed and mentions SmartScreen and the unknown publisher; the README and release-notes wording is a review item.

## Evaluation

None. This spec does not change agent behavior, so `evals/` is unchanged and its gates still apply to every release.

## Implementation Tasks

- [x] Phase 1: add `workflow_dispatch` to `release.yml`; move the tag check to `scripts/`, with tests; publish `v0.1.0`; add the clean-machine, VirusTotal and false-positive steps to `docs/release-checklist.md`.
- [x] Phase 2 (shipped 2026-10-06; the SmartScreen screenshot is still a drawn stand-in until one is taken on a clean machine): build `site/` (home and privacy pages, styles, assets); re-encode the video to at most 8 MB; make the share image and SmartScreen screenshot; connect the Vercel project (root directory `site`); run the site checks in the Vercel build; link the site from the README.
- [ ] Phase 3: ~~manifest generator script with tests~~ (`scripts/winget_manifest.py`, done); ~~attach the manifest zip in `release.yml`~~ (done); ~~document the submission~~ (done); `v0.1.0` manifest committed in `packaging/winget/0.1.0/` and passing `winget validate` (done); still to do: `winget install --manifest` on a clean machine, submit the first pull request to `microsoft/winget-pkgs`, add `winget install` to the site once it is merged.
- [ ] ~~Phase 4: one-folder build (`build_desktop --onedir`), MSIX assets (`make_icon`), manifest template and `makeappx` step (`scripts/build_msix.py`, skipped in the workflow until the identity is committed), document the Store steps (all done, Decision 0030); still to do: reserve the name in Partner Center and commit the identity to `packaging/msix/identity.json`, test the package locally (`--local-test`) on a clean machine, submit.~~ **Dropped by the user 2026-10-16 (Decision 0033).** The done scaffold is kept; the remaining steps will not be done. Not ticked, because it was not completed.
- [ ] Phase 5 (optional): packaging changes and the trusted-publishing PyPI job.
- [x] Record the approved decisions in `docs/decisions.md` and update `CHANGELOG.md` per phase.
- [x] (Decision 0033, tech-lead) Record the launch plan change: Decision 0033, this spec amended (Phase 4 dropped, R25, R26, Open Question 4 resolved), and the standing constraints in `ORCHESTRATION.md`.
- [ ] (Decision 0033, release-engineer) Mark `docs/release-checklist.md` section 8 (Microsoft Store), the MSIX row in the clean-machine table and the Partner Center items in "steps only the user can do" as dropped (keep the text as history); add a `CHANGELOG.md` line for the plan change. Both are already edited in the working tree (uncommitted, 2026-10-16); tick after review. Section 8's sentence "Spec 016 R18-R23 and Phase 4 are superseded and need an update by the spec owner" can now point at Decision 0033.
- [ ] (R25, release-engineer) Release notes in `.github/workflows/release.yml` and the README install paragraph state plainly that the `.exe` is not code-signed and SmartScreen will warn about an unknown publisher. The README paragraph is already rewritten in the working tree (uncommitted, 2026-10-16); the release-notes text in `release.yml` still says "may show" and does not name the unknown publisher.
- [ ] (R25, ui-engineer) The site's Install step and "Why does Windows warn me?" FAQ say the same; add the R25 site check. Replace the drawn SmartScreen stand-in with a real screenshot when one is taken (Phase 2 note).
- [ ] (Decision 0033, tech-lead via the main agent) Route updates to stale Store and signing references outside this spec's owner: `docs/roadmap.md` (Store items, branding item, monetization B, success signals; uncommitted edits already in the working tree on 2026-10-16), `.claude/agents/release-engineer.md` (Store/MSIX in its description) and `.claude/agents/product-growth.md` ("no paid signing").
- [ ] (Next release, release-engineer then the user) Cut a new release from `main` with the security hardening (Decision 0032) and the WebView2 handling (Decision 0031, spec 012 R6-R20): agents bump `version` in `pyproject.toml` (number chosen by the user; `0.2.0` is being prepared in the working tree), update `CHANGELOG.md`, run `docs/release-checklist.md`, and prepare the winget manifest; the user pushes the tag, publishes the release, runs R4 and submits to winget.
- [ ] Phase 6 (future, no date, no vendor chosen): the user buys a code-signing certificate; then amend R26 with the vendor and the signing step, with the user's approval, before any workflow change.

## Dependencies

Depends on `012-desktop-ui` (the app being shipped) and Decisions 0025 (logo and palette), 0026 (license and release pipeline) and 0033 (launch plan change: no Store, unsigned until a bought certificate, branding cleared).

## Open Questions

1. ~~**winget package identifier.**~~ Resolved 2026-10-07: `Jotade.Galliani`, from the Partner Center publisher name "Jotade" (Decision 0029). It cannot change after the first winget-pkgs merge.
2. **Custom domain.** Stay on `galliani.vercel.app` for launch, or buy a domain first? A domain costs money, so launch stays on the free Vercel subdomain.
3. **Copyright holder.** The license notice says "Galliani contributors". If paid commercial licenses are planned, the maintainer should hold the copyright, and outside contributions would need a contributor agreement (to be reviewed by a lawyer). Decide before accepting outside pull requests.
4. ~~**Branding check.**~~ Resolved by the user 2026-10-16 (Decision 0033): the logo has no problem and the Claude mascot in the video is fine. Branding no longer blocks promotion. Original question, kept as history: Before wide promotion, check that the name "Galliani" is free to use as a trademark, get an opinion on how close the silver G and four-point sparkle are to Google's G and the Gemini sparkle, and confirm the video's Claude mascot follows Anthropic's brand guidelines (Decision 0024).
5. **WebView2.** The app needs the Microsoft Edge WebView2 runtime, which ships with Windows 11 but may be missing on some Windows 10 machines. Should the app show a clear message with a download link when it is missing? That would be a small behavior change, so it needs its own requirement in `012-desktop-ui`. Update 2026-10-15: resolved as `012-desktop-ui` R6-R15, approved by the user (Decision 0031 Accepted).
6. **Security review.** Should a security review of the agent's file access and accept-edits mode (spec 014) be a gate before the public announcement? This draft recommends yes, but does not make it a requirement.
