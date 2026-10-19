# 018 - TUI polish: look and feel, motion, completion, launch

## Status

Approved by the user (2026-10-19, "we can now proceed"); implementation in progress. The user answered the four open questions the same day (see "Settled by the user"). Design choices: `docs/decisions.md` Decision 0035 (Proposed).

Amendments to spec 017:

- **Already applied (user decision, 2026-10-19):** the terminal console script is renamed from `galliani` to `galliacli` (017 R2, R5, Behavior "Start", acceptance criteria, tests, Open Item 4). The code still uses `galliani` until task C2 lands.
- **Applied with this spec's approval (2026-10-19):** 017 R20 (layout), R22 (Up/Down while the popup is open), R28 (more motion than the spinner) and Behavior "Start" (banner instead of start notice).

Spec 016 needs no change. R15 (winget alias `galliani`) and R24 (console scripts for the desktop app and CLI; `pipx install galliani` starts the app) already fit: the desktop keeps `galliani`, the CLI script is `galliacli`, and the PyPI package and extra keep the name `galliani`.

## Goal

After trying the spec 017 terminal UI, the user asked for four changes:

1. A look and feel close to Claude Code, using only the colors already in the palette.
2. Calm, modern motion that switches off cleanly.
3. Slash-command and argument auto-completion.
4. Launching as easily as typing `claude`.

The supervisor, permissions, Task State, Memory and observability stay unchanged. This is presentation and launch work on top of `galliani/tui/`.

## Non-goals

- New colors, themes loaded from disk, or changes to the `DARK_PALETTE`, `LIGHT_PALETTE` and `_ANSI_VARIABLES` values in `galliani/tui/styles.py`.
- `galliacli -c` / `--continue`, session resume, a persistent transcript or history, or any settings or cache file (017 Non-goals stand).
- Streaming token output (017 Open Item 2).
- Showing model "thinking". The working verbs are fixed UI strings, not model output.
- A short alias beside `galliacli` (user decision: `galliacli` is the short, distinct name; no extra alias in v1).
- Reading file contents for `@` mentions, or attaching files to the objective. An `@path` mention is plain text; the agent still reads files only through its registered, permission-checked tools.
- A trust prompt with a remembered answer (that would need persistence).
- Changing the one-shot `python -m galliani.cli`.
- Publishing to PyPI (016 Phase 5) or bundling the TUI into `Galliani.exe`.

## Requirements

### A. Look and feel (amends 017 R20, R21 placement, Behavior "Start")

