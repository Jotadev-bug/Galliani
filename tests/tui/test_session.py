"""Spec 017 controller (task A): `Session` against scripted runtimes. No terminal, no Textual."""

from __future__ import annotations

import asyncio
import json

import pytest

from app.models.registry import ModelRegistry
from app.models.schemas import ProviderConfig
from app.providers.factory import ProviderPool
from app.providers.mock import MockProvider
from galliani.cli import build_runtime
from galliani.memory import InMemoryMemoryStore, MemoryRecord, project_scope
from galliani.permissions import EditMode
from galliani.state import TaskStatus
from galliani.tui import session as session_mod
from galliani.tui.session import (
    BUSY_NOTICE,
    MAX_BODY_CHARS,
    NO_KEYS,
    EntryKind,
    Phase,
    Session,
    SessionConfig,
    UiAction,
    sanitize,
)
from tests.conftest import spec
from tests.tui.conftest import (
    BASIC_PLAN,
    SUMMARY,
    ScriptedRuntimes,
    all_text,
    kinds,
    make_session,
    model_step,
    read_step,
    write_step,
)


def task_state(factory: ScriptedRuntimes, session: Session):
    return factory.runtime.supervisor.store.get(session._task_id)


def spy(obj, name: str, calls: list):
    original = getattr(obj, name)

    def wrapper(*args, **kw):
        calls.append((args, kw))
        return original(*args, **kw)
    setattr(obj, name, wrapper)


# ---------------------------------------------------------------------- Send Objective


async def test_send_objective_shows_entries_in_order_and_returns_to_idle(workspace):
    session, factory = make_session(workspace, plans=[{"steps": [read_step(), model_step()]}])
    changes = []
    session.subscribe(lambda: changes.append(session.state.phase))
    assert await session.submit("Summarize notes.md") is None
    order = kinds(session)
    assert order[0] == "notice" and order[1] == "user"
    for earlier, later in [("user", "plan"), ("plan", "tool"), ("tool", "verification"),
                           ("verification", "result"), ("result", "usage")]:
        assert order.index(earlier) < order.index(later)
    assert order[-2:] == ["result", "usage"]
    plan = next(e for e in session.entries() if e.kind is EntryKind.plan)
    assert plan.detail == ("s1 (tool: read_file) read the notes", "s2 (model: text) summarize")
    result = next(e for e in session.entries() if e.kind is EntryKind.result)
    assert result.text.startswith("Status: done") and result.body == SUMMARY and result.markdown
    state = session.state
    assert state.phase is Phase.idle and Phase.running in changes
    assert state.plan is not None and [s.state for s in state.plan.steps] == ["verified", "verified"]
    assert state.status.route == "w1" and state.status.status_label is None
    seqs = [e.seq for e in session.entries()]
    assert seqs == sorted(set(seqs)) and seqs[0] == 1


async def test_blank_objective_starts_nothing(workspace):
    session, factory = make_session(workspace)
    before = len(session.entries())
    await session.submit("   ")
    assert len(session.entries()) == before and session.state.phase is Phase.idle
    assert factory.planner.calls == 0


async def test_double_slash_is_sent_as_an_objective(workspace):
    session, factory = make_session(workspace, plans=[{"steps": [read_step()]}])
    calls = []
    spy(factory.runtime.supervisor, "start", calls)
    await session.submit("//etc/hosts is a path, not a command")
    assert calls[0][0][0].objective.goal == "/etc/hosts is a path, not a command"


# ---------------------------------------------------------------------- Approval y / n / a, Esc denies


async def test_approve_y_runs_the_write(workspace):
    session, factory = make_session(workspace)
    await session.submit("Summarize into summary.md")
    pending = session.state.pending_approval
    assert session.state.phase is Phase.awaiting_approval and pending.can_accept_edits and pending.scope == "summary.md"
    assert session.state.status.status_label == "Needs your input"
    await session.approve()
    assert (workspace / "summary.md").read_text(encoding="utf-8") == SUMMARY
    assert session.state.phase is Phase.idle and "You approved." in all_text(session)
    assert task_state(factory, session).status is TaskStatus.done


