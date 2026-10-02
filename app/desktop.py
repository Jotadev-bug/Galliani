"""Desktop app: the web UI in a native window (pywebview), backed by the local API.

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

APP_NAME = "Router"


def user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    path = base / "AI Model Router"
    path.mkdir(parents=True, exist_ok=True)
    return path


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


def smoke_test(base: str, token: str) -> int:
    import httpx

    ok = httpx.get(f"{base}/api/config", headers={"X-App-Token": token}, timeout=10)
    blocked = httpx.get(f"{base}/api/config", timeout=10)
    page = httpx.get(f"{base}/", timeout=10)
    checks = {
        "config with token": ok.status_code == 200 and ok.json().get("desktop") is True,
        "config without token rejected": blocked.status_code == 403,
        "UI served": page.status_code == 200 and "Jev picks the right model" in page.text,
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

        webview.create_window(
            APP_NAME, f"{base}/?token={token}", width=1120, height=840, min_size=(420, 560),
        )
        webview.start(private_mode=False, storage_path=str(data / "webview"), debug=args.debug)
        return 0
    finally:
        server.should_exit = True


if __name__ == "__main__":
    sys.exit(main())
