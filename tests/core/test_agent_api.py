"""Spec 012 - UI integration tests: the agent API through every lifecycle state, no network."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from galliani.observability import Observability
from galliani.planner import StaticPlanner
from galliani.router import ModelRouter
from galliani.supervisor import Supervisor
from galliani.testing import ScriptedAdapter
from galliani.tools import ToolSystem
from galliani.web.agent_api import ROOT_ENV, AgentService, agent_router
from galliani.memory import InMemoryMemoryStore, project_scope
from galliani.memory_tool import remember_tool
from galliani.workspace import Workspace
from tests.core.helpers import worker

READ = {"step_id": "s1", "kind": "tool", "purpose": "read the note", "required_capability": "read_file",
        "expected_output": "note text", "tool": {"tool_name": "read_file", "arguments": {"path": "notes/q3.md"}},
        "verification_criteria": [{"kind": "field_present", "field": "text"}]}
SUMMARIZE = {"step_id": "s2", "kind": "model", "purpose": "summarize", "required_capability": "text",
             "input_refs": ["s1"], "expected_output": "summary", "instruction": "Summarize.",
             "verification_criteria": [{"kind": "contains", "value": "under plan"}]}
WRITE = {"step_id": "s3", "kind": "tool", "purpose": "save the summary", "required_capability": "write_file",
         "expected_output": "file", "tool": {"tool_name": "write_file",
                                             "arguments": {"path": "summary.md", "content": {"$ref": "s2"}}},
         "verification_criteria": [{"kind": "field_equals", "field": "path", "value": "summary.md"}]}
PLAN = {"steps": [READ, SUMMARIZE, WRITE]}


class FakeRuntime:
    def __init__(self, supervisor):
        self.supervisor = supervisor
        self.available_workers = ["w1"]
        self.closed = False

    async def aclose(self):
        self.closed = True


def factory(script: list[dict]):
    def build(workspace, keys, budget, sinks, memory):
        adapter = ScriptedAdapter("scripted", {"w1": [{"output": "Q3 spend is under plan."}] * 3})
        tools = Workspace(workspace).registry()
        if memory is not None:
            tools.register(remember_tool(memory, project_scope=project_scope(workspace)))
        return FakeRuntime(Supervisor(planner=StaticPlanner(script), router=ModelRouter([worker("w1")]),
                                      adapters=[adapter], tools=ToolSystem(tools), observability=Observability(sinks),
                                      memory=memory))
    return build


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "q3.md").write_text("Q3 spend is 4% under plan.", encoding="utf-8")
    return tmp_path


def client_for(script, monkeypatch, root, memory=None) -> TestClient:
    monkeypatch.setenv(ROOT_ENV, str(root))
    app = FastAPI()
    service = AgentService(factory(script), memory=memory if memory is not None else InMemoryMemoryStore())
    app.include_router(agent_router(keys_for=lambda request: {}, service=service))
    return TestClient(app)


def wait_for(client, task_id, *statuses, seq=0):
    """Poll like the UI does; the returned page carries every event seen since `seq`."""
    seen = []
    for _ in range(100):
        page = client.get(f"/api/agent/tasks/{task_id}/events", params={"after": seq, "wait": 0.5}).json()
        seen += page["events"]
        seq = page["seq"]
        if page["view"]["status"] in statuses:
            return {**page, "events": seen}
    raise AssertionError(f"task never reached {statuses}")


def start(client, ws, objective="Summarize notes/q3.md into summary.md"):
    res = client.post("/api/agent/tasks", json={"objective": objective, "workspace": str(ws)})
    assert res.status_code == 200, res.text
    return res.json()


# AC: Start Task -> task view opens with created or planning status
def test_start_returns_view_in_created_or_planning(ws, monkeypatch):
    with client_for([PLAN], monkeypatch, ws) as client:
        view = start(client, ws)
        assert view["status"] == "created" and view["objective_summary"].startswith("Summarize")
        assert view["memory"]["records"] == [] and "long-term memory" in view["memory"]["note"]


# AC: Approval -> clear prompt, execution paused; then Done -> result, verification, artifacts
def test_approval_pause_then_done_with_result_verification_and_artifacts(ws, monkeypatch):
    with client_for([PLAN], monkeypatch, ws) as client:
        task_id = start(client, ws)["task_id"]
        page = wait_for(client, task_id, "waiting_for_user")
        view = page["view"]
        assert view["approval_prompt"]["scope"] == "summary.md"
        assert "write_file" in view["approval_prompt"]["action_summary"]
        assert view["next_options"] == ["approve", "deny", "cancel"]
        assert [s["state"] for s in view["plan"]["steps"]] == ["verified", "verified", "waiting"]
        assert not (ws / "summary.md").exists()
        types = [e["type"] for e in page["events"]]
        assert "plan_created" in types and "permission_decided" in types

        assert client.post(f"/api/agent/tasks/{task_id}/approve").status_code == 200
        done = wait_for(client, task_id, "done", seq=page["seq"])["view"]
        assert done["result"]["verification"]["status"] == "pass"
        assert done["result"]["artifacts"] == [{"kind": "file", "uri": "summary.md"}]
        assert done["result"]["output_kind"] == "json" and done["usage"]["calls"] == 1
        assert (ws / "summary.md").read_text(encoding="utf-8") == "Q3 spend is under plan."
        assert "simulated private reasoning" not in str(done) and '"reasoning"' not in str(done)


def test_denial_explains_block_and_offers_next_options(ws, monkeypatch):
    with client_for([PLAN], monkeypatch, ws) as client:
        task_id = start(client, ws)["task_id"]
        wait_for(client, task_id, "waiting_for_user")
        view = client.post(f"/api/agent/tasks/{task_id}/deny").json()
        view = wait_for(client, task_id, "blocked")["view"]
        assert "denied" in view["result"]["summary"] and view["next_options"] == ["retry", "edit_and_retry", "new_task"]
        assert view["terminal"] and not (ws / "summary.md").exists()


def test_question_is_answered_through_the_api(ws, monkeypatch):
    with client_for([{"clarify": "Which note?"}, PLAN], monkeypatch, ws) as client:
        task_id = start(client, ws)["task_id"]
        view = wait_for(client, task_id, "waiting_for_user")["view"]
        assert view["clarification"] == "Which note?" and view["next_options"] == ["answer", "cancel"]
        res = client.post(f"/api/agent/tasks/{task_id}/clarify", json={"answer": "notes/q3.md"})
        assert res.status_code == 200
        assert wait_for(client, task_id, "waiting_for_user")["view"]["approval_prompt"] is not None


def test_cancel_and_invalid_actions(ws, monkeypatch):
    with client_for([PLAN], monkeypatch, ws) as client:
        task_id = start(client, ws)["task_id"]
        wait_for(client, task_id, "waiting_for_user")
        assert client.post(f"/api/agent/tasks/{task_id}/clarify", json={"answer": "x"}).status_code == 409
        assert client.post(f"/api/agent/tasks/{task_id}/cancel").json()["status"] == "canceled"
        assert client.post(f"/api/agent/tasks/{task_id}/approve").status_code == 409
        assert client.get("/api/agent/tasks/nope").status_code == 404
        listed = client.get("/api/agent/tasks").json()
        assert listed[0]["task_id"] == task_id and listed[0]["status"] == "canceled"


def test_long_poll_returns_after_timeout_without_new_events(ws, monkeypatch):
    with client_for([PLAN], monkeypatch, ws) as client:
        task_id = start(client, ws)["task_id"]
        page = wait_for(client, task_id, "waiting_for_user")
        began = time.monotonic()
        idle = client.get(f"/api/agent/tasks/{task_id}/events", params={"after": page["seq"], "wait": 0.3}).json()
        assert idle["events"] == [] and idle["seq"] == page["seq"] and time.monotonic() - began >= 0.25


def test_workspace_rules(ws, tmp_path_factory, monkeypatch):
    outside = tmp_path_factory.mktemp("outside")
    with client_for([PLAN], monkeypatch, ws) as client:
        res = client.post("/api/agent/tasks", json={"objective": "x", "workspace": str(outside)})
        assert res.status_code == 403 and "must be inside" in res.json()["detail"]
        res = client.post("/api/agent/tasks", json={"objective": "x", "workspace": str(ws / "missing")})
        assert res.status_code == 400
        assert client.post("/api/agent/tasks", json={"objective": "x", "workspace": "notes"}).status_code == 200


def test_agent_is_disabled_outside_desktop_without_a_workspace_root(ws, monkeypatch):
    monkeypatch.delenv(ROOT_ENV, raising=False)
    monkeypatch.delenv("ROUTER_DESKTOP", raising=False)
    app = FastAPI()
    app.include_router(agent_router(keys_for=lambda request: {}, service=AgentService(factory([PLAN]), memory=None)))
    with TestClient(app) as client:
        assert client.get("/api/agent/config").json()["enabled"] is False
        assert client.get("/api/agent/memory").status_code == 403
        res = client.post("/api/agent/tasks", json={"objective": "x", "workspace": str(ws)})
        assert res.status_code == 403


def test_desktop_app_token_protects_the_agent_api(monkeypatch):
    import app.api.routes as routes

    monkeypatch.setenv("ROUTER_APP_TOKEN", "secret-token")
    monkeypatch.setenv("ROUTER_DESKTOP", "1")
    with TestClient(routes.app) as client:
        assert client.get("/api/agent/config").status_code == 403
        ok = client.get("/api/agent/config", headers={"X-App-Token": "secret-token"})
        assert ok.status_code == 200 and ok.json()["enabled"] is True


def test_approval_prompt_markup_is_accessible():
    """012 Tests: accessibility checks for approval prompts (static guard; verified live in the browser too)."""
    from pathlib import Path

    html = (Path(__file__).resolve().parents[2] / "app" / "web" / "index.html").read_text(encoding="utf-8")
    assert 'role="alertdialog" aria-labelledby="apTitle" aria-describedby="apDesc"' in html
    assert '<h3 id="apTitle" tabindex="-1">' in html and '$("apTitle")?.focus()' in html  # focus moves to the prompt
    assert 'aria-label="Approve ${esc(action)} for ${esc(p.scope)}"' in html  # scope named before consent
    assert '<dt>Scope</dt>' in html and 'aria-live="polite"' in html


# Spec 010 through the API: explicit user writes, listing with redaction, deletion, and task memory views
def test_memory_api_add_list_redact_delete(ws, monkeypatch):
    store = InMemoryMemoryStore()
    with client_for([PLAN], monkeypatch, ws, memory=store) as client:
        added = client.post("/api/agent/memory", json={"content": "Write summaries in Spanish"}).json()
        assert added["scope"] == "user" and added["provenance"] == "added by you in the app"
        folder = client.post("/api/agent/memory", json={"content": "Reports go in reports/", "type": "instruction",
                                                         "scope": "project", "workspace": str(ws)}).json()
        assert folder["scope"] == project_scope(ws)
        client.post("/api/agent/memory", json={"content": "Blood type O+", "type": "fact", "sensitivity": "sensitive"})
        listed = client.get("/api/agent/memory").json()
        assert {m["content"] for m in listed} == {"Write summaries in Spanish", "Reports go in reports/", "[redacted]"}
        secret = client.post("/api/agent/memory", json={"content": "key sk-" + "q" * 30})
        assert secret.status_code == 422 and "secret" in secret.json()["detail"]
        assert client.delete(f"/api/agent/memory/{added['id']}").status_code == 200
        assert client.delete(f"/api/agent/memory/{added['id']}").status_code == 404
        assert len(store.list()) == 2


def test_task_view_shows_memory_used_and_saved(ws, monkeypatch):
    store = InMemoryMemoryStore()
    remember = {"step_id": "m", "kind": "tool", "purpose": "save it", "required_capability": "remember",
                "expected_output": "saved", "tool": {"tool_name": "remember", "arguments": {"content": "Prefer short bullets"}},
                "verification_criteria": [{"kind": "field_present", "field": "id"}]}
    with client_for([PLAN], monkeypatch, ws, memory=store) as client:
        client.post("/api/agent/memory", json={"content": "Summaries should mention the plan variance"})
        task_id = start(client, ws)["task_id"]
        view = wait_for(client, task_id, "waiting_for_user")["view"]
        assert [m["summary"] for m in view["memory"]["used"]] == ["Summaries should mention the plan variance"]
        assert view["memory"]["records"] == []

    with client_for([{"steps": [remember]}], monkeypatch, ws, memory=store) as client:
        task2 = start(client, ws, objective="Remember that I prefer short bullets")["task_id"]
        prompt = wait_for(client, task2, "waiting_for_user")["view"]["approval_prompt"]
        assert '"Prefer short bullets"' in prompt["action_summary"]
        client.post(f"/api/agent/tasks/{task2}/approve")
        done = wait_for(client, task2, "done")["view"]
        assert [m["summary"] for m in done["memory"]["records"]] == ["Prefer short bullets"]
        assert "with your approval" in done["memory"]["note"]
        assert {m["content"] for m in client.get("/api/agent/memory").json()} == {
            "Summaries should mention the plan variance", "Prefer short bullets"}