async def test_deny_n_blocks_and_leaves_workspace_untouched(workspace):
    session, factory = make_session(workspace)
    await session.submit("Summarize into summary.md")
    await session.deny()  # the UI's n and Esc both call deny (Esc Denies)
    assert not (workspace / "summary.md").exists()
    assert task_state(factory, session).status is TaskStatus.blocked
    assert session.state.phase is Phase.idle and "Status: blocked" in all_text(session)


async def test_esc_on_approval_calls_supervisor_deny(workspace):
    session, factory = make_session(workspace)
    await session.submit("Summarize into summary.md")
    calls = []
    original = factory.runtime.supervisor.deny

    async def deny(*args, **kw):
        calls.append(args)
        return await original(*args, **kw)
    factory.runtime.supervisor.deny = deny
    await session.deny()
    assert len(calls) == 1 and task_state(factory, session).status is TaskStatus.blocked


async def test_approve_a_switches_only_the_task_to_accept_edits(workspace):
    plan = {"steps": [read_step(), model_step(), write_step(), write_step("s4", "copy.md", "s2")]}
    session, factory = make_session(workspace, plans=[plan])
    await session.submit("Summarize into two files")
    await session.approve(accept_edits=True)
    assert (workspace / "summary.md").exists() and (workspace / "copy.md").exists()  # second write not asked
    assert task_state(factory, session).edit_mode is EditMode.accept_edits
    assert session.config.edit_mode is EditMode.ask and session.state.status.edit_mode is EditMode.ask
    text = all_text(session)
    assert "edits auto-approved: 1" in text and "turned on accept-edits mode" in text
    assert [e.kind for e in session.entries()].count(EntryKind.approval) == 2  # one prompt, one answer


async def test_task_edit_mode_is_shown_while_active(workspace):
    plan = {"steps": [read_step(), model_step(), write_step(), write_step("s4", "copy.md", "s2")]}
    factory = ScriptedRuntimes([plan])
    session, _ = make_session(workspace, factory=factory)
    modes = []
    session.subscribe(lambda: modes.append(session.state.status.edit_mode) if session.state.phase is Phase.running else None)
    await session.submit("Summarize into two files")
    await session.approve(accept_edits=True)
    assert EditMode.accept_edits in modes


async def test_spending_approval_does_not_offer_accept_edits(workspace):
    plan = {"steps": [model_step("s1", refs=(), must_contain="plan"), model_step("s2", refs=(), must_contain="plan")]}
    factory = ScriptedRuntimes([plan], outputs=[{"output": SUMMARY, "cost_micro_usd": 1_000}])
    session, _ = make_session(workspace, factory=factory, budget_usd=0.0006)
    await session.submit("Summarize twice")
    pending = session.state.pending_approval
    assert pending is not None and not pending.can_accept_edits and pending.scope == "budget/1"
    await session.approve(accept_edits=True)  # ineligible: the supervisor's ContractError becomes an error entry
    assert session.entries()[-1].kind is EntryKind.error and "ContractError" in session.entries()[-1].text
    assert session.state.phase is Phase.awaiting_approval and session.state.pending_approval == pending
    await session.approve()
    assert task_state(factory, session).status is TaskStatus.done and session.state.phase is Phase.idle


async def test_answers_in_the_wrong_phase_add_a_notice(workspace):
    session, factory = make_session(workspace)
    await session.approve()
    await session.deny()
    await session.answer("x")
    assert kinds(session)[-3:] == ["notice", "notice", "notice"]
    assert factory.planner.calls == 0


# ---------------------------------------------------------------------- Clarification


