# 016 - Public Launch

## Status

Approved (2026-10-06, Decision 0027). Phase 1 is implemented first. The license and release pipeline it builds on are already in place (Decision 0026).

Amended 2026-10-16 (Decision 0033, approved by the user): Phase 4 (Microsoft Store) is dropped; the `.exe` ships unsigned, with the SmartScreen warning stated plainly, until the user buys a code-signing certificate (Phase 6, no date, no vendor chosen); Open Question 4 (branding) is resolved. Distribution is GitHub Releases, winget and the landing page.

Amended 2026-10-28 (Decision 0039, **Accepted 2026-10-28**: the user approved Phase 5a with the recommended answers to Open Questions 7-11 (keep `app` for now; reword the in-app install hint; add `keyring` to the `tui` extra; attach wheel and sdist to GitHub Releases; wheel check on Windows only)): Phase 5 is split. New Phase 5a (R27-R38, roadmap F1) makes a built wheel work without an editable install: the desktop console script stays `galliani`, the terminal stays `galliacli`, and the files they read at runtime ship as package data. It publishes nothing. Phase 5b (R24, PyPI with trusted publishing) stays optional and unscheduled. Open Questions 7-11 are user decisions for Phase 5a.

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
- Phase 5a starting point (2026-10-28). A wheel built from `main` (`f8440e9`, version 0.2.0) with `pip wheel` contains only `.py` files plus metadata:
  - It has no `config/models.yaml`, no `config/routing.yaml`, and nothing from `app/web/`. `config/` sits outside every package, and `app/web/` is not declared as package data.
  - Its top-level packages are `app`, `benchmarks` and `galliani`.
  - Its only console script is `galliacli`.

  As a result, `CONFIG_DIR` resolves to `site-packages/config`, which does not exist, and `galliacli` works only from a source or editable install (017 Open Item 4). There is no `galliani` console script for the desktop app yet.

## Non-goals

- ~~Paid code signing (Azure Trusted Signing, Certum) or SignPath.~~ Superseded 2026-10-16 (Decision 0033): signing the `.exe` now. Releases ship unsigned until the user buys a certificate (Phase 6). SignPath remains a non-goal.
- A Microsoft Store listing or MSIX distribution (Phase 4 dropped by the user 2026-10-16, Decision 0033). The scaffold in `packaging/msix/` is kept but not pursued.
- A macOS or Linux desktop build. The page says Windows only for now.
- A hosted web version, accounts, paid credits, or any server the project runs.
- Analytics, tracking pixels, cookies, or telemetry, on the site or in the app.
- Auto-update inside the app.
- ~~Automating Microsoft Store submissions (the `msstore` CLI needs an Azure AD app). The first Store submissions are manual.~~ Superseded 2026-10-16: there are no Store submissions (Phase 4 dropped).
- For Phase 5a (added 2026-10-28, Decision 0039): publishing to PyPI or any package index (that is Phase 5b, R24); renaming the top-level `app` package (Open Question 7); a pip-installed desktop app on macOS or Linux; running `python -m galliani.evaluation` or `benchmark.py` from an installed wheel (they stay source-checkout tools); bundling the terminal into `Galliani.exe` (roadmap F3); update checks, telemetry, accounts or any new network call.
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

### Phase 5a: Installable package (roadmap F1)

Added 2026-10-28 (Decision 0039, Proposed). Goal: a wheel built from a clean checkout installs into a fresh virtual environment (or with pipx), and both commands start and find their files without the source tree. This phase publishes nothing, adds no network call, and changes no agent, routing or Memory behavior. Owners: core-engineer (`app/`, the configuration move), release-engineer (`pyproject.toml`, `scripts/`, `.github/`, `CHANGELOG.md`), product-growth (README), qa-security (review and gate).

27. **Console scripts.** `[project.scripts]` declares exactly two scripts and nothing else (no extra alias, no `gui-scripts`):
    - `galliani = "app.desktop:main"`: the desktop app. This is the same name as the winget command alias (R15). Both start the desktop app.
    - `galliacli = "galliani.tui.entry:main"`: the terminal, unchanged from spec 018 R27.

    The module forms stay as they are: `python -m app.desktop`, `python -m galliani`, `python -m galliani.tui` and `python -m galliani.cli`. `galliani` is a console script, not a GUI script, so `--smoke-test` output and start errors stay visible.
