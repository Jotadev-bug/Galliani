"""Independent security review of agent file access and accept-edits mode (roadmap item 4).

Specs: 005 (tool system), 009 (permissions), 014 (accept-edits). Each test names the finding it pins
down in docs/security.md ("Review findings"). They were written as `xfail(strict=True)` while each gap
was open; the markers were removed as the fixes landed, so every finding is now a regression guard.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from galliani.contracts import Objective
from galliani.observability import InMemoryEventSink, Observability
from galliani.permissions import EditMode
from galliani.planner import StaticPlanner
from galliani.router import ModelRouter
from galliani.state import TaskStatus
from galliani.supervisor import StartTaskRequest, Supervisor, UserPolicy
from galliani.testing import ScriptedAdapter
from galliani.tools import ToolCall, ToolStatus, ToolSystem
from galliani.workspace import Workspace
from tests.core.helpers import worker

WINDOWS = sys.platform == "win32"
windows_only = pytest.mark.skipif(not WINDOWS, reason="Win32 path normalization trick")
REFUSED = {"rejected_input", "invalid_arguments"}
LOCAL = "http://127.0.0.1"  # the API only answers local Host names (SEC-8)
ORIGINAL_GIT = "[core]\n"
ORIGINAL_ENV = "API_KEY=real-secret-value\n"
ORIGINAL_KEY = "-----KEY-----\n"


@pytest.fixture
def ws(tmp_path) -> Workspace:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text(ORIGINAL_GIT, encoding="utf-8")
    (tmp_path / ".env").write_text(ORIGINAL_ENV, encoding="utf-8")
    (tmp_path / "server.key").write_text(ORIGINAL_KEY, encoding="utf-8")
    (tmp_path / "notes.txt").write_text("plain notes", encoding="utf-8")
    return Workspace(tmp_path)


def call(tool: str, **arguments) -> ToolCall:
    return ToolCall(tool_name=tool, call_id="c1", arguments=arguments, requested_by_step="s1")


async def run_tool(ws: Workspace, tool: str, **arguments):
    """Run a tool the way an accept-edits task does: writes need no approval."""
    return await ToolSystem(ws.registry()).execute(call(tool, **arguments), task_id="t", edit_mode=EditMode.accept_edits)


def untouched(ws: Workspace) -> bool:
    root = ws.root
    return ((root / ".git" / "config").read_text(encoding="utf-8") == ORIGINAL_GIT
            and (root / ".env").read_text(encoding="utf-8") == ORIGINAL_ENV
            and (root / "server.key").read_text(encoding="utf-8") == ORIGINAL_KEY
            and not (root / ".git" / "hooks").exists())


def leaked(result, secret: str) -> bool:
    return secret.strip() in result.model_dump_json()


def make_dir_link(link: Path, target: Path) -> None:
    """A directory link the agent did not create (e.g. from a cloned repo or another tool)."""
    if WINDOWS:  # junctions need no special privilege on Windows
        done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
        if done.returncode != 0 or not link.exists():
            pytest.skip("could not create a junction")
    else:
        link.symlink_to(target, target_is_directory=True)


# ------------------------------------------------------------------ controls that hold today (regression guards)

@pytest.mark.parametrize("path", [".ENV", ".env.", ".env ", "SERVER.KEY", "ID_RSA", "Secrets.json", ".Env.Local"])
async def test_case_and_trailing_variants_of_protected_file_names_are_refused(ws, path):
    result = await run_tool(ws, "write_file", path=path, content="PWNED")
    assert result.error and result.error.code in REFUSED and untouched(ws)


@pytest.mark.parametrize("path", ["..\\outside.txt", "a/../../outside.txt", "\\\\server\\share\\x.txt",
                                  "\\\\?\\C:\\x.txt", "//server/share/x.txt", "C:x.txt", "C:\\x.txt", "/tmp/x.txt"])
async def test_absolute_unc_drive_and_traversal_paths_never_run(ws, path):
    result = await run_tool(ws, "write_file", path=path, content="PWNED")
    assert result.error and result.error.code == "invalid_arguments"
    assert not (ws.root.parent / "outside.txt").exists()


async def test_junction_or_symlink_escaping_the_workspace_is_refused(ws, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    (outside / "secret.txt").write_text("OUTSIDE-SECRET", encoding="utf-8")
    make_dir_link(ws.root / "escape", outside)
    read = await run_tool(ws, "read_file", path="escape/secret.txt")
    write = await run_tool(ws, "write_file", path="escape/new.txt", content="PWNED")
    assert read.error.code == "rejected_input" and not leaked(read, "OUTSIDE-SECRET")
    assert write.error.code == "rejected_input" and sorted(os.listdir(outside)) == ["secret.txt"]


# ------------------------------------------------------------------ SEC-1: protected names vs Win32 normalization

@windows_only
@pytest.mark.parametrize("path", [".GIT/config", ".Git/hooks/pre-commit", ".git./config", ".git /config"])
async def test_git_directory_variants_are_refused_in_accept_edits(ws, path):
    # On Windows every one of these names reaches the real .git folder; hooks give code execution.
    result = await run_tool(ws, "write_file", path=path, content="#!/bin/sh\necho PWNED\n")
    assert result.error and result.error.code in REFUSED
    assert untouched(ws)


@windows_only
@pytest.mark.parametrize("path", [".env::$DATA", "server.key::$DATA", "server.key."])
async def test_protected_files_via_data_stream_or_trailing_dot_are_not_written(ws, path):
    result = await run_tool(ws, "write_file", path=path, content="PWNED")
    assert result.error and result.error.code in REFUSED
    assert untouched(ws)


@windows_only
@pytest.mark.parametrize("path,secret", [(".env::$DATA", ORIGINAL_ENV), ("server.key.", ORIGINAL_KEY),
                                         (".GIT/config", ORIGINAL_GIT)])
async def test_protected_files_are_not_read_through_aliases(ws, path, secret):
    # read_file is read-only: it never prompts, and its output goes to model providers.
    result = await run_tool(ws, "read_file", path=path)
    assert result.error and result.error.code in REFUSED and not leaked(result, secret)


@windows_only
async def test_alternate_data_streams_of_ordinary_files_are_refused(ws):
    result = await run_tool(ws, "write_file", path="notes.txt:hidden", content="invisible payload")
    assert result.error and result.error.code in REFUSED


@windows_only
async def test_accept_edits_task_cannot_plant_a_git_hook(ws):
    """End to end: a plan (e.g. from a prompt-injected file) writes a hook; accept-edits must not run it."""
    step = {"step_id": "s1", "kind": "tool", "purpose": "add a helper script", "required_capability": "write_file",
            "expected_output": "file", "verification_criteria": [{"kind": "field_present", "field": "bytes"}],
            "tool": {"tool_name": "write_file",
                     "arguments": {"path": ".Git/hooks/post-checkout", "content": "#!/bin/sh\necho PWNED\n"}}}
    sup = Supervisor(planner=StaticPlanner([{"steps": [step]}]), router=ModelRouter([worker("w1")]),
                     adapters=[ScriptedAdapter("scripted", {})], tools=ToolSystem(ws.registry()),
                     observability=Observability([]))
    result = await sup.start(StartTaskRequest(objective=Objective(goal="Add a helper"),
                                              user_policy=UserPolicy(edit_mode=EditMode.accept_edits)))
    assert result.status is not TaskStatus.done
    assert not (ws.root / ".git" / "hooks").exists()


# ------------------------------------------------------------------ SEC-2: resolved target is not re-checked

async def test_link_inside_the_workspace_to_git_is_refused(ws):
    make_dir_link(ws.root / "gitlink", ws.root / ".git")
    write = await run_tool(ws, "write_file", path="gitlink/config", content="PWNED")
    read = await run_tool(ws, "read_file", path="gitlink/config")
    listed = await run_tool(ws, "list_files")
    assert write.error and write.error.code == "rejected_input" and untouched(ws)
    assert read.error and read.error.code == "rejected_input"
    assert not any(f.startswith("gitlink/") for f in listed.data["files"])


async def test_file_symlink_to_env_is_refused(ws):
    try:
        (ws.root / "settings.txt").symlink_to(ws.root / ".env")
    except OSError:
        pytest.skip("file symlinks not permitted on this system")
    read = await run_tool(ws, "read_file", path="settings.txt")
    write = await run_tool(ws, "write_file", path="settings.txt", content="PWNED")
    assert read.error and not leaked(read, ORIGINAL_ENV)
    assert write.error and untouched(ws)


@windows_only
async def test_short_8dot3_name_of_git_is_refused(ws):
    if not (ws.root / "GIT~1").exists():
        pytest.skip("8.3 short names are not generated on this volume")
    write = await run_tool(ws, "write_file", path="GIT~1/config", content="PWNED")
    read = await run_tool(ws, "read_file", path="GIT~1/config")
    assert write.error and write.error.code in REFUSED and untouched(ws)
    assert read.error and read.error.code in REFUSED


# ------------------------------------------------------------------ SEC-3: events must not carry file contents

async def test_events_name_files_but_never_their_contents(tmp_path):
    marker = "CONFIDENTIAL-BODY-7f3a"  # not a recognizable secret pattern, so redaction does not catch it
    steps = [
        {"step_id": "s1", "kind": "tool", "purpose": "write the page", "required_capability": "write_file",
         "expected_output": "file", "verification_criteria": [{"kind": "field_present", "field": "bytes"}],
         "tool": {"tool_name": "write_file", "arguments": {"path": "index.html", "content": f"<p>{marker}</p>"}}},
        {"step_id": "s2", "kind": "tool", "purpose": "write the rest", "required_capability": "write_files",
         "expected_output": "files", "verification_criteria": [{"kind": "field_present", "field": "bytes"}],
         "tool": {"tool_name": "write_files", "arguments": {"bundle": f"=== a.js ===\n{marker}\n=== b.css ===\nx\n"}}},
    ]
    sink = InMemoryEventSink()
    sup = Supervisor(planner=StaticPlanner([{"steps": steps}]), router=ModelRouter([worker("w1")]),
                     adapters=[ScriptedAdapter("scripted", {})], tools=ToolSystem(Workspace(tmp_path).registry()),
                     observability=Observability([sink]))
    result = await sup.start(StartTaskRequest(objective=Objective(goal="Build it"),
                                              user_policy=UserPolicy(edit_mode=EditMode.accept_edits)))
    assert result.status is TaskStatus.done
    dumped = "\n".join(e.model_dump_json() for e in sink.for_task(result.task_id))
    assert "index.html" in dumped  # files are named ...
    assert marker not in dumped  # ... their contents are not (014 Security)


# ------------------------------------------------------------------ SEC-4: API surfaces the ineligible choice

def test_api_rejects_approve_and_accept_edits_on_a_non_write_prompt(tmp_path, monkeypatch):
    from tests.core.test_agent_api import client_for, wait_for

    remember = {"step_id": "m1", "kind": "tool", "purpose": "save a preference", "required_capability": "remember",
                "expected_output": "saved", "verification_criteria": [{"kind": "field_present", "field": "id"}],
                "tool": {"tool_name": "remember", "arguments": {"content": "Use tabs.", "type": "preference"}}}
    with client_for([{"steps": [remember]}], monkeypatch, tmp_path) as client:
        task_id = client.post("/api/agent/tasks", json={"objective": "Remember tabs", "workspace": str(tmp_path)}
                              ).json()["task_id"]
        paused = wait_for(client, task_id, "waiting_for_user")["view"]
        assert "approve_and_accept_edits" not in paused["approval_prompt"]["allowed_choices"]
        res = client.post(f"/api/agent/tasks/{task_id}/approve", json={"accept_edits": True})
        assert res.status_code == 409  # 014 Error Handling: rejected, the prompt stays open
        view = client.get(f"/api/agent/tasks/{task_id}").json()
        assert view["status"] == "waiting_for_user" and view["edit_mode"] == "ask"


# ------------------------------------------------------------------ SEC-1 (all platforms): names Win32 would rewrite

@pytest.mark.parametrize("path", ["notes.txt:hidden", ".env::$DATA", "a:b/c.txt", "docs./x.md", "docs /x.md",
                                  "x.txt.", "x.txt. ", "CON", "con.txt", "nul", "Aux.log", "COM1", "lpt9.txt",
                                  "COM¹", "CON .txt", "sub/PRN", "conin$", "a*b.txt", "a?.txt", "a|b", "a\x01b"])
async def test_names_windows_would_rewrite_are_invalid_on_every_platform(ws, path):
    result = await run_tool(ws, "write_file", path=path, content="PWNED")
    assert result.error and result.error.code == "invalid_arguments" and untouched(ws)


@pytest.mark.parametrize("path", ["console.txt", "connect/x.md", "com10.txt", "nullable.py", "a.b.c", "docs/v1.2/x.md"])
async def test_ordinary_names_that_look_like_devices_are_still_writable(ws, path):
    result = await run_tool(ws, "write_file", path=path, content="ok")
    assert result.status is ToolStatus.succeeded, result.error


# ------------------------------------------------------------------ SEC-3: memory text stays out of events

async def test_events_never_carry_memory_text():
    from galliani.memory import InMemoryMemoryStore
    from galliani.memory_tool import remember_tool
    from galliani.tools import ToolRegistry

    marker = "PRIVATE-NOTE-4c1e"
    step = {"step_id": "m1", "kind": "tool", "purpose": "save a preference", "required_capability": "remember",
            "expected_output": "saved", "verification_criteria": [{"kind": "field_present", "field": "id"}],
            "tool": {"tool_name": "remember", "arguments": {"content": f"Use {marker}.", "type": "preference"}}}
    memory, sink = InMemoryMemoryStore(), InMemoryEventSink()
    sup = Supervisor(planner=StaticPlanner([{"steps": [step]}]), router=ModelRouter([worker("w1")]),
                     adapters=[ScriptedAdapter("scripted", {})], tools=ToolSystem(ToolRegistry([remember_tool(memory)])),
                     observability=Observability([sink]), memory=memory)
    result = await sup.start(StartTaskRequest(objective=Objective(goal="Remember it")))
    result = await sup.approve(result.task_id)
    assert result.status is TaskStatus.done
    called = [e for e in sink.for_task(result.task_id) if e.type.value == "tool_called"]
    assert called and called[0].metadata["argument_names"] == ["content", "type"]
    assert not any(marker in e.model_dump_json() for e in sink.for_task(result.task_id))


# ------------------------------------------------------------------ SEC-5: local API refuses cross-site writes

@pytest.fixture
def server_mode(tmp_path, monkeypatch):
    """Workspace-root server mode: no desktop app token, the agent API is enabled for one folder."""
    from fastapi.testclient import TestClient

    import app.api.routes as routes
    from galliani.web.agent_api import ROOT_ENV

    monkeypatch.delenv("ROUTER_APP_TOKEN", raising=False)
    monkeypatch.delenv("ROUTER_DESKTOP", raising=False)
    monkeypatch.setenv(ROOT_ENV, str(tmp_path))
    with TestClient(routes.app, base_url=LOCAL) as client:
        yield client


@pytest.mark.parametrize("method,path", [("post", "/api/agent/tasks/t1/approve"), ("post", "/api/agent/tasks/t1/deny"),
                                         ("post", "/api/agent/tasks/t1/cancel"), ("post", "/api/agent/memory"),
                                         ("delete", "/api/agent/memory/m1"), ("put", "/api/key")])
def test_state_changing_calls_without_the_custom_header_are_refused(server_mode, method, path):
    # A cross-site form or `fetch(..., {mode: "no-cors"})` can send these without a preflight.
    res = getattr(server_mode, method)(path, headers={"Content-Type": "text/plain"})
    assert res.status_code == 403 and "Cross-site" in res.json()["detail"]


def test_a_foreign_origin_is_refused_even_with_the_header(server_mode):
    res = server_mode.post("/api/agent/tasks/t1/approve",
                           headers={"X-Requested-With": "galliani", "Origin": "https://evil.example"})
    assert res.status_code == 403


def test_the_apps_own_page_passes_the_guard(server_mode):
    own = {"X-Requested-With": "galliani", "Origin": LOCAL}
    assert server_mode.post("/api/agent/tasks/t1/approve", headers=own).status_code == 404  # reached the API
    assert server_mode.post("/api/agent/tasks/t1/approve", headers={"X-Requested-With": "x"}).status_code == 404
    assert server_mode.get("/api/agent/config").status_code == 200  # reads need no header


def test_desktop_token_counts_as_the_custom_header(monkeypatch):
    from fastapi.testclient import TestClient

    import app.api.routes as routes

    monkeypatch.setenv("ROUTER_APP_TOKEN", "launch-token")
    monkeypatch.setenv("ROUTER_DESKTOP", "1")
    with TestClient(routes.app, base_url=LOCAL) as client:
        res = client.post("/api/agent/tasks/t1/approve", headers={"X-App-Token": "launch-token"})
        assert res.status_code == 404


# ------------------------------------------------------------------ SEC-6: only sandboxed tools are workspace edits

def test_a_hand_built_write_tool_cannot_opt_into_accept_edits(tmp_path):
    from galliani.errors import ContractError
    from galliani.permissions import PermissionLevel
    from galliani.tools import SideEffect, ToolDefinition, ToolRegistry
    from galliani.workspace import WriteIn, WriteOut

    rogue = ToolDefinition(name="write_anywhere", description="", input_schema=WriteIn, output_schema=WriteOut,
                           permission_level=PermissionLevel.write, side_effects=[SideEffect.write],
                           handler=lambda a: {}, resource_field="path", workspace_edit=True)
    with pytest.raises(ContractError, match="sandbox"):
        ToolRegistry([rogue])
    sandboxed = {t.name: t for t in Workspace(tmp_path).tools()}
    copy = sandboxed["write_file"].model_copy(update={"name": "write_file_2"})
    assert ToolRegistry([copy]).get("write_file_2").workspace_edit  # copies of a sandboxed tool stay eligible
    assert not rogue.model_copy().workspace_sandboxed


# ------------------------------------------------------------------ SEC-7: a link swapped in before the write

async def test_link_swapped_in_after_the_path_check_is_refused(ws, monkeypatch):
    original = Workspace.resolve

    def resolve_then_swap(self, rel):
        target = original(self, rel)
        if rel == "late/hook" and not (self.root / "late").exists():
            make_dir_link(self.root / "late", self.root / ".git")  # attacker swaps the folder for a link
        return target

    monkeypatch.setattr(Workspace, "resolve", resolve_then_swap)
    result = await run_tool(ws, "write_file", path="late/hook", content="PWNED")
    assert result.error and result.error.code == "rejected_input" and untouched(ws)
    assert not (ws.root / ".git" / "hook").exists()


# ================================================================== independent re-review of the fixes (2026-10-15)
# Probes beyond the original findings. Passing tests are regression guards; strict xfails are open gaps;
# `test_hard_link_to_env_is_read_accepted_residual_risk_sec9` documents an accepted residual risk (SEC-9).

def test_protected_names_are_case_folded_without_relying_on_the_filesystem():
    # Kills the "case-sensitive _blocked" mutant: on Windows the resolved-path check hides it whenever the
    # protected file already exists, so the name check itself must be pinned directly.
    for rel in (".GIT/config", "sub/.Git/hooks/x", ".ENV", "Server.KEY", "ID_RSA.pub", "Credentials.json",
                "NODE_MODULES/x.js", ".Venv/pyvenv.cfg"):
        assert Workspace._blocked(rel), rel
    for rel in (".env.example", ".ENV.EXAMPLE", "gitignore.txt", "keys.md", "src/env.py"):
        assert not Workspace._blocked(rel), rel


async def test_git_hook_cannot_be_planted_before_the_repository_exists(tmp_path):
    """`.GIT/hooks/pre-commit` in a folder with no `.git` yet: a later `git init` reuses that folder on a
    case-insensitive volume and keeps the hook. Only the case-folded name check stops this."""
    ws = Workspace(tmp_path)
    for path in (".GIT/hooks/pre-commit", ".Git/hooks/post-checkout", "app/.GIT/hooks/pre-commit"):
        result = await run_tool(ws, "write_file", path=path, content="#!/bin/sh\necho PWNED\n")
        assert result.error and result.error.code in REFUSED, path
    assert os.listdir(tmp_path) == []


@windows_only
@pytest.mark.parametrize("path", [".gıt/config", ".GİT/config", ".git​/config", ".ＧIT/config"])
async def test_unicode_look_alikes_of_git_do_not_reach_the_real_folder(ws, path):
    # NTFS does not fold dotless i, dotted I, zero-width or fullwidth letters onto ASCII: these create a
    # separate, harmless folder. The guard is that the real .git is never touched.
    await run_tool(ws, "write_file", path=path, content="PWNED")
    assert untouched(ws)


@windows_only
async def test_short_8dot3_names_of_protected_files_are_refused(ws):
    (ws.root / "credentials.json").write_text("CRED-SECRET\n", encoding="utf-8")
    shorts = [n for n in ("ENV~1", "SERVER~1.KEY", "CREDEN~1.JSO") if (ws.root / n).exists()]
    if not shorts:
        pytest.skip("8.3 short names are not generated on this volume")
    for name in shorts:
        read = await run_tool(ws, "read_file", path=name)
        write = await run_tool(ws, "write_file", path=name, content="PWNED")
        assert read.error and read.error.code in REFUSED, name
        assert "real-secret-value" not in read.model_dump_json() and "CRED-SECRET" not in read.model_dump_json()
        assert write.error and write.error.code in REFUSED, name
    assert untouched(ws)


async def test_a_chain_of_links_ending_in_git_is_refused(ws):
    make_dir_link(ws.root / "b", ws.root / ".git")
    make_dir_link(ws.root / "a", ws.root / "b")
    write = await run_tool(ws, "write_file", path="a/hooks/pre-commit", content="PWNED")
    listed = await run_tool(ws, "list_files")
    assert write.error and write.error.code == "rejected_input" and untouched(ws)
    assert not any(f.startswith(("a/", "b/")) for f in listed.data["files"])


@pytest.mark.parametrize("headers", [{"X-Requested-With": "x", "Origin": "null"},  # sandboxed iframe, file://
                                     {"X-Requested-With": "", "Origin": LOCAL},
                                     {"X-Requested-With": "x", "Origin": "chrome-extension://abc"},
                                     {"X-Requested-With": "x", "Origin": "http://127.0.0.1.evil.example"}])
def test_odd_origins_and_empty_headers_are_refused(server_mode, headers):
    assert server_mode.post("/api/agent/tasks/t1/approve", headers=headers).status_code == 403


@pytest.mark.parametrize("method,path", [("patch", "/api/agent/tasks/t1/approve"),
                                         ("post", "/api/agent/tasks/t1/approve/"),  # redirect_slashes
                                         ("post", "/api/chat")])
def test_guard_covers_other_methods_and_slash_variants(server_mode, method, path):
    assert getattr(server_mode, method)(path).status_code == 403


@pytest.mark.parametrize("method,path", [("post", "/api/agent/tasks"), ("get", "/api/agent/memory"), ("get", "/")])
def test_dns_rebinding_host_is_refused(server_mode, method, path):
    rebound = {"Host": "attacker.example:8000", "Origin": "http://attacker.example:8000", "X-Requested-With": "x"}
    res = getattr(server_mode, method)(path, headers=rebound, **({"json": {"objective": "x"}} if method == "post" else {}))
    assert res.status_code in (400, 403)


@pytest.mark.parametrize("host", ["127.0.0.1.attacker.example", "localhost.attacker.example", "evil.localhost",
                                  "0.0.0.0:8000", "127.0.0.2", "", "[::1].evil", "localhost:80.evil"])
def test_look_alike_and_missing_hosts_are_refused(server_mode, host):
    assert server_mode.get("/api/agent/config", headers={"Host": host}).status_code == 403


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.1:8000", "localhost:51234", "LOCALHOST", "[::1]:8000", "[::1]"])
def test_local_hosts_on_any_port_reach_the_app(server_mode, host):
    assert server_mode.get("/api/agent/config", headers={"Host": host}).status_code == 200
    assert server_mode.get("/", headers={"Host": host}).status_code == 200


def test_desktop_app_on_its_launch_port_still_works(monkeypatch):
    from fastapi.testclient import TestClient

    import app.api.routes as routes

    monkeypatch.setenv("ROUTER_APP_TOKEN", "launch-token")
    monkeypatch.setenv("ROUTER_DESKTOP", "1")
    with TestClient(routes.app, base_url="http://127.0.0.1:49731") as client:  # app/desktop.py: random free port
        assert client.get("/api/agent/config", headers={"X-App-Token": "launch-token"}).status_code == 200
        assert client.get("/").status_code == 200


@pytest.mark.parametrize("text", ["ghp_short", "github_pat_tooShort", "AIza is a name", "xoxo-hugs-and-kisses",
                                  "glpat-x", "sk_live_", "the desk_live_feed table",
                                  "Use tabs for indentation.", "https://github.com/org/repo/pull/123"])
def test_ordinary_text_is_not_a_secret(text):
    from galliani.redaction import contains_secret, redact_text

    assert not contains_secret(text) and redact_text(text) == text


async def test_hard_link_to_env_is_read_accepted_residual_risk_sec9(ws):
    """SEC-9: accepted residual risk (user decision 2026-10-15), see docs/security.md.

    `resolve()` cannot see hard links, so a hard link inside the workspace to a protected file is read like
    any other file. Creating one needs a local process with the user's rights, and git does not create hard
    links. This test documents the accepted behavior; if it starts failing because hard links are now
    refused, update SEC-9 in docs/security.md and turn this into a regression guard instead.
    """
    try:
        os.link(ws.root / ".env", ws.root / "notes-copy.txt")
    except OSError:
        pytest.skip("hard links not supported here")
    read = await run_tool(ws, "read_file", path="notes-copy.txt")
    assert read.status is ToolStatus.succeeded and leaked(read, ORIGINAL_ENV)  # accepted, not a guarantee
    assert (await run_tool(ws, "read_file", path=".env")).error  # the protected name itself is still refused


@pytest.mark.parametrize("text", ["task-runner-1234567890", "see the disk-cleanup-utility-v2 notes",
                                  "risk-assessment-template"])
def test_words_ending_in_sk_are_not_secrets(text):
    from galliani.redaction import contains_secret, redact_text

    assert not contains_secret(text) and redact_text(text) == text


@pytest.mark.parametrize("text", ["sk-or-v1-abcdefghijklmnop1234", "key=sk-abcdefghijklmnop1234",
                                  'token "sk-abcdefghijklmnop1234"', "Authorization: sk-proj-abcdefghijklmnop",
                                  "line\nsk-abcdefghijklmnop1234", "(sk-abcdefghijklmnop1234)",
                                  "https://x/?q=key%3Dsk-proj-abcdefghijklmnop1234", "a%20sk-abcdefghijklmnop1234",
                                  r"'line\nsk-abcdefghijklmnop1234'", r'{"k": "\tsk-abcdefghijklmnop1234"}'])
def test_sk_keys_after_a_boundary_are_still_secrets(text):
    # Guard for the word-boundary fix above: real keys at the start, after `=`, quotes, spaces or brackets.
    from galliani.redaction import REDACTED, contains_secret, redact_text

    assert contains_secret(text) and REDACTED in redact_text(text) and "abcdefghijklmnop" not in redact_text(text)


@pytest.mark.parametrize("text", [
    # json.dumps(..., ensure_ascii=True) of a key in smart quotes or after a non-ASCII letter.
    '{"note": "\\u201csk-abcdefghijklmnop1234\\u201d"}', '{"k": "\\u00e9sk-abcdefghijklmnop1234"}',
    "b'\\x00sk-abcdefghijklmnop1234'",  # repr() of bytes in an error message
])
def test_sk_keys_after_unicode_or_hex_escapes_are_secrets(text):
    from galliani.redaction import contains_secret, redact_text

    assert contains_secret(text) and "abcdefghijklmnop" not in redact_text(text)


@pytest.mark.parametrize("token", ["sk_test_" + "Ab12" * 6, "rk_test_" + "Ab12" * 6])
def test_stripe_test_mode_keys_are_secrets(token):
    from galliani.redaction import contains_secret

    assert contains_secret(f"my token is {token}")


KEY = "sk-abcdefghijklmnop1234"


@pytest.mark.parametrize("text", [
    # 012 AC "Redaction Trade-offs": every accepted left context, one case each.
    KEY, f"key {KEY}", f"key=%3D{KEY}", f"q=key%253D{KEY}", f"a%2f{KEY}", f"key={KEY}",
    *(f"text\\{c}{KEY}" for c in "nrtfvb0"), f"b'\\x3d{KEY}'", f"b'\\xFF{KEY}'", f"\\u00E9{KEY}",
    f"sk_live_{'Ab12' * 6}", f"rk_live_{'Ab12' * 6}", f"sk_test_{'Ab12' * 6}", f"rk_test_{'Ab12' * 6}",
])
def test_every_accepted_left_context_masks_the_key(text):
    from galliani.redaction import REDACTED, contains_secret, redact_text

    assert contains_secret(text) and REDACTED in redact_text(text) and "Ab12Ab12" not in redact_text(text)
    assert "abcdefghijklmnop" not in redact_text(text)


@pytest.mark.parametrize("text", [
    # The accepted trade-off (Decision 0032): a key glued to a letter or digit with no escape before it is
    # left alone, like ordinary words ending in "sk". Includes look-alikes of the escapes that are not escapes.
    f"abc{KEY}", f"9{KEY}", "task-runner-1234567890", "disk-1234567890abcdef",
    f"%2g{KEY}", f"\\q{KEY}", f"\\x3{KEY}", f"\\u00e{KEY}",
])
def test_glued_keys_and_ordinary_words_stay_unmasked(text):
    from galliani.redaction import contains_secret, redact_text

    assert not contains_secret(text) and redact_text(text) == text


@pytest.mark.xfail(strict=True, reason="qa-security 2026-10-15: a key right after an ANSI colour code ends in "
                   "'m' (a letter), so the left boundary (Decision 0032) lets it through; the pre-0032 pattern "
                   "masked it. Low: Galliani has no shell tool, so such text arrives only from read files or "
                   "pages. Needs a spec 012 Security decision (owner tech-lead, then core-engineer).")
@pytest.mark.parametrize("text", [f"\x1b[32m{KEY}\x1b[0m", f"\\x1b[0m{KEY}"])
def test_sk_key_after_an_ansi_colour_code_is_masked(text):
    from galliani.redaction import contains_secret

    assert contains_secret(text)


@pytest.mark.xfail(strict=True, reason="qa-security 2026-10-15: the Stripe pattern has no left boundary, unlike "
                   "`sk-`, so identifiers ending in 'sk'/'rk' followed by `_test_`/`_live_` are masked and memory "
                   "refuses them. Low over-redaction. Owner core-engineer (spec 012 Security trade-off).")
@pytest.mark.parametrize("text", ["network_test_connectivitycheck", "mask_live_previewcomponents"])
def test_identifiers_ending_in_sk_or_rk_before_test_or_live_are_not_secrets(text):
    from galliani.redaction import contains_secret

    assert not contains_secret(text)


def test_the_apps_page_sends_the_guard_header_and_treats_403_as_an_error():
    # 012 R19: the app's own page sends X-Requested-With on every call and never shows a 403 as success.
    # Static guard: dropping the header would break every state-changing call while all API tests still pass.
    html = (Path(__file__).resolve().parents[2] / "app" / "web" / "index.html").read_text(encoding="utf-8")
    assert html.count("fetch(") == 1, "every request must go through api(), which adds the guard header"
    assert '"X-Requested-With": "galliani"' in html
    assert "if (res.status === 403) {" in html and "Galliani refused this request and did nothing." in html


async def test_swapped_link_gets_no_folders_created_through_it(ws, monkeypatch):
    original = Workspace.resolve

    def resolve_then_swap(self, rel):
        target = original(self, rel)
        if rel == "late/hooks/x" and not (self.root / "late").exists():
            make_dir_link(self.root / "late", self.root / ".git")
        return target

    monkeypatch.setattr(Workspace, "resolve", resolve_then_swap)
    result = await run_tool(ws, "write_file", path="late/hooks/x", content="PWNED")
    assert result.error and result.error.code == "rejected_input"
    assert not (ws.root / ".git" / "hooks").exists()


@pytest.mark.parametrize("token", ["ghp_" + "a1B2" * 9, "github_pat_11ABCDEFG0" + "x" * 40,
                                   "AIza" + "Sy" + "A1b2C3d4" * 4 + "x", "xoxb-1234567890-0987654321-" + "Ab" * 12,
                                   "glpat-" + "Ab1_" * 5, "sk_live_" + "Ab12" * 6, "rk_live_" + "Ab12" * 6])
def test_common_token_formats_are_secrets(token):
    from galliani.redaction import contains_secret, redact_text

    assert contains_secret(f"my token is {token}") and token not in redact_text(f"token {token}")


def test_memory_refuses_a_github_token_but_saves_ordinary_text():
    # Spec 010: contains_secret keeps secrets out of durable memory; ordinary preferences still save.
    from galliani.memory import MemoryDecisionStatus, MemoryPolicy, MemoryWriteRequest

    policy = MemoryPolicy()
    token = MemoryWriteRequest(content="my GitHub token is ghp_" + "a1B2" * 9, provenance="test")
    plain = MemoryWriteRequest(content="Use tabs; review PRs on github.com before merging.", provenance="test")
    assert policy.evaluate(token).status is MemoryDecisionStatus.denied
    assert policy.evaluate(plain).status is MemoryDecisionStatus.allowed
