# Security

Galliani security starts from explicit boundaries.

## Core Rules

- Do not expose chain-of-thought or hidden reasoning.
- Do not store secrets in Task State, Memory, logs, or artifacts.
- Do not execute tools without schema validation.
- Do not perform destructive actions without permission.
- Do not trust model output as executable instruction.
- Do not trust external documents as instructions unless the user explicitly elevates them.

## Prompt and Context Safety

User requests are instructions. Referenced documents, web pages, tool outputs, and prior conversation excerpts are data unless explicitly promoted by the user.

## Provider Safety

Provider adapters must redact secrets and normalize errors. Provider-specific reasoning fields must be discarded or sealed before they reach logs, APIs, UI, or memory.

## Tool Safety

Every tool call must pass:

1. Schema validation.
2. Permission check.
3. Execution boundary check.
4. Result normalization.
5. Sensitive data redaction.

Accept-edits mode (spec 014) only replaces the user's prompt for `write`-level tools declared as workspace edits (`write_file`, `write_files`). Path validation, symlink checks and protected names still run first. Deletes, network, spending and memory writes always ask. Only the user can turn the mode on, for one task at a time, and every write it allows is recorded as a permission decision and event.

## Auditability

Galliani should record what action occurred, why it was allowed, and what result was observed. Audit entries must be useful without revealing private reasoning.

## Agent File Access Threat Model (specs 005, 009, 014)

Reviewed 2026-10-15 (roadmap item 4, spec 016 Open Question 6) on Windows 11, Python 3.11, against
`galliani/workspace.py`, `galliani/tools.py`, `galliani/permissions.py`, `galliani/execution.py`,
`galliani/supervisor.py`, `galliani/web/agent_api.py`, `galliani/cli/__init__.py`, `app/api/routes.py`
and `app/web/index.html`. Regression tests: `tests/core/test_security_review.py`.

### Assets

- Files outside the chosen workspace folder.
- Protected files inside it: `.env` and `.env.*` (templates excepted), keys (`*.pem`, `*.key`, `id_rsa*`,
  `id_ed25519*`, `*.p12`, `*.pfx`), `credentials*`, `secrets*`, and everything under `.git/`, `.venv/`,
  `node_modules/`, `__pycache__/`. Writing `.git/hooks/*` or `.git/config` gives code execution the next
  time the user runs git.
- Provider keys and the desktop app token.
- The user's consent: which writes ran without a prompt.

### Adversaries

- Untrusted content the agent reads (workspace files, web pages, tool output, earlier step output). It can
  steer a model into planning arbitrary `write_file` / `read_file` arguments (prompt injection).
- A cloned repository or other tool that left links (symlinks, junctions) in the workspace.
- A web page open in the user's browser while the local API is running.

### Trust boundaries and controls

