"""Missing WebView2 on Windows: detection, the native message boxes and the exit paths (spec 012 R6-R15, R20).

pywebview silently falls back to the Internet Explorer engine (MSHTML) when no usable WebView2 runtime is
registered, and that engine cannot run the bundled UI. The launcher checks first, with the same rule as
pywebview (Decision 0031), and shows a native Yes/No message box instead of a blank window.

Everything here is offline: detection only reads the registry, the message box is a Win32 call, and the
only network action is the user's own browser opening `WEBVIEW2_URL` after they select Yes. Detection,
the message box, the link opener and the window are injectable so tests run on any machine.

R20: a WebView2 runtime that is registered but fails to initialize raises nothing in pywebview; it only logs
an ERROR record. A flag-only watcher on the `pywebview` logger turns that record into the R12 path.
"""

from __future__ import annotations

import logging
import sys
import threading
import webbrowser
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from platform import machine as platform_machine
from typing import Callable, Iterator

# The launcher's logger. Its records reach desktop.log only through the redacting handler (R13).
LOG = logging.getLogger("galliani.desktop")
# R10: the only WebView2 URL in Galliani. No query string or fragment, so it carries nothing about the user.
WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"

EXIT_WEBVIEW2_MISSING = 3  # R11
EXIT_WINDOW_FAILED = 4  # R12

# R20: pywebview 6.2.1 `EdgeChrome.on_webview_ready` logs this (and raises nothing) when WebView2 reports
# `IsSuccess` false. `tests/test_pywebview_pin.py` fails if the installed pywebview rewords it.
PYWEBVIEW_LOGGER = "pywebview"
INIT_FAILED_PREFIX = "WebView2 initialization failed"
INIT_FAILED_ERROR = "WebView2InitializationFailed"  # the R13 `error=` of case webview2_init_failed

MISSING_TITLE = "Galliani needs Microsoft Edge WebView2"
MISSING_TEXT = (
    "Galliani uses Microsoft Edge WebView2, a free component from Microsoft, to show its window. "
    "It is not installed on this PC. Nothing has been downloaded or changed on this PC. "
    "Nothing was sent anywhere.\n"
    "\n"
    "Open Microsoft's WebView2 page now?\n"
    "\n"
    "Yes opens the page in your browser, where you can install the Evergreen Runtime and then open "
    "Galliani again; No closes Galliani."
)
FAILED_TITLE = "Galliani could not open its window"
FAILED_TEXT = (
    "Galliani could not open its window. Microsoft Edge WebView2 may be damaged or out of date. "
    "Reinstalling or updating it often helps.\n"
    "\n"
    "Select Yes to open Microsoft's WebView2 download page in your browser. Select No to close Galliani.\n"
    "\n"
    "Details were saved on this PC only, in:\n"
    "{log_path}"
)

# R7: exactly the rule of pywebview 6.2.1 (`webview/platforms/winforms.py` `_is_chromium()`), which the
# `pywebview>=6.2,<7` pin keeps honest. A pywebview upgrade outside the pin needs an R7 re-check.
MIN_MAJOR = 86  # only the first number of `pv` is compared
MIN_DOTNET_RELEASE = 394802  # .NET Framework 4.6.2
DOTNET_KEY = r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"
CLIENT_KEYS = (  # EdgeUpdate client ids, in pywebview's order: Evergreen runtime, Beta, Dev, Canary
    "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",
    "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}",
    "{65C35B14-6C1D-4122-AC46-7148CC9D6497}",
)
CLIENT_PATH = "SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\{}"
CLIENT_PATH_WOW64 = "SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\{}"  # HKLM, any machine but x86
HIVES = ("HKCU", "HKLM")  # within each client id, HKCU first

# reader(hive, key_path, value_name, view) -> the value, or ABSENT when the key or value is absent. A value
# that is present but has no data (an empty REG_NONE) reads as None, which is not ABSENT: pywebview turns it
# into "None", whose int() fails and stops the search. The check always passes view=None (the process's
# default view, as pywebview); the parameter exists so tests can prove that no explicit 32-bit or 64-bit
# view was asked for.
ABSENT = object()
RegistryReader = Callable[[str, str, str, "int | None"], object]