1. **Palette frozen.** `DARK_PALETTE`, `LIGHT_PALETTE` and `_ANSI_VARIABLES` keep their exact current keys and values. `APP_CSS` and every widget style use only `$g-*` variables (and Textual's derived theme variables built from them). No hex, `rgb()` or named color literal appears outside those three dicts. Animation in-between frames may blend existing tokens (for example `$g-fg` toward `$g-bg` during a fade), but nothing rests on a new color.
2. **Welcome banner.** The session opens with one bordered banner (round border, `$g-border`) in place of 017's start notice. It shows:
   - "Galliani" and the version (`galliani.__version__`).
   - The workspace as an absolute path, with the home folder shown as `~`.
   - The model line: `routing: auto` plus the names of providers that have a key (names only, never keys or key fragments), or the R15 no-key message.
   - Edit mode, budget and memory state.
   - Three tips: `/help for commands`, `/ to complete commands` and `Esc to stop a task` and `@ to mention a file`.

   The banner is shown once. `/clear` does not show it again.
3. **Prompt box.** The prompt is a full-width bordered box at the bottom with a `>` lead glyph. The border is `$g-border`, or `$g-accent` with a heavier border when focused, so focus still shows under `NO_COLOR`. The placeholder reads `Type an objective, or / for commands`. While a task is active the placeholder reads `Esc to stop`.
4. **Status line.** The 017 R21 fields move to one dim line (`$g-muted`) directly under the prompt box. 017 R20's field-dropping order at narrow widths is unchanged.
5. **Compact transcript.** Each entry is one lead glyph plus one line, with optional indented detail lines prefixed `└`. User turns: `>` in `$g-accent`. Tool calls: `●` plus the tool name and public target, and a result line `└ <public summary>`. Verification: `●` in `$g-agent`. Errors: `●` in `$g-bad`. Result: `●` in `$g-good`, with a Markdown body. There is one blank line between turns and none inside a turn. Entry text sources are exactly those of 017 R17. The layout changes, the content does not.
6. **Minimal chrome.** There is no header bar or footer key bar. The only border lines on screen are the banner, the prompt box, the docked plan panel (017 R20) and the approval card.
7. **Glyph set.** Every glyph used by the TUI (lead glyphs, `└`, the spinner frames, step-state glyphs) is in the WGL4 character set, which Consolas and Cascadia Mono render on Windows. Step states keep their 017 R28 words or glyphs so that color is never the only signal.

### B. Motion (amends 017 R28 "the spinner is the only animation")

8. **Motion is gated in one place.** One predicate, `motion_enabled(app)`, decides. It is false when any of these holds: `GALLIANI_REDUCED_MOTION=1`, the app's animation level is `none`, `NO_COLOR` is set, or the ANSI theme is active. Because `TEXTUAL_ANIMATIONS` does not stop `set_interval` timers, every timer-driven effect checks this predicate itself. Textual's `animate` calls also check it explicitly rather than relying on Textual alone.
9. **One shared ticker.** All motion is driven by a single app-level ticker of at most 10 Hz. The ticker runs only while a task is active (phase not `idle` or `closed`) or while an entry or exit transition is in flight. When idle it is stopped, with zero app-owned timers. With motion off, the ticker runs at 1 Hz while a task is active (elapsed time and cost only), and not at all when idle.
10. **Working line.** While a task is active, one line above the prompt box shows:
    - A spinner from WGL4 frames (`·`, `•`, `●`, `•`).
    - A status verb.
    - Elapsed seconds, the task cost against the budget, and `step N/M` when a plan exists.

    Verbs come from a fixed list per phase (planning, running, verifying, waiting, canceling), derived from `SessionState.phase` and `viewmodel.STATUS_LABELS`. They rotate every 3 seconds. With motion off, the spinner is a static `●`, the verb is the phase label and does not rotate, and elapsed time and cost still update at 1 Hz.
11. **Plan-step transitions.** When a step changes state (pending to running to done, failed or skipped), its glyph changes at once. With motion on, the running step's glyph uses the spinner frame, and a finished step's line is shown bold in its status token for 400 ms, then settles. With motion off the change is instant and has no highlight.
12. **Approval and question entry.** The approval card and the question field appear with a fade or slide of 150-200 ms (ease-out, from 1-2 rows below) when motion is on, and instantly when it is off. Keys are live from the first frame. 017 R23 and R24 are unchanged; animation never delays or swallows a key.
13. **Progress and cost.** Cost is updated only from `worker_completed` usage (017 R12), and step progress only from the plan. No indicator implies progress or cost it does not have. With no plan there is no `step N/M`. With no budget it shows `no limit`.
14. **Bounded cost.** A render tick that changes nothing does not refresh any widget. Only the working line, the running plan step and in-flight transitions refresh on a tick.

### C. Completion (amends 017 R22 Up/Down while the popup is open)

15. **Data comes from the headless layer.** Pure completion of commands and arguments lives in `galliani/tui/commands.py`, with no I/O. Completion that needs I/O lives in `Session` (`galliani/tui/session.py`): workspace folders, workspace files and memory ids. The UI only displays and inserts results. It computes no candidates.
16. **Slash popup.** Typing `/` as the first character of the prompt opens a popup above the prompt box listing the R26 commands with their `CommandSpec.summary`. It filters by prefix as the user types, falling back to substring matching when no prefix matches. Commands refused while a task is active stay listed, dimmed and marked `(not while a task runs)`.
17. **Popup keys.** While the popup is open:
    - `Up`/`Down` move the selection and do not recall history.
    - `Tab` inserts the selected item.
    - `Enter` on a command that takes no argument (`/help`, `/clear`, `/quit`) or on a finished argument inserts it and sends the line at once. On anything else (a command that takes an argument, a folder, a file) it only inserts. Settled by the user, 2026-10-19.
    - `Esc` closes the popup and does nothing else. It does not cancel a task while the popup is open.
    - Typing a space after a complete command name switches to argument completion.

    When the popup is closed, 017 R22 and R25 apply unchanged.
18. **Finite arguments.**
    - `/edit-mode`: `ask`, `accept-edits`.
    - `/theme`: `dark`, `light`.
    - `/events`: `on`, `off`.
    - `/budget`: `off`.
    - `/memory`: `list`, `forget`, `on`, `off`.
    - `/memory forget`: ids of records in the session's scopes only. The summary text is redacted exactly as `/memory list` shows it.

    No completion is offered for free values (a budget amount).
19. **`/workspace` path completion.** Only existing directories are offered, never files. The typed prefix is resolved against the current workspace, an absolute path, or `~`. A folder whose name `Workspace._blocked` would refuse (for example `.git`) is not listed. Dot-folders are listed only when the typed segment starts with `.`. At most 50 entries. The listing runs off the UI thread and stops after 0.5 s, showing what it has with `...`.
20. **`@file` mentions (required; included in this wave by the user, 2026-10-19).** An `@` typed at the start of the prompt or after whitespace opens file completion. Candidates come only from `Workspace(root).list_files(ListIn(path=".", pattern=...))` for the current workspace, so protected files and links that escape the workspace are never listed and the 200-entry cap applies. The listing runs off the UI thread and is cached per workspace for 30 s. The cache is dropped on `/workspace`. Accepting a candidate inserts `@<relative/path>` as plain text.
21. **Completion text is safe.** Every label and summary shown passes `sanitize()` (017 R18). A candidate whose name `sanitize()` would change (control, bidi or redacted characters) is omitted rather than inserted, so inserted text is always exactly what is displayed. Completion never runs on text the user did not type (017 R34). It is never offered in the approval card or the question field.

### D. Launch (delta over 017 R2-R5)

22. **What 017 already does.** With no objective, the terminal command already starts a session with `--workspace .`, the current folder. This spec adds only items 23-27.
23. **`python -m galliani`** runs `galliani.tui.entry:main` through a new `galliani/__main__.py`, with behavior identical to `galliacli` and `python -m galliani.tui`. The module names stay `galliani`; only the console script is renamed (R27).
24. **`galliacli --version`** prints `galliacli <__version__>` and exits 0 without importing Textual. `-h`/`--help` is unchanged apart from the name.
25. **Wide-workspace warning.** When the resolved workspace is the user's home folder or a filesystem root, the banner adds a `$g-warn` line: "This workspace is your whole home folder (or drive). The agent can read any file in it that is not protected. Start galliacli in a project folder, or use /workspace." This is a notice only. It needs no answer and stores nothing. The session still starts.
26. **On PATH after install.** The docs (README "Interactive terminal" and `docs/release-checklist.md` smoke step) give the supported installs in order:
    - From a clone: `pipx install -e ".[tui]"` (recommended, because `pipx ensurepath` fixes PATH), or `pip install -e ".[tui]"` in a venv.
    - `pip install --user` on Windows: scripts go to `%APPDATA%\Python\Python3XY\Scripts`, which is not on PATH by default. The docs give the PowerShell command to add it, and say that `python -m galliani` always works.

    Non-editable installs still lack package data until 016 Phase 5 (017 Open Item 4), and the docs say so. No installer edits PATH by itself.
27. **Command name (user decision, 2026-10-19).** The terminal console script is `galliacli` (`[project.scripts] galliacli = "galliani.tui.entry:main"`). `galliani` belongs to the desktop app: the winget alias (016 R15) and the future 016 R24 desktop script, neither of which is renamed. `argparse` `prog`, usage, help, the R5 fallback text (one-shot form `galliacli "<objective>"`) and all docs name `galliacli`. The PyPI package and extra keep the name `galliani` (`pip install "galliani[tui]"`). No extra alias in v1.

## Behavior

- **Start.** `galliacli` (or `python -m galliani`) runs the 017 R5 checks, then `Session`, then `run_app`. The transcript opens with the R2 banner (and the R25 warning when it applies), with the prompt box focused.
- **Completion.** A keystroke in the prompt goes to `complete_command(text, cursor, ...)` (pure). When the token is a path, file or memory id, it goes to `Session.complete(...)` (async, off the UI thread). The result is a `CompletionResult` and the popup renders it. A late result for stale text is dropped.
- **Motion.** Phase leaves `idle`: the ticker starts. Phase returns to `idle` and no transitions are in flight: the ticker stops.

## Interfaces and Data Contracts

These are additions only. The 017 contracts are unchanged.

```python
# galliani/tui/commands.py  -- still pure, no I/O
@dataclass(frozen=True)
class Completion:
    insert: str                  # replaces CompletionResult.start..cursor; equals the shown label's text
    label: str                   # sanitized
    summary: str = ""            # sanitized, one line
    kind: Literal["command", "argument", "folder", "file", "memory_id"] = "command"
    enabled: bool = True         # False: shown dimmed, "(not while a task runs)"
    submits: bool = False        # R17: Enter on this item also sends the line

@dataclass(frozen=True)
class CompletionResult:
    start: int                   # index in text where the completed token begins
    items: tuple[Completion, ...]
    needs_io: Literal["folder", "file", "memory_id"] | None = None   # ask Session.complete
    truncated: bool = False

def complete_command(text: str, cursor: int, *, task_active: bool) -> CompletionResult | None: ...
    # None: no popup (not a "/" line, "//" escape, or free-value argument)

# galliani/tui/session.py
class Session:
    async def complete(self, text: str, cursor: int) -> CompletionResult | None: ...
        # R18-R21; runs folder/file listing via asyncio.to_thread with R19/R20 bounds; never raises
    def banner(self) -> BannerInfo: ...

@dataclass(frozen=True)
class BannerInfo:
    version: str
    workspace: str               # absolute, home shown as "~", sanitized
    providers: tuple[str, ...]   # provider names with a key; never key material
    wide_workspace: bool         # R25
    edit_mode: EditMode
    budget_usd: float | None
    memory: Literal["on", "off", "unavailable"]
```

- `galliani/__main__.py`: `sys.exit(main())`, importing `galliani.tui.entry.main` lazily so `import galliani` stays light.
- `galliani/tui/widgets.py` gains `motion_enabled(app) -> bool` (it replaces `animations_enabled`), an app-level `Ticker` with a public `running: bool` for tests, and a `CompletionPopup` widget.

## Error Handling

- A listing error (permission denied, folder vanished, timeout) gives an empty or partial result with `truncated=True`. It produces no error entry and no crash.
- `@` with no workspace files: the popup shows `no files` and closes on the next key.
- A ticker exception is caught and logged to nothing on disk. Motion turns off for the session, and the static R10 equivalents remain.
- `--version` with other flags: prints the version and exits 0.

## Security

- **No new disclosure.** File completion uses only `Workspace.list_files`, so protected names (`.env`, `.git/`, keys) and escaping links are never shown (Decision 0032). Folder completion applies `Workspace._blocked` to each name. The folders listed are on the user's own machine and shown only to that user. Nothing is sent to a model by completion.
- **No hidden reasoning.** Verbs are fixed strings. The working line, banner and popup show only `SessionState`, `BannerInfo` and sanitized completion text.
- **No key leak.** The banner lists provider names from `load_keys().keys()` only.
- **No injection.** R21 sanitizes completion text, and a name that would need sanitizing is never inserted. Completion triggers only on user keystrokes in the prompt (017 R34).
- **No persistence.** No cache file, no history file, no remembered trust or warning answer. The 30 s file cache lives in process memory only. 017 R31 and R32 stand.
- **Fail closed.** No popup key can approve, deny or answer a prompt. `Esc` with the popup open only closes it.

## Acceptance Criteria

### Palette Unchanged
Given the styles module after this change
When the palette dicts and all CSS are inspected
Then the three dicts equal their 017 values and no color literal exists outside them.

### Banner
Given keys for two providers and a workspace in the home folder
When `galliacli` starts
Then the banner shows the version, `~/...` workspace, both provider names and no key characters; started in `~` itself it also shows the R25 warning.

### Reduced Motion Is Static
Given `GALLIANI_REDUCED_MOTION=1` (and separately `TEXTUAL_ANIMATIONS=none`, `NO_COLOR=1`)
When a task runs, a step finishes and an approval appears
Then the spinner is a static `●`, the verb does not rotate, the card appears without transition, and the ticker runs at most 1 Hz.

### Idle Means No Timers
Given an idle session after a finished task
When 2 seconds pass
Then `Ticker.running` is false and no widget refreshed.

### Slash Popup
Given an idle prompt
When the user types `/me`, presses Down, then Tab
Then the popup lists `/memory` with its summary, and the prompt reads `/memory ` with argument choices `list forget on off`; `Esc` closes it and leaves the text.

### Popup Does Not Steal Keys
Given a running task and the popup open
When the user presses `Esc`
Then the popup closes and the task keeps running; a second `Esc` cancels it (017 R25).

### Workspace Completion
Given folders `a/`, `.git/`, `.hidden/` and file `b.txt` in the workspace
When the user types `/workspace ` then `/workspace .`
Then the first lists only `a/`, the second lists `.hidden/` but never `.git/`, and `b.txt` never appears.

### File Mention Hides Protected Files
Given a workspace seeded with `.env`, `.git/config`, `server.key`, `notes.md` and a link to a file outside it
When the user types `@`
Then only `notes.md` is offered.

### Unsafe Name Not Inserted
Given a workspace file whose name contains U+202E or an `sk-` key
When `@` completion runs
Then that file is not offered.

### Launch Forms
Given an installed checkout in folder W
When the user runs `galliacli`, `python -m galliani` and `python -m galliani.tui` in W, and `galliacli --version`
Then the first three start a session with workspace W and the last prints `galliacli 0.2.0` and exits 0 without importing Textual.

### Console Script Name
Given a fresh editable install with the `tui` extra
When `pyproject.toml` and the installed scripts are inspected
Then `galliacli` is the only console script that runs `galliani.tui.entry:main`, no `galliani` console script is installed, and `galliacli --help` and the R5 fallback name `galliacli`.

### Enter In The Popup
Given the popup open on `/help`, and separately on `/theme`
When the user presses Enter
Then `/help` is sent at once; `/theme ` is inserted and nothing is sent.

## Tests

- **Headless, `tests/tui/` (core-engineer):**
  - `complete_command` for every command, prefix and substring filtering, argument lists, `//` escape, `task_active` dimming, `submits` flags, and `None` cases.
  - `Session.complete` against a temporary workspace seeded as in 014/013 evals (protected files, an escaping link, dot-folders, a folder over 50 entries, a name with control or bidi characters or a fake key), and memory ids scoped and redacted.
  - The timeout path.
  - `BannerInfo`: no key material, home shown as `~`, `wide_workspace` for home and root.
  - `galliani/__main__.py` and `--version` with Textual blocked (`sys.modules["textual"] = None`).
  - The rename: `prog` and usage, help and fallback text say `galliacli`; existing `tests/tui` assertions that expect `galliani` as the command name are updated.
  - A `pyproject.toml` check: `[project.scripts]` has `galliacli` and no `galliani` entry.
  - A palette and CSS literal scan.
  - A WGL4 glyph check.
- **Pilot, `tests/tui/test_app_pilot.py` (ui-engineer):**
  - Banner render.
  - Prompt focus border.
  - Popup open, filter, Up/Down, Tab, Enter-submits, Esc.
  - Popup closed: Up/Down history still works.
  - `Esc` precedence with a task running.
  - Working-line verb rotation with a fake clock.
  - Step-transition highlight, and approval keys live during the transition.
  - Reduced motion, `TEXTUAL_ANIMATIONS=none` and `NO_COLOR`: static states and the ticker at most 1 Hz.
  - Idle: ticker stopped.
  - Widths 80 and 60.
  - At least one failure path each: an unknown command filtered to empty, a listing error.
- **Security (qa-security):** the File Mention, Unsafe Name and Banner criteria as tests, plus a review that no completion path bypasses `Workspace` checks.
- **Release (release-engineer):** a fresh-venv smoke test of `pipx install -e ".[tui]"`, then `galliacli --version`, recorded in the PR, and `where galliacli` shows it on PATH. The existing 017 tests stay green.

## Evaluation

- A manual check on Windows Terminal and a 16-color console: glyphs render, motion looks calm, reduced motion is static. Recorded in the PR.
- CPU: idle CPU is about 0 % (no timers). While a task runs, the ticker is at most 10 Hz. Measured once by hand and noted in the PR.
- The hidden reasoning leak count and the protected-file disclosure count stay 0.

## Implementation Tasks

The user approved this spec as a whole on 2026-10-19. The paths are disjoint, and the contracts above let tasks A, B and C start in parallel.

- [ ] A (core-engineer): `galliani/tui/commands.py` (`Completion`, `CompletionResult`, `complete_command`), `galliani/tui/session.py` (`complete`, `banner`, `BannerInfo`), `galliani/tui/entry.py` (`--version`, R25 detection), `galliani/__main__.py`, and the headless tests in `tests/tui/` except `test_app_pilot.py`. Covers R13, R15, R18-R25 and the entry.py part of R27.
- [ ] B (ui-engineer): `galliani/tui/app.py`, `widgets.py` and `styles.py` (layout, banner, prompt box, status line, compact entries, `motion_enabled`, `Ticker`, `CompletionPopup`, transitions), and `tests/tui/test_app_pilot.py`. Covers R1-R12, R14, R16, R17, R21 display. The palette dicts are read-only.
- [ ] C1 (release-engineer): the README "Interactive terminal" install and PATH section (with `galliacli`), the `docs/release-checklist.md` smoke step and `CHANGELOG.md`. `scripts/winget_manifest.py` (`COMMAND_ALIAS = "galliani"`) and spec 016 are **not** changed. Covers R26.
- [ ] C2 (rename, R27; the code still says `galliani` today):
  - release-engineer: `pyproject.toml` `[project.scripts]` `galliani` -> `galliacli`; any mention in CI workflows, `CHANGELOG.md` and the README.
  - core-engineer: `galliani/tui/entry.py` (`prog`, `ONE_SHOT_HINT` and other usage and fallback strings) and the `tests/tui` tests that expect `galliani` as the command name.
- [ ] D (qa-security, after A and B): the security tests, a review of R19-R21 and the banner, the full `pytest` run and the gate. Updates the `docs/security.md` TUI section.

## Dependencies

Spec 017 (all contracts), spec 014 and Decision 0032 (`Workspace` protections), spec 016 R15, R24 and Phase 5, and Textual `>=8.2.8,<9` (no new dependency).

## Settled by the user (2026-10-19)

1. **Name clash.** The desktop keeps `galliani` (016 R15 winget alias, future 016 R24 script). The terminal console script is `galliacli` (R27). Spec 017 is amended accordingly.
2. **Short alias.** None. `galliacli` is the short, distinct name.
3. **`@file` mentions.** Included in this wave (R20 is required).
4. **Enter in the popup.** Commands that take no argument (and finished arguments) are sent at once; everything else only inserts (R17).

## Open Questions

None. The remaining step is the user's approval of the whole spec.
