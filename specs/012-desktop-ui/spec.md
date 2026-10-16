# 012 - Desktop UI

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0018).

Amendment "Missing WebView2 on Windows" (requirements 6-15, its acceptance criteria and tests): **Approved for implementation (2026-10-15, approved by the user with every default; Decision 0031 Accepted).** Its open questions are resolved below.

Amendment to R7, R8 and R10 (pywebview's exact rule, the legacy-engine path, the pywebview pin): **Approved (2026-10-15, the user: "approve with defaults"; Decision 0031 amendment Accepted; Open Question 7 resolved).** It is folded into R7, R8 and R10 below; the reasons are kept under "Why R7, R8 and R10 read this way". **Implemented (2026-10-15):** the amended R6-R15 (detection in `app/webview2.py`, the R8 legacy-engine path, the `desktop.log` redaction, the pywebview pin) is in the code and covered by `tests/test_desktop_webview2.py`, `tests/test_pywebview_pin.py` and `tests/core/test_security_review.py`. Pending: the manual Windows 10 check on a real machine without WebView2 (`docs/release-checklist.md`) and the qa-security re-check (Implementation Tasks).

Amendment "Local API request guard" (requirements 16-19): **Approved (2026-10-15, Decision 0032 Accepted).** It writes down the contract already implemented in `app/api/routes.py` and pinned by `tests/core/test_security_review.py`.

Amendment "WebView2 installed but fails to initialize" (R20, its acceptance criteria, tests, tasks and Open Question 8): **Approved for implementation (2026-10-15, approved by the user with every default of Open Question 8; Decision 0031 R20 bullet Accepted).** It closes the QA gap recorded in `docs/security.md` (WebView2 check) for the case where WebView2 reports the failure; a hang stays a known limitation. R9, R12 (and its text), R13's existing cases and R14 are unchanged. With it, R13 gained one rule, approved at the same time: the app sets pywebview's log level itself and ignores `PYWEBVIEW_LOG` (Decision 0031). **Implemented (2026-10-15):** `InitFailureWatcher`, `watch_init_failure` and `launch_window` in `app/webview2.py`, the `PYWEBVIEW_LOG` rule in `app/desktop.py`, covered by `tests/test_desktop_webview2.py` and `tests/test_pywebview_pin.py`. Pending: the qa-security review, and the manual `WEBVIEW2_RUNTIME_PATH` run (Implementation Tasks).

R20 clarification (2026-10-15): the failure record is ignored once the window's `closing` or `closed` event is set, because the user's own close is not a failure. This makes the approved sentence "If the user closed the empty window before the flag was set, the exit is unchanged (0)" explicit; it is not a new requirement. QA reproduced the R12 box with exit code 4 when the window was closed within 0.2 s of `shown` (6 of 6 runs; not at 0.4 s or later). Formerly proposed as R20-A1, now folded into R20's Signal bullet and the AC "User Closes First" (Decision 0031). The code fix is in progress and not yet verified.

Proposed amendment R20-A2 (the close request): **Proposed, not approved (2026-10-15, Open Question 9 open, narrowed to R20-A2; Decision 0031 R20-A2 bullet Proposed).** R20 as approved stays in force until the user answers.

Requirements 1-5 remain approved and unchanged.

        ## Goal

        Define the desktop experience for starting, monitoring, approving, and reviewing Galliani tasks.

        ## Non-goals

        - Building a full visual design system.
- Exposing internal hidden reasoning.
- Replacing developer documentation.
- (WebView2 amendment) Bundling, downloading, or installing the WebView2 runtime or its bootstrapper. Galliani only points the user to Microsoft's page.
- (WebView2 amendment) A "use my browser instead" fallback when WebView2 is missing (Open Question 3, resolved: no).
- (WebView2 amendment) Translating the message into other languages. The app UI is English only; the dialog's Yes/No buttons are labelled by Windows in the user's language.
- (WebView2 amendment) Any telemetry, crash reporting, account, or server call about the missing runtime.
- (API guard amendment) Serving the local API under any host name other than `127.0.0.1`, `localhost` or `[::1]`, or granting CORS to any origin. Either would need a new, reviewed spec change.
- (API guard amendment) Authentication or accounts for the local API beyond the existing per-launch desktop token.

        ## Requirements

        1. The UI must let the user submit an objective.
2. The UI must show task status, plan steps, observations, approvals, verification, and final result.
3. The UI must clearly request permission when needed.
4. The UI must show public rationales without chain-of-thought.
5. The UI must distinguish Task State from durable Memory.

### Missing WebView2 on Windows (amendment, Approved 2026-10-15, Decision 0031)

Background, checked against the pinned dependency: pywebview (pinned `pywebview>=6.2,<7` by R7; 6.2.1 checked) decides while importing its Windows backend whether a usable WebView2 runtime exists by reading the registry (the Evergreen runtime, Beta, Dev and Canary client keys, a `pv` whose first number is at least 86, plus .NET Framework 4.6.2 or later). When the check fails it does not raise an error: it silently falls back to the deprecated Internet Explorer engine (MSHTML), which cannot run the bundled UI. The user sees a blank or broken window, and because the windowed build has no console, the only trace is `desktop.log`. These requirements replace that with a clear message.

6. **Where it lives.** The check and the message belong to the desktop launcher (`app/desktop.py` or a module next to it under `app/`). Nothing is added to the `galliani/` core, Task State, or Memory: no task exists yet when the check runs.
7. **Detection.** On Windows only, after the local server has started and before any window is created, the launcher decides whether a usable WebView2 runtime is present. "Usable" means exactly the rule of the pinned pywebview version (`webview/platforms/winforms.py` `_is_chromium()` in 6.2.1), reproduced in Galliani's own tested function, without importing pywebview's Windows backend:
   - **.NET Framework.** `HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full`, value `Release`, read once in the process's default registry view, must be at least 394802 (4.6.2). Absent or unreadable means missing.
   - **Paths and order.** For each client id in the order Evergreen runtime, Beta, Dev, Canary, and within each id for each hive in the order `HKEY_CURRENT_USER`, then `HKEY_LOCAL_MACHINE`: read the value `pv` from `SOFTWARE\Microsoft\EdgeUpdate\Clients\{id}` for `HKEY_CURRENT_USER`, and for `HKEY_LOCAL_MACHINE` when `platform.machine()` is `x86`; otherwise (any other machine, including AMD64 and ARM64) from `SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{id}`. Every read uses the default view (no explicit 32-bit or 64-bit view flag). An absent or unreadable key or value counts as not usable and the search continues.
   - **Version.** Only the first number of `pv` (the part before the first `.`) is compared. The runtime is usable at the first `pv` in the order above whose first number is 86 or higher; that `pv` is the reported version (R13, R15). A `pv` whose first number is below 86 (for example `0.0.0.0` or `85.0.564.40`) is not usable and the search continues. If a `pv` is present but its first part is not a number (including an empty value), the search stops and the runtime counts as missing, as in pywebview.
   - **No backend import first.** The launcher does not import pywebview's Windows backend (`webview.platforms.winforms`), directly, through `webview.start`, through `webview.guilib.initialize`, or through any other call that imports it, before this check has decided. So on the R9 path, and under R14, pywebview has changed nothing.
   - **Read-only.** The check only reads the registry. It makes no network request, starts no process, writes nothing, and finishes in under one second. On macOS and Linux the check is skipped and the launcher behaves as today.
   - **Pin.** The `desktop` extra in `pyproject.toml` pins pywebview to the range this rule was checked against: `pywebview>=6.2,<7`. A unit test fails when the installed pywebview is outside that range, so any upgrade forces a re-check of this rule against the new `winforms.py` and a spec update if the rule changed.
8. **No legacy engine.** The app must never show its window with the MSHTML (Internet Explorer) engine. If the R7 check passes but pywebview still selects a renderer other than Edge Chromium on Windows, no window is created and the launcher shows the R12 message box (not R9, because pywebview may already have written the values named in R10), writes the R13 line with case `webview2_legacy_engine`, stops the server and exits with code 4. With R7 mirroring pywebview's rule, this path is reachable only if pywebview's rule changes despite the pin. The R9 box is shown only when R7 reports missing or under R14.
9. **Missing-runtime message.** When the runtime is missing, the launcher shows a native, modal Windows message box (it must not need WebView2 to render) with the title, text, icon and buttons below, exactly. No window or web page is opened first.
   - Title: `Galliani needs Microsoft Edge WebView2`
   - Icon: information.
   - Buttons: Yes and No (the standard Windows Yes/No pair). The default button is No.
   - Text:

     ```text
     Galliani uses Microsoft Edge WebView2, a free component from Microsoft, to show its window. It is not installed on this PC. Nothing has been downloaded or changed on this PC. Nothing was sent anywhere.

     Open Microsoft's WebView2 page now?

     Yes opens the page in your browser, where you can install the Evergreen Runtime and then open Galliani again; No closes Galliani.
     ```

     The text has three paragraphs separated by one blank line: the explanation, the question the Yes/No buttons answer, and what each button does. (Wording revised 2026-10-15 after the ui-engineer copy review, approved by the user; Decision 0031.)
10. **The link.** Galliani contains exactly one WebView2 URL, defined in one place: `https://developer.microsoft.com/microsoft-edge/webview2/` (Microsoft's official WebView2 page, which offers the Evergreen Runtime download). The URL has no query string or fragment, so it carries nothing about the user, the machine or the app version. It is opened in the user's default browser only when the user selects Yes, and at most once per launch. Galliani never downloads, runs or elevates an installer, and never changes the registry or system settings on the user's behalf. Known exception, R8 path only: when pywebview itself selects the MSHTML engine, its own backend import (`webview/platforms/mshtml.py` `_set_ie_mode()` in 6.2.1) has already written two per-user values under `HKEY_CURRENT_USER\Software\Microsoft\Internet Explorer\Main\FeatureControl`, in the keys `FEATURE_BROWSER_EMULATION` and `FEATURE_96DPI_PIXEL` (each value named after the running executable), before the launcher can see its choice. Galliani writes nothing else and does not try to undo them. No message box and no site text claims that nothing changed on that path; the R12 text, shown there, makes no such claim.
11. **Exit after the message.** After the user answers Yes or No (a Yes/No message box has no Cancel, so Windows disables its close button and Esc; any other result is treated as No), the launcher stops the local server and exits with exit code 3. No window opens, no background process remains, and the dialog is not shown again in that launch. Nothing is remembered: the next launch checks again, and if the runtime is now installed the app opens normally. There is no "don't ask again" setting.
12. **Window that fails to start.** If the runtime is detected but creating or starting the window raises an error, the launcher shows a second native message box, then stops the server and exits with exit code 4.
    - Title: `Galliani could not open its window`
    - Icon: warning. Buttons: Yes and No, default No.
    - Text (where `<log path>` is the full path of `desktop.log` in the user data folder):

      ```text
      Galliani could not open its window. Microsoft Edge WebView2 may be damaged or out of date. Reinstalling or updating it often helps.

      Select Yes to open Microsoft's WebView2 download page in your browser. Select No to close Galliani.

      Details were saved on this PC only, in:
      <log path>
      ```
    - Yes opens the R10 URL under the same rules.
13. **Local log only, no telemetry.** The launcher writes one line per occurrence to the existing local `desktop.log`: the time, which case happened (`webview2_missing`, `webview2_legacy_engine`, or `window_start_failed`), the detected version or "none", and the user's answer (`opened_download_page` or `closed`). For R12 it also writes the exception type and message. Log lines never contain the app token, the window URL, API keys, or the contents of the credential store. This holds for everything written to `desktop.log`, not only the launcher's own lines: records from pywebview's own logger (`pywebview`) and any traceback written there (including one re-raised from pywebview or from the window start in R12) pass through the same redaction first (see Security). Nothing about the check, the answer or the error is sent anywhere, by Galliani or through the URL. R20 adds the case `webview2_init_failed`.
    - **pywebview's log level is set by the app (added 2026-10-15 with R20, Decision 0031).** While the app runs, the launcher sets the `pywebview` logger's level itself: DEBUG when started with `--debug`, otherwise INFO. The `PYWEBVIEW_LOG` environment variable is ignored, whatever its value (valid level name, invalid name, empty). So a user setting can neither hide pywebview's ERROR records, which R20 depends on, nor put more pywebview detail into `desktop.log` than the app's own level allows. Every pywebview record reaches `desktop.log` only through the redacting filter. The previous level is restored when the log closes, as today.
14. **Simulation flag.** `python -m app.desktop --simulate-missing-webview2` (and the same flag on `Galliani.exe`) forces the R9 path on any machine, so the message, the link and the exit can be checked without uninstalling WebView2. It changes nothing else and is documented in `--help`.
15. **Smoke test.** `--smoke-test` adds one informational line, `INFO  webview2: <version>` or `INFO  webview2: missing`. It never fails the smoke test, because CI runners and clean machines differ. The existing PASS/FAIL checks and exit codes are unchanged.

#### Why R7, R8 and R10 read this way (amendment approved 2026-10-15, Decision 0031)

Found during the core-engineer implementation review and checked against pywebview 6.2.1 (`webview/platforms/winforms.py` `_is_chromium()`, `webview/platforms/mshtml.py` `_set_ie_mode()`). Approved by the user with the three defaults of Open Question 7.

- **The R8 probe writes to the registry.** pywebview decides its renderer while importing its Windows backend. When it decides MSHTML, the same import calls `_set_ie_mode()`, which writes two per-user values under `HKCU\Software\Microsoft\Internet Explorer\Main\FeatureControl` (`FEATURE_BROWSER_EMULATION` and `FEATURE_96DPI_PIXEL`; the second was found by qa-security). The launcher cannot learn pywebview's choice without those writes having happened. Showing R9 there would make "Nothing has been downloaded or changed on this PC." untrue, so R8 shows R12 instead and R10 names the exception.
- **The earlier R7 differed from pywebview's rule, which made that path reachable.** (a) On any non-x86 Windows, pywebview reads HKLM only at `SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{id}` plus HKCU; it never reads the native 64-bit HKLM path, which the earlier R7 accepted. (b) It reads the .NET `Release` value once, in the process's default view; the earlier R7 accepted either view. (c) It compares only the first number of `pv`; the earlier R7 compared the full version against 86.0.622.0, so a runtime from 86.0.0.0 to 86.0.621.x would have shown R9 although pywebview would use it. (d) It checks the client ids in the order runtime, Beta, Dev, Canary and, within each, HKCU before HKLM, and a present but non-numeric `pv` (including empty) ends the whole check; the earlier R7 skipped such a value and kept looking.
- **Rejected alternatives.** Rewording the twice-approved R9 text (it is true on every path where R9 is shown once the rule is mirrored); replacing pywebview's private `_set_ie_mode` with a no-op before the probe (removes the writes, but patches a private function and fails silently if pywebview renames it).
- **R9, R11, R12, R14, R15 and the R9 and R12 texts are unchanged.** R13 only gained the sentence on pywebview's logger and tracebacks.

### WebView2 installed but fails to initialize (amendment R20, Approved 2026-10-15, Decision 0031)

Approved by the user on 2026-10-15 with the defaults of Open Question 8: option (b), pywebview's own failure record; no timeout backstop; no new simulation flag; the R12 text unchanged.

Background, checked against pywebview 6.2.1 (read-only): R12 fires only when "creating or starting the window raises an error". When WebView2 is registered (R7 passes) and pywebview picks `edgechromium` (R8 passes) but the runtime is damaged, the WebView2 control reports `CoreWebView2InitializationCompleted` with `IsSuccess` false. pywebview's handler (`webview/platforms/edgechromium.py` `EdgeChrome.on_webview_ready`, lines 267-273) only calls `logger.error('WebView2 initialization failed with exception:\n ' + ...)` on the `pywebview` logger and returns. Nothing raises, no page is loaded, and the window's `loaded` event never fires. The user gets an empty window. When they close it, the exit code is 0, and they never see the R12 box. Two pywebview facts limit the options: the window's `shown` event fires on the WinForms `Form.Shown` event whether or not WebView2 started (`webview/platforms/winforms.py` `on_shown`, lines 367-369). The `loaded` event fires only after a navigation completes and pywebview's script is injected (`webview/util.py` `inject_pywebview`, lines 229-238).

20. **WebView2 that fails to initialize.** On Windows, after R7 reports "present" and R8 confirms `edgechromium`, the launcher must detect pywebview's report that WebView2 failed to initialize and handle it like a window start failure (R12).
    - **Signal.** The signal is a record from the `pywebview` logger at level ERROR whose unformatted message (`record.msg`, before any formatting or redaction) starts with `WebView2 initialization failed`. That is the exact prefix pywebview 6.2.1 logs in `EdgeChrome.on_webview_ready` when `IsSuccess` is false. No other record, level or logger counts. The record counts only while the window's `closing` and `closed` events are both not set (and `loaded` is not set, below). Once `closing` or `closed` is set, a matching record is ignored: the user's own close is not a failure, even when the WebView2 control disposed by that close reports `IsSuccess` false. A flag already set before `closing` was set stays set. The `closing`/`closed` check is injectable like `loaded` (a `WindowHooks` field); if reading those events fails, the record counts. (Clarification of the approved "user closed first" rule below, 2026-10-15; folded in from proposed R20-A1, see "Why R20 reads this way".)
    - **Watcher.** The launcher attaches one watcher handler to the `pywebview` logger just before it creates the window. It removes the handler when `open_window` returns or raises. The handler only sets a flag. It stores, copies, formats and writes nothing. The record still reaches `desktop.log` only through the R13 redacting handler, exactly as today.
    - **The ERROR record must never be filtered out first.** The watcher only sees the record if the `pywebview` logger lets ERROR through. So no setting, flag or environment variable may set the `pywebview` logger's level above ERROR, or disable logging at ERROR or above, while the window starts. The app sets that level itself (INFO, or DEBUG with `--debug`) and ignores `PYWEBVIEW_LOG` (R13). The watcher handler itself has level NOTSET or ERROR and no filter other than the R20 signal match.
    - **Only before the page is up.** The signal counts only while the window's `loaded` event is not set. A matching record after `loaded` is ignored.
    - **No timeout.** The decision depends only on the failure report, never on elapsed time. A slow start, however long, never shows the box.
    - **What happens.** When the flag is set, the launcher closes the pywebview window, outside the logging call, so no empty window is left behind the box. That close is not a user close and does not lead to exit code 0. Once `webview.start` has returned, the launcher shows the R12 box with the R12 text unchanged. It writes one R13 line with the new case `webview2_init_failed`, the detected version, the answer, and `error=WebView2InitializationFailed`. The exception detail is already in `desktop.log`, redacted, through pywebview's own record. Then it stops the server and exits with code 4. Yes and No behave as in R10 and R11. If the user closed the empty window before the flag was set, the exit is unchanged (0); this includes a failure record that arrives after the close started (`closing` or `closed` set), because such a record is ignored (Signal). If the flag was set before the user closed it, the R12 box is still shown. The launcher's own close happens only after the flag is set, so it never cancels the box.
    - **Nothing new leaves or changes the PC.** There is no network request, no process started by Galliani, no registry write, no file other than `desktop.log`, and no telemetry. The R10 URL opens only on Yes.
    - **Pinned to pywebview's text.** A unit test reads the source text of the installed `webview/platforms/edgechromium.py` without importing it. The test fails unless `on_webview_ready` still contains a `logger.error(` call whose string starts with `WebView2 initialization failed`. Its failure message says to re-check R20. Together with the `pywebview>=6.2,<7` pin (R7), any pywebview upgrade that rewords or removes the report fails CI instead of silently bringing back the empty window.
    - **Known limitation that remains.** A WebView2 start that never reports anything, a hang, is not detected. The window stays empty, as before R20. There is no timeout backstop (Open Question 8 b).
    - **No simulation flag.** R20 adds no command-line flag. The manual check uses pywebview's `WEBVIEW2_RUNTIME_PATH` setting from a source checkout (Tests, Open Question 8 c).

#### Why R20 reads this way (approved 2026-10-15)

- **(a) Events with a bounded timeout. Rejected as the primary signal.** `shown` cannot tell success from failure, because it fires on `Form.Shown` either way. `loaded` is a correct success signal, but only a timeout can turn its absence into a failure. The first WebView2 start on a slow machine can take many seconds: it creates the profile folder under the user data folder, starts the `msedgewebview2` processes, and antivirus scans them. Sleep or resume during start-up, or a debugger, stretches that further. A timeout short enough to help (5-10 s) would close a working app and tell the user their WebView2 "may be damaged". That is the worst outcome: a false alarm that also stops a working app. A timeout long enough to be safe (60 s or more) arrives after the user has already closed the empty window. The false-positive risk is high and grows on exactly the machines (old, slow, Windows 10) this amendment serves.
- **(b) The pywebview log record. Chosen.** It is a positive report made by WebView2 itself (`IsSuccess` false), delivered within the same start-up. It has no time element, so a slow machine can never trigger it. It needs no private pywebview attribute and no .NET types in the launcher. It uses only the logger that R13 already filters. The cost is depending on a log string, not an API. The source-text pin test and the `<7` pin turn a silent drift into a failing test.
  - **False-positive risk: low.** It needs WebView2 to report a real initialization failure. A failure with a cause other than a damaged install, for example a locked or unwritable profile folder, low memory, or a group policy that blocks the runtime, also shows the R12 box. Its hedged text ("may be damaged or out of date ... often helps") is still more useful than an empty window, and the exact cause is in `desktop.log`.
  - **False-negative risk.** A hang that never reports (R20 known limitation).
- **(c) Accept as a known limitation. Rejected.** R12 already names "may be damaged" as its case, and an empty window with exit code 0 is exactly what the WebView2 amendment set out to remove.
- **Dependence on the log level.** Because (b) reads a log record, anything that raised the `pywebview` logger's level above ERROR would silently switch R20 off. That is why R13 has the app set pywebview's level itself and ignore `PYWEBVIEW_LOG`.
- **(d) Subscribe to `CoreWebView2InitializationCompleted` directly. Rejected.** This would go through `window.native` and pywebview's private `browser.webview` attribute, and would add .NET types to the launcher. The handler must also be attached before the control's own asynchronous start completes, which is a race. If pywebview renames the attribute, it fails silently. This is the same reason `_set_ie_mode` patching was rejected in the R7/R8/R10 amendment.
- **The `closing`/`closed` rule in Signal (clarification, 2026-10-15, formerly proposed R20-A1).** This is not a new requirement. It makes explicit what the approved sentence "If the user closed the empty window before the flag was set, the exit is unchanged (0)" already requires. If the user closes the still-empty window while WebView2 is starting, WinForms disposes the WebView2 control, and the pending `EnsureCoreWebView2Async` can complete with `IsSuccess` false (for example an `ObjectDisposedException` or an aborted-operation `COMException`). pywebview logs that through the same `WebView2 initialization failed with exception:` line. Without the rule, a record arriving before `launch_window` removes the watcher (including the moment after `webview.start` returns) sets the flag and shows the R12 box with exit code 4 for what was only a user close. **Evidence:** QA reproduced it on Windows (2026-10-15): closing the window within 0.2 s of `shown` produced the R12 box and exit code 4 in 6 of 6 runs; closing at 0.4 s or later did not. Cost: a real damaged-runtime failure reported only after the user already clicked close shows no box on that launch; the user chose to close, and the next launch reports the same failure.

### Proposed amendment R20-A2: the close request (PROPOSED, NOT APPROVED, Open Question 9)

**Status: Proposed. Not approved. Nothing here may be implemented until the user answers Open Question 9.** R20 above stays the approved requirement. This section only proposes an addition to it. Raised in the code review of the R20 implementation (2026-10-15) and checked against pywebview 6.2.1 (read-only). The former concern (a) of this section, the user close during start (R20-A1), was folded into R20's Signal bullet as a clarification of the approved text on 2026-10-15 and is no longer part of this proposal.

**Concern (b): the close request can block, and the thread is only joined for 1 s.** `close_window` calls pywebview's `Window.destroy()`, which is decorated `_shown_call`: it waits up to 20 s for the window's `shown` event and then raises `WebViewException('Main window failed to start')`. `watch_init_failure` joins its thread for only 1 s. So (1) if `shown` is late, the empty window stays up to 20 s before the close happens; (2) if the user closes the window while `destroy()` is still waiting, `launch_window` goes on after 1 s and the thread is abandoned (daemon). When it wakes, `destroy_window` finds no instance and does nothing, or `destroy()` raises after 20 s and the thread logs "The empty window could not be closed" after `desktop_log` has already closed. That late line goes to Python's last-resort stderr handler (a console run) or nowhere (windowed build). It holds only an exception type name, so it leaks nothing, but it is a write outside `desktop.log` and outside R13.

**Proposed text (addition to R20; the approved bullets stay as written):**

- **R20-A1.** Folded into R20 (Signal) on 2026-10-15 as a clarification; see "Why R20 reads this way". Not part of this proposal.
- **R20-A2. The close request never blocks the launcher and never writes late.** The close thread does not call `close_window` until the window's `shown` event is set, waiting in the same 0.2 s steps it already uses and stopping as soon as the launcher's `done` is set. It does not call `close_window` if `closing` or `closed` is already set. The launcher's join on that thread stays bounded (1 s); there is no new timeout, and no decision depends on elapsed time. A close still pending when the launcher continues is abandoned, and the thread writes no log line once `done` is set. So nothing is written outside `desktop.log`.
- **Unchanged.** The R12 text, the R13 case `webview2_init_failed`, exit code 4, no timeout backstop, no new flag, no network, the pin tests.

**Proposed acceptance criteria (not yet part of the AC list):**

- *Close Request Waits for Shown (R20-A2).* Given the flag is set while `shown` is not set, `close_window` is not called until `shown` is set; given `closing` or `closed` is already set, `close_window` is never called; given the launcher returns while the thread is still waiting, the launcher returns within the 1 s join (fake clock, no real sleep) and the thread writes no log record after that.

**Recommendation.** Approve R20-A2. It removes a 20 s wait and a log line written outside R13. It does not need private pywebview attributes: `events.shown`, `events.closing` and `events.closed` are public. Not recommended: lengthening the 1 s join (it would delay the R12 box or a normal exit), or catching `WebViewException` only (it leaves the 20 s wait).

### Local API request guard (amendment, Approved 2026-10-15, Decision 0032)

The desktop window and the browser-served UI both talk to the same local HTTP API (`app/api/routes.py`, with the agent routes in `galliani/web/agent_api.py`). That API can approve or deny agent writes, change the edit mode, start tasks, and save keys and memory. These requirements stop other web pages open in the user's browser from driving it (cross-site requests, SEC-5) and stop DNS rebinding (SEC-8). They apply in every mode: the desktop app (with its per-launch `X-App-Token`) and the server started without a desktop token.

16. **Host allowlist.** The server refuses with 403 every request, on every path including `/` and static files and for every method, unless its `Host` header names `127.0.0.1`, `localhost` or `[::1]`, compared case-insensitively. The name may be followed only by `:<digits>` (any port, so the desktop app's random launch port works). A missing or empty `Host`, a look-alike (`127.0.0.1.attacker.example`, `evil.localhost`, `[::1].evil`, `localhost:80.evil`), another loopback or wildcard address (`127.0.0.2`, `0.0.0.0`), or any other name is refused. A server started with `--host` on another address therefore answers only clients that use one of these names; there is no opt-in for other names.
17. **Custom header on state-changing calls.** Every request under `/api/` whose method is not GET, HEAD or OPTIONS (POST, PUT, PATCH, DELETE and any other), including trailing-slash variants of a route, must carry a non-empty `X-Requested-With` header (any value; the app's own page sends `galliani`) or the `X-App-Token` header. Otherwise it is refused with 403 and a `detail` that starts with "Cross-site". The header is what forces a browser to preflight a cross-site request; the server grants no CORS, so the preflight fails. In desktop mode the existing token check still applies on top of this rule. GET, HEAD and OPTIONS are unchanged.
18. **Origin check.** When a request covered by R17 carries an `Origin` header, it must be the server's own origin: scheme `http` or `https`, and a host and port equal to the request's `Host` header (compared case-insensitively; R16 has already limited `Host` to the local names). Any other value is refused with 403 and the R17 "Cross-site" detail, including `null` (sandboxed frames, `file://` pages), browser-extension origins, and look-alike hosts. A request without `Origin` (a non-browser client) is judged by R16 and R17 alone.
19. **Clients and errors.** The app's own pages (desktop and browser) send `X-Requested-With: galliani` on every state-changing call and are never refused by R16-R18. A refusal is a structured JSON error (`{"detail": ...}`) that names the rule, never echoes header values or the app token, and changes no state. Other API clients (scripts, tests) must send the header; this is documented wherever the API is documented.

        ## Behavior

        - A user starts a task from an objective input.
- The task view updates as lifecycle events arrive.
- Approval prompts pause the task until answered.
- Final results include verification status and artifacts.

        ## Interfaces and Data Contracts

        - `TaskViewModel`: task_id, status, objective_summary, plan, current_step, observations, approvals, verification, result.
- `ApprovalPrompt`: prompt_id, action_summary, risk_summary, allowed_choices, scope.
- `EventFeedItem`: timestamp, type, public_summary, refs.
- `MemoryIndicator`: record_id, summary, provenance, sensitivity.

        ## Error Handling

        - Disconnected event stream shows stale state and retry option.
- Permission denial explains that execution is blocked.
- Failed tasks show safe error summaries and next options.
- (WebView2 amendment) A missing or unusable WebView2 runtime shows the R9 message box instead of a blank or broken window; a window that fails to start, or pywebview still choosing the legacy engine (R8), shows the R12 message box. An unreadable registry key counts as "missing", never as a crash. If the native message box itself cannot be shown, the launcher still writes the R13 log line and exits with the same code.
- (R20) A WebView2 runtime that is registered but reports a failed initialization closes the empty window and shows the R12 box with exit code 4 (case `webview2_init_failed`). A start that never reports success or failure is not detected (known limitation).
- (API guard amendment) A request refused by R16-R18 gets 403 with a JSON `detail` and nothing runs: no task starts, no approval or denial is recorded, no key, memory or edit mode changes. The UI shows a refusal as a safe error, never as success.
- (API guard amendment, known limitation) The R18 Origin check compares `Origin` with the request's own `Host` header. A reverse proxy in front of the server that rewrites `Host` (for example to `127.0.0.1:<port>`) while the browser still sends its own `Origin` makes every state-changing call from a browser get 403. Running the local API behind a reverse proxy is an unsupported setup; this is documented, not fixed.

        ## Security

        - The UI must not display hidden reasoning.
- Sensitive observations must be redacted or collapsed.
- Approval prompts must describe scope before the user consents.
- (WebView2 amendment) The WebView2 check is read-only and offline (R7), and pywebview's Windows backend is not imported before it decides, so on the R9 path nothing on the PC has changed. The only registry writes in the process are pywebview's own two `FeatureControl` values on the R8 path (R10 known exception). The only network action is the user's own browser opening the fixed Microsoft URL after they select Yes (R10). The app token and window URL never reach the log or the dialogs (R13).
- (WebView2 amendment) **Everything in `desktop.log` is redacted (R13).** The handler that writes `desktop.log` applies one filter to every record from every logger, including pywebview's own `pywebview` logger, and to the formatted traceback of any exception logged or re-raised into it (`exc_info`, `logging.exception`, an uncaught exception hook). The filter removes the exact app token and window URL of the current launch (known to the launcher) and then applies the shared redactor `galliani/redaction.py`. No code path writes to `desktop.log` around that filter.
- (R20) The R20 watcher on the `pywebview` logger only sets a flag. It keeps no copy of the record, writes nothing, and opens no file or connection, so it adds no path around the R13 filter. Detection is in-process only: no telemetry and no new network access.
- (R13, R20) **`PYWEBVIEW_LOG` is ignored.** The `pywebview` logger's level comes only from the app (INFO, or DEBUG with `--debug`). An environment variable cannot raise it above ERROR, which would hide the R20 failure record, and cannot lower it to add pywebview detail to `desktop.log`. All pywebview records pass the R13 redacting filter.
- **Redaction trade-offs (shared redactor `galliani/redaction.py`, used here, in Task State, events and the memory secret check; recorded 2026-10-15, Decision 0032).**
  - An `sk-` key is masked when the character before `sk-` is not a letter or digit (start of text, space, punctuation, quote), or when `sk-` directly follows an escape, where a real key still starts: a URL escape `%XX`, including a double-encoded one such as `%253D`; a string escape `\n`, `\r`, `\t`, `\f`, `\v`, `\b` or `\0`; a hex escape `\xNN`; or a Unicode escape `\uXXXX`.
  - Accepted trade-off: an `sk-` key glued directly to a letter or digit with no escape before it (for example `abcsk-...`) is not masked. Masking it would also mask ordinary words ending in "sk" (`task-runner-1234567890`, `disk-...`) and make memory refuse them.
  - Stripe test keys `sk_test_` and `rk_test_` are secrets and are masked like `sk_live_` and `rk_live_`.
- (API guard amendment) The local API trusts no other web origin: no CORS headers are ever sent (R17), state-changing calls need a header a cross-site page cannot send without a failed preflight (R17, R18), and hostile host names are refused before any route runs (R16). Threat model and findings SEC-5 and SEC-8: `docs/security.md`.

        ## Acceptance Criteria

        ### Start Task

Given the user enters an objective

When they submit it

Then a task view opens with created or planning status.

### Approval

Given a restricted tool is needed

When the task reaches the permission boundary

Then the UI shows a clear approval prompt and pauses execution.

### Done

Given verification passes

When the task completes

Then the UI shows final result, verification summary, and artifacts.

### Missing WebView2 (amendment, Approved)

Each criterion names the requirements it verifies. "Fake registry" means the detection function reads through an injected reader, so tests run on any machine.

#### WebView2 Detected (R7)

Given a fake registry with the Evergreen runtime `pv = 120.0.2210.91` under `HKEY_CURRENT_USER` only, and .NET `Release = 528040`
When the launcher checks for WebView2
Then the result is "present, 120.0.2210.91", no network or subprocess call was made, and nothing was written.

And, each case giving the same answer as pywebview 6.2.1 (.NET `Release = 528040` unless stated):
- (a) `platform.machine()` is `AMD64` or `ARM64` and the runtime `pv = 120.0.2210.91` is under HKLM `SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{id}`: "present, 120.0.2210.91". `platform.machine()` is `x86` and the same `pv` is under HKLM `SOFTWARE\Microsoft\EdgeUpdate\Clients\{id}`: "present".
- (c) `pv = 86.0.0.0` or `86.0.621.99`: "present" with that version.
- (d) The runtime `pv = 85.0.564.40` under HKCU and `pv = 120.0.2210.91` under HKLM: "present, 120.0.2210.91" (a too-old value does not stop the search). The runtime under HKCU `pv = 120.0.2210.91` and Beta under HKCU `pv = 130.0.1.1`: "present, 120.0.2210.91" (first in order wins). Only Canary `pv = 120.0.2210.91`: "present".
- Every registry read used the default view (the fake reader records that no explicit 32-bit or 64-bit view flag was passed), and .NET `Release` was read exactly once.

#### WebView2 Absent or Unusable (R7)

Given a fake registry with no WebView2 client keys, or `pv` empty, `0.0.0.0`, or `85.0.564.40`, or .NET `Release = 394254`, or an unreadable key
When the launcher checks for WebView2
Then the result is "missing" in every case, never a crash.

And, each case giving the same answer as pywebview 6.2.1:
- (a) `platform.machine()` is `AMD64` or `ARM64` and the only `pv` is under HKLM `SOFTWARE\Microsoft\EdgeUpdate\Clients\{id}` (not `WOW6432Node`): "missing".
- (b) .NET `Release` is present only where an explicit non-default view would find it (the fake reader returns it only when a view flag is passed): "missing".
- (d) The runtime `pv` under HKCU is empty or `abc`, and a valid `pv = 120.0.2210.91` exists under HKLM or under Beta: "missing" (a non-numeric value stops the search).

#### Non-Windows Skips the Check (R7)

Given the platform is not Windows
When the launcher starts
Then no WebView2 check runs and no dialog is shown.

#### Legacy Engine Refused (R8)

Given the check reports "present" but pywebview reports a renderer other than `edgechromium`
When the launcher is about to open the window
Then no window is created, the R12 message box is shown (never R9), the `desktop.log` line has case `webview2_legacy_engine`, the server is stopped, and the exit code is 4.

#### Backend Not Loaded Before the Check (R7, R14)

Given the check reports "missing", or `--simulate-missing-webview2` is set
When the R9 message box is shown and the launcher exits
Then `webview.platforms.winforms` is not in `sys.modules`, neither `webview.start` nor `webview.guilib.initialize` was called, and no registry write was made (the fake writer fails the test if called).

#### pywebview Pin (R7)

Given the test environment
When the unit tests run
Then a test passes only if the installed pywebview version is at least 6.2 and below 7, and the `desktop` extra in `pyproject.toml` reads `pywebview>=6.2,<7`; outside that range it fails with a message that says to re-check R7 against the new `winforms.py`.

#### Message Text (R9, R12)

Given the missing-runtime case and the window-failure case
When each message box is shown
Then its title, text, icon, buttons and default button match R9 and R12 exactly (golden test), and no pywebview window was created before it.

#### Yes Opens Microsoft's Page Only (R10, R11)

Given the missing-runtime message box is shown
When the user selects Yes
Then the default browser is asked to open exactly `https://developer.microsoft.com/microsoft-edge/webview2/` once, no file is downloaded or run by Galliani, the local server is stopped, and the process exits with code 3.

#### No Opens Nothing (R10, R11)

Given the missing-runtime message box is shown
When the user selects No
Then no URL is opened, the local server is stopped, no Galliani process remains, and the exit code is 3.

#### Next Launch Rechecks (R11)

Given the user selected No on one launch and then installed WebView2
When they start Galliani again
Then the main window opens normally and no message box appears.

#### Window Start Failure (R12)

Given the check reports "present" and starting the window raises an error
When the launcher handles it
Then the R12 message box shows the real `desktop.log` path, Yes and No behave as in R10 and R11, and the exit code is 4.

#### Local Log Without Secrets (R13)

Given any of the three cases
When the launcher writes to `desktop.log`
Then exactly one line names the case, the detected version or "none", and the answer, and the log contains neither the app token nor the window URL.

#### pywebview Logger and Tracebacks Redacted (R13, Security)

Given a known app token in the window URL, a record logged by the `pywebview` logger that contains the URL, and an exception whose message contains the URL and an `sk-` key, logged with its traceback and re-raised (as in the R12 window failure)
When both reach `desktop.log`
Then the file contains neither the token, nor the window URL, nor the key; the case line of R13 is still written.

#### Redaction Trade-offs (Security)

Given the shared redactor
When it is applied to text containing an `sk-` key at the start, after a space, after `%3D`, after `%253D`, after `\n`, `\b`, `\0`, `\x3d` or `=`, or a Stripe `sk_test_`, `rk_test_`, `sk_live_` or `rk_live_` key
Then every key is masked;
and `task-runner-1234567890` and `disk-1234567890abcdef` are left unchanged (and so is an `sk-` key glued directly to letters, the accepted trade-off), with `test_words_ending_in_sk_are_not_secrets` passing as a normal test, not an xfail.

#### No Telemetry (R10, R13)

Given network access is blocked or monitored during a test of the missing-runtime path
When the user selects No
Then Galliani made no outbound connection; when the user selects Yes, the only outbound request comes from the browser, to the R10 URL.

#### Simulation (R14)

Given a machine with WebView2 installed
When Galliani starts with `--simulate-missing-webview2`
Then the R9 message box appears and R10 and R11 hold.

#### Smoke Test Unaffected (R15)

Given a machine with or without WebView2
When `--smoke-test` runs
Then it prints one `INFO  webview2:` line, and its exit code depends only on the existing PASS/FAIL checks.

#### WebView2 Fails to Initialize (R20)

Given the check reports "present", the renderer is `edgechromium`, and the injected window factory logs, on the `pywebview` logger at ERROR, `WebView2 initialization failed with exception:\n System.IO.FileNotFoundException ...`, with the window URL (including the app token) and an `sk-` key in the text, and then waits until the window is closed
When the launcher runs
Then the window close is requested exactly once, the R12 box is shown only after the window factory has returned (no empty window behind it), `desktop.log` has exactly one R13 line with case `webview2_init_failed`, the version, the answer and `error=WebView2InitializationFailed`, the log contains neither the token, nor the URL, nor the key, the server is stopped, and the exit code is 4;
and Yes opens exactly the R10 URL once, No opens nothing, and `socket.create_connection` and `httpx`, patched to fail if called, were never called.

#### No False Alarm (R20)

Given the check reports "present" and the renderer is `edgechromium`
When the window factory (a) logs another `pywebview` ERROR (`Error occurred in script`), (b) logs the R20 text at WARNING, or on a logger other than `pywebview`, (c) logs the R20 text after the window's `loaded` event is set, or (d) sets `loaded` only after a long delay (a fake clock advanced by 300 s) with no failure record, and the user then closes the window
Then no message box is shown, no `webview2_init_failed` line is written, and the exit code is 0;
and after the launcher returns, the R20 watcher is no longer attached to the `pywebview` logger, in every case including when `open_window` raises.

#### User Closes First (R20)

Given the failure record has not been logged
When the user closes the empty window
Then the exit is unchanged (0) and no box is shown;
and this holds when the window's `closing` event (or `closed` event) is set first and the window factory then logs the R20 text at ERROR on the `pywebview` logger before returning (the record caused by the user's own close is ignored): no box is shown, no `webview2_init_failed` line is written, the R12 path is not taken, and the exit code is 0.
Given instead that the record was logged before `closing` was set (the user closed the window afterwards), the R12 box is shown and the exit code is 4.
Given reading `closing`/`closed` raises, a matching record before `loaded` still counts (R12 box, exit code 4).
(Clarified 2026-10-15 after QA reproduced the R12 box with exit code 4 when the window was closed within 0.2 s of `shown`, 6 of 6 runs; not at 0.4 s or later. Formerly proposed as R20-A1.)

#### pywebview Init-Failure Report Pin (R20)

Given the installed pywebview
When the unit tests run
Then a test that reads `webview/platforms/edgechromium.py` as text (without importing it) passes only if `on_webview_ready` contains a `logger.error(` call whose string starts with `WebView2 initialization failed`. Otherwise it fails with a message that says to re-check R20.

#### PYWEBVIEW_LOG Ignored (R13, R20, Security)

Given `PYWEBVIEW_LOG` is unset, `CRITICAL`, `ERROR`, `DEBUG`, `bogus` or empty
When the launcher runs with and without `--debug`
Then while the window starts the `pywebview` logger's level is DEBUG with `--debug` and INFO without it, in every case;
and with `PYWEBVIEW_LOG=CRITICAL` the R20 failure record is still detected (the R12 box is shown, exit code 4, one `webview2_init_failed` line);
and with `PYWEBVIEW_LOG=DEBUG` and no `--debug`, a `pywebview` DEBUG record is not in `desktop.log`, while a `pywebview` ERROR record carrying the token and URL is in it, redacted;
and after the launcher returns, the `pywebview` logger's previous level is restored.

### Local API Request Guard (amendment, Approved)

Each criterion names the requirements it verifies and the tests in `tests/core/test_security_review.py` that pin it. "Server mode" is the server started without a desktop token, with the agent API enabled for one folder.

#### Host Allowlist (R16)

Given server mode
When a request arrives with `Host` `127.0.0.1`, `127.0.0.1:8000`, `localhost:51234`, `LOCALHOST`, `[::1]` or `[::1]:8000`
Then `GET /api/agent/config` and `GET /` succeed (`test_local_hosts_on_any_port_reach_the_app`);
and when `Host` is `127.0.0.1.attacker.example`, `localhost.attacker.example`, `evil.localhost`, `0.0.0.0:8000`, `127.0.0.2`, empty, `[::1].evil` or `localhost:80.evil`, the request is refused with 403 (`test_look_alike_and_missing_hosts_are_refused`).

#### DNS Rebinding Refused (R16)

Given server mode and a request with `Host: attacker.example:8000`, a matching `Origin` and `X-Requested-With`
When it calls `POST /api/agent/tasks`, `GET /api/agent/memory` or `GET /`
Then it is refused (403, or 400 if the HTTP layer rejects it first) and no task starts (`test_dns_rebinding_host_is_refused`).

#### Desktop App Unaffected (R16, R17, R19)

Given the desktop app on a random launch port with its app token
When its page calls `/api/agent/config` with `X-App-Token`, and a state-changing route with `X-App-Token` only
Then both reach the API (`test_desktop_app_on_its_launch_port_still_works`, `test_desktop_token_counts_as_the_custom_header`).

#### Missing Custom Header Refused (R17)

Given server mode
When `POST .../approve`, `.../deny`, `.../cancel`, `POST /api/agent/memory`, `DELETE /api/agent/memory/{id}` or `PUT /api/key` is sent without `X-Requested-With` or `X-App-Token` (as a cross-site form or `no-cors` fetch would)
Then each is refused with 403 and a "Cross-site" detail (`test_state_changing_calls_without_the_custom_header_are_refused`);
and `PATCH`, a trailing-slash variant of a route, and `POST /api/chat` are refused the same way (`test_guard_covers_other_methods_and_slash_variants`).

#### Foreign or Odd Origin Refused (R17, R18)

Given server mode and a state-changing call carrying `X-Requested-With`
When its `Origin` is `https://evil.example`, `null`, `chrome-extension://abc` or `http://127.0.0.1.evil.example`, or `X-Requested-With` is empty
Then it is refused with 403 (`test_a_foreign_origin_is_refused_even_with_the_header`, `test_odd_origins_and_empty_headers_are_refused`).

#### Own Page Passes, Reads Unchanged (R17, R18, R19)

Given server mode
When a state-changing call carries `X-Requested-With` with the server's own `Origin` or with no `Origin`, and a GET carries neither header
Then all three reach the API (`test_the_apps_own_page_passes_the_guard`).

        ## Tests

        - View-model unit tests.
- UI integration tests for lifecycle states.
- Accessibility checks for approval prompts.
- (WebView2 amendment) Unit tests in `tests/` for the WebView2 detection with a fake registry reader: present (HKCU, HKLM `WOW6432Node` on AMD64/ARM64, HKLM native path on x86, Beta and Canary channels, `86.0.0.0`), absent, empty (stops the search), non-numeric (stops the search), `0.0.0.0`, too old (search continues), HKLM native path on AMD64/ARM64 (missing), order (HKCU before HKLM, runtime before Beta), default view only, .NET read once and too old, unreadable keys (treated as missing, never a crash), non-Windows skip. Each case lists pywebview 6.2.1's answer next to the expected result.
- (WebView2 amendment) A test that pywebview's Windows backend is not imported before R7 decides (R9 path, R14), and a pin test for `pywebview>=6.2,<7` (installed version and `pyproject.toml`).
- (WebView2 amendment) A `desktop.log` test with the `pywebview` logger and a logged, re-raised traceback carrying the token, URL and an `sk-` key (R13, Security).
- (Security) Redaction unit tests for each accepted left context (`%XX`, `%253D`, `\n \r \t \f \v \b \0`, `\xNN`, `\uXXXX`), the Stripe `sk_test_`/`rk_test_` keys, and the ordinary-word cases; `test_words_ending_in_sk_are_not_secrets` loses its xfail.
- (WebView2 amendment) Unit tests for the launcher flow with injected message box, URL opener and window factory: Yes, No, legacy renderer (R12 box, exit code 4), window start failure, simulation flag; the server is stopped and the exit code is 3 or 4; the opener receives exactly the R10 URL or nothing; `socket.create_connection` and `httpx` are patched to fail if called.
- (WebView2 amendment) A golden test for the two message box titles and texts (R9, R12) and the R10 URL constant.
- (WebView2 amendment) A log test: the `desktop.log` line for each case, with a known token in the URL, contains neither the token nor the URL.
- (WebView2 amendment) Manual check on a Windows 10 machine or VM without the WebView2 runtime, using `Galliani.exe` from a release build: the R9 dialog, Yes, No, then install the runtime and relaunch (AC Next Launch Rechecks). Where no such machine is available, use `--simulate-missing-webview2` and record that the real-machine check is pending. This step is added to `docs/release-checklist.md`.
- (R20) Unit tests in `tests/test_desktop_webview2.py` for the AC "WebView2 Fails to Initialize", "No False Alarm" and "User Closes First". They use the injected window factory, message box and opener, a fake `loaded` event, fake `closing`/`closed` events and a fake clock, with no real sleep. A source-text pin test in `tests/test_pywebview_pin.py` covers the AC "pywebview Init-Failure Report Pin". A golden-test update covers the new R13 case name.
- (R13, R20) Tests in `tests/test_desktop_webview2.py` for the AC "PYWEBVIEW_LOG Ignored". They replace `test_pywebview_level_follows_pywebview_log_then_debug` and `test_debug_and_pywebview_log_set_what_reaches_desktop_log_still_redacted`, which pin the old rule (`PYWEBVIEW_LOG` wins).
- (R20) A manual check on Windows with WebView2 installed, run from the root of a source checkout (revised 2026-10-15):
  `python -c "import os, tempfile; os.environ['LOCALAPPDATA'] = tempfile.mkdtemp(prefix='galliani-r20-data-'); rt = tempfile.mkdtemp(prefix='galliani-r20-runtime-'); print('desktop.log folder:', os.path.join(os.environ['LOCALAPPDATA'], 'Galliani')); from app import desktop, webview2 as w; raise SystemExit(desktop.main([], hooks=w.WindowHooks(renderer=lambda: (__import__('webview').settings.__setitem__('WEBVIEW2_RUNTIME_PATH', rt), w.current_renderer())[1])))"`
  then `$LASTEXITCODE` (PowerShell) or `echo %ERRORLEVEL%` (cmd).
  - **Why it reads this way.** (1) `app.desktop` is imported first and `webview` is imported only inside the R8 renderer hook, which `launch_window` calls after R7 has decided and while `desktop_log` is active. So pywebview's import-time setup finds the app's NullHandler and adds no stderr handler of its own, the run uses the app's real logging (R13 level and redacting filter), and pywebview's failure record, which carries the .NET exception text, reaches only `desktop.log`, redacted, never the tester's console. The import point is the same as in the shipped app (`current_renderer` imports `webview.guilib`). (2) `LOCALAPPDATA` is set for this process only, so `user_data_dir()` puts `desktop.log`, `requests.jsonl` and the WebView2 profile (`webview` folder) in a new temp folder, and the tester's real `%LOCALAPPDATA%\Galliani` is not touched. The command prints that folder. The OS credential store is not in that folder and is not changed. (3) The runtime path is a second, empty temp folder. pywebview uses it only if it exists (otherwise it warns and falls back to the system runtime), and its `_is_chromium()` then answers `edgechromium`, so R8 passes and R20 is what the run exercises.
  - **Expected result.** The R12 box with no empty window behind it, exit code 4, and in `<printed folder>\desktop.log` one `webview2_init_failed` line plus pywebview's own failure record, redacted. pywebview's failure record is not printed to the console. Pointing pywebview at an empty runtime folder is expected to make WebView2 report a failed initialization; the first run must confirm it. Delete the two `galliani-r20-*` temp folders afterwards.
  - This step is in `docs/release-checklist.md` section 9 (step 9), which must copy this command exactly.
- (API guard amendment) `tests/core/test_security_review.py`, SEC-5 and SEC-8 sections and the 2026-10-15 re-review probes, as named in each acceptance criterion above. Existing API tests (`tests/test_api.py`, `tests/core/test_agent_api.py`) use a local `base_url`, and their state-changing calls send `X-Requested-With` or the desktop token.

        ## Evaluation

        - Task comprehension review.
- Approval prompt clarity review.
- No hidden reasoning visible in UI snapshots.
- (WebView2 amendment) None for WebView2: it does not change agent behavior, so `evals/` is unchanged. The message text was approved by the user (Open Question 1).
- (API guard amendment) None: the guard is transport behavior, covered by the tests above.

        ## Implementation Tasks

        - [x] Define task view model.
- [x] Define approval prompt model.
- [x] Map lifecycle events to UI feed items.
- [x] Design final result and verification display.
- [x] (WebView2 amendment) WebView2 detection with an injectable registry reader (R6, R7) and the legacy-engine guard (R8), as first written. Superseded by the amended R7, R8 and R10 tasks below.
- [x] (WebView2 amendment) Native message boxes, the URL constant, the exit paths and the local log line (R9-R13).
- [x] (WebView2 amendment) `--simulate-missing-webview2` and the smoke-test info line (R14, R15).
- [x] (WebView2 amendment) Tests above (`tests/test_desktop_webview2.py`, 53 passing on 2026-10-15) and a CHANGELOG entry. The privacy page needs no change, because no data is collected or sent.
- [x] (WebView2 amendment, release-engineer) The manual Windows 10 check in `docs/release-checklist.md` (Open Question 6). The step is written; running it on a real Windows 10 machine without WebView2 is still pending and is recorded per release.
- [x] (WebView2 amendment, ui-engineer) A WebView2 entry in the site FAQ: what it is, that Windows 11 includes it, the R10 link, and that Galliani never downloads it itself (Open Question 6). Done in `site/src/main.tsx` (the answer now says Windows 11 includes WebView2); the ui-engineer is revising the question wording, which needs no spec change. The FAQ must not claim that nothing changes on the PC on every path (R10 known exception).
- [x] (Amended R7, core-engineer, step 1) Rewrite `detect_webview2` in `app/webview2.py` to the amended R7 rule (paths by `platform.machine()`, default view only, .NET read once, order runtime/Beta/Dev/Canary with HKCU before HKLM, first-number comparison, stop on a non-numeric or empty `pv`), with the AC "WebView2 Detected" and "WebView2 Absent or Unusable" cases (a)-(d). Done when every listed case passes and matches pywebview 6.2.1.
- [x] (Amended R7, core-engineer, step 2) Make sure `app/desktop.py` does not import `webview.platforms.winforms` (nor call `webview.start` or `webview.guilib.initialize`) before R7 decides; AC "Backend Not Loaded Before the Check".
- [x] (Amended R8, core-engineer, step 3) Route the legacy-engine case to the R12 box, log case `webview2_legacy_engine`, stop the server, exit code 4; AC "Legacy Engine Refused".
- [x] (R13 and Security, core-engineer, step 4) One redacting filter on the `desktop.log` handler covering every logger including `pywebview` and every logged or re-raised traceback (exact token and URL, then `galliani/redaction.py`); AC "pywebview Logger and Tracebacks Redacted".
- [x] (Security, core-engineer, step 5) `galliani/redaction.py`: accept the `%253D`, `\b`, `\0`, `\xNN` and `\uXXXX` left contexts for `sk-`, mask Stripe `sk_test_`/`rk_test_`, remove the xfail from `test_words_ending_in_sk_are_not_secrets`; AC "Redaction Trade-offs".
- [x] (Amended R7, release-engineer, after step 1) Pin `pywebview>=6.2,<7` in the `desktop` extra of `pyproject.toml`, add the pin test (AC "pywebview Pin"), add a `docs/release-checklist.md` step "a pywebview upgrade outside the pin needs an R7 re-check and a spec update", and a CHANGELOG line for the amended R7/R8 and the log redaction.
- [ ] (Security, qa-security, last) Update `docs/security.md` "Notes and limits" to the redaction trade-offs (the `sk-` word boundary is no longer open; the glued-key case is accepted) and re-review the `desktop.log` redaction and the R8 path.
- [x] (API guard amendment) Host allowlist, custom-header rule and Origin check in `app/api/routes.py`; the app's page sends `X-Requested-With: galliani` (R16-R19, Decision 0032).
- [x] (API guard amendment) Document the `X-Requested-With` requirement for other API clients wherever the API is documented (R19). Done in the README section "Calling the local API".
- [x] (R20, core-engineer, step 1) In `app/webview2.py`, add the R20 watcher (`InitFailureWatcher`, a `logging.Handler` that matches only the R20 signal and sets a `threading.Event`), the `webview2_init_failed` case, and the R12 path with exit code 4 in `launch_window`. Make the watcher and the `loaded` check injectable through `WindowHooks`. `launch_window` attaches the watcher with `watch_init_failure` around its call to `open_window()` (so still before `webview.create_window`, which runs inside `open_window`), starts a thread that calls the injected `close_window` (in `app/desktop.py`, `window.destroy()`) when the flag is set, and removes the handler when `open_window` returns or raises. `app/desktop.py` only supplies `loaded` and `close_window`; `open_window` itself is unchanged. Done when the AC "WebView2 Fails to Initialize", "No False Alarm" and "User Closes First" pass, and the existing WebView2 tests still pass (except the two `PYWEBVIEW_LOG` tests replaced in step 1b). Done 2026-10-15: `tests/test_desktop_webview2.py` and `tests/test_pywebview_pin.py`, 188 passing.
- [x] (R13, R20, core-engineer, step 1b) In `app/desktop.py`, make `pywebview_level(debug)` ignore `PYWEBVIEW_LOG` (DEBUG with `--debug`, otherwise INFO) and update its docstring and the `desktop_log` docstring. Make sure nothing after `desktop_log` sets the level again (including pywebview's own import-time setup). Replace the two old `PYWEBVIEW_LOG` tests with the AC "PYWEBVIEW_LOG Ignored". Done when that AC passes.
- [x] (R20, core-engineer, step 2) The source-text pin test (AC "pywebview Init-Failure Report Pin"), plus a `docs/release-checklist.md` line: "a pywebview upgrade needs an R20 re-check".
- [ ] (R13, R20, R18, qa-security, step 3) Review that the watcher stores and writes nothing (Security), that redaction still covers pywebview's own failure record, and that no path raises the `pywebview` level above ERROR. Update `docs/security.md`: the WebView2 note (the "installed but fails to initialize" gap is closed for the reported case; the hang case remains a known limitation), the `PYWEBVIEW_LOG` line (ignored by design, with the reason: R20 depends on the ERROR record), and the SEC-5 notes (the reverse-proxy `Host` rewrite limitation of R18).
- [ ] (R13, R20, release-engineer, step 4) Run the manual check above on a real Windows machine and record the result. Add a CHANGELOG line for R20, and correct the existing CHANGELOG line that says `PYWEBVIEW_LOG` "is honoured again": it is now ignored. The two CHANGELOG changes are done; the manual run is still pending, and step 9 of `docs/release-checklist.md` section 9 must first be updated to the revised command in Tests.
- [x] (R20 Signal clarification, formerly R20-A1, core-engineer, step 1c) In `app/webview2.py`, the watcher ignores a matching record once the window's `closing` or `closed` event is set (injectable through `WindowHooks` like `loaded`; if reading fails, the record counts); `app/desktop.py` supplies the check from the window's public `events.closing`/`events.closed`. Done when the clarified AC "User Closes First" passes (including the record-after-`closing` and read-failure cases), the AC "WebView2 Fails to Initialize" and "No False Alarm" still pass, and the existing WebView2 tests still pass. Ticked only after verification is confirmed. Verified 2026-10-16: implemented in the launcher's `loaded()` in `app/desktop.py` (the watcher in `app/webview2.py` is unchanged and flag-only); tests pass.
- [x] (R20 Signal clarification, qa-security) Re-run the QA reproduction on Windows (close within 0.2 s of `shown`, at least 6 runs): exit code 0, no R12 box, no `webview2_init_failed` line. Done 2026-10-16: 10 of 10 real-window runs exited 0 with no box and no `webview2_init_failed` line; the control without the fix gave exit 4.
- [ ] (Proposed amendment R20-A2, core-engineer, blocked on Open Question 9) Only if the user approves: the close-request rule of "Proposed amendment R20-A2", with its proposed acceptance criterion. Nothing is implemented before approval.

        ## Dependencies

        Depends on `001-agent-core`, `002-task-state`, `009-permissions`, and `011-observability`.

The WebView2 amendment depends only on the desktop launcher (`app/desktop.py`) and the pinned `pywebview` version. It resolves `016-public-launch` Open Question 5.

The API guard amendment depends on `app/api/routes.py` and `galliani/web/agent_api.py`; it is the transport side of `009-permissions` and `014-accept-edits` (approvals and the edit mode are only as safe as the API that accepts them).

## Open Questions (WebView2 amendment)

Questions 1-8 were resolved by the user on 2026-10-15 (Decision 0031) and are kept for the record. Question 9 is open.

1. **Message text.** Resolved: the R9 and R12 titles and texts exactly as written (wording revised and re-approved by the user on 2026-10-15 after the copy review: R9 now asks a question and states that nothing was sent; R12 says "often helps").
2. **Link target.** Resolved: Microsoft's WebView2 page, `https://developer.microsoft.com/microsoft-edge/webview2/` (R10), not the direct bootstrapper link.
3. **Browser fallback.** Resolved: no browser fallback (Non-goals).
4. **.NET Framework below 4.6.2.** Resolved: treated as "missing" under R9 with the same text; no separate .NET message.
5. **Default button and exit codes.** Resolved: No is the default button; exit codes 3 (runtime missing) and 4 (window failed).
6. **Docs outside this spec's owner.** Resolved: yes to both. `docs/release-checklist.md` gains the manual Windows 10 check (release-engineer) and the site FAQ gains a WebView2 entry (ui-engineer); see Implementation Tasks.
7. **Amendment to R7, R8, R10.** Resolved 2026-10-15 ("approve with defaults"): (a) R7 copies pywebview's rule exactly, including its first-number-only version comparison, its paths, the default view, the HKCU-before-HKLM order and stop-on-bad-value; (b) the R8 legacy-engine case shows the R12 box with exit code 4, and R10 names pywebview's two HKCU writes (`FEATURE_BROWSER_EMULATION`, `FEATURE_96DPI_PIXEL`) as a known exception; (c) pin `pywebview>=6.2,<7` with a test that fails outside that range. pywebview's Windows backend is not loaded until the check has decided. Rejected alternatives: see "Why R7, R8 and R10 read this way".
8. **WebView2 installed but fails to initialize (R20).** Resolved 2026-10-15 (the user approved every default):
   - (a) R20 as written: detect pywebview's own failure record, with no timeout, and show the R12 box with exit code 4 and the new R13 case `webview2_init_failed`. Not chosen: keeping it as a known limitation with R12 reworded to cover only raised errors, or a `loaded` timeout (false-alarm risk on slow machines).
   - (b) The hang case (WebView2 never reports) stays a documented known limitation, with no timeout backstop. Not chosen: a long `loaded` timeout of at least 120 s that only logs a warning.
   - (c) No new public flag to simulate the failure. The manual check uses the `WEBVIEW2_RUNTIME_PATH` one-liner from a source checkout. Not chosen: a `--simulate-webview2-init-failure` flag like R14.
   - (d) The R12 text is unchanged: its "may be damaged or out of date" already describes this case.
   - Follow-up decided with it: the app ignores `PYWEBVIEW_LOG` and sets pywebview's level itself (R13), because R20 depends on pywebview's ERROR record reaching the watcher.
9. **The close request (Proposed amendment R20-A2). OPEN, for the user.** From the code review of the R20 implementation. See "Proposed amendment R20-A2" for the details.
   - (a) No longer part of this question. The user close during start (formerly R20-A1) is a clarification of R20's approved sentence "If the user closed the empty window before the flag was set, the exit is unchanged (0)", confirmed by QA (6 of 6 runs closing within 0.2 s of `shown`), and is folded into R20's Signal bullet and the AC "User Closes First" (2026-10-15).
   - (b) `Window.destroy()` can wait up to 20 s for `shown`, while the watcher thread is joined for only 1 s, so a late close or a late warning can happen after the launcher has moved on. Default (recommended): R20-A2, request the close only once `shown` is set and the window is not already closing, keep the 1 s join, and write nothing once the launcher has moved on. Alternatives: a longer join (delays the box and normal exits), or leave it as is (up to 20 s of empty window, a possible stray line outside `desktop.log`).
   - Until the user answers, R20 (with its clarified Signal) stays as approved, and nothing of R20-A2 is implemented.