@dataclass(frozen=True)
class WebView2Status:
    present: bool
    version: str | None = None  # the first usable `pv` in pywebview's order, or None


MISSING = WebView2Status(False)


@dataclass(frozen=True)
class MessageBox:
    title: str
    text: str
    icon: str  # "information" or "warning"
    buttons: str = "yes_no"
    default: str = "no"  # R9, R12: Enter never opens a browser


def missing_box() -> MessageBox:
    return MessageBox(MISSING_TITLE, MISSING_TEXT, "information")


def failed_box(log_path: Path | str) -> MessageBox:
    return MessageBox(FAILED_TITLE, FAILED_TEXT.format(log_path=log_path), "warning")


# ---------------------------------------------------------------------------------------------- detection

def windows_registry_reader(hive: str, key_path: str, value_name: str, view: int | None) -> object:
    """Read one value, read-only. Absent or unreadable keys and values return ABSENT."""
    import winreg

    access = winreg.KEY_READ | {64: winreg.KEY_WOW64_64KEY, 32: winreg.KEY_WOW64_32KEY}.get(view, 0)
    root = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[hive]
    try:
        with winreg.OpenKey(root, key_path, 0, access) as key:
            return winreg.QueryValueEx(key, value_name)[0]
    except OSError:
        return ABSENT


def _read(reader: RegistryReader, hive: str, key_path: str, name: str) -> object:
    try:
        return reader(hive, key_path, name, None)  # default view only
    except Exception:  # noqa: BLE001 - an unreadable key counts as absent, never a crash
        return ABSENT


def _client_path(hive: str, client: str, machine: str) -> str:
    return (CLIENT_PATH if hive == "HKCU" or machine == "x86" else CLIENT_PATH_WOW64).format(client)


def detect_webview2(reader: RegistryReader | None = None, machine: str | None = None) -> WebView2Status:
    """R7: is a usable WebView2 runtime registered? Only reads the registry; no network, process or write.

    Mirrors pywebview 6.2.1: .NET `Release` read once; then for each client id (runtime, Beta, Dev, Canary)
    and each hive (HKCU, HKLM) the first `pv` whose first number is at least 86 wins. An absent `pv` or one
    below 86 lets the search continue; a present `pv` whose first part is not a number stops it as missing.
    """
    reader = reader or windows_registry_reader
    machine = platform_machine() if machine is None else machine
    release = _read(reader, "HKLM", DOTNET_KEY, "Release")
    if not isinstance(release, int) or release < MIN_DOTNET_RELEASE:  # pywebview: absent or not a number fails
        return MISSING
    for client in CLIENT_KEYS:
        for hive in HIVES:
            pv = _read(reader, hive, _client_path(hive, client, machine), "pv")
            if pv is ABSENT:
                continue  # absent or unreadable: pywebview reads it as "0" and goes on
            try:
                major = int(str(pv).split(".")[0])
            except ValueError:
                # empty, no data (None -> "None") or not a number: pywebview's int() raises and its whole
                # check fails
                return MISSING
            if major >= MIN_MAJOR:
                return WebView2Status(True, str(pv))
    return MISSING


def current_renderer() -> str:
    """R8: the engine pywebview will use on this machine ("edgechromium", "mshtml", ...)."""
    from webview.guilib import initialize

    return initialize().renderer


# ------------------------------------------------------------------------------------------ message boxes

_MB_SETFOREGROUND, _IDYES = 0x10000, 6
_MB_BUTTONS = {"yes_no": 0x4}  # MB_YESNO
_MB_DEFAULTS = {"yes": 0x0, "no": 0x100}  # MB_DEFBUTTON1, MB_DEFBUTTON2 (the second button of Yes/No)
_MB_ICONS = {"information": 0x40, "warning": 0x30}


def message_box_flags(box: MessageBox) -> int:
    """The Win32 flags, derived from the box fields; an unknown value raises instead of guessing."""
    return _MB_BUTTONS[box.buttons] | _MB_DEFAULTS[box.default] | _MB_ICONS[box.icon] | _MB_SETFOREGROUND


