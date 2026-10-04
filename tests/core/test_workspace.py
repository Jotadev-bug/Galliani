"""Workspace toolkit: sandboxing, permission levels and protected files (specs 005, 009)."""

from __future__ import annotations

import pytest

from galliani.permissions import ApprovalRecord
from galliani.tools import ToolCall, ToolStatus, ToolSystem
from galliani.workspace import Workspace, normalize_relative


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "q3.md").write_text("Q3 spend is under plan.", encoding="utf-8")
    (tmp_path / ".env").write_text("API_KEY=real-secret", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x", encoding="utf-8")
    return Workspace(tmp_path)


def call(tool: str, **arguments) -> ToolCall:
    return ToolCall(tool_name=tool, call_id="c1", arguments=arguments, requested_by_step="s1")


@pytest.mark.parametrize("raw,expected", [("notes\\q3.md", "notes/q3.md"), ("./notes/", "notes"), ("", ".")])
def test_paths_are_normalized(raw, expected):
    assert normalize_relative(raw) == expected


@pytest.mark.parametrize("raw", ["../outside.txt", "notes/../../x", "/etc/passwd", "C:/Windows/win.ini"])
async def test_escaping_paths_are_invalid_arguments_and_never_run(ws, raw):
    result = await ToolSystem(ws.registry()).execute(call("read_file", path=raw), task_id="t")
    assert result.error.code == "invalid_arguments"


async def test_list_and_read_are_read_only_and_skip_protected_files(ws):
    system = ToolSystem(ws.registry())
    listed = await system.execute(call("list_files"), task_id="t")
    assert listed.status is ToolStatus.succeeded and listed.data["files"] == ["notes/q3.md"]
    read = await system.execute(call("read_file", path="notes/q3.md"), task_id="t")
    assert read.data["text"] == "Q3 spend is under plan."


@pytest.mark.parametrize("path", [".env", ".git/config"])
async def test_protected_files_are_refused(ws, path):
    result = await ToolSystem(ws.registry()).execute(call("read_file", path=path), task_id="t")
    assert result.error.code == "rejected_input" and "real-secret" not in result.model_dump_json()


async def test_write_requires_approval_scoped_to_the_path(ws):
    system = ToolSystem(ws.registry())
    blocked = await system.execute(call("write_file", path="out/summary.md", content="hi"), task_id="t")
    assert blocked.error.code == "permission_required" and blocked.permission_request.scope == "out/summary.md"
    assert not (ws.root / "out").exists()
    approval = ApprovalRecord(user_id="u", action="write_file", scope="out/summary.md")
    ok = await system.execute(call("write_file", path="out\\summary.md", content="hi"), task_id="t", approvals=[approval])
    assert ok.status is ToolStatus.succeeded and (ws.root / "out" / "summary.md").read_text() == "hi"
    other = await system.execute(call("write_file", path="out/other.md", content="x"), task_id="t", approvals=[approval])
    assert other.error.code == "permission_denied"  # scope mismatch is denied (009 AC Denied)


async def test_symlink_escape_is_refused(ws, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    (outside / "secret.txt").write_text("nope", encoding="utf-8")
    try:
        (ws.root / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not permitted on this system")
    result = await ToolSystem(ws.registry()).execute(call("read_file", path="link/secret.txt"), task_id="t")
    assert result.error.code == "rejected_input"


async def test_errors_give_replanning_usable_evidence(ws):
    system = ToolSystem(ws.registry())
    missing = await system.execute(call("list_files", path="docs"), task_id="t")
    assert "the workspace root ('.') contains: notes/" in missing.error.safe_summary
    assert ".env" not in missing.error.safe_summary and ".git" not in missing.error.safe_summary
    nested = await system.execute(call("read_file", path="notes/q4.md"), task_id="t")
    assert "'notes' contains: q3.md" in nested.error.safe_summary
    absolute = await system.execute(call("list_files", path="/docs"), task_id="t")
    assert "path must be relative to the workspace" in absolute.error.safe_summary


def test_overview_states_the_workspace_root(ws):
    from galliani.cli import workspace_overview

    overview = workspace_overview(ws.root)
    assert f"Workspace root: the folder '{ws.root.name}'" in overview and "use '.' for the root" in overview


async def test_read_files_reads_a_folder_in_one_bounded_step(ws):
    (ws.root / "notes" / "q2.md").write_text("Q2 on plan.", encoding="utf-8")
    (ws.root / "notes" / "img.png").write_bytes(b"\x89PNG")
    system = ToolSystem(ws.registry())
    result = await system.execute(call("read_files", path="notes", pattern="*.md"), task_id="t")
    assert result.status is ToolStatus.succeeded
    assert [f["path"] for f in result.data["files"]] == ["notes/q2.md", "notes/q3.md"]
    explicit = await system.execute(call("read_files", paths=["notes\\q3.md"]), task_id="t")
    assert explicit.data["files"][0]["text"] == "Q3 spend is under plan."
    blocked = await system.execute(call("read_files", paths=[".env"]), task_id="t")
    assert blocked.error.code == "rejected_input" and "real-secret" not in blocked.model_dump_json()
    escaped = await system.execute(call("read_files", paths=["../x"]), task_id="t")
    assert escaped.error.code == "invalid_arguments"
    everything = await system.execute(call("read_files"), task_id="t")
    assert ".env" not in {f["path"] for f in everything.data["files"]}


async def test_read_files_respects_the_total_size_limit(ws, monkeypatch):
    import galliani.workspace as wsmod

    monkeypatch.setattr(wsmod, "MAX_READ_MANY_BYTES", 30)
    (ws.root / "notes" / "q2.md").write_text("x" * 25, encoding="utf-8")
    result = await ToolSystem(ws.registry()).execute(call("read_files", path="notes"), task_id="t")
    assert [f["path"] for f in result.data["files"]] == ["notes/q2.md"]
    assert result.data["skipped"] == ["notes/q3.md"] and result.data["truncated"]
