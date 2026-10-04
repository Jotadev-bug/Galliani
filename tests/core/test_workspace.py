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