def native_message_box(box: MessageBox) -> bool:
    """Show a modal Win32 Yes/No box (it does not need WebView2). True only for Yes; anything else is No."""
    import ctypes

    return ctypes.windll.user32.MessageBoxW(None, box.text, box.title, message_box_flags(box)) == _IDYES


# ------------------------------------------------------------------------------------- R20 init failure

class InitFailureWatcher(logging.Handler):
    """R20: a flag-only handler on the `pywebview` logger.

    It matches only pywebview's own report that WebView2 failed to initialize (logger `pywebview`, level
    ERROR, unformatted `record.msg` starting with `INIT_FAILED_PREFIX`) while `loaded()` is false, and then
    sets `failed`. The launcher's `loaded()` is true once the page loaded or the window started closing
    ("User Closes First": a record caused by the user's own close is not a failure). It keeps, copies, formats and writes nothing: the record reaches desktop.log only
    through the redacting handler (R13). Level ERROR and no filter, so nothing else can hide the record.
    """

    def __init__(self, loaded: Callable[[], bool] = lambda: False):
        super().__init__(logging.ERROR)
        self.failed = threading.Event()
        self._loaded = loaded

    def emit(self, record: logging.LogRecord) -> None:
        if (record.name != PYWEBVIEW_LOGGER or record.levelno != logging.ERROR
                or not isinstance(record.msg, str) or not record.msg.startswith(INIT_FAILED_PREFIX)):
            return
        try:
            loaded = self._loaded()
        except Exception:  # noqa: BLE001 - unknown counts as "not loaded": WebView2 itself reported the failure
            loaded = False
        if not loaded:
            self.failed.set()


@contextmanager
def watch_init_failure(watcher: InitFailureWatcher, close_window: Callable[[], object]) -> Iterator[None]:
    """R20: attach `watcher` to the `pywebview` logger for the body (the window's whole life); a thread closes
    the window once the flag is set, outside the logging call, so no empty window stays behind the R12 box.
    The handler is removed when the body returns or raises."""
    logger = logging.getLogger(PYWEBVIEW_LOGGER)
    done = threading.Event()

    def close_on_failure() -> None:
        while not done.is_set():
            if watcher.failed.wait(0.2):  # how often `done` is checked; R20 never decides on elapsed time
                try:
                    close_window()
                except Exception as exc:  # noqa: BLE001 - the user can still close it; the R12 box follows
                    LOG.warning("The empty window could not be closed (%s).", type(exc).__name__)
                return

    thread = threading.Thread(target=close_on_failure, name="webview2-watch", daemon=True)
    logger.addHandler(watcher)
    try:
        thread.start()
        yield
    finally:
        logger.removeHandler(watcher)
        done.set()
        thread.join(1.0)  # bounded: a close still waiting on pywebview cannot hang the exit


# ------------------------------------------------------------------------------------------------- flow

@dataclass
class WindowHooks:
    """The parts of the window launch that tests replace."""

    detect: Callable[[], WebView2Status] = detect_webview2
    renderer: Callable[[], str] = current_renderer
    ask: Callable[[MessageBox], bool] = native_message_box
    open_url: Callable[[str], object] = webbrowser.open
    watcher: Callable[[Callable[[], bool]], InitFailureWatcher] = InitFailureWatcher  # R20
    loaded: Callable[[], bool] | None = None  # R20 "page is up"; None: the launcher's `loaded` argument


def log_event(case: str, version: str | None, answer: str, *, error: BaseException | str | None = None) -> None:
    """R13: one line in desktop.log. It goes through the desktop.log handler, whose filter removes the app
    token and the window URL and applies the shared redactor (`app.desktop.RedactingFilter`). `error` is an
    exception (its type and message) or a fixed name such as `INIT_FAILED_ERROR`."""
    line = f"{case} version={version or 'none'} answer={answer}"
    if isinstance(error, BaseException):
        line += f" error={type(error).__name__}: {' '.join(str(error).split())}"  # one line per case
    elif error:
        line += f" error={error}"
    LOG.info(line)