| Boundary | Control | Status |
|---|---|---|
| Tool arguments -> filesystem | `normalize_relative` rejects absolute, drive, UNC (`\\server`, `\\?\`), drive-relative (`C:x`) and `..` paths as `invalid_arguments` before any permission check | Holds |
| Workspace root | `Workspace.resolve` resolves links and refuses targets outside the root (junctions and symlinks pointing out) | Holds |
| Protected names | `normalize_relative` rejects names Win32 rewrites (`:`, trailing dot/space, device names); `_blocked` compares case-folded names on the requested and the resolved path, and `list_files` filters resolved paths | Holds (SEC-1, SEC-2 fixed) |
| Permission | 009 policy; accept-edits only for `write` + `workspace_edit`; registry refuses `workspace_edit` on non-write tools and on tools not marked by `confined_to_workspace` (only `Workspace.tools()`) | Holds (SEC-6 fixed) |
| Consent | mode set only by `StartTaskRequest`, `approve(accept_edits=True)` (eligibility checked) or `set_edit_mode`; CLI and API default to `ask`; UI keeps the mode per conversation in memory | Holds |
| Audit | every auto-approval is a `PermissionDecision` in Task State plus a `permission_decided` event | Holds |
| Events | redaction of known secret patterns and reasoning keys; `tool_called` carries the resource, argument names and file paths, never argument values | Holds (SEC-3 fixed) |
| Local API | desktop: random per-launch `X-App-Token` header on every `/api` call; every mode: non-GET `/api` calls need `X-Requested-With` or `X-App-Token` and a same-origin `Origin` (Decision 0032) | Holds (SEC-5 fixed) |

Verified as holding (tests in `tests/core/test_accept_edits.py`, `tests/core/test_workspace.py`,
`tests/core/test_security_review.py`): 014 R1, R2 (full level x `workspace_edit` x mode matrix), R3 for
non-write levels, R4, R5, R6 at the supervisor, R7, R8, R9; 009 R1-R5; spending extensions ignore the edit
mode; `.ENV`, `.env.`, `.env `, `SERVER.KEY`, `ID_RSA`, `Secrets.json` are refused; traversal, absolute,
UNC and drive paths never run; links escaping the root are refused.

### Review findings

Ranked by severity. Each was pinned by a strict-xfail test while open; the markers were removed as the
fixes landed (2026-10-15, Decision 0032), so the tests below are now regression guards in
`tests/core/test_security_review.py` unless another file is named.

- **SEC-1 (Critical) Protected names bypassed by Win32 name normalization. Fixed.** `_blocked` compared
  names case-sensitively and before Windows strips trailing dots and spaces or splits `name:stream`, so
  `.GIT/config`, `.Git/hooks/pre-commit`, `.git./config`, `.git /config`, `.env::$DATA`, `server.key.` and
  `notes.txt:hidden` reached protected files or hidden streams (a git hook written with no prompt in
  accept-edits; `.env` read with no prompt in any mode). Fix (`galliani/workspace.py`): `normalize_relative`
  rejects, on every platform, components containing `: * ? " < > |` or control characters, ending in a dot
  or a space, or naming a reserved device (`CON`, `PRN`, `AUX`, `NUL`, `CONIN$`, `CONOUT$`, `COM0-9`,
  `LPT0-9`, superscript digits, with or without extension); `_blocked` compares case-folded names with
  `fnmatch.fnmatchcase`, ignoring a stream suffix and trailing dots and spaces. Tests:
  `test_git_directory_variants_are_refused_in_accept_edits`,
  `test_protected_files_via_data_stream_or_trailing_dot_are_not_written`,
  `test_protected_files_are_not_read_through_aliases`, `test_alternate_data_streams_of_ordinary_files_are_refused`,
  `test_accept_edits_task_cannot_plant_a_git_hook`, `test_names_windows_would_rewrite_are_invalid_on_every_platform`,
  `test_ordinary_names_that_look_like_devices_are_still_writable`; evals `accept_edits_git_hook_aliases_refused`,
  `protected_file_aliases_are_not_read`.
- **SEC-2 (High) Resolved target not re-checked against protected names. Fixed.** A link inside the
  workspace pointing at `.git` or `.env`, or the 8.3 short name `GIT~1`, reached protected files. Fix:
  `Workspace.resolve` checks `_blocked` again on the resolved path relative to the root (`_escapes`), and
  `list_files` and the `_nearby` hint skip items whose resolved path is protected or outside the root.
  Tests: `test_link_inside_the_workspace_to_git_is_refused`, `test_file_symlink_to_env_is_refused` (skipped
  where file symlinks need privileges), `test_short_8dot3_name_of_git_is_refused`.
- **SEC-3 (Medium) `tool_called` events carried raw tool arguments. Fixed.** `galliani/execution.py` now emits
  `resource` (the permission scope), `argument_names`, `files` (artifact paths) and `error` instead of
  `arguments`, so file bodies and memory text never reach `--events` files (014 Security). Tests:
  `test_events_name_files_but_never_their_contents`, `test_events_never_carry_memory_text`.
- **SEC-5 (Medium) No CSRF protection outside the desktop app. Fixed.** `app/api/routes.py` refuses (403)
  every non-GET/HEAD/OPTIONS `/api` request, in every mode, that carries neither `X-Requested-With` nor
  `X-App-Token`, or whose `Origin` is not the server's own. The app's page sends
  `X-Requested-With: galliani` (`app/web/index.html`). Contract change recorded in Decision 0032. Tests:
  `test_state_changing_calls_without_the_custom_header_are_refused`,
  `test_a_foreign_origin_is_refused_even_with_the_header`, `test_the_apps_own_page_passes_the_guard`,
  `test_desktop_token_counts_as_the_custom_header`. Known limitation (spec 012 R18, Error Handling): the
  `Origin` check compares `Origin` with the request's own `Host`, so a reverse proxy that rewrites `Host`
  (for example to `127.0.0.1:<port>`) while the browser keeps its own `Origin` gets 403 on every
  state-changing browser call. Running the local API behind a reverse proxy is unsupported; this fails
  closed and is documented, not fixed.
- **SEC-4 (Low) The API swallowed the "not eligible" error of approve-and-accept-edits. Fixed.**
  `AgentService.act` checks `accepts_edits(state.pending_permission.request)` before launching the job and
  answers 409; the prompt stays open. Test: `test_api_rejects_approve_and_accept_edits_on_a_non_write_prompt`.
- **SEC-6 (Low) 014 R3 enforced only for permission level. Fixed.** `ToolRegistry.register` refuses
  `workspace_edit` unless the definition was marked by `galliani.tools.confined_to_workspace`, which only
  `Workspace.tools()` calls. Any new caller must be reviewed against 014 R3. Tests:
  `test_a_hand_built_write_tool_cannot_opt_into_accept_edits`,
  `tests/core/test_evaluation.py::test_eval_write_tools_are_the_sandboxed_workspace_toolkit`.
- **SEC-7 (Low) Remaining filesystem edge cases. Mitigated.** Reserved device names are refused (SEC-1
  fix). Writes re-resolve the path just before writing and refuse if it changed or now resolves to a
  protected or outside path (`Workspace._recheck`). Test:
  `test_link_swapped_in_after_the_path_check_is_refused`. Residual risk, accepted: a process that can
  already write to the workspace and swaps a link in the microseconds between that re-check and the open
  is not detected (Windows has no portable `O_NOFOLLOW` for this). Such a process already runs with the
  user's rights.

### Re-review of the fixes (2026-10-15)

Independent re-review of Decision 0032 (QA). Probed on Windows 11 / NTFS: mixed separators, `.git/` with a
trailing slash, reserved names in subfolders (`sub/CON/x`, `sub/con.txt/x`), 8.3 names of `.env`,
`server.key` and `credentials.json`, junction chains ending in `.git`, Unicode look-alikes of `.git`
(dotless i, dotted capital I, zero-width space, fullwidth G), and CSRF variants (`Origin: null`, extension
origins, look-alike hosts, empty `X-Requested-With`, PATCH, trailing-slash redirects, `//api/...`, `/API/...`).
All were refused or harmless (NTFS does not fold the look-alikes onto `.git`). Mutation check: reverting
the name normalization, the resolved-path check, the re-check or the device-name check each fails a unit
test; reverting all of them fails the eval gates `permission_bypasses` and `false_done_on_negative`. A
case-sensitive `_blocked` was not caught by any test on Windows (the resolved-path check hides it while the
protected file exists), so `test_protected_names_are_case_folded_without_relying_on_the_filesystem` and
`test_git_hook_cannot_be_planted_before_the_repository_exists` now pin it.

New findings, pinned by tests in `tests/core/test_security_review.py` (strict xfails while open):

- **SEC-8 (Medium) DNS rebinding in workspace-root server mode. Fixed.** No `Host` allowlist, so a hostile
  name rebound to 127.0.0.1 was same-origin: its page could send `X-Requested-With`, start tasks (including
  accept-edits ones), approve writes, spend the server's provider key through `/api/chat`, and read task
  views and memory. The desktop app was not affected (its token is only in the window URL). Fix
  (`app/api/routes.py`, `foreign_host`): every request whose `Host`, port ignored, is not `127.0.0.1`,
  `localhost` or `[::1]` is refused with 403, before the token and CSRF checks; a missing `Host` or
  anything after the name other than `:<digits>` is refused too. Contract added to Decision 0032. Tests:
  `test_dns_rebinding_host_is_refused`, `test_look_alike_and_missing_hosts_are_refused`,
  `test_local_hosts_on_any_port_reach_the_app`, `test_desktop_app_on_its_launch_port_still_works`.
- **SEC-9 (Low) Hard links to protected files are not detected. Accepted residual risk (user decision
  2026-10-15).** `resolve()` cannot see hard links, so `notes.txt` hard-linked to `.env` is read (and a
  write through it changes `.env`). Rationale for accepting: creating a hard link needs a local process
  already running with the user's rights, which could read `.env` directly; git does not create hard links,
  so a cloned repository cannot plant one. Refusing every file with `st_nlink > 1` was the rejected
  alternative. Test (documents the accepted behavior, not a guarantee):
  `test_hard_link_to_env_is_read_accepted_residual_risk_sec9`.
  User-facing mitigation: do not point Galliani at a folder where untrusted software can create files, and
  keep real secrets outside the workspace.
- **SEC-10 (Info) Folders were created before the SEC-7 re-check. Fixed.** If a link was swapped in after
  `resolve`, `mkdir(parents=True)` created empty folders through it (e.g. `.git/hooks/`) before the write
  was refused. Fix: `write_file` and `write_files` run `_recheck` before `mkdir` and again before the
  write. Test: `test_swapped_link_gets_no_folders_created_through_it`.
- **SEC-11 (Low) Common token formats were not secrets to redaction. Fixed.** `galliani/redaction.py` now
  matches `gh[pousr]_` and `github_pat_` (GitHub), `AIza` (Google), `xox[abprs]-` (Slack), `glpat-`
  (GitLab) and `sk_live_`/`rk_live_`/`sk_test_`/`rk_test_` (Stripe; test keys added 2026-10-15, spec 012
  Security), so they are masked in events and refused by the memory
  secret check (`contains_secret`, spec 010). Tests: `test_common_token_formats_are_secrets`,
  `test_ordinary_text_is_not_a_secret`, `test_memory_refuses_a_github_token_but_saves_ordinary_text`.
- **Nits. Fixed.** The eval report no longer counts sandbox escapes a second time as "restricted tool
  execution(s) without an allowed permission decision" (`galliani/evaluation.py`; the
  `permission_bypasses` metric is unchanged); formatting in `galliani/web/agent_api.py`; the
  `app/api/routes.py` docstring now says every method except GET, HEAD and OPTIONS.

