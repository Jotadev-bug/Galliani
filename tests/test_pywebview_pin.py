"""Spec 012 R7, AC "pywebview Pin": the WebView2 check mirrors pywebview 6.2.1."""

from __future__ import annotations

import re
import tomllib
from importlib import metadata
from pathlib import Path

EXPECTED_SPEC = "pywebview>=6.2,<7"
MIN_VERSION = (6, 2)
MAX_EXCLUSIVE = (7,)
RECHECK = (
    "Re-check spec 012 R7 against the new webview/platforms/winforms.py "
    "_is_chromium() (and R8 against mshtml.py _set_ie_mode()), update the spec, "
    "then change the pin in pyproject.toml and this test together."
)


def _numeric_parts(version: str) -> tuple[int, ...]:
    match = re.match(r"\d+(?:\.\d+)*", version)
    assert match, f"Unparseable version {version!r}"
    return tuple(int(p) for p in match.group(0).split("."))


def test_installed_pywebview_is_inside_the_pin() -> None:
    version = metadata.version("pywebview")
    parts = _numeric_parts(version)
    assert MIN_VERSION <= parts < MAX_EXCLUSIVE, (
        f"Installed pywebview {version} is outside >=6.2,<7. {RECHECK}"
    )


def test_pyproject_desktop_extra_declares_the_pin() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    desktop = data["project"]["optional-dependencies"]["desktop"]
    declared = [d.replace(" ", "") for d in desktop if d.lower().startswith("pywebview")]
    assert declared == [EXPECTED_SPEC], (
        f"pyproject.toml desktop extra declares {declared}, expected [{EXPECTED_SPEC!r}]. {RECHECK}"
    )