def _offer_download(box: MessageBox, hooks: WindowHooks) -> str:
    """Show the box once; on Yes, open the R10 URL once. Returns the R13 answer."""
    try:
        yes = hooks.ask(box) is True
    except Exception:  # noqa: BLE001 - the box could not be shown: same log line, same exit code
        if sys.stderr and sys.stderr.isatty():  # a console only: the windowed build's stderr goes to desktop.log
            print(f"{box.title}\n\n{box.text}", file=sys.stderr)
        yes = False
    if not yes:
        return "closed"
    try:
        hooks.open_url(WEBVIEW2_URL)
    except Exception:  # noqa: BLE001 - the browser could not be started; the exit is unchanged
        pass
    return "opened_download_page"


def launch_window(open_window: Callable[[], object], *, log_path: Path, hooks: WindowHooks | None = None,
                  simulate_missing: bool = False, platform: str | None = None,
                  shown: Callable[[], bool] = lambda: False, loaded: Callable[[], bool] = lambda: False,
                  close_window: Callable[[], object] = lambda: None) -> int:
    """R7-R14, R20: check WebView2, then open the window. Returns the process exit code (0, 3 or 4).

    `open_window` creates and runs the pywebview window; it is only called when the runtime is usable.
    Nothing imports pywebview's Windows backend before the R7 check has decided (the renderer probe and
    `open_window` both run after it). `shown` tells whether the window was already shown: an error after
    that is not a start failure (R12) and is raised as before. `log_path` is shown in the R12 box.
    On Windows the R20 watcher is attached while `open_window` runs: if WebView2 reports a failed
    initialization before `loaded()`, `close_window` is called and, once `open_window` has returned, the
    R12 box is shown with exit code 4.
    """
    hooks = hooks or WindowHooks()
    windows = (platform or sys.platform) == "win32"
    if simulate_missing:
        status = MISSING
    elif not windows:
        status = WebView2Status(True)  # R7: macOS and Linux skip the check
    else:
        try:
            status = hooks.detect()
        except Exception:  # noqa: BLE001 - a failed check counts as missing, never a crash
            status = MISSING

    if not status.present:  # R9 only here: pywebview's backend is not loaded, so nothing has changed
        log_event("webview2_missing", status.version, _offer_download(missing_box(), hooks))
        return EXIT_WEBVIEW2_MISSING
    watcher = hooks.watcher(hooks.loaded or loaded)
    try:
        if windows and hooks.renderer() != "edgechromium":
            # R8: pywebview's backend import may already have written its FeatureControl values (R10), so the
            # R9 text ("Nothing ... changed") would be untrue here; R12 claims nothing about changes.
            log_event("webview2_legacy_engine", status.version, _offer_download(failed_box(log_path), hooks))
            return EXIT_WINDOW_FAILED
        with watch_init_failure(watcher, close_window) if windows else nullcontext():
            open_window()
    except Exception as exc:  # noqa: BLE001 - R12: any failure to create or start the window
        if watcher.failed.is_set():  # R20 came first: the error is a consequence, handled as R20 below
            LOG.error("The window stopped after WebView2 failed to initialize.", exc_info=exc)
        elif shown():
            raise
        else:
            LOG.error("The window failed to start.", exc_info=exc)  # the details the R12 box points to
            answer = _offer_download(failed_box(log_path), hooks)
            log_event("window_start_failed", status.version, answer, error=exc)
            return EXIT_WINDOW_FAILED
    if watcher.failed.is_set():  # R20: the empty window is closed; pywebview's own record holds the details
        answer = _offer_download(failed_box(log_path), hooks)
        log_event("webview2_init_failed", status.version, answer, error=INIT_FAILED_ERROR)
        return EXIT_WINDOW_FAILED
    return 0


def smoke_line(platform: str | None = None, detect: Callable[[], WebView2Status] | None = None) -> str:
    """R15: information only; it never changes the smoke test's exit code."""
    try:
        status = (detect or detect_webview2)() if (platform or sys.platform) == "win32" else MISSING
    except Exception:  # noqa: BLE001
        status = MISSING
    return f"INFO  webview2: {status.version if status.present else 'missing'}"