async def test_clarification_answer_continues_the_task(workspace):
    session, factory = make_session(workspace, plans=[{"clarify": "Which quarter?"}, {"steps": [read_step()]}])
    await session.submit("Summarize the notes")
    assert session.state.phase is Phase.awaiting_answer and session.state.question == "Which quarter?"
    calls = []
    original = factory.runtime.supervisor.clarify

    async def clarify(task_id, answer, **kw):
        calls.append(answer)
        return await original(task_id, answer, **kw)
    factory.runtime.supervisor.clarify = clarify
    await session.answer("  Q3  ")
    assert calls == ["Q3"] and task_state(factory, session).status is TaskStatus.done
    assert "You answered: Q3" in all_text(session) and session.state.phase is Phase.idle


async def test_clarification_esc_cancels_the_task(workspace):
    session, factory = make_session(workspace, plans=[{"clarify": "Which quarter?"}])
    await session.submit("Summarize the notes")
    await session.answer("   ")  # empty answers are not sent
    assert session.state.phase is Phase.awaiting_answer
    session.cancel()  # the UI's Esc on the answer field
    assert task_state(factory, session).status is TaskStatus.canceled
    assert session.state.phase is Phase.idle and "Status: canceled" in all_text(session)


# ---------------------------------------------------------------------- Cancel While Running


async def test_cancel_while_running_is_cooperative(workspace):
    factory = ScriptedRuntimes([{"steps": [model_step("s1", refs=()), model_step("s2", refs=())]}], gate=True)
    session, _ = make_session(workspace, factory=factory)
    cancels = []
    spy(factory.runtime.supervisor, "cancel", cancels)
    run = asyncio.create_task(session.submit("Summarize"))
    await asyncio.wait_for(factory.adapter.entered.wait(), 5)
    assert session.state.phase is Phase.running
    session.cancel()
    assert session.state.phase is Phase.canceling and len(cancels) == 1
    session.cancel()  # a second press while canceling does nothing more
    assert len(cancels) == 1 and not run.done()
    factory.adapter.gate.set()  # the model call in flight finishes first
    await asyncio.wait_for(run, 5)
    assert not run.cancelled() and task_state(factory, session).status is TaskStatus.canceled
    assert session.state.phase is Phase.idle and "Status: canceled" in all_text(session)
    assert len(factory.adapter.calls) == 1  # s2 never ran


async def test_cancel_when_idle_is_a_notice(workspace):
    session, _ = make_session(workspace)
    session.cancel()
    assert session.entries()[-1].text == "No task is running." and session.state.phase is Phase.idle


async def test_quit_with_a_task_active_cancels_and_closes(workspace):
    factory = ScriptedRuntimes([{"steps": [model_step("s1", refs=()), model_step("s2", refs=())]}], gate=True)
    session, _ = make_session(workspace, factory=factory)
    run = asyncio.create_task(session.submit("Summarize"))
    await asyncio.wait_for(factory.adapter.entered.wait(), 5)
    factory.adapter.gate.set()
    await session.aclose(timeout=3)
    await run
    assert session.state.phase is Phase.closed and factory.adapter.closed
    assert task_state(factory, session).status is TaskStatus.canceled


async def test_quit_times_out_without_asyncio_canceling_the_call(workspace):
    factory = ScriptedRuntimes([{"steps": [model_step("s1", refs=())]}], gate=True)
    session, _ = make_session(workspace, factory=factory)
    run = asyncio.create_task(session.submit("Summarize"))
    await asyncio.wait_for(factory.adapter.entered.wait(), 5)
    await session.aclose(timeout=0.05)
    assert session.state.phase is Phase.closed and not run.done()
    factory.adapter.gate.set()
    await asyncio.wait_for(run, 5)
    assert not run.cancelled() and session.state.phase is Phase.closed  # a late return cannot reopen it
    assert await session.submit("again") is None


# ---------------------------------------------------------------------- One Task At A Time


async def test_one_task_at_a_time(workspace):
    session, factory = make_session(workspace)
    await session.submit("Summarize into summary.md")
    assert session.state.phase is Phase.awaiting_approval
    starts = []
    spy(factory.runtime.supervisor, "start", starts)
    await session.submit("Another objective")
    assert session.entries()[-1].text == BUSY_NOTICE and starts == [] and factory.planner.calls == 1
    assert session.state.phase is Phase.awaiting_approval