### Notes and limits

- `read_file` / `read_files` are read-only and never prompt. Their content is sent to the selected model
  provider and stored in Task State. Only protected names are kept out, so the SEC-1/SEC-2 fixes are what
  keep secrets on the machine.
- Redaction (`galliani/redaction.py`) masks `sk-...`, bearer tokens, AWS access key ids, PEM private key
  headers, and GitHub, Google, Slack, GitLab and Stripe tokens, Stripe live and test keys both (SEC-11).
  Other formats are not masked. The `sk-` false positive is fixed (spec 012 Security, Decision 0032). An
  `sk-` or Stripe key is masked when the character before it is not an ASCII letter or digit, or when it
  directly follows an escape: `%XX`, `%25XX`, `\n \r \t \f \v \b \0`, `\xNN`, `\uXXXX`, or an ANSI colour
  code (SGR, `ESC[...m`, with ESC as the raw character or written `\x1b`, `\033`, `\u001b` or `\e`).
  Ordinary words such as `task-runner-1234567890`, `disk-...` and `network_test_connectivitycheck` are left
  alone. Accepted trade-off: a key glued to a letter or digit (`abcsk-...`) is not masked. The two
  residuals of the 2026-10-15 re-review are fixed and their strict xfails are now regression tests in
  `tests/core/test_security_review.py`: `test_sk_key_after_an_ansi_colour_code_is_masked` (a key after
  an ANSI colour code) and `test_identifiers_ending_in_sk_or_rk_before_test_or_live_are_not_secrets` (the
  Stripe pattern now has the same left boundary as `sk-`).
