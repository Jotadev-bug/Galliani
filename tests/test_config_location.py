"""Spec 016 Phase 5a R30: one location for the shipped configuration (`app/defaults/`)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import app.config

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = Path(app.config.__file__).resolve().parent / "defaults"

# History records keep the old path on purpose (R30: past entries are not edited).
HISTORY = ("specs/", "docs/decisions.md", "CHANGELOG.md")
# Split so this file does not name the old paths itself.
OLD_PATHS = tuple(("config" + "/" + name).encode() for name in ("models.yaml", "routing.yaml"))


def _config_dir_in_subprocess(tmp_path: Path, **env: str) -> Path:
    """Import app.config in a fresh interpreter, so the module-level CONFIG_DIR is what gets checked."""
    clean = {k: v for k, v in os.environ.items() if k != "ROUTER_CONFIG_DIR"}
    clean["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT), clean.get("PYTHONPATH")]))
    clean.update(env)
    out = subprocess.run([sys.executable, "-c", "from app.config import CONFIG_DIR; print(CONFIG_DIR)"],
                         cwd=tmp_path, env=clean, capture_output=True, text=True, timeout=60, check=True)
    return Path(out.stdout.strip())


def test_default_is_the_defaults_folder_next_to_app_config(tmp_path):
    # Run from an unrelated folder: the default does not depend on the working directory.
    assert _config_dir_in_subprocess(tmp_path).resolve() == DEFAULTS


def test_router_config_dir_overrides_the_default(tmp_path):
    own = tmp_path / "my-config"
    assert _config_dir_in_subprocess(tmp_path, ROUTER_CONFIG_DIR=str(own)) == own


def test_the_shipped_files_live_in_app_defaults_and_load():
    from app.config import load_routing_config
    from app.models.registry import ModelRegistry

    assert (DEFAULTS / "models.yaml").is_file() and (DEFAULTS / "routing.yaml").is_file()
    assert ModelRegistry.from_yaml(DEFAULTS / "models.yaml").all()
    assert load_routing_config(DEFAULTS / "routing.yaml").modes


def test_the_old_config_folder_is_gone():
    # Nothing falls back to the old path (R30).
    assert not (ROOT / "config" / "models.yaml").exists() and not (ROOT / "config" / "routing.yaml").exists()


def _repo_files() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                             cwd=ROOT, capture_output=True, timeout=60, check=True)
    except (OSError, subprocess.SubprocessError):
        pytest.skip("not a git checkout: the stale-path check needs `git ls-files`")
    return [name for name in out.stdout.decode("utf-8").split("\0") if name]


def test_no_file_outside_history_names_the_old_config_path():
    stale = []
    for name in _repo_files():
        path = ROOT / name
        if name.startswith(HISTORY) or not path.is_file():
            continue
        data = path.read_bytes()
        stale += [f"{name}: {old.decode()}" for old in OLD_PATHS if old in data]
    assert stale == [], "files still name the old configuration path:\n" + "\n".join(stale)