async def test_second_submit_while_running_starts_nothing(workspace):
    factory = ScriptedRuntimes([{"steps": [model_step("s1", refs=())]}], gate=True)
    session, _ = make_session(workspace, factory=factory)
    run = asyncio.create_task(session.submit("First"))
    await asyncio.wait_for(factory.adapter.entered.wait(), 5)
    await session.submit("Second")
    assert session.entries()[-1].text == BUSY_NOTICE and factory.planner.calls == 1
    factory.adapter.gate.set()
    await run
    assert [e.text for e in session.entries() if e.kind is EntryKind.user] == ["First"]


# ---------------------------------------------------------------------- earlier-task context (R9)


async def test_earlier_tasks_are_passed_as_context_up_to_three(workspace):
    plans = [{"steps": [read_step()]} for _ in range(5)]
    session, factory = make_session(workspace, plans=plans)
    requests = []
    spy(factory.runtime.supervisor, "start", requests)
    for i in range(5):
        await session.submit(f"Task {i}")
    first = requests[0][0][0].objective.context
    assert "Earlier tasks in this session" not in first and "- notes.md" in first
    last = requests[4][0][0].objective.context
    tail = last.split("Earlier tasks in this session:\n")[1].splitlines()
    assert len(tail) == 3 and tail[0].startswith("- Task 1 -> done: ") and tail[2].startswith("- Task 3 -> done: ")
    memory = factory.builds[-1][1]
    assert memory.list() == []  # context is data in Task State; nothing goes to Memory


# ---------------------------------------------------------------------- runtime rebuild (R8)


async def test_budget_workspace_and_memory_changes_rebuild_the_runtime(workspace, tmp_path):
    session, factory = make_session(workspace, plans=[{"steps": [read_step()]}] * 2)
    await session.submit("First")
    assert len(factory.builds) == 1
    first_adapter = factory.adapter
    other = tmp_path / "other"
    other.mkdir()
    (other / "notes.md").write_text("other notes", encoding="utf-8")
    for command in ("/budget 2", "/workspace " + str(other), "/memory off"):
        await session.submit(command)
    assert len(factory.builds) == 1  # applied to the next task, not immediately
    await session.submit("Second")
    config, memory, _ = factory.builds[-1]
    assert len(factory.builds) == 2 and first_adapter.closed
    assert config.budget_usd == 2.0 and config.workspace == other and memory is None
    assert session.state.status.memory == "off"


async def test_budget_off_means_no_limit(workspace):
    session, factory = make_session(workspace, plans=[{"steps": [read_step()]}])
    await session.submit("/budget off")
    assert session.state.status.budget_usd is None
    await session.submit("/budget 0")
    assert session.state.status.budget_usd is None
    await session.submit("go")
    assert factory.builds[-1][0].budget_usd is None


async def test_unchanged_settings_reuse_the_runtime(workspace):
    session, factory = make_session(workspace, plans=[{"steps": [read_step()]}] * 2)
    await session.submit("one")
    await session.submit("/events on")
    await session.submit("two")
    assert len(factory.builds) == 1


async def test_supervisor_exception_becomes_an_error_entry_and_rebuilds(workspace):
    session, factory = make_session(workspace, plans=[{"steps": [read_step()]}])

    async def boom(request):
        raise RuntimeError("secret detail sk-abcdefghijklmnopqrstuvwx")
    factory.runtime.supervisor.start = boom
    await session.submit("anything")
    last = session.entries()[-1]
    assert last.kind is EntryKind.error and last.text == "Unexpected error (RuntimeError)."
    assert session.state.phase is Phase.idle and "secret detail" not in all_text(session)
    await session.submit("again")
    assert len(factory.builds) == 2 and "Status: done" in all_text(session)


