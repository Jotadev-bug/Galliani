"""Spec 017 R1: only galliani/tui/app.py, widgets.py and styles.py may import Textual or Rich."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import galliani

UI_MODULES = {"galliani/tui/app.py", "galliani/tui/widgets.py", "galliani/tui/styles.py"}
BLOCKED = ("textual", "rich")


def _imports(tree: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", None)) in (
                "import_module", "__import__") and node.args and isinstance(node.args[0], ast.Constant):
            names.add(str(node.args[0].value).split(".")[0])
    return names


def test_only_the_three_ui_modules_import_textual_or_rich():
    root = Path(galliani.__file__).parent
    offenders = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root.parent).as_posix()
        if rel in UI_MODULES:
            continue
        found = _imports(ast.parse(path.read_text(encoding="utf-8"), rel)) & set(BLOCKED)
        if found:
            offenders.append(f"{rel}: {sorted(found)}")
    assert offenders == []


def test_the_scan_detects_an_import():
    assert _imports(ast.parse("import rich.text\nfrom textual.app import App")) == {"rich", "textual"}
    assert _imports(ast.parse("importlib.import_module('textual')")) == {"textual"}


def test_session_commands_and_entry_import_with_textual_and_rich_blocked():
    code = ("import sys\n"
            "sys.modules['textual'] = None\nsys.modules['rich'] = None\n"
            "import galliani.tui, galliani.tui.session, galliani.tui.commands, galliani.tui.entry\n"
            "loaded = sorted(m for m in sys.modules if m.split('.')[0] in ('textual', 'rich')"
            " and sys.modules[m] is not None)\n"
            "print(loaded, 'galliani.tui.app' in sys.modules)\n")
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[] False"
