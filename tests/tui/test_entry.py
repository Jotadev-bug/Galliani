"""Spec 017 R2-R5: the `galliani` entry point. One-shot delegation, fallbacks and flag errors."""

from __future__ import annotations

import subprocess
import sys
import types

import pytest

import galliani.cli as cli
from galliani.permissions import EditMode
from galliani.tui import entry, session as session_mod


@pytest.fixture
def tty(monkeypatch):
    """Pretend Textual is installed and stdin/stdout are a terminal."""
    monkeypatch.setattr(entry, "_textual_missing", lambda: False)
    monkeypatch.setattr(entry, "_isatty", lambda stream: True)
    monkeypatch.delenv("TERM", raising=False)


# ---------------------------------------------------------------------- One-Shot Unchanged


def test_objective_delegates_to_the_one_shot_with_the_same_arguments(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(cli, "main", lambda argv=None: seen.append(argv) or 7)
    argv = ["Summarize notes", "--workspace", str(tmp_path), "--budget", "1", "--accept-edits", "--context", "c"]
    assert entry.main(argv) == 7 and seen == [argv]


def test_one_shot_output_and_exit_code_equal_the_cli(tmp_path, capsys):
    argv = ["Summarize notes", "--workspace", str(tmp_path / "missing")]
    code = cli.main(argv)
    expected = capsys.readouterr()
    assert entry.main(argv) == code == 2
    assert capsys.readouterr() == expected


def test_one_shot_usage_errors_are_the_cli_s(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(cli, "main", lambda argv=None: seen.append(argv) or 2)
    assert entry.main(["do it", "--non-interactive", "--events", str(tmp_path / "e.jsonl")]) == 2
    assert seen and seen[0][0] == "do it"


# ---------------------------------------------------------------------- Fallback Without Textual Or TTY


def test_fallback_when_textual_is_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(sys.modules, "textual", None)  # blocks `import textual`
    monkeypatch.delitem(sys.modules, "galliani.tui.app", raising=False)
    built = []
    monkeypatch.setattr(session_mod, "Session", lambda *a, **k: built.append(1))
    assert entry.main(["--workspace", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "Textual" in err and 'pip install "galliani[tui]"' in err and 'galliani "<objective>"' in err
    assert sys.modules["textual"] is None and "galliani.tui.app" not in sys.modules and built == []


def test_fallback_when_not_a_tty(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(entry, "_textual_missing", lambda: False)
    monkeypatch.setattr(entry, "_isatty", lambda stream: stream is sys.stdin)  # stdout redirected
    assert entry.main(["--workspace", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "TTY" in err and 'galliani "<objective>"' in err and "pip install" not in err


def test_fallback_when_term_is_dumb(tty, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("TERM", "dumb")
    assert entry.main(["--workspace", str(tmp_path)]) == 2
    assert "TERM=dumb" in capsys.readouterr().err


def test_fallback_ignores_galliani_require_tui(monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(sys.modules, "textual", None)
    monkeypatch.setenv("GALLIANI_REQUIRE_TUI", "1")
    assert entry.main(["--workspace", str(tmp_path)]) == 2
    assert "pip install" in capsys.readouterr().err


def test_real_stdout_pipe_falls_back_without_importing_textual(tmp_path):
    code = ("import sys, galliani.tui.entry as e; rc = e.main(['--workspace', sys.argv[1]]); "
            "print('textual' in sys.modules, 'galliani.tui.app' in sys.modules); sys.exit(rc)")
    proc = subprocess.run([sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=120)
    assert proc.returncode == 2 and proc.stdout.strip() == "False False"
    assert 'galliani "<objective>"' in proc.stderr


def test_textual_missing_check_does_not_import_it(monkeypatch):
    monkeypatch.delitem(sys.modules, "textual", raising=False)
    entry._textual_missing()
    assert "textual" not in sys.modules


# ---------------------------------------------------------------------- session start


def test_no_objective_builds_a_session_and_runs_the_app_lazily(tty, monkeypatch, tmp_path):
    seen = {}

    class FakeSession:
        def __init__(self, config):
            seen["config"] = config

    def run_app(session, *, theme="dark"):
        seen["run"] = (session, theme)
        return 0

    monkeypatch.setattr(session_mod, "Session", FakeSession)
    monkeypatch.setitem(sys.modules, "galliani.tui.app", types.SimpleNamespace(run_app=run_app))
    events = tmp_path / "events.jsonl"
    argv = ["--workspace", str(tmp_path), "--budget", "0", "--no-memory", "--accept-edits", "--events", str(events),
            "--theme", "light"]
    assert entry.main(argv) == 0
    config = seen["config"]
    assert config.workspace == tmp_path and config.budget_usd is None and config.memory_on is False
    assert config.edit_mode is EditMode.accept_edits and config.events_path == events
    assert seen["run"][1] == "light" and isinstance(seen["run"][0], FakeSession)


def test_session_defaults(tty, monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(session_mod, "Session", lambda config: seen.setdefault("config", config))
    monkeypatch.setitem(sys.modules, "galliani.tui.app",
                        types.SimpleNamespace(run_app=lambda s, theme="dark": 3 if theme == "dark" else 9))
    monkeypatch.chdir(tmp_path)
    assert entry.main([]) == 3
    config = seen["config"]
    assert config.budget_usd == cli.DEFAULT_BUDGET_USD and config.memory_on and config.edit_mode is EditMode.ask
    assert config.events_path is None and str(config.workspace) == "."


# ---------------------------------------------------------------------- flag errors


@pytest.mark.parametrize("argv, needle", [
    (["--context", "notes"], "--context needs an objective"),
    (["--non-interactive"], "--non-interactive needs an objective"),
])
def test_one_shot_flags_without_an_objective_are_usage_errors(tty, argv, needle, tmp_path, capsys):
    assert entry.main([*argv, "--workspace", str(tmp_path)]) == 2
    assert needle in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["--theme", "blue"], ["--budget", "lots"], ["--bogus"]])
def test_bad_flags_exit_2(tty, argv, capsys):
    assert entry.main(argv) == 2
    assert "usage: galliani" in capsys.readouterr().err


def test_missing_workspace_prints_the_one_shot_message(tty, tmp_path, capsys):
    assert entry.main(["--workspace", str(tmp_path / "nope")]) == 2
    err = capsys.readouterr().err
    assert err.startswith("Workspace folder not found") and "Traceback" not in err


def test_help_exits_0(capsys):
    assert entry.main(["--help"]) == 0
    assert "--theme" in capsys.readouterr().out


def test_python_dash_m_galliani_tui_runs_entry_main(tmp_path):
    proc = subprocess.run([sys.executable, "-m", "galliani.tui", "--workspace", str(tmp_path / "nope")],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    assert proc.returncode == 2 and "Workspace folder not found" in proc.stderr