28. **Desktop app without its extra.** When the installed `galliani` is asked to open the window (any start without `--smoke-test`) and `webview` (pywebview, from the `desktop` extra) cannot be imported, it prints one message to stderr and exits 2. The check runs before the server starts or a window opens. The message names the cause, says the desktop app needs the `desktop` extra, points to the README install section, and says that `galliacli` is the terminal. It does not show the WebView2 message from spec 012 R6-R15, because that message is about the Windows runtime, not about a Python package. `--smoke-test` does not need pywebview and behaves exactly as today. The frozen `Galliani.exe` always contains pywebview, so its behavior does not change.
29. **Package data.** `python -m build` builds the sdist first and then builds the wheel from that sdist. The wheel must contain every non-Python file the installed entry points read at runtime:
    - `app/defaults/models.yaml` and `app/defaults/routing.yaml` (R30),
    - every file in `app/web/`, which today means `index.html` and `logo.png`. A file added to `app/web/` later is included without another packaging change.

    The sdist contains the same files.
30. **One location for the configuration.** `config/models.yaml` and `config/routing.yaml` move with `git mv` to `app/defaults/`, with their contents unchanged. They are declared as package data of `app` (`[tool.setuptools.package-data] app = ["web/*", "defaults/*.yaml"]`).

    `app.config.CONFIG_DIR` follows one rule everywhere: `ROUTER_CONFIG_DIR` when it is set, otherwise the `defaults` folder next to `app/config.py`. The rule is the same for a source checkout, an editable install, a wheel and the PyInstaller build. In `scripts/build_desktop.py`, `--add-data` changes to `app/defaults`. Nothing falls back to the old `config/` path, and `ROUTER_CONFIG_DIR` keeps its current meaning.

    These files are updated to the new path: `scripts/sync_pricing.py` (which writes `models.yaml`), `app/router/scoring.py` and `galliani/providers/app_bridge.py` (docstrings), `.env.example`, `docs/routing.md`, the README and `CONTRIBUTING.md` where they name the folder, and the `ORCHESTRATION.md` ownership row (`config/` becomes `app/defaults/`). Past entries in `CHANGELOG.md` and `docs/decisions.md` are history and are not edited.
31. **Only runtime packages.** The wheel installs exactly two top-level import packages, `app` and `galliani`. `benchmarks` is removed from `[tool.setuptools.packages.find]` (no installed code imports it). `tests`, `scripts`, `evals`, `site`, `video` and `packaging` are not in the wheel.
32. **Nothing is written into the installation.** The checks run the installed `galliani --smoke-test`, `galliacli --version`, `galliacli --help`, `galliacli` with no TTY (the 017 R5 fallback) and the R34 import probe. None of them creates, changes or deletes a file under the virtual environment, ignoring `__pycache__` folders and `.pyc` files. User data goes where it goes today: `user_data_dir()` for memory, the desktop log and the request log, and the chosen workspace. This phase adds no file, setting, cache or log of its own.
33. **Version agrees.** From an installed wheel, `galliacli --version` and `python -m galliani --version` print `galliacli <version>`. `<version>` equals `importlib.metadata.version("galliani")`, which in turn equals `version` in `pyproject.toml`. If any two differ, the R34 check fails.
34. **Wheel check.** `scripts/check_wheel.py` is run as `python -m scripts.check_wheel` and owned by release-engineer. It runs the steps below in order. At the first failure it stops with a non-zero exit and a message that names the failed step and the missing or unexpected item.
    1. It builds the sdist and the wheel with `python -m build` into a temporary folder outside the checkout.
    2. It inspects the wheel without installing it. Every R29 file is present. The top-level packages are exactly those in R31. `entry_points.txt` declares exactly the R27 scripts. This step is a pure function over the wheel's file list and its `entry_points.txt`, so it can be unit-tested.
    3. **Terminal environment.** It creates a fresh venv (`python -m venv`) in a temporary folder and installs `<wheel>[tui]`. It then runs these commands, each with the working folder set to a new empty temporary folder, with `PYTHONPATH` unset, and with the Python probe under `-I`:
       - `galliacli --version` and `python -m galliani --version` (R33),
       - `galliacli` with stdin not a TTY, which must exit 2 with the 017 R5 fallback text,
       - `galliani` with no `desktop` extra installed, which must exit 2 with the R28 message,
       - an import probe. The probe asserts that `app.__file__` and `galliani.__file__` are inside the venv and not inside the checkout. It loads `ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")` and `load_routing_config()`, imports `galliani.tui.app`, and asserts that `import benchmarks` fails.
    4. **Desktop environment.** It creates a second fresh venv with `<wheel>[desktop,tui]` and runs `galliani --smoke-test` in the same isolated way. Every smoke check must print `PASS`, including "UI served" and "logo bundled".
    5. It takes a snapshot of each venv's files before step 3 or 4 and again after it, and fails if anything changed apart from what R32 allows.
    6. It deletes its temporary folders, including after a failure.

    The check never runs a real task or a one-shot objective. Those could reach a provider with a key found in the OS credential store and spend money. It never prints environment variables or key values.
