"""Spec 017 R2-R5 and 018 R23-R25, R27: the `galliacli` entry point. One-shot delegation, fallbacks and flag errors."""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import pytest

import galliani
import galliani.cli as cli
from galliani.permissions import EditMode
from galliani.tui import entry, session as session_mod

ROOT = Path(__file__).resolve().parents[2]


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


@pytest.mark.parametrize("argv", [["do it", "--budget", "abc"], ["do it", "--theme", "blue"], ["do it", "--budget"]])
def test_one_shot_usage_errors_name_the_cli_program(argv, capsys):
    assert entry.main(argv) == 2
    err = capsys.readouterr().err
    assert "usage: python -m galliani.cli" in err and "usage: galliacli" not in err


# ---------------------------------------------------------------------- Fallback Without Textual Or TTY


def test_fallback_when_textual_is_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(sys.modules, "textual", None)  # blocks `import textual`
    monkeypatch.delitem(sys.modules, "galliani.tui.app", raising=False)
    built = []
    monkeypatch.setattr(session_mod, "Session", lambda *a, **k: built.append(1))
    assert entry.main(["--workspace", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "Textual" in err and 'pip install "galliani[tui]"' in err and 'galliacli "<objective>"' in err
    assert sys.modules["textual"] is None and "galliani.tui.app" not in sys.modules and built == []


def test_fallback_when_not_a_tty(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(entry, "_textual_missing", lambda: False)
    monkeypatch.setattr(entry, "_isatty", lambda stream: stream is sys.stdin)  # stdout redirected
    assert entry.main(["--workspace", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "TTY" in err and 'galliacli "<objective>"' in err and "pip install" not in err


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
    assert 'galliacli "<objective>"' in proc.stderr


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
    assert "usage: galliacli" in capsys.readouterr().err


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


# ---------------------------------------------------------------------- 018 R23, R24, R27: launch forms and name


BLOCK_TEXTUAL = "import sys; sys.modules['textual'] = None; sys.modules['rich'] = None; "


def test_version_prints_galliacli_and_the_version(capsys):
    assert entry.main(["--version"]) == 0
    assert capsys.readouterr().out == f"galliacli {galliani.__version__}\n"


@pytest.mark.parametrize("argv", [["--version", "--workspace", "nope"], ["do it", "--version"],
                                  ["--theme", "blue", "--version"], ["--version", "--bogus"]])
def test_version_with_other_flags_still_prints_and_exits_0(argv, capsys, monkeypatch):
    monkeypatch.setattr(cli, "main", lambda argv=None: pytest.fail("the one-shot must not run"))
    assert entry.main(argv) == 0
    assert capsys.readouterr().out.strip() == f"galliacli {galliani.__version__}"


def test_version_after_double_dash_is_not_the_flag(monkeypatch):
    seen = []
    monkeypatch.setattr(cli, "main", lambda argv=None: seen.append(argv) or 0)
    assert entry.main(["--", "--version"]) == 0 and seen == [["--", "--version"]]


@pytest.mark.parametrize("module", ["galliani", "galliani.tui"])
def test_version_does_not_import_textual(module):
    code = (BLOCK_TEXTUAL + f"import runpy; sys.argv = ['x', '--version']; "
            f"\ntry:\n    runpy.run_module('{module}', run_name='__main__')\nexcept SystemExit as e:\n"
            "    print('exit', e.code)\n"
            "print(sorted(m for m in sys.modules if m.split('.')[0] in ('textual', 'rich') and sys.modules[m]))")
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines() == [f"galliacli {galliani.__version__}", "exit 0", "[]"]


def test_python_dash_m_galliani_runs_entry_main(tmp_path):
    proc = subprocess.run([sys.executable, "-m", "galliani", "--workspace", str(tmp_path / "nope")],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    assert proc.returncode == 2 and "Workspace folder not found" in proc.stderr


def test_python_dash_m_galliani_falls_back_like_galliacli(tmp_path):
    proc = subprocess.run([sys.executable, "-m", "galliani", "--workspace", str(tmp_path)],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    assert proc.returncode == 2 and 'galliacli "<objective>"' in proc.stderr


def test_importing_galliani_does_not_load_the_entry_point():
    code = "import sys, galliani; print('galliani.tui.entry' in sys.modules, 'galliani.__main__' in sys.modules)"
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert proc.stdout.strip() == "False False"


def test_galliani_main_module_runs_entry_main(monkeypatch):
    import galliani.__main__ as main_module

    monkeypatch.setattr(entry, "main", lambda argv=None: 5)
    assert main_module._main() == 5


def test_help_and_usage_name_galliacli(capsys):
    assert entry.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("usage: galliacli ") and "--version" in out and "usage: galliani " not in out
    assert entry.main(["--bogus"]) == 2
    assert "usage: galliacli " in capsys.readouterr().err


def test_one_shot_hint_and_flag_errors_name_galliacli(tty, tmp_path, capsys):
    assert entry.ONE_SHOT_HINT.endswith('galliacli "<objective>"') and "galliani " not in entry.ONE_SHOT_HINT
    assert entry.main(["--context", "x", "--workspace", str(tmp_path)]) == 2
    assert capsys.readouterr().err.startswith("galliacli: --context needs an objective.")


def test_pyproject_installs_galliacli_and_galliani_stays_the_desktop():
    import tomllib

    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]
    assert scripts.get("galliacli") == "galliani.tui.entry:main"
    assert "galliani" not in scripts
    assert [name for name, target in scripts.items() if target == "galliani.tui.entry:main"] == ["galliacli"]
    assert data["project"]["name"] == "galliani" and "tui" in data["project"]["optional-dependencies"]
