"""Spec 016 R27, R29, R31, R32, R34: the pure parts of scripts.check_wheel (the full build is the `wheel` CI job)."""

from __future__ import annotations

from scripts.check_wheel import (REQUIRED_FILES, diff_snapshots, inspect_wheel, project_version, sdist_problems,
                                 snapshot)

GOOD_ENTRY_POINTS = """[console_scripts]
galliacli = galliani.tui.entry:main
galliani = app.desktop:main
"""

GOOD_NAMES = [
    *REQUIRED_FILES,
    "app/__init__.py",
    "app/desktop.py",
    "galliani/__init__.py",
    "galliani/tui/entry.py",
    "galliani-0.2.0.dist-info/METADATA",
    "galliani-0.2.0.dist-info/entry_points.txt",
    "galliani-0.2.0.dist-info/RECORD",
]


def test_good_wheel_has_no_problems():
    assert inspect_wheel(GOOD_NAMES, GOOD_ENTRY_POINTS) == []


def test_missing_data_file_is_named():
    names = [n for n in GOOD_NAMES if n != "app/defaults/routing.yaml"]
    assert inspect_wheel(names, GOOD_ENTRY_POINTS) == ["missing file: app/defaults/routing.yaml"]


def test_old_config_folder_is_not_enough():
    names = [n for n in GOOD_NAMES if not n.startswith("app/defaults/")] + ["config/" + "models.yaml"]  # split so the stale-path test does not flag this negative case
    problems = inspect_wheel(names, GOOD_ENTRY_POINTS)
    assert "missing file: app/defaults/models.yaml" in problems
    assert "unexpected top-level package: config" in problems


def test_benchmarks_and_other_packages_are_refused():
    names = GOOD_NAMES + ["benchmarks/__init__.py", "tests/test_x.py", "scripts/build_desktop.py"]
    problems = inspect_wheel(names, GOOD_ENTRY_POINTS)
    assert {"unexpected top-level package: benchmarks", "unexpected top-level package: tests",
            "unexpected top-level package: scripts"} <= set(problems)


def test_loose_top_level_file_is_refused():
    assert "unexpected top-level file: .env" in inspect_wheel(GOOD_NAMES + [".env"], GOOD_ENTRY_POINTS)


def test_missing_package_is_reported():
    names = [n for n in GOOD_NAMES if not n.startswith("galliani/")]
    assert "missing top-level package: galliani" in inspect_wheel(names, GOOD_ENTRY_POINTS)


def test_missing_web_directory_files():
    names = [n for n in GOOD_NAMES if not n.startswith("app/web/")]
    problems = inspect_wheel(names, GOOD_ENTRY_POINTS)
    assert "missing files: app/web/*" in problems and "missing file: app/web/logo.png" in problems


def test_extra_script_wrong_target_and_gui_scripts():
    entry = """[console_scripts]
galliani = app.main:main
extra = app.x:y

[gui_scripts]
galliani-gui = app.desktop:main
"""
    problems = inspect_wheel(GOOD_NAMES, entry)
    assert "script galliani points to app.main:main, expected app.desktop:main" in problems
    assert "missing script: galliacli" in problems
    assert "unexpected script: extra" in problems
    assert "unexpected entry point group: gui_scripts" in problems


def test_empty_entry_points_reports_both_scripts():
    problems = inspect_wheel(GOOD_NAMES, "")
    assert "missing script: galliani" in problems and "missing script: galliacli" in problems


def test_sdist_must_hold_the_data_files():
    names = [f"galliani-0.2.0/{n}" for n in REQUIRED_FILES]
    assert sdist_problems(names) == []
    assert sdist_problems(names[1:]) == [f"sdist is missing file: {REQUIRED_FILES[0]}"]


def test_snapshot_ignores_bytecode_and_reports_changes(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "__pycache__").mkdir()
    before = snapshot(tmp_path)
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"x")
    (tmp_path / "m.pyc").write_bytes(b"x")
    assert diff_snapshots(before, snapshot(tmp_path)) == []
    (tmp_path / "a.txt").write_text("changed!")
    (tmp_path / "new.cfg").write_text("n")
    assert diff_snapshots(before, snapshot(tmp_path)) == ["created: new.cfg", "changed: a.txt"]
    (tmp_path / "a.txt").unlink()
    assert "deleted: a.txt" in diff_snapshots(before, snapshot(tmp_path))


def test_project_version_reads_pyproject(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nversion = "1.2.3"\n')
    assert project_version(path) == "1.2.3"