async def test_runtime_factory_failure_is_an_error_entry(workspace):
    def factory(config, sinks, memory):
        raise OSError("disk")
    session = Session(SessionConfig(workspace=workspace), runtime_factory=factory, memory=None)
    assert any(e.kind is EntryKind.error and "OSError" in e.text for e in session.entries())
    await session.submit("go")
    assert session.state.phase is Phase.idle


# ---------------------------------------------------------------------- no keys, memory unavailable


async def test_no_provider_key_starts_but_refuses_objectives(workspace):
    factory = ScriptedRuntimes([{"steps": [read_step()]}], available=False)
    session, _ = make_session(workspace, factory=factory)
    assert any(e.kind is EntryKind.error and e.text == NO_KEYS for e in session.entries())
    await session.submit("do it")
    assert session.entries()[-1].text == NO_KEYS and factory.planner.calls == 0
    assert session.state.phase is Phase.idle
    await session.submit("/help")  # slash commands still work
    assert session.entries()[-1].kind is EntryKind.notice


async def test_memory_unavailable_at_start(workspace, monkeypatch):
    monkeypatch.setattr(session_mod, "open_memory", lambda out: out("Memory is unavailable (bad file); "
                                                                     "continuing without it.") or None)
    factory = ScriptedRuntimes([{"steps": [read_step()]}])
    session = Session(SessionConfig(workspace=workspace), runtime_factory=factory)
    assert session.state.status.memory == "unavailable"
    assert "Memory is unavailable (bad file)" in all_text(session)
    await session.submit("go")
    assert factory.builds[-1][1] is None and "Status: done" in all_text(session)
    await session.submit("/memory list")
    assert session.entries()[-1].kind is EntryKind.error


async def test_memory_is_opened_once_and_only_when_on(workspace, monkeypatch):
    opened = []
    monkeypatch.setattr(session_mod, "open_memory", lambda out: opened.append(1) or InMemoryMemoryStore())
    session = Session(SessionConfig(workspace=workspace, memory_on=False),
                      runtime_factory=ScriptedRuntimes([]))
    assert opened == [] and session.state.status.memory == "off"
    await session.submit("/memory on")
    await session.submit("/memory list")
    await session.submit("/memory off")
    await session.submit("/memory on")
    assert opened == [1] and session.state.status.memory == "on"


async def test_default_runtime_uses_build_runtime_with_session_sinks(workspace, monkeypatch, tmp_path):
    seen = {}

    def fake_build(workspace_arg, **kw):
        seen.update(kw, workspace=workspace_arg)
        raise RuntimeError("stop here")
    monkeypatch.setattr(session_mod, "build_runtime", fake_build)
    events = tmp_path / "events.jsonl"
    store = InMemoryMemoryStore()
    Session(SessionConfig(workspace=workspace, budget_usd=None, events_path=events), memory=store)
    assert seen["workspace"] == workspace and seen["budget_usd"] is None and seen["events_path"] == events
    assert seen["memory"] is store and len(seen["sinks"]) == 1 and seen["out"]("x") is None
    assert not events.exists()


async def test_build_runtime_with_mock_provider(workspace):
    plan = {"status": "planned", "reason": "read", "steps": [read_step()]}
    registry = ModelRegistry([spec("fast", "cheap", 0.5, 0.1, 0.4), spec("smart", "strong", 0.9, 3, 15)],
                             {"mock": ProviderConfig(adapter="mock")})

    def respond(messages, model) -> str:
        task = messages[-1].content
        if "planning worker" in task:
            return json.dumps(plan)
        return json.dumps({"verdict": "pass", "summary": "ok"})

    def factory(config, sinks, memory):
        pool = ProviderPool(registry, overrides={"mock": MockProvider("mock", responder=respond)})
        return build_runtime(config.workspace, registry=registry, pool=pool, out=lambda _: None, sinks=sinks,
                             budget_usd=config.budget_usd, memory=memory)

    session = Session(SessionConfig(workspace=workspace), runtime_factory=factory, memory=InMemoryMemoryStore())
    await session.submit("Read the notes")
    assert "Status: done" in all_text(session) and session.state.status.task_cost_usd > 0
    assert session.state.status.session_cost_usd == session.state.status.task_cost_usd
    assert session.state.status.route in ("fast", "smart")