35. **CI.** `.github/workflows/ci.yml` gets a `wheel` job. It runs on `windows-latest` with Python 3.11, under the workflow's existing `contents: read` permission, on the same triggers as `test` and in parallel with it. It installs `build` and runs `python -m scripts.check_wheel`. A failure fails CI. `release.yml` does not change in Phase 5a unless Open Question 10 is answered yes (R38).
36. **Docs.** The README "Interactive terminal" section and its install steps are rewritten:
    - They drop the sentence saying non-editable installs lack package data.
    - They list install forms that work without an editable install: from a clone, `pipx install ".[tui]"` or `pip install ".[tui]"`; and straight from the repository, a pipx or pip command with a `git+https://github.com/Jotadev-bug/Galliani` URL. Release-engineer runs each command exactly as printed in a clean venv on Windows before it goes into the README.
    - They say that the pip-installed desktop app needs the `desktop` extra, is Windows only and needs WebView2, and that `Galliani.exe` or winget remains the recommended way to install the desktop app.
    - They say that a pip-installed `galliani` and the winget `galliani` are the same app, and how to see which one is first on PATH (`where galliani`).

    `CHANGELOG.md` gets a line for the move to `app/defaults/` and the two scripts.
37. **No unclaimed PyPI name in instructions.** Until the project itself publishes `galliani` on PyPI (Phase 5b), no doc, site page or release note tells users to run a command that would fetch `galliani` from PyPI. That rules out `pip install galliani`, `pip install "galliani[tui]"`, `pipx install galliani` and similar commands. Reason: the name was unclaimed when checked on 2026-10-06, and anyone could register it. The in-app fallback text in 017 R5 and 018 R27 is a separate spec and is covered by Open Question 8. This requirement does not change it.
38. **(Only if Open Question 10 is answered yes.)** `release.yml` runs `python -m scripts.check_wheel` before building the `.exe`, and attaches the checked wheel, the sdist and a `.sha256` file for each to the release. A wheel check failure stops the release, just as a smoke-test failure does. The release notes give the pipx command that installs from the versioned wheel URL, never from `latest`.

### Phase 5b (optional): PyPI

(Renamed from "Phase 5" on 2026-10-28, Decision 0039. The packaging changes R24 depends on are now Phase 5a, R27-R38, which must ship first. R24 itself is unchanged and not scheduled.)

24. Only if developers are a meaningful share of users: publish `galliani` to PyPI from the Release workflow using PyPI trusted publishing (no stored token). This needs packaging changes first: `[project.scripts]` entry points for the desktop app and CLI, and `config/` and `app/web/` included as package data so a non-editable install runs. `pipx install galliani` must start the app and pass the smoke test. (Note 2026-10-28: the packaging changes are Phase 5a. The scripts are `galliani` for the desktop app and `galliacli` for the terminal (R27); the configuration moves to `app/defaults/` (R30). Open Question 7 must be settled before this requirement is implemented.)

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
- `pyproject.toml` (Phase 5a, Decision 0039):
  - `[project.scripts]` lists `galliani = "app.desktop:main"` and `galliacli = "galliani.tui.entry:main"` (R27).
  - `[tool.setuptools.packages.find] include = ["app*", "galliani*"]` (R31).
  - `[tool.setuptools.package-data] app = ["web/*", "defaults/*.yaml"]` (R29, R30).
  - `build>=1.2` is added to the `build` extra, so the wheel check can run locally with `pip install -e ".[build]"`.
  - A `MANIFEST.in` is added only if the sdist turns out to miss an R29 file; the R34 check decides.
