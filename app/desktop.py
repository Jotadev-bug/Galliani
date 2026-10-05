"""Galliani desktop app: the web UI in a native window (pywebview), backed by the local API.

    python -m app.desktop                # open the app
    python -m app.desktop --smoke-test   # start the server, check it, exit (used to verify builds)

Each launch picks a free localhost port and a random token. The window's URL carries the token
and the server rejects /api calls without it, so other programs on the machine cannot use the
OpenRouter key saved in the OS credential store.
"""

from __future__ import annotations

import argparse
import os
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

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
    threading.Thread(target=server.run, daemon=True, name="api").start()
    deadline = time.monotonic() + 20
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("The local server did not start within 20 s.")
        time.sleep(0.05)
    return server


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
    return 0 if all(checks.values()) else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--smoke-test", action="store_true")
    p.add_argument("--debug", action="store_true", help="enable the web inspector")
    args = p.parse_args()

    data = user_data_dir()
    if sys.stdout is None:  # windowed build: no console, so keep output in a log file
        sys.stdout = sys.stderr = open(data / "desktop.log", "a", encoding="utf-8", buffering=1)

    token = secrets.token_urlsafe(32)
    os.environ["ROUTER_DESKTOP"] = "1"
    os.environ["ROUTER_APP_TOKEN"] = token
    os.environ.setdefault("ROUTER_LOG_PATH", str(data / "requests.jsonl"))

    port = free_port()
    server = start_server(port)
    base = f"http://127.0.0.1:{port}"
    try:
        if args.smoke_test:
            return smoke_test(base, token)
        import webview

        bridge = DesktopBridge()
        bridge._window = webview.create_window(
            APP_NAME, f"{base}/?token={token}", width=1120, height=840, min_size=(420, 560), js_api=bridge,
        )
        webview.start(private_mode=False, storage_path=str(data / "webview"), debug=args.debug)
        return 0
    finally:
        server.should_exit = True


if __name__ == "__main__":
    sys.exit(main())