# ---------------------------------------------------------------------- slash commands (session effects)


async def test_slash_commands_take_effect(workspace):
    session, _ = make_session(workspace)
    assert await session.submit("/quit") == UiAction("quit")
    assert await session.submit("/theme light") == UiAction("theme", "light")
    assert await session.submit("/theme") is None
    await session.submit("/help")
    help_entry = session.entries()[-1]
    assert any(line.startswith("/memory [list|forget ID|on|off]") for line in help_entry.detail)
    await session.submit("/events on")
    assert session.state.status.verbose_events
    await session.submit("/events")
    assert session.entries()[-1].text == "Verbose events: on."
    await session.submit("/events off")
    assert not session.state.status.verbose_events
    await session.submit("/edit-mode accept-edits")
    assert session.state.status.edit_mode is EditMode.accept_edits
    await session.submit("/edit-mode")
    assert "accept-edits" in session.entries()[-1].text
    await session.submit("/budget 1.25")
    assert session.state.status.budget_usd == 1.25
    await session.submit("/workspace")
    assert str(workspace.resolve()) in session.entries()[-1].text
    await session.submit("/clear")
    assert session.entries() == [] and session.state.cleared_after > 0
    await session.submit("/budget")
    assert [e.text for e in session.entries()] == ["Budget: $1.25 per task."]


async def test_invalid_commands_show_usage_and_change_nothing(workspace):
    session, factory = make_session(workspace)
    before = session.state
    for line in ("/nope", "/edit-mode always", "/budget lots", "/budget nan", "/memory wipe", "/events maybe",
                 "/theme blue", "/help me", "/memory forget"):
        assert await session.submit(line) is None
        last = session.entries()[-1]
        assert last.kind is EntryKind.error and ("Usage: /" in last.text or "Type /help" in last.text), line
    assert session.state == before and factory.planner.calls == 0


async def test_workspace_switch_to_missing_folder_is_refused(workspace, tmp_path):
    session, _ = make_session(workspace)
    await session.submit(f"/workspace {tmp_path / 'missing'}")
    last = session.entries()[-1]
    assert last.kind is EntryKind.error and last.text.startswith("Workspace folder not found")
    assert session.state.status.workspace == workspace


async def test_refused_commands_while_a_task_is_active(workspace, tmp_path):
    store = InMemoryMemoryStore([MemoryRecord(id="mem_1", content="likes tea", type="preference",
                                              provenance="user")])
    session, factory = make_session(workspace, memory=store)
    await session.submit("Summarize into summary.md")
    assert session.state.phase is Phase.awaiting_approval
    before = session.state.status
    for line in (f"/workspace {tmp_path}", "/budget 3", "/memory forget mem_1", "/memory off", "/memory on"):
        await session.submit(line)
        assert "not available while a task is active" in session.entries()[-1].text, line
    assert session.state.status == before and store.list() != []
    # allowed while active
    await session.submit("/memory list")
    assert "likes tea" in "\n".join(session.entries()[-1].detail)
    await session.submit("/events on")
    assert session.state.status.verbose_events
    await session.submit("/edit-mode accept-edits")  # also switches the active task (014 R7)
    assert session.config.edit_mode is EditMode.accept_edits
    assert session.state.status.edit_mode is EditMode.accept_edits
    assert await session.submit("/quit") == UiAction("quit")


async def test_verbose_events_are_filtered_until_events_on(workspace):
    session, _ = make_session(workspace, plans=[{"steps": [read_step()]}])
    await session.submit("go")
    assert not any(e.verbose for e in session.entries())
    await session.submit("/events on")
    verbose = [e for e in session.entries() if e.verbose]
    assert verbose and all(e.kind is EntryKind.event for e in verbose)
    assert any(e.text.startswith("status_changed:") for e in verbose)


# ---------------------------------------------------------------------- Memory Forget Is Scoped