- `app/defaults/models.yaml`, `app/defaults/routing.yaml`: the shipped configuration (moved from `config/`, R30). `ROUTER_CONFIG_DIR` overrides the folder.
- `scripts/check_wheel.py` (R34): run as `python -m scripts.check_wheel [--keep]`. `--keep` leaves the temporary folders in place for debugging. Exit codes: 0 when every step passes, 1 when a step fails, 2 for a usage error. It exposes `inspect_wheel(names: list[str], entry_points: str) -> list[str]`, which returns the problems found and an empty list when the wheel is fine, so step 2 can be unit-tested.
- R28 message, as a fixed string with no interpolated paths: `galliani: the desktop app needs the "desktop" extra (pywebview is not installed). See the README "Install" section. For the terminal, run: galliacli`.

## Error Handling

- A manual Release run with a tag that does not exist, or does not match `pyproject.toml`, fails before building, with a message naming the tag and the version.
- If the smoke test fails, nothing is published (unchanged from Decision 0026).
- If MSIX packaging fails, the `.exe` release still publishes, and the job reports the MSIX failure clearly. MSIX is not allowed to block the main download. (Still true for the kept scaffold step after Phase 4 was dropped.)
- If the Vercel build or the site checks fail, the deployment is not promoted and the previous site stays live.
- The site's API fallback is described in R8.
- If `galliani` starts without pywebview, it prints the R28 message and exits 2. There is no traceback, no server and no window.
- If the configuration folder is missing or unreadable (for example, `ROUTER_CONFIG_DIR` points nowhere), the behavior is the same as today when `config/` is missing. Phase 5a adds no new recovery path. The R34 probe makes sure the shipped folder is present in every wheel.
- If `check_wheel` fails, it names the step and the missing or unexpected file, package or script. CI shows that message as the job failure.

## Security

- Workflows use the minimum permissions each needs (`contents: write` for releases). The Vercel project must not enable Vercel Analytics, Speed Insights or any other injected script (see Non-goals). No long-lived secrets are added in this spec.
- No signing certificate, private key or Partner Center credential is ever committed or logged. The local-test MSIX certificate is generated per run and discarded. This also binds the future Phase 6 certificate (R26).
- The site loads no third-party code, so it has no supply-chain or tracking exposure. It sets a strict Content Security Policy meta tag (`default-src 'self'`, plus `connect-src https://api.github.com` for R8).
- Release notes and the site never tell users to disable SmartScreen or antivirus. They only explain the one-time "Run anyway" step for this app.
- The privacy page must match what the app actually does. If app behavior around data changes, the page is updated in the same change.
- Phase 5a (Decision 0039):
  - The project does not own the PyPI name `galliani`, so instructions must never send users to PyPI for it (R37, Open Question 8).
  - The wheel ships no secret, `.env` file, test fixture or request log. The R34 inspection fails on any file outside `app/` and `galliani/` other than the `.dist-info` metadata.
  - `check_wheel` runs no task, calls no provider, and prints no environment variables or keys (R34).
  - The CI job keeps `contents: read` and adds no secret.
  - `app.config.load_dotenv` still reads `.env` from the folder above `app/`. In a wheel install that folder is `site-packages`, where no `.env` exists unless someone with write access to the environment put one there. That is no new exposure, so the behavior is unchanged and recorded here.

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

### Phase 5a: Wheel Contains Its Data (R29, R31)

Given a clean checkout of the Phase 5a branch
When `python -m build` runs and the wheel is listed
Then it contains `app/defaults/models.yaml`, `app/defaults/routing.yaml`, `app/web/index.html` and `app/web/logo.png`, its only top-level packages are `app` and `galliani`, and `entry_points.txt` declares exactly `galliani` and `galliacli`.

### Phase 5a: Terminal From a Clean Venv (R27, R30, R33)

Given a fresh venv with only `<wheel>[tui]` installed, and an empty working folder outside the checkout
When the user runs `galliacli --version` and `python -m galliani --version`
Then both print `galliacli <version>`, exit 0, and the version matches `pyproject.toml`
And the import probe finds `app` and `galliani` inside the venv and loads `models.yaml` and `routing.yaml` from the installed `app/defaults/`.

### Phase 5a: Desktop Smoke From a Clean Venv (R27, R29)