- `desktop.log` (spec 012 R13). One `RedactingFilter` on the only `desktop.log` handler renders every
  record before the handler writes it. That includes records from every logger (`pywebview`, uvicorn,
  asyncio), tracebacks with chained causes, notes and exception groups, stack info, uncaught thread
  exceptions, warnings, and, in the windowed build, every stdout and stderr line, including unraisable
  exception reports. The filter removes the exact app token, window URL and base URL of this launch, then
  runs the shared redactor. A record that cannot be formatted is replaced by a fixed line, so it is never
  written raw. The filter rewrites the record in place. Handlers that run after it see only the redacted
  text, without `exc_info`. Handlers that run before it (none in the app; pytest's capture handler in
  tests) see the raw record. pywebview gets a `NullHandler`, so it never adds its own stderr handler.
  The log now starts before the port is chosen, so a `free_port()` failure is recorded, and the launcher
  waits up to 3 s for the local server to stop inside the log, so uvicorn's shutdown lines are recorded
  too, both redacted (tests `test_an_error_before_the_port_is_chosen_reaches_desktop_log_redacted` and
  `test_late_server_lines_reach_desktop_log_redacted` in `tests/test_desktop_webview2.py`).
  Residuals, all accepted (Info/Low):
  - In the windowed build (stderr is `None`), only text written before `desktop_log` starts (command-line
    parsing, creating the user data folder) or by a server thread still running after the 3 s wait is not
    recorded. Nothing leaks, but nothing is recorded either.
  - A token that one writer splits across two stdout/stderr writes, with a flush in between, lands on two
    lines, so neither line contains the whole token and the exact-token filter misses both halves.
    Nothing in Galliani or pywebview writes like this.
  - Other secrets appear only in shapes the shared redactor knows (see above).
  - `PYWEBVIEW_LOG` is ignored by design (spec 012 R13, R20, Security; Decision 0031). The app sets the
    `pywebview` logger's level itself, INFO or DEBUG with `--debug`, and restores the previous level on
    exit. R20 depends on pywebview's ERROR record reaching the watcher, so a user value such as `CRITICAL`
    must not be able to hide it, and a value such as `DEBUG` must not add pywebview detail to `desktop.log`
    beyond what the app allows. pywebview's import-time setup, which would read the variable, is skipped
    because `desktop_log` adds a `NullHandler` first. Nothing in the app or its runtime dependencies calls
    `logging.disable`, `logging.config` (uvicorn runs with `log_config=None`) or raises that logger's level;
    `tests/test_pywebview_pin.py` checks pywebview's own source for this, aliases included. pywebview's
    messages do not appear on the console of `python -m app.desktop`. They go only to `desktop.log`.
