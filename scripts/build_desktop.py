"""Build the standalone desktop app with PyInstaller.

    pip install -e ".[desktop,build]"
    python -m scripts.build_desktop            # -> dist/Galliani.exe (Windows) / dist/Galliani.app (macOS)
    python -m scripts.build_desktop --onedir   # -> dist/onedir/Galliani/Galliani.exe, the MSIX layout (spec 016 R20)

The build bundles config/ and the web UI, then runs the binary's --smoke-test to verify it.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

from scripts.make_icon import main as make_icon

ROOT = Path(__file__).resolve().parent.parent
NAME = "Galliani"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.build_desktop")
    parser.add_argument("--onedir", action="store_true",
                        help="one-folder build for the MSIX package (starts faster, nothing extracts to %%TEMP%%)")
    options = parser.parse_args(sys.argv[1:] if argv is None else argv)
    dist = ROOT / "dist" / "onedir" if options.onedir else ROOT / "dist"
    work = ROOT / "build" / "onedir" if options.onedir else ROOT / "build"
    sep = os.pathsep
    args = [
        str(ROOT / "app" / "desktop.py"),
        "--name", NAME,
        "--onedir" if options.onedir else "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--distpath", str(dist),
        "--workpath", str(work),
        "--specpath", str(work),
        "--add-data", f"{ROOT / 'config'}{sep}config",
        "--add-data", f"{ROOT / 'app' / 'web'}{sep}app/web",
        "--collect-submodules", "uvicorn",
        "--collect-submodules", "keyring",
        "--collect-submodules", "app",
        "--collect-submodules", "galliani",  # the supervisor; the agent API and CLI are imported lazily
    ]
    make_icon()
    icon = ROOT / "assets" / ("galliani.ico" if sys.platform == "win32" else "galliani.icns")
    if icon.exists():
        args += ["--icon", str(icon)]
    PyInstaller.__main__.run(args)

    exe_name = f"{NAME}.exe" if sys.platform == "win32" else NAME
    exe = dist / NAME / exe_name if options.onedir else dist / exe_name
    print(f"\nBuilt {exe} ({exe.stat().st_size / 1e6:.0f} MB). Running smoke test...")
    code = subprocess.run([str(exe), "--smoke-test"], timeout=120).returncode
    print("Smoke test", "passed" if code == 0 else f"FAILED (exit {code}); see the desktop.log in the app data folder")
    return code


if __name__ == "__main__":
    sys.exit(main())
