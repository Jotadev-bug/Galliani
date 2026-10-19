"""Spec 018 R2 (banner data), R13 (honest progress and cost), R15 and R25: headless `Session` checks."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

import galliani
from galliani.observability import EventType, LifecycleEvent, TraceContext
from galliani.permissions import EditMode
from galliani.tui import entry
from galliani.tui import session as session_mod
from galliani.tui.session import WIDE_WORKSPACE_WARNING, BannerInfo, display_path
from tests.tui.conftest import make_session, read_step

KEYS = {"OPENAI_API_KEY": "sk-abcdefghijklmnopqrstuvwx1234", "ANTHROPIC_API_KEY": "sk-ant-zyxwvutsrqponmlkjihg9876"}


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fake home folder, so `~` and the R25 check never depend on the real one."""
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: folder))
    return folder


def keys(monkeypatch, found: dict[str, str]):
    monkeypatch.setattr(session_mod, "load_keys", lambda: dict(found))


# ---------------------------------------------------------------------- R2 Banner


def test_banner_shows_version_home_relative_workspace_and_provider_names_only(home, monkeypatch):
    project = home / "projects" / "site"
    project.mkdir(parents=True)
    keys(monkeypatch, KEYS)
    session, _ = make_session(project, budget_usd=1.25, edit_mode=EditMode.accept_edits)
    info = session.banner()
    assert isinstance(info, BannerInfo)
    assert info.version == galliani.__version__
    assert info.workspace == str(Path("~") / "projects" / "site")
    assert info.providers == ("anthropic", "openai")
    assert info.wide_workspace is False
    assert info.edit_mode is EditMode.accept_edits and info.budget_usd == 1.25 and info.memory == "on"
    shown = repr(dataclasses.astuple(info))
    for value in KEYS.values():
        assert value not in shown and value[:8] not in shown and value[-4:] not in shown


def test_banner_with_no_keys_lists_no_provider(home, monkeypatch):
    keys(monkeypatch, {})
    session, _ = make_session(home / ".." / "home")
    assert session.banner().providers == ()


def test_banner_ignores_unknown_key_names_and_a_broken_key_store(home, monkeypatch, workspace):
    keys(monkeypatch, {"SOMETHING_ELSE": "x"})
    session, _ = make_session(workspace)
    assert session.banner().providers == ()

    def broken():
        raise OSError("keyring locked")
    monkeypatch.setattr(session_mod, "load_keys", broken)
    assert session.banner().providers == ()


def test_banner_outside_home_shows_the_absolute_path(home, tmp_path, monkeypatch, workspace):
    keys(monkeypatch, {})
    session, _ = make_session(workspace)
    info = session.banner()
    assert info.workspace == str(workspace.resolve()) and not info.workspace.startswith("~")


def test_banner_workspace_text_is_sanitized(home, monkeypatch):
    odd = home / "ev‮il"
    odd.mkdir()
    keys(monkeypatch, {})
    session, _ = make_session(odd)
    assert "‮" not in session.banner().workspace


def test_banner_follows_session_settings(home, monkeypatch, workspace):
    keys(monkeypatch, {})
    session, _ = make_session(workspace, memory_on=False, budget_usd=None)
    info = session.banner()
    assert info.memory == "off" and info.budget_usd is None and info.edit_mode is EditMode.ask


def test_session_opens_without_the_017_start_notice(workspace, monkeypatch):
    keys(monkeypatch, {})
    session, _ = make_session(workspace)
    assert session.entries() == []  # the banner replaces it (R2); /clear cannot bring it back


def test_display_path_home_itself_is_a_tilde(home):
    assert display_path(home) == "~"


# ---------------------------------------------------------------------- R25 wide workspace


def test_home_folder_is_a_wide_workspace(home, monkeypatch):
    keys(monkeypatch, {})
    session, _ = make_session(home)
    info = session.banner()
    assert info.wide_workspace is True and info.workspace == "~"
    assert entry.is_wide_workspace(home / "x" / "..")


def test_filesystem_root_is_a_wide_workspace(home):
    root = Path(Path.cwd().anchor)
    assert entry.is_wide_workspace(root)


@pytest.mark.parametrize("sub", ["project", "project/deeper"])
def test_a_project_folder_is_not_wide(home, sub):
    folder = home / sub
    folder.mkdir(parents=True)
    assert not entry.is_wide_workspace(folder)


def test_wide_workspace_warning_text_is_the_spec_s():
    assert WIDE_WORKSPACE_WARNING == (
        "This workspace is your whole home folder (or drive). The agent can read any file in it that is not "
        "protected. Start galliacli in a project folder, or use /workspace.")


def test_wide_workspace_is_a_notice_only(home, monkeypatch):
    keys(monkeypatch, {})
    session, factory = make_session(home)
    assert session.banner().wide_workspace and session.state.phase.value == "idle" and factory.builds
    assert list(home.iterdir()) == []  # nothing stored


# ---------------------------------------------------------------------- R13 honest progress and cost


def event(session, type_: EventType, **metadata) -> None:
    task_id = session._task_id or "t1"
    session._task_id = task_id
    session._on_event(LifecycleEvent(task_id=task_id, type=type_, public_summary="x",
                                     refs=TraceContext(task_id=task_id), metadata=metadata))


def test_cost_moves_only_on_worker_completed(workspace):
    session, _ = make_session(workspace)
    event(session, EventType.worker_completed, usage={"cost_micro_usd": 250_000})
    assert session.state.status.task_cost_usd == 0.25 and session.state.status.session_cost_usd == 0.25
    for other in (EventType.step_executed, EventType.route_selected, EventType.tool_called):
        event(session, other, usage={"cost_micro_usd": 9_000_000})
    assert session.state.status.task_cost_usd == 0.25


def test_no_plan_means_no_step_progress_and_no_budget_means_no_limit(workspace):
    session, _ = make_session(workspace, budget_usd=None)
    state = session.state
    assert state.plan is None and state.status.budget_usd is None and state.status.task_cost_usd == 0


async def test_step_progress_comes_only_from_the_plan(workspace):
    session, _ = make_session(workspace, plans=[{"steps": [read_step()]}])
    await session.submit("Read notes.md")
    plan = session.state.plan
    assert plan is not None and [s.step_id for s in plan.steps] == ["s1"]


async def test_budget_label_reads_no_limit(workspace):
    session, _ = make_session(workspace)
    await session.submit("/budget off")
    assert session.entries()[-1].text == "Budget: no limit (applies to the next task)."
    assert session.banner().budget_usd is None