- WebView2 check (spec 012 R7, R8). The check matches pywebview 6.2.1's `_is_chromium()`. This is shown
  by the hand-written table and by a seeded differential test that runs the installed pywebview's own
  source against 1,500 random fake registries. The empty `REG_NONE` `pv` difference is fixed: it now
  stops the search as in pywebview (`test_an_empty_reg_none_pv_stops_the_search_like_pywebview`, no longer
  an xfail). On the R9, R14 and `--smoke-test` paths, pywebview's Windows backend is never imported.
- WebView2 installed but fails to initialize (spec 012 R20). The gap is closed for failures WebView2
  reports: pywebview 6.2.1 raises nothing and only logs `WebView2 initialization failed ...` at ERROR on
  the `pywebview` logger. A flag-only watcher on that logger matches exactly that record (logger name
  `pywebview`, level ERROR, unformatted `record.msg` prefix, before the page's `loaded` event). It keeps,
  copies, formats and writes nothing, so pywebview's record, which can hold paths and exception text,
  reaches `desktop.log` only through the redacting filter (tested with the token, the window URL and an
  `sk-` key in the record). A separate thread then closes the empty window, and the R12 box follows once
  the window is gone, with exit code 4 and the R13 case `webview2_init_failed`. No network, registry,
  process or file other than `desktop.log` is touched. The watcher thread's join is bounded (1 s), so a
  pywebview close that blocks cannot hang the exit (`test_a_close_that_blocks_cannot_hang_the_exit`).
  `tests/test_pywebview_pin.py` fails if pywebview rewords or moves the record, and the release checklist
  requires an R20 re-check on any pywebview upgrade. Known limitation that remains: a WebView2 start that
  never reports anything (a hang) is not detected; the window stays empty and the exit code is 0. There is
  no timeout backstop, by decision, because a timeout would close working apps on slow machines.
  - **R20-1 (Medium, fixed 2026-10-16; spec 012 R20 Signal clarification, AC "User Closes First").**
    Closing the window while WebView2 is still starting makes WebView2 itself report a failed
    initialization (`E_ABORT`), and pywebview logs the R20 text with the window's `closing` and `closed`
    events already set. Before the fix the launcher then showed the R12 box and exited with code 4 after
    the user's own close (reproduced 6 of 6 times within about 0.3 s of `shown`). Fix: the launcher's
    `loaded()` check in `app/desktop.py` is also true once `events.closing` or `events.closed` is set, so
    the watcher ignores that record; the watcher is unchanged and still flag-only. Evidence: (1) real
    window, pywebview 6.2.1, Windows 11, `app.desktop.main` itself with only the message box and opener
    stubbed, fresh `LOCALAPPDATA` and WebView2 profile per run, closed 0, 0.05, 0.1 and 0.2 s after `shown`
    (10 runs): pywebview logged the R20 text in all 10, and every run exited 0 with no box and no
    `webview2_init_failed` line. Control: with the `closing`/`closed` condition removed, the same probe
    gave exit 4 and the box (2 of 2), so the probe exercises the race. (2) A real failed initialization
    (empty `WEBVIEW2_RUNTIME_PATH`) still gives the box, exit 4 and the `webview2_init_failed` line (2 of
    2), with no token in `desktop.log`. (3) Tests: `test_the_report_caused_by_the_users_own_close_is_not_a_failure`
    (no longer an xfail), `test_either_close_event_alone_ignores_the_report` (`closing` alone, `closed`
    alone), `test_report_before_closing_was_set_still_shows_r12`, and
    `test_reading_the_close_events_fails_the_record_still_counts` (if reading the events raises, the record
    counts and nothing about the error is written). Mutation check of the condition: dropping `closing`,
    dropping `closed`, dropping both, inverting it, or requiring `loaded` too each fails at least one test.
- The evaluation suite runs every case against a real `Workspace` in a temporary folder seeded with
  `.env`, `.git/config`, `server.key` and a folder outside the workspace; changing them or leaking their
  text counts toward the `permission_bypasses` gate (`evals/cases/v0_1_sandbox.yaml`). CI runs on Windows,
  where the aliases would reach the real files; on Linux and macOS they are rejected by the same checks but
  would not reach the real files anyway. The eval cases do not seed links, so link handling (SEC-2) is
  guarded by unit tests only.
- The local API's CSRF guard alone does not stop DNS rebinding (a hostile name resolving to 127.0.0.1
  makes the page same-origin); the `Host` allowlist (SEC-8) closes it. A server started with `--host` on
  another address therefore only answers clients that use `127.0.0.1`, `localhost` or `[::1]`.