async def test_memory_forget_deletes_an_in_scope_record(workspace):
    store = InMemoryMemoryStore([MemoryRecord(id="mem_user", content="prefers short answers", type="preference",
                                              provenance="user"),
                                 MemoryRecord(id="mem_proj", content="uses tabs", type="fact",
                                              scope=project_scope(workspace), provenance="user")])
    session, _ = make_session(workspace, memory=store)
    await session.submit("/memory forget mem_proj")
    assert session.entries()[-1].text == "Forgot memory record mem_proj."
    assert [r.id for r in store.list()] == ["mem_user"]


async def test_memory_forget_out_of_scope_or_unknown_deletes_nothing(workspace, tmp_path):
    other = MemoryRecord(id="mem_other", content="other project", type="fact",
                         scope=project_scope(tmp_path / "elsewhere"), provenance="user")
    store = InMemoryMemoryStore([other])
    session, _ = make_session(workspace, memory=store)
    for record_id in ("mem_other", "mem_missing"):
        await session.submit(f"/memory forget {record_id}")
        assert session.entries()[-1].kind is EntryKind.error
    assert [r.id for r in store.list()] == ["mem_other"]
    await session.submit("/memory list")
    assert session.entries()[-1].text == "No memory records for you or this workspace."


async def test_memory_list_redacts_sensitive_records(workspace):
    store = InMemoryMemoryStore([MemoryRecord(id="mem_s", content="my bank PIN hint", type="fact",
                                              provenance="user", sensitivity="sensitive")])
    session, _ = make_session(workspace, memory=store)
    await session.submit("/memory")
    detail = "\n".join(session.entries()[-1].detail)
    assert "mem_s" in detail and "[redacted]" in detail and "PIN" not in detail


# ---------------------------------------------------------------------- No Hidden Reasoning Or Secrets


HOSTILE = ("Done. key sk-abcdefghijklmnopqrstuvwx1234 \x1b]52;c;ZXZpbA==\x07 \x1b]8;;http://evil\x1b\\link\x1b]8;;\x1b\\ "
           "\x1b[31mred\x1b[0m [bold]markup[/bold] \u202eevil\u202c \x9b2J end, under plan")


async def test_no_hidden_reasoning_or_secrets_reach_the_transcript(workspace):
    factory = ScriptedRuntimes([{"steps": [model_step("s1", refs=())]}],
                               outputs=[{"output": HOSTILE, "reasoning": "PRIVATE CHAIN OF THOUGHT"}])
    session, _ = make_session(workspace, factory=factory)
    await session.submit("Echo sk-zyxwvutsrqponmlkjihgf9876 back \x1b[2J")
    text = all_text(session)
    assert "PRIVATE CHAIN OF THOUGHT" not in text
    assert "sk-abcdefghijklmnopqrstuvwx1234" not in text and "sk-zyxwvutsrqponmlkjihgf9876" not in text
    assert "[redacted]" in text
    assert "\x1b" not in text and "\x07" not in text and "\x9b" not in text and "\u202e" not in text
    result = next(e for e in session.entries() if e.kind is EntryKind.result)
    assert "[bold]markup[/bold]" in result.body and "red" in result.body and "link" in result.body


async def test_failure_path_redaction_in_error_entries(workspace):
    session, factory = make_session(workspace)
    from galliani.errors import ContractError

    async def boom(request):
        raise ContractError("bad \x1b]52;c;eA==\x07 sk-abcdefghijklmnopqrstuvwx")
    factory.runtime.supervisor.start = boom
    await session.submit("go")
    last = session.entries()[-1].text
    assert last.startswith("ContractError: bad") and "\x1b" not in last and "sk-abcdefghijklmnop" not in last


