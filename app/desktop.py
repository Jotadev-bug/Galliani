"""Galliani desktop app: the web UI in a native window (pywebview), backed by the local API.

    python -m app.desktop                # open the app
    python -m app.desktop --smoke-test   # start the server, check it, exit (used to verify builds)
    python -m app.desktop --simulate-missing-webview2   # show the missing-WebView2 message, then exit

On Windows the launcher checks for Microsoft Edge WebView2 before opening the window (spec 012 R6-R15).
If it is missing, a message box offers Microsoft's download page and the app exits with code 3; if the
window fails to start, it exits with code 4. Details go to desktop.log in the user data folder only.

Each launch picks a free localhost port and a random token. The window's URL carries the token
and the server rejects /api calls without it, so other programs on the machine cannot use the
OpenRouter key saved in the OS credential store.
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import secrets
import socket
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

from app.webview2 import LOG, WindowHooks, launch_window, smoke_line
from galliani.redaction import REDACTED, redact_text

APP_NAME = "Galliani"


def user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


# ------------------------------------------------------------------------------------- desktop.log (R13)

class RedactingFilter(logging.Filter):
    """The one filter on the desktop.log handler (spec 012 R13, Security).

    Every record from every logger (the launcher, pywebview's `pywebview` logger, uvicorn, stray output)
    is rendered with its traceback and stack, the exact app token and window URL of this launch are
    removed, and the shared redactor runs. The record is then rewritten in place to that text, so no
    formatter can bring the raw traceback back.
    """

    def __init__(self, secrets: Iterable[str]):
        super().__init__()
        self._secrets: list[str] = []
        self.add(*secrets)

    def add(self, *secrets: str) -> None:
        """Add secrets known only later (the window URL once the port is chosen). Swapped in one step, so a
        record filtered meanwhile on another thread sees the old or the new list, never a partial one."""
        self._secrets = sorted({s for s in (*self._secrets, *secrets) if s}, key=len, reverse=True)  # URL first

    def scrub(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, REDACTED)
        return redact_text(text)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            parts = [record.getMessage()]
            if record.exc_info:
                parts.append("".join(traceback.format_exception(*record.exc_info)).rstrip())
            elif record.exc_text:
                parts.append(record.exc_text)
            if record.stack_info:
                parts.append(record.stack_info)
            text = self.scrub("\n".join(parts))
        except Exception:  # noqa: BLE001 - a record that cannot be rendered is never written raw
            text = "A log record could not be formatted; it was dropped."
        record.msg, record.args = text, None
        record.exc_info = record.exc_text = record.stack_info = None
        return True


class _LogStream(io.TextIOBase):
    """stdout and stderr of the windowed build (no console): each line becomes a log record, so print() and
    anything written to stderr reach desktop.log only through the redacting filter."""

    def __init__(self, logger: logging.Logger):
        super().__init__()
        self._logger, self._buffer, self._lock, self._local = logger, "", threading.Lock(), threading.local()

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        if getattr(self._local, "busy", False):  # a logging error while logging: drop it, never recurse
            return len(text)
        with self._lock:
            self._buffer += text
            chunk = ""
            if "\n" in self._buffer:
                chunk, self._buffer = self._buffer.rsplit("\n", 1)
        self._emit(chunk)
        return len(text)

    def flush(self) -> None:
        with self._lock:
            chunk, self._buffer = self._buffer, ""
        self._emit(chunk)

    def _emit(self, chunk: str) -> None:
        if not chunk.strip():
            return
        self._local.busy = True
        try:
            self._logger.info(chunk)
        finally:
            self._local.busy = False


def _log_thread_exception(args: threading.ExceptHookArgs) -> None:
    if args.exc_type is not SystemExit:
        name = args.thread.name if args.thread else "unknown"
        LOG.error("Uncaught exception in thread %s.", name, exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def pywebview_level(debug: bool) -> int:
    """pywebview's own rule, which its skipped logger setup would have applied: a valid `PYWEBVIEW_LOG` level
    name wins; otherwise `--debug` means DEBUG and the default is INFO. An invalid name falls back to INFO,
    as in pywebview. Every record still reaches desktop.log only through the redacting filter."""
    name = os.environ.get("PYWEBVIEW_LOG")
    if name:  # any non-empty value counts as set, as in pywebview; it is not stripped
        return logging.getLevelNamesMapping().get(name.upper(), logging.INFO)
    return logging.DEBUG if debug else logging.INFO


@contextmanager
def desktop_log(path: Path, secrets: Iterable[str], *, windowed: bool,
                debug: bool = False) -> Iterator[logging.Handler]:
    """R13: route everything bound for desktop.log through one handler with the redacting filter.

    `secrets` are the app token and window URL of this launch (more can be added through the handler's
    `RedactingFilter.add`). In the windowed build stdout and stderr become log records too, and uncaught
    thread exceptions are logged, so no path writes around the filter. pywebview gets a NullHandler first,
    so it does not add its own stderr handler; its records reach desktop.log through the root handler only,
    at the level pywebview itself would use (`pywebview_level`). Everything is restored on exit.
    """
    handler = logging.FileHandler(path, encoding="utf-8", delay=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%SZ")
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    handler.addFilter(RedactingFilter(secrets))
    root, pywebview, null = logging.getLogger(), logging.getLogger("pywebview"), logging.NullHandler()
    levels = {logger: logger.level for logger in (LOG, pywebview)}
    if LOG.level == logging.NOTSET:
        LOG.setLevel(logging.INFO)
    pywebview.setLevel(pywebview_level(debug))
    pywebview.addHandler(null)
    root.addHandler(handler)
    streams, thread_hook = (sys.stdout, sys.stderr), threading.excepthook
    stream = _LogStream(LOG.getChild("output")) if windowed else None
    if stream:
        sys.stdout = sys.stderr = stream
    threading.excepthook = _log_thread_exception
    try:
        yield handler
    finally:
        if stream:
            stream.flush()
        sys.stdout, sys.stderr = streams
        threading.excepthook = thread_hook
        root.removeHandler(handler)
        pywebview.removeHandler(null)
        for logger, level in levels.items():
            logger.setLevel(level)
        handler.close()


class DesktopBridge:
    """Methods the page may call as window.pywebview.api.* (only in the desktop app)."""

    def __init__(self):
        # Private on purpose: pywebview exposes public attributes to JS and walks them, and walking the
        # native window object from the wrong thread raises WebView2 errors.
        self._window = None

    def pick_folder(self) -> str | None:
        """Native folder chooser for the agent's workspace (spec 012). Returns a path or None."""
        import webview

        dialog = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        chosen = self._window.create_file_dialog(dialog) if self._window else None
        return chosen[0] if chosen else None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(port: int):
    """Run uvicorn in a background thread; return the server once it accepts connections."""
    import uvicorn

    from app.api.routes import app

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", log_config=None))
    server.thread = threading.Thread(target=server.run, daemon=True, name="api")  # joined by stop_server
    server.thread.start()
    deadline = time.monotonic() + 20
    while not server.started:
        if time.monotonic() > deadline:
            server.should_exit = True  # never leave a half-started server running
            raise RuntimeError("The local server did not start within 20 s.")
        time.sleep(0.05)
    return server


def stop_server(server, timeout: float = 3.0) -> None:
    """Ask uvicorn to stop and wait briefly, so its shutdown lines still reach desktop.log (R13)."""
    server.should_exit = True
    thread = getattr(server, "thread", None)
    if thread is not None:
        thread.join(timeout)


def _redactor(handler: logging.Handler) -> RedactingFilter:
    return next(f for f in handler.filters if isinstance(f, RedactingFilter))


def _agent_runtime_builds() -> bool:
    """Import and wire the lazily loaded agent stack (planner, tools, memory) without keys or network."""
    import asyncio
    import tempfile

    from galliani.cli import build_runtime
    from galliani.memory import JsonMemoryStore

    with tempfile.TemporaryDirectory() as tmp:
        runtime = build_runtime(tmp, keys={}, out=lambda _line: None, memory=JsonMemoryStore(Path(tmp) / "m.json"))
        ok = "remember" in runtime.supervisor.tools.registry.names() and runtime.supervisor.memory is not None
        asyncio.run(runtime.aclose())
    return ok


def smoke_test(base: str, token: str) -> int:
    import httpx

    ok = httpx.get(f"{base}/api/config", headers={"X-App-Token": token}, timeout=10)
    blocked = httpx.get(f"{base}/api/config", timeout=10)
    page = httpx.get(f"{base}/", timeout=10)
    logo = httpx.get(f"{base}/logo.png", timeout=10)
    agent = httpx.get(f"{base}/api/agent/config", headers={"X-App-Token": token}, timeout=10)
    agent_blocked = httpx.get(f"{base}/api/agent/config", timeout=10)
    checks = {
        "config with token": ok.status_code == 200 and ok.json().get("desktop") is True,
        "config without token rejected": blocked.status_code == 403,
        "UI served": page.status_code == 200 and "Welcome to Galliani" in page.text,
        "logo bundled": logo.status_code == 200 and logo.headers.get("content-type") == "image/png",
        "agent API enabled": agent.status_code == 200 and agent.json().get("enabled") is True,
        "agent API without token rejected": agent_blocked.status_code == 403,
        "agent runtime builds (offline)": _agent_runtime_builds(),
    }
    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
    print(smoke_line())  # R15: information only, never part of the exit code
    return 0 if all(checks.values()) else 1


def main(argv: list[str] | None = None, hooks: WindowHooks | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--smoke-test", action="store_true")
    p.add_argument("--debug", action="store_true", help="enable the web inspector")
    p.add_argument("--simulate-missing-webview2", action="store_true",
                   help="show the missing-WebView2 message on any machine, then exit with code 3 (spec 012 R14)")
    args = p.parse_args(argv)

    data = user_data_dir()
    token = secrets.token_urlsafe(32)
    os.environ["ROUTER_DESKTOP"] = "1"
    os.environ["ROUTER_APP_TOKEN"] = token
    os.environ.setdefault("ROUTER_LOG_PATH", str(data / "requests.jsonl"))

    bridge = DesktopBridge()
    base = url = ""  # set once the port is chosen, inside desktop_log

    def open_window() -> None:  # imports pywebview only after the R7 check has decided (launch_window)
        import webview

        bridge._window = webview.create_window(
            APP_NAME, url, width=1120, height=840, min_size=(420, 560), js_api=bridge,
        )
        webview.start(private_mode=False, storage_path=str(data / "webview"), debug=args.debug)

    def shown() -> bool:  # an error after the window appeared is not a start failure (R12)
        return bridge._window is not None and bridge._window.events.shown.is_set()

    # Windowed build (no console): output goes to desktop.log too, always through the redacting filter (R13).
    # The log starts before anything that can fail (free_port too), and the token is a secret from the start.
    with desktop_log(data / "desktop.log", (token,), windowed=sys.stdout is None, debug=args.debug) as log:
        server = None
        try:
            port = free_port()
            base = f"http://127.0.0.1:{port}"
            url = f"{base}/?token={token}"
            _redactor(log).add(url, base)
            server = start_server(port)
            if args.smoke_test:
                return smoke_test(base, token)
            return launch_window(open_window, log_path=data / "desktop.log", hooks=hooks, shown=shown,
                                 simulate_missing=args.simulate_missing_webview2)
        except Exception:
            LOG.exception("The desktop app stopped with an error.")  # redacted here, then re-raised as before
            raise
        finally:
            if server is not None:
                stop_server(server)  # inside desktop_log: late uvicorn lines are still filtered and kept


if __name__ == "__main__":
    sys.exit(main())