Given a fresh venv with `<wheel>[desktop,tui]` installed on Windows
When `galliani --smoke-test` runs from an empty working folder
Then every check prints `PASS`, including "UI served" and "logo bundled", and the exit code is 0.

### Phase 5a: Desktop Extra Missing (R28)

Given a venv with `<wheel>[tui]` only
When the user runs `galliani`
Then it prints the R28 message to stderr and exits 2, with no traceback, and starts no server and no window
And `galliani --smoke-test` in the same venv still runs the smoke checks (it does not need pywebview).

### Phase 5a: Nothing Written Into the Install (R32)

Given the venvs from the two criteria above
When every R32 command has run
Then the venv's file snapshot is unchanged apart from `__pycache__` folders and `.pyc` files.

### Phase 5a: CI Catches Missing Data (R34, R35)

Given a branch that removes `"defaults/*.yaml"` from `package-data`
When CI runs
Then the `wheel` job fails at step 2 and names `app/defaults/models.yaml` as missing. The unit test for `inspect_wheel` covers this case, so nobody has to break the real build to prove it.

### Phase 5a: Source Checkout Unchanged (R30)

Given a checkout with `pip install -e ".[dev,desktop,build,tui]"`
When `python -m pytest -q`, `python -m galliani.evaluation evals/cases` and `python -m scripts.build_desktop` followed by `Galliani.exe --smoke-test` run
Then all pass, reading the configuration from `app/defaults/`, and nothing reads `config/`.

### Phase 5a: pipx Install (R27, R36; manual, Windows)

Given pipx on a Windows machine where Galliani has never been installed
When the maintainer installs the built wheel with the `[desktop,tui]` extras using the pipx command printed in the README
Then `galliacli --version` and `galliani --smoke-test` work from a new terminal in any folder.

### Phase 5a: No PyPI Install Instructions (R37)

Given the README, `CONTRIBUTING.md`, the user-facing pages in `docs/` (all except the planning records `docs/decisions.md` and `docs/roadmap.md`, which describe Phase 5b as a plan), the built site and the release-notes text in `release.yml`
When they are searched for `pip install galliani`, `pip install "galliani`, `pipx install galliani` and `pipx install "galliani`
Then nothing is found, except in text that says PyPI is not used yet.

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
- Phase 5a (Decision 0039):
  - `tests/test_check_wheel.py` unit-tests `inspect_wheel`. The cases are: a complete wheel passes; a missing `app/defaults/models.yaml` fails; a missing `app/web/logo.png` fails; an extra top-level `benchmarks/` fails; a stray `.env` fails; an extra or missing console script fails; and a renamed script (`galliani` pointing at the TUI) fails.
  - Unit tests for `CONFIG_DIR`: the default is the `defaults` folder next to `app/config.py`, and `ROUTER_CONFIG_DIR` overrides it. Run the module in a subprocess, or reload it, so the module-level value is checked.
  - Unit tests for R28: with `webview` made unimportable (a `sys.modules` entry set to `None`), `app.desktop.main([])` returns 2, prints the R28 text to stderr, and never calls `start_server` (monkeypatched). The same setup with `--smoke-test` reaches the smoke path.
  - A test fails if any file outside `specs/`, `docs/decisions.md` and `CHANGELOG.md` still names `config/models.yaml` or `config/routing.yaml`.
  - The full wheel build is the `wheel` CI job (R35), not a pytest test, because it needs a network and minutes. The ordinary test run stays fast and offline.

### Phase 5a requirement-to-test map

| Requirement | Covered by |
|---|---|
| R27 | `inspect_wheel` unit tests; R34 steps 2-4 |
| R28 | `app.desktop` unit tests; R34 step 3 |
| R29, R31 | `inspect_wheel` unit tests; R34 step 2 |
| R30 | `CONFIG_DIR` unit tests; the stale-path test; the existing `tests/conftest.py` and `tests/test_jev.py` reading `CONFIG_DIR`; R34 step 3 probe |
| R32 | R34 step 5 |
| R33 | R34 step 3 |
| R34, R35 | `wheel` CI job on the pull request |
| R36, R37 | the manual pipx criterion; a qa-security search of the docs and site |

## Evaluation

None. This spec does not change agent behavior, so `evals/` is unchanged and its gates still apply to every release.

## Implementation Tasks