## Interactive Terminal Trust Boundary (spec 017, Decision 0034)

The interactive terminal (`galliacli`, `python -m galliani`, `python -m galliani.tui`; spec 018 R27 renamed
the console script from `galliani`, which stays the desktop app's name) is a front end only. It drives the
supervisor through its public methods, so permissions, sandboxing, memory and redaction are the ones
described above. What it adds is a new place where untrusted text is shown: a terminal acts on control
sequences, which a browser does not.

### Trust boundary

- Trusted: what the user types into the prompt. Slash commands are parsed only from that text (R34), so
  model output, tool output, file names, memory records and questions cannot change a setting, run a
  command or answer a prompt.
- Untrusted: everything else that is shown, including plan steps, tool and model output, approval prompts,
  questions, error text, memory records and route names. It comes from redacted lifecycle events and
  `TaskState.for_display()` (R17), never from raw `TaskResult.output`.
- Every transcript entry, every approval and question field, the plan panel, the banner and every completion
  label and summary pass `sanitize()` (`galliani/tui/commands.py`, re-exported by `galliani/tui/session.py`):
  `redact_text`, then removal of ESC sequences (CSI, OSC, DCS, SOS, PM, APC),
  of C0 and C1 controls except newline and tab, of DEL, and of bidi override and isolate characters
  (U+202A-U+202E, U+2066-U+2069). OSC 52 clipboard writes, OSC 8 links, title changes, cursor movement,
  screen clears and right-to-left file-name spoofing are removed, and `redact_text` runs again so a secret
  split by a stripped character is masked once rejoined. An 8-bit OSC or CSI loses its introducer and
  terminator, so what remains is printable text.
- Text is rendered with Rich `Text` and `markup=False`, so `[bold]` or `[@click=...]` stays literal. The
  result body is Markdown; Textual turns its links into click actions, not OSC 8 sequences, and
  `open_links=False` means a click opens nothing. Images are not loaded.
- Path validation (SEC-1) rejects file names with control characters before any prompt, so a file name
  can carry only bidi characters to the approval card, and `sanitize()` removes those.
- Plans that contain secret-like values are rejected before they run, so a key in a plan step never
  reaches the screen.

### Permissions

The TUI calls `Supervisor.approve` and `deny` and nothing else; the `a` key is offered and accepted only
when the supervisor lists `approve_and_accept_edits`, and it changes only the current task (014 R6). The
session default edit mode is kept in memory only (014 R9). `Esc` on an approval denies. One key press
decides at most one prompt. `tests/tui/test_security.py` runs every existing eval fixture that answers an
approval or a question through `Session` and through the one-shot loop, and checks that both end in the
same status, run the same tools and record the same permission decisions.

### Privacy

The TUI writes no transcript, history, settings, log or screenshot file. Textual's command palette and
screenshot actions are disabled. The only files are the ones the existing stack writes: approved workspace
edits, memory through approved `remember` calls, and the redacted `--events` log when the user asks for
it. The TUI opens no network connection of its own. `test_security.py` checks this with a Python audit
hook during a full Pilot session (task, approval, quit): no file is opened for writing except the approved
workspace file, and no non-loopback socket is opened. Textual's `TEXTUAL=devtools` and `TEXTUAL_LOG` can
send screen text to a devtools console or a log file. The app never sets them; only the user can.

### Review findings (task D, 2026-10-19)

Both findings were fixed in the spec 017 follow-up (the plan is sanitized when the session stores it, and
`sanitize()` redacts, strips, then redacts again); their tests now run without xfail markers.

Each open finding is pinned by a strict-xfail test in `tests/tui/test_security.py`. The test fails the
suite once the fix lands, as a reminder to remove the marker.

- **TUI-1 (High) Plan steps reach the terminal unsanitized. Fixed.** `SessionState.plan` is the raw
  `PlanView` from `build_task_view` (`galliani/tui/session.py:427`, `:517`). `PlanPanel` and `PlanSummary`
  render `step.purpose` and `revision_reason` (`galliani/tui/widgets.py:185`, `:211`). Rich `Text` strips
  only BEL, BS, VT, FF and CR, so ESC survives. A model-written plan (`ModelPlanner` parses JSON, and
  `\u001b` is valid JSON) can put OSC 52 clipboard writes, OSC 8 links, title and cursor sequences into
  the bytes Textual writes to the terminal, both in the docked panel and in the expanded summary. The
  transcript's plan entry is sanitized; the panel is not. Fix: build the session's `PlanView` with
  sanitized `purpose` and `revision_reason`. Tests: `test_hostile_plan_step_purposes_are_clean_in_state`,
  `test_screen_bytes_are_clean_for_a_hostile_plan[120|80]`.
- **TUI-2 (Medium) A secret split by a control character is masked before it is joined. Fixed.** `sanitize()`
  redacts first and strips second (`galliani/tui/session.py:62-63`, as R18 orders it). `sk-abcd\x1b[0mefgh...`,
  `sk-abcd‮efgh...`, a GitHub token with a BEL inside it, or an AWS key id with a NUL inside it does
  not match the redaction pattern, and then the strip joins it back into a whole, unmasked key on screen.
  Upstream event redaction ran on the same split text, so it missed the key too. Fix: run `redact_text`
  again after stripping, which also needs an R18 wording change. Test:
  `test_sanitize_masks_a_secret_split_by_control_characters`.

### Completion, `@file` mentions and the banner (spec 018, task D review 2026-10-19)

Spec 018 adds three new places where names reach the screen. None of them sends anything to a model,
writes a file, or opens a connection: completion only shows names to the user who typed the key.

- **`@file` completion** lists files only through `Workspace(root).list_files(ListIn(path=".", pattern="*"))`,
  so protected names (`.env*`, `*.key`, `*.pem`, `id_rsa*`, `credentials*`, `secrets*`), the `.git`,
  `.venv`, `node_modules` and `__pycache__` folders, and links or junctions that resolve outside the
  workspace or into a protected folder are never offered, and the 200-entry cap applies. The listing runs
  in a worker thread and is cached in process memory for 30 s per workspace; `/workspace` drops it.
  An accepted mention is plain text (`@notes.md`): the agent still reads files only through its
  permission-checked tools.
- **`/workspace` folder completion** lists folders under the typed parent (workspace-relative, absolute or
  `~`), which the user could type anyway. Names `Workspace._blocked` refuses are skipped, a typed parent
  with a protected segment lists nothing, dot-folders appear only when the typed segment starts with `.`,
  and the listing stops at 50 entries or 0.5 s.
- **R21, names are never cleaned and inserted.** A candidate whose name `sanitize()` would change (ESC
  sequences, C0/C1 controls, bidi characters, anything `redact_text` masks) is left out, so the inserted
  text is always exactly the displayed text and a hostile file name cannot smuggle a hidden suffix into the
  objective. Memory-id summaries are redacted as `/memory list` shows them (sensitive records read
  `[redacted]`) and only the session's own scopes are listed.
- **Banner.** Provider names come from `load_keys().keys()` only; no key value or fragment is shown. The
  workspace is shown with the home folder as `~`. When the workspace is the home folder or a drive root the
  banner adds the R25 warning; nothing about it is stored.
- **Working line and status line** show only `SessionState` (phase label, elapsed seconds, the task cost
  from `worker_completed` usage, `step N/M` from the plan). The rotating verbs are fixed UI strings, not
  model output, so they reveal no reasoning.
- **Motion and timers.** One app ticker drives all motion and runs only while a task is active or a
  transition is in flight; idle means no app-owned timer. `GALLIANI_REDUCED_MOTION=1`, animation level
  `none`, `NO_COLOR` and the ANSI theme give static output.
- **Popup keys fail closed.** The popup closes when an approval card or question appears; Enter, Tab and
  Up/Down never answer a prompt; `Esc` with the popup open only closes it.

`tests/tui/test_security.py` (section "spec 018") checks the File Mention, Unsafe Name and Banner
acceptance criteria on real files (protected names, a junction out of the workspace and one into `.git`;
C1 and bidi names on NTFS), feeds every escape payload through the file and folder listings, checks the
exact screen bytes with the popup open at 60 and 80 columns, checks that `y` still approves after popup use
and that completion writes nothing and opens no connection (audit hook).

Open findings from this review, each pinned by a strict-xfail test:

- **TUI2-1 (Medium) A slow `@` listing keeps the process alive after quitting.** `Session._workspace_files`
  (`galliani/tui/session.py`) runs `Workspace.list_files` through `asyncio.to_thread`. `list_files` walks and
  sorts the whole tree (`sorted(base.rglob("*"))`) before applying the 200 cap, so in a large workspace,
  such as the home folder the R25 warning is about, one `@` keystroke starts a walk that took more than
  60 s here. `complete` gives up after 2 s, but the thread cannot be canceled and Python joins the default
  executor at exit, so `/quit` hangs until the walk ends, and the walk costs CPU and memory meanwhile. Fix
  options: a bounded, lazily-stopped walk for completion (stop at 200 matches or a deadline), or a daemon
  thread that is abandoned on exit. Test: `test_018_a_slow_file_listing_does_not_keep_the_process_alive`.
- **TUI2-2 (Low) Folder completion can list inside `.git` through an alias.** `_complete_folders` checks the
  typed segments and each listed name with `Workspace._blocked`, but not the resolved folder, so
  `/workspace GIT~1/` (an 8.3 short name) or a junction to `.git` lists `hooks/`, `refs/` and the like.
  Only folder names are shown, to the local user, who could type the same path; `@file` is not affected
  (it resolves every path). Fix: resolve the base and refuse it when `_escapes`-style checks find a
  protected segment. Test: `test_018_folder_completion_never_lists_inside_git_through_an_alias`.
- **TUI2-3 (Low, from spec 017) Tab moves focus off the approval card.** After Tab or Shift+Tab, `y`, `n`
  and `a` do nothing until the card is focused again (`Esc` still denies). This fails closed: nothing is
  approved. Fix: keep focus on the card while it is shown, or bind the keys at the app level while the
  session waits. Test: `test_018_tab_on_the_approval_card_keeps_its_keys_live`.

## Installable Package (spec 016 Phase 5a, Decision 0039)

- **Nothing is written into the installation (R32).** The installed `galliani --smoke-test`, `galliacli --version`,
  `galliacli --help`, `galliacli` without a TTY and the import probe create, change or delete no file under the
  virtual environment, apart from `__pycache__` and `.pyc`. User data stays in `user_data_dir()` and the chosen
  workspace. `python -m scripts.check_wheel` step 5 compares venv snapshots before and after to prove it.
- **No PyPI install instructions (R37).** The project does not own the PyPI name `galliani`, so no doc, site page
  or release note tells users to fetch it from PyPI. The release notes install the wheel attached to the
  versioned release through a PEP 508 direct URL (`"galliani[tui] @ https://.../releases/download/vX.Y.Z/..."`),
  which never resolves `galliani` on PyPI. Its dependencies still come from PyPI, as for any source install.
  Open at the P5 review (2026-10-28): the README "Interactive terminal" section (P4, not yet done) and the
  in-app Textual-missing hint in `galliani/tui/entry.py` (Open Question 8 answered "reword", spec 017 R5 not
  yet amended) still print `pip install "galliani[tui]"`.
- **The wheel ships only runtime code and data.** `inspect_wheel` refuses any file outside `app/` and `galliani/`
  other than the `.dist-info` metadata, including a `.data` folder, so no `.env`, fixture or request log is
  packaged. `check_wheel` runs no task, calls no provider and prints no environment variable or key; the CI job
  keeps `contents: read` and uses no secret.
- **`.env` lookup unchanged.** `app.config.load_dotenv` still reads `.env` from the folder above `app/`. In a wheel
  install that is `site-packages`, where no `.env` exists unless someone who can already write to the
  environment puts one there. That is no new exposure.
- **Top-level `app` package (Open Question 7, accepted for Phase 5a).** The generic name can collide with another
  distribution's `app` in a shared environment; install with pipx or a dedicated venv. It must be renamed before
  any PyPI publication (Phase 5b).