def test_sanitize():
    assert sanitize("a\tb\nc") == "a\tb\nc"
    assert sanitize("x\x00\x07\x08\r\x7f\x85\x9fy") == "xy"
    assert sanitize("\x1b[1;31mred\x1b[0m") == "red"
    assert sanitize("\x1b]52;c;ZXZpbA==\x07after") == "after"
    assert sanitize("\x1b]8;;https://x\x1b\\text\x1b]8;;\x1b\\") == "text"
    assert sanitize("\x1bPpayload\x1b\\ok") == "ok"
    assert sanitize("lone \x1b") == "lone "
    assert sanitize("a\u202ab\u202ec\u2066d\u2069e") == "abcde"
    assert sanitize("[bold]x[/bold] [link=http://e]y[/link]") == "[bold]x[/bold] [link=http://e]y[/link]"
    assert "sk-" not in sanitize("token sk-abcdefghijklmnopqrstuvwx")
    assert "sk-" not in sanitize("\x1b[31msk-abcdefghijklmnopqrstuvwx\x1b[0m")


# ---------------------------------------------------------------------- Untrusted Text Cannot Run Commands


async def test_untrusted_output_cannot_run_commands(workspace):
    output = "/edit-mode accept-edits\n/quit\n/memory forget mem_1\n/workspace C:\\ under plan"
    store = InMemoryMemoryStore([MemoryRecord(id="mem_1", content="keep me", type="note", provenance="user")])
    factory = ScriptedRuntimes([{"clarify": "/edit-mode accept-edits"}, {"steps": [model_step("s1", refs=())]}],
                               outputs=[{"output": output}])
    session, _ = make_session(workspace, factory=factory, memory=store)
    action = await session.submit("Say something")
    assert action is None and session.state.question == "/edit-mode accept-edits"
    await session.answer("go on")
    assert "/edit-mode accept-edits" in next(e for e in session.entries() if e.kind is EntryKind.result).body
    assert session.state.status.edit_mode is EditMode.ask and session.config.edit_mode is EditMode.ask
    assert session.state.phase is Phase.idle and store.list() != [] and session.state.status.workspace == workspace


async def test_user_typed_command_does_change_the_mode(workspace):
    session, _ = make_session(workspace)
    await session.submit("/edit-mode accept-edits")
    assert session.config.edit_mode is EditMode.accept_edits


# ---------------------------------------------------------------------- result rendering (R19)


async def test_long_result_body_is_cut(workspace):
    factory = ScriptedRuntimes([{"steps": [model_step("s1", refs=(), must_contain="x")]}],
                               outputs=[{"output": "x" * (MAX_BODY_CHARS + 5)}])
    session, _ = make_session(workspace, factory=factory)
    await session.submit("long")
    body = next(e for e in session.entries() if e.kind is EntryKind.result).body
    assert body.endswith("(5 more characters not shown)") and body.startswith("x" * MAX_BODY_CHARS)


async def test_failed_task_result_has_no_body(workspace):
    factory = ScriptedRuntimes([{"steps": [model_step("s1", refs=(), must_contain="never")]}],
                               outputs=[{"output": "nope"}] * 10)
    session, _ = make_session(workspace, factory=factory)
    await session.submit("fail please")
    result = next(e for e in session.entries() if e.kind is EntryKind.result)
    assert result.text.startswith("Status: failed") or result.text.startswith("Status: blocked")
    assert result.body == "nope"  # no output: the last model text (ResultView.preview), never TaskResult.output
    assert session.entries()[-1].kind is EntryKind.usage


async def test_listener_errors_never_reach_the_caller(workspace):
    session, _ = make_session(workspace, plans=[{"steps": [read_step()]}])

    def bad():
        raise RuntimeError("ui bug")
    unsubscribe = session.subscribe(bad)
    await session.submit("go")
    assert "Status: done" in all_text(session)
    unsubscribe()
    unsubscribe()


@pytest.mark.parametrize("edit_mode", [EditMode.ask, EditMode.accept_edits])
async def test_session_default_edit_mode_is_used_for_new_tasks(workspace, edit_mode):
    session, factory = make_session(workspace, edit_mode=edit_mode)
    await session.submit("Summarize into summary.md")
    expected = Phase.awaiting_approval if edit_mode is EditMode.ask else Phase.idle
    assert session.state.phase is expected