- [x] Phase 1: add `workflow_dispatch` to `release.yml`; move the tag check to `scripts/`, with tests; publish `v0.1.0`; add the clean-machine, VirusTotal and false-positive steps to `docs/release-checklist.md`.
- [x] Phase 2 (shipped 2026-10-06; the SmartScreen screenshot is still a drawn stand-in until one is taken on a clean machine): build `site/` (home and privacy pages, styles, assets); re-encode the video to at most 8 MB; make the share image and SmartScreen screenshot; connect the Vercel project (root directory `site`); run the site checks in the Vercel build; link the site from the README.
- [ ] Phase 3: ~~manifest generator script with tests~~ (`scripts/winget_manifest.py`, done); ~~attach the manifest zip in `release.yml`~~ (done); ~~document the submission~~ (done); `v0.1.0` manifest committed in `packaging/winget/0.1.0/` and passing `winget validate` (done); still to do: `winget install --manifest` on a clean machine, submit the first pull request to `microsoft/winget-pkgs`, add `winget install` to the site once it is merged.
- [ ] ~~Phase 4: one-folder build (`build_desktop --onedir`), MSIX assets (`make_icon`), manifest template and `makeappx` step (`scripts/build_msix.py`, skipped in the workflow until the identity is committed), document the Store steps (all done, Decision 0030); still to do: reserve the name in Partner Center and commit the identity to `packaging/msix/identity.json`, test the package locally (`--local-test`) on a clean machine, submit.~~ **Dropped by the user 2026-10-16 (Decision 0033).** The done scaffold is kept; the remaining steps will not be done. Not ticked, because it was not completed.
- [ ] Phase 5 (optional): packaging changes and the trusted-publishing PyPI job. (Split 2026-10-28, Decision 0039: the packaging changes are the Phase 5a tasks below; the PyPI job is Phase 5b.)
- [x] Phase 5a, P0 (user, 2026-10-28): approve this amendment and answer Open Questions 7-11. Nothing below starts before that.
- [ ] Phase 5a, P1 (core-engineer; can start in parallel with P2 because the path `app/defaults/` is fixed here):
  - `git mv config/*.yaml app/defaults/`.
  - Apply the `CONFIG_DIR` rule in `app/config.py` (R30).
  - Add the R28 check and message in `app/desktop.py`.
  - Update the docstrings in `app/router/scoring.py` and `galliani/providers/app_bridge.py`, `.env.example` and `docs/routing.md`.
  - Add the `CONFIG_DIR`, R28 and stale-path unit tests.

  Done when `pytest` and the evals pass and the R28 tests cover the failure path and the `--smoke-test` path.
- [ ] Phase 5a, P2 (release-engineer):
  - In `pyproject.toml`: the two scripts, `packages.find` without `benchmarks`, `package-data`, and `build` in the `build` extra (R27, R29-R31).
  - Point `--add-data` in `scripts/build_desktop.py` at `app/defaults`.
  - Update the path in `scripts/sync_pricing.py`.
  - Add `scripts/check_wheel.py` with `inspect_wheel` and `tests/test_check_wheel.py` (R34).
  - Add the `wheel` job to `.github/workflows/ci.yml` (R35).
  - Add the `CHANGELOG.md` line.

  Done when `python -m scripts.check_wheel` passes locally on Windows after P1 is merged into the branch, and the `wheel` job is green on the pull request.
- [ ] Phase 5a, P3 (release-engineer, only if Open Question 10 is yes): R38 in `release.yml`, and the release-checklist line for checking the attached wheel.
- [ ] Phase 5a, P4 (product-growth, after P2, because the pipx commands are verified against the real wheel): rewrite the README "Interactive terminal" and install sections and fix the `CONTRIBUTING.md` folder name (R36, R37). Use only commands that release-engineer verified in a clean venv.
- [ ] Phase 5a, P5 (qa-security, after P1-P4):
  - Review the diff against R27-R38.
  - Run `python -m scripts.check_wheel` and the manual pipx criterion on Windows.
  - Run the R37 search over the README, `docs/`, `site/` and the release-notes text.
  - Add a short packaging note to `docs/security.md` covering R32 and R37 and the unchanged `.env` lookup.
  - Gate the work.
- [ ] Phase 5a, P6 (main agent): update the `config/` ownership row in `ORCHESTRATION.md`, and mark roadmap F1 done after the merge.
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

