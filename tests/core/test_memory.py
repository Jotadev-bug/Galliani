"""Spec 010 - Memory: schema contract, write policy, scoped retrieval, durability, supervisor integration."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from galliani.contracts import Sensitivity, utcnow
from galliani.errors import ContractError
from galliani.memory import (
    InMemoryMemoryStore,
    JsonMemoryStore,
    MemoryDecisionStatus,
    MemoryPolicy,
    MemoryQuery,
    MemoryRecord,
    MemoryUnavailable,
    MemoryWriteRequest,
    project_scope,
)
from galliani.memory_tool import remember_tool
from galliani.planner import StaticPlanner
from galliani.state import TaskStatus
from galliani.testing import fixture_tool_registry
from galliani.tools import ToolSystem
from tests.core.helpers import Harness, summarize_step
from tests.core.test_supervisor import GOOD, start

S = TaskStatus
SECRET = "sk-" + "x" * 30


def req(content: str, **kw) -> MemoryWriteRequest:
    return MemoryWriteRequest(content=content, **{"provenance": "test", **kw})


# ------------------------------------------------------------------ schema contract
def test_memory_record_contract_round_trip_and_validation():
    record = MemoryRecord(content="Prefer Spanish", type="preference", provenance="user via UI")
    assert MemoryRecord.model_validate_json(record.model_dump_json()) == record
    assert record.id.startswith("mem_") and record.scope == "user"
    with pytest.raises(ValueError):
        MemoryWriteRequest(content="x", provenance="p", scope="team")
    with pytest.raises(ValueError):
        MemoryWriteRequest(content="   ", provenance="p")
    with pytest.raises(ValueError):
        MemoryRecord(content="x", type="opinion", provenance="p")


def test_sensitive_records_display_redacted():
    record = MemoryRecord(content="My doctor is Dr. X", type="fact", provenance="p", sensitivity=Sensitivity.sensitive)
    assert record.display_content() == "[redacted]"


# ------------------------------------------------------------------ write policy (010 R2)
def test_write_policy():
    policy = MemoryPolicy()
    assert policy.evaluate(req("Use metric units")).status is MemoryDecisionStatus.allowed
    assert policy.evaluate(req("Use metric units", source="agent")).status is MemoryDecisionStatus.needs_user
    assert policy.evaluate(req(f"my key is {SECRET}")).status is MemoryDecisionStatus.denied


def test_stores_never_persist_secrets(tmp_path):
    for store in (InMemoryMemoryStore(), JsonMemoryStore(tmp_path / "m.json")):
        with pytest.raises(ContractError):
            store.write(req(f"token {SECRET}"))
        assert store.list() == []
    assert not (tmp_path / "m.json").exists() or SECRET not in (tmp_path / "m.json").read_text()


# ------------------------------------------------------------------ scoped retrieval (010 R4, AC Scoped Retrieval)
@pytest.fixture
def store(tmp_path):
    s = InMemoryMemoryStore()
    s.write(req("Always write summaries in Spanish", type="preference"))
    s.write(req("The finance team owns the budget notes", type="fact"))
    s.write(req("Reports go in reports/", type="instruction", scope=project_scope(tmp_path / "a")))
    s.write(req("Use British spelling", type="preference", scope=project_scope(tmp_path / "b")))
    s.write(req("Dentist appointment is on Friday", type="note"))
    return s


def test_retrieval_returns_only_scoped_relevant_records(store, tmp_path):
    scopes = ["user", project_scope(tmp_path / "a")]
    result = store.query(MemoryQuery(scope=scopes, keywords=["summarize", "budget", "notes"]))
    contents = {r.content for r in result.records}
    assert contents == {"Always write summaries in Spanish", "The finance team owns the budget notes",
                        "Reports go in reports/"}
    assert "Use British spelling" not in contents  # another project's scope
    assert "Dentist appointment is on Friday" not in contents  # in scope but not relevant


def test_retrieval_limits_orders_and_counts_omitted(store):
    result = store.query(MemoryQuery(scope=["user"], keywords=["budget", "dentist", "friday"], max_records=2))
    assert len(result.records) == 2 and result.omitted_count == 1
    assert result.records[0].type == "preference"  # standing preferences first
    assert "omitted" in result.retrieval_summary


def test_expired_records_are_not_returned():
    s = InMemoryMemoryStore([MemoryRecord(content="Old rule", type="preference", provenance="p", ttl=60,
                                          updated_at=utcnow() - timedelta(hours=1))])
    assert s.query(MemoryQuery(keywords=[])).records == []


def test_conflicting_records_are_returned_side_by_side_not_merged():
    s = InMemoryMemoryStore()
    s.write(req("Reports are due on Monday", type="fact", provenance="user, March"))
    s.write(req("Reports are due on Friday", type="fact", provenance="user, April"))
    s.write(req("Reports are due on Friday", type="fact", provenance="again"))  # identical: refreshed, not duplicated
    records = s.query(MemoryQuery(keywords=["reports"])).records
    assert sorted(r.content for r in records) == ["Reports are due on Friday", "Reports are due on Monday"]
    assert {r.provenance for r in records} == {"user, March", "user, April"}


# ------------------------------------------------------------------ durability
def test_json_store_persists_and_reports_unreadable_files(tmp_path):
    path = tmp_path / "data" / "memory.json"
    first = JsonMemoryStore(path)
    record = first.write(req("Prefer tables over bullet lists", type="preference"))
    again = JsonMemoryStore(path)
    assert [r.id for r in again.list()] == [record.id]
    assert again.delete(record.id) and JsonMemoryStore(path).list() == []
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(MemoryUnavailable):
        JsonMemoryStore(path)


# ------------------------------------------------------------------ supervisor integration
class SpyPlanner(StaticPlanner):
    def __init__(self, script):
        super().__init__(script)
        self.requests = []

    async def plan(self, request, *, task_id):
        self.requests.append(request)
        return await super().plan(request, task_id=task_id)


async def test_memory_is_retrieved_before_planning_as_context_and_task_state_keeps_only_ids():
    store = InMemoryMemoryStore()
    pref = store.write(req("Always mention the budget variance", type="preference"))
    store.write(req("Private health note", type="preference", sensitivity=Sensitivity.sensitive))
    h = Harness([{"steps": [summarize_step(refs=())]}], script={"w1": [GOOD]})
    spy = SpyPlanner([{"steps": [summarize_step(refs=())]}])
    h.supervisor.planner = spy
    h.supervisor.replanner.planner = spy
    h.supervisor.memory = store
    result = await h.supervisor.start(start())
    assert result.status is S.done
    sent = spy.requests[0].memory
    assert sent == [{"id": pref.id, "type": "preference", "content": "Always mention the budget variance"}]
    state = h.supervisor.store.get(result.task_id)
    assert "Always mention" not in state.model_dump_json()  # Task State records the ids, not the content
    assert any(o.kind == "memory" and pref.id in o.summary for o in state.observations)
    assert any(e.type.value == "memory_retrieved" for e in h.events(result.task_id))


async def test_unavailable_memory_does_not_block_the_task():
    class Broken:
        def query(self, query):
            raise MemoryUnavailable("disk gone")

    h = Harness([{"steps": [summarize_step(refs=())]}], script={"w1": [GOOD]})
    h.supervisor.memory = Broken()
    result = await h.supervisor.start(start())
    assert result.status is S.done
    assert any(e.type.value == "diagnostic" and "memory unavailable" in e.public_summary
               for e in h.events(result.task_id))


# ------------------------------------------------------------------ remember tool (AC Explicit Write)
def remember_step(content: str, scope: str = "user") -> dict:
    return {"step_id": "m", "kind": "tool", "purpose": "save the preference", "required_capability": "remember",
            "expected_output": "saved", "tool": {"tool_name": "remember",
                                                 "arguments": {"content": content, "type": "preference", "scope": scope}},
            "verification_criteria": [{"kind": "field_present", "field": "id"}]}


def harness_with_memory(plan, store, project=None):
    h = Harness([plan])
    registry = fixture_tool_registry(h.world)
    registry.register(remember_tool(store, project_scope=project))
    h.supervisor.tools = ToolSystem(registry)
    h.supervisor.engine.tools = h.supervisor.tools
    return h


async def test_user_requested_memory_write_needs_approval_and_records_provenance(tmp_path):
    store = InMemoryMemoryStore()
    h = harness_with_memory({"steps": [remember_step("Write summaries in Spanish")]}, store)
    paused = await h.supervisor.start(start("Remember that I want summaries in Spanish"))
    assert paused.status is S.waiting_for_user and store.list() == []
    assert '"Write summaries in Spanish"' in paused.approval_prompt.action_summary  # exact text before consent
    done = await h.supervisor.approve(paused.task_id)
    assert done.status is S.done
    [record] = store.list()
    assert record.content == "Write summaries in Spanish" and record.scope == "user"
    assert paused.task_id in record.provenance and "approved by the user" in record.provenance


async def test_denied_memory_write_is_an_observation_not_memory():
    store = InMemoryMemoryStore()
    h = harness_with_memory({"steps": [remember_step("Something")]}, store)
    paused = await h.supervisor.start(start("Remember something"))
    result = await h.supervisor.deny(paused.task_id)
    assert result.status is S.blocked and store.list() == []
    assert any(o.kind == "permission" and o.outcome == "denied" for o in result.observations)


async def test_project_scoped_memory_and_secret_refusal(tmp_path):
    store = InMemoryMemoryStore()
    scope = project_scope(tmp_path)
    h = harness_with_memory({"steps": [remember_step("Reports go in reports/", scope="project")]}, store, project=scope)
    await h.supervisor.approve((await h.supervisor.start(start("Remember where reports go"))).task_id)
    assert [r.scope for r in store.list()] == [scope]

    # A plan carrying a secret is rejected before any tool runs ...
    h = harness_with_memory({"steps": [remember_step(f"my key {SECRET}")]}, store)
    result = await h.supervisor.start(start("Remember my key"))
    assert result.status is S.blocked and "secret" in result.summary and len(store.list()) == 1
    # ... and the tool itself refuses secret-like text even after approval.
    from galliani.permissions import ApprovalRecord
    from galliani.tools import ToolCall, ToolRegistry

    system = ToolSystem(ToolRegistry([remember_tool(store)]))
    call = ToolCall(tool_name="remember", call_id="c", requested_by_step="m",
                    arguments={"content": f"my key {SECRET}", "scope": "user"})
    tool_result = await system.execute(call, task_id="t", approvals=[ApprovalRecord(user_id="u", action="remember", scope="user")])
    assert tool_result.error.code == "rejected_input" and len(store.list()) == 1
    assert SECRET not in json.dumps([r.model_dump(mode="json") for r in store.list()])
