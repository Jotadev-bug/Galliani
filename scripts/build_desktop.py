"""Build the standalone desktop app with PyInstaller.

    pip install -e ".[desktop,build]"
    python -m scripts.build_desktop            # -> dist/Router.exe (Windows) / dist/Router.app (macOS)

The build bundles config/ and the web UI, then runs the binary's --smoke-test to verify it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
NAME = "Router"


def main() -> int:
    sep = os.pathsep
    args = [
        str(ROOT / "app" / "desktop.py"),
        "--name", NAME,
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        "--add-data", f"{ROOT / 'config'}{sep}config",
        "--add-data", f"{ROOT / 'app' / 'web'}{sep}app/web",
        "--collect-submodules", "uvicorn",
        "--collect-submodules", "keyring",
        "--collect-submodules", "app",
    ]
    icon = ROOT / "assets" / ("router.ico" if sys.platform == "win32" else "router.icns")
    if icon.exists():
        args += ["--icon", str(icon)]
    PyInstaller.__main__.run(args)

    exe = ROOT / "dist" / (f"{NAME}.exe" if sys.platform == "win32" else NAME)
    print(f"\nBuilt {exe} ({exe.stat().st_size / 1e6:.0f} MB). Running smoke test...")
    code = subprocess.run([str(exe), "--smoke-test"], timeout=120).returncode
    print("Smoke test", "passed" if code == 0 else f"FAILED (exit {code}); see the desktop.log in the app data folder")
    return code


if __name__ == "__main__":
    sys.exit(main())