Phase 5a also depends on these:
- spec 017 (R2, R5, R7, Open Item 4) and spec 018 (R23, R24, R27) for the terminal entry point, its fallback and `--version`;
- spec 012 for the desktop start and smoke test;
- Decision 0039;
- roadmap F1.

Roadmap F3 (the terminal in the `.exe`) waits for Phase 5a.

## Open Questions

1. ~~**winget package identifier.**~~ Resolved 2026-10-07: `Jotade.Galliani`, from the Partner Center publisher name "Jotade" (Decision 0029). It cannot change after the first winget-pkgs merge.
2. **Custom domain.** Stay on `galliani.vercel.app` for launch, or buy a domain first? A domain costs money, so launch stays on the free Vercel subdomain.
3. **Copyright holder.** The license notice says "Galliani contributors". If paid commercial licenses are planned, the maintainer should hold the copyright, and outside contributions would need a contributor agreement (to be reviewed by a lawyer). Decide before accepting outside pull requests.
4. ~~**Branding check.**~~ Resolved by the user 2026-10-16 (Decision 0033): the logo has no problem and the Claude mascot in the video is fine. Branding no longer blocks promotion. The name "Galliani" was also researched and confirmed available by the user (2026-10-16). Original question, kept as history: Before wide promotion, check that the name "Galliani" is free to use as a trademark, get an opinion on how close the silver G and four-point sparkle are to Google's G and the Gemini sparkle, and confirm the video's Claude mascot follows Anthropic's brand guidelines (Decision 0024).
5. **WebView2.** The app needs the Microsoft Edge WebView2 runtime, which ships with Windows 11 but may be missing on some Windows 10 machines. Should the app show a clear message with a download link when it is missing? That would be a small behavior change, so it needs its own requirement in `012-desktop-ui`. Update 2026-10-15: resolved as `012-desktop-ui` R6-R15, approved by the user (Decision 0031 Accepted).
6. **Security review.** Should a security review of the agent's file access and accept-edits mode (spec 014) be a gate before the public announcement? This draft recommends yes, but does not make it a requirement.

Phase 5a questions (added 2026-10-28, Decision 0039). These are user decisions. The recommendation is the tech lead's.

7. **The top-level package name `app`.** The wheel installs a top-level package called `app`. That generic name can collide with another distribution's `app` package if both are installed in one shared environment. pipx and a dedicated venv avoid the collision.
   - (a) Accept it for Phase 5a. The README recommends pipx or a venv. Renaming the package is required before Phase 5b publishes to PyPI. **Recommended.**
   - (b) Rename it now, to `galliani_app` or into `galliani/`. That is a large mechanical change across `app/`, `tests/`, PyInstaller and the docs, and it would make Phase 5a much bigger.
8. **The in-app fallback hint names a PyPI command.** 017 R5 and 018 R27 have `galliacli` print `pip install "galliani[tui]"` when Textual is missing. On PyPI that would install whatever package someone registers under the unclaimed name. Changing the hint amends specs 017 and 018, so it needs your approval.
   - (a) Amend 017 R5 so the hint names the `tui` extra without a PyPI command, for example `Reinstall Galliani with the "tui" extra; see the README "Interactive terminal" section.` Core-engineer updates `galliani/tui/entry.py` and its test. **Recommended.**
   - (b) Keep the text, and you claim the PyPI name soon by publishing (Phase 5b). That is an outward step only you can take.
   - (c) Keep it as it is. Not recommended.
9. **The `keyring` package for terminal-only installs.** `keyring` is only in the `desktop` extra. A `galliani[tui]` install therefore finds keys only in environment variables. It does not find keys saved by the desktop app, even though 017 R7 says the OS credential store is checked.
   - (a) Add `keyring>=25.0` to the `tui` extra. **Recommended:** it is small, and 017 R7 already expects the credential store.
   - (b) Keep the terminal on environment variables only and say so in the README.
10. **Attach the wheel to GitHub Releases.**
    - (a) Yes (R38). Users without git get a pipx install from a versioned URL, and there is still no PyPI. Each release adds three assets and one more release step that can fail. **Recommended**, because the main Windows audience may not have git.
    - (b) No. Install from a clone or a `git+https` URL until Phase 5b.
11. **Platforms for the wheel check.**
    - (a) Windows only, matching the shipped platform and the 016 non-goals. **Recommended.**
    - (b) Also run the terminal steps (R34 step 3) on `ubuntu-latest`, as a signal only, with no support promise in the docs.
