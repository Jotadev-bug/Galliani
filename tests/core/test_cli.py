"""CLI wiring: the full agentic stack (bridge + ModelPlanner + ModelSemanticVerifier + workspace tools),
exercised end to end with the app's MockProvider standing in for the network."""

from __future__ import annotations

import json

import pytest

from app.models.registry import ModelRegistry
from app.models.schemas import ProviderConfig
from app.providers.factory import ProviderPool
from app.providers.mock import MockProvider
from galliani.cli import ConsoleSink, build_runtime, run
from galliani.observability import EventType, Observability
from tests.conftest import spec

PLAN = {
    "status": "planned", "reason": "read, summarize, save",
    "steps": [
        {"step_id": "s1", "kind": "tool", "purpose": "read the notes", "required_capability": "read_file",
         "expected_output": "note text", "tool": {"tool_name": "read_file", "arguments": {"path": "notes/q3.md"}},
         "verification_criteria": [{"kind": "field_present", "field": "text"}]},
        {"step_id": "s2", "kind": "model", "purpose": "summarize", "required_capability": "text", "input_refs": ["s1"],
         "expected_output": "one-line summary", "instruction": "Summarize the note in one line.",
         "verification_criteria": [{"kind": "contains", "value": "under plan"},
                                   {"kind": "semantic", "value": "a faithful one-line summary"}]},
        {"step_id": "s3", "kind": "tool", "purpose": "save the summary", "required_capability": "write_file",
         "expected_output": "file written",
         "tool": {"tool_name": "write_file", "arguments": {"path": "summary.md", "content": {"$ref": "s2"}}},
         "verification_criteria": [{"kind": "field_equals", "field": "path", "value": "summary.md"}]},
    ],
    "success_criteria": [{"kind": "field_equals", "field": "path", "value": "summary.md"}],
}


def responder(plan: dict):
    def respond(messages, model) -> str:
        task = messages[-1].content
        if "planning worker" in task:
            return json.dumps(plan)
        if "verification worker" in task:
            return json.dumps({"verdict": "pass", "summary": "faithful summary"})
        return "Q3 spend is under plan."
    return respond


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "q3.md").write_text("Q3 budget review: spend is 4% under plan.", encoding="utf-8")
    return tmp_path


def runtime(workspace, plan=PLAN, lines=None):
    registry = ModelRegistry([spec("fast", "cheap", 0.5, 0.1, 0.4), spec("smart", "strong", 0.9, 3, 15)],
                             {"mock": ProviderConfig(adapter="mock")})
    mock = MockProvider("mock", responder=responder(plan))
    rt = build_runtime(workspace, registry=registry, pool=ProviderPool(registry, overrides={"mock": mock}),
                       out=(lines.append if lines is not None else lambda _: None))
    return rt, mock


async def test_end_to_end_with_approval(workspace):
    lines: list[str] = []
    rt, mock = runtime(workspace, lines=lines)
    answers = iter(["y"])
    code = await run("Summarize notes/q3.md into summary.md", workspace, runtime=rt,
                     ask=lambda _: next(answers), out=lines.append)
    assert code == 0
    assert (workspace / "summary.md").read_text(encoding="utf-8") == "Q3 spend is under plan."
    text = "\n".join(lines)
    assert "Approval needed" in text and "scope: summary.md" in text and "Status: done" in text
    # planner and judge run on the reasoning-capable worker; the bounded step on the cheapest one
    assert mock.calls[0] == "smart" and "fast" in mock.calls


async def test_denied_write_blocks_and_leaves_workspace_untouched(workspace):
    rt, _ = runtime(workspace)
    code = await run("Summarize into summary.md", workspace, runtime=rt, ask=lambda _: "n", out=lambda _: None)
    assert code == 1 and not (workspace / "summary.md").exists()


async def test_non_interactive_stops_at_the_approval(workspace):
    lines: list[str] = []
    rt, _ = runtime(workspace, lines=lines)
    code = await run("Summarize into summary.md", workspace, runtime=rt, interactive=False, out=lines.append)
    assert code == 1 and "Waiting for approval" in "\n".join(lines)


async def test_planner_question_is_asked_and_empty_answer_cancels(workspace):
    rt, _ = runtime(workspace, plan={"status": "needs_clarification", "reason": "Which quarter?"})
    lines: list[str] = []
    code = await run("Summarize the notes", workspace, runtime=rt, ask=lambda _: "", out=lines.append)
    assert code == 1 and "Question: Which quarter?" in "\n".join(lines) and "Status: canceled" in "\n".join(lines)


async def test_missing_keys_exit_with_guidance(workspace, monkeypatch):
    for name in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    from app.config import CONFIG_DIR

    registry = ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
    rt = build_runtime(workspace, registry=registry, pool=ProviderPool(registry, keys={}), out=lambda _: None)
    lines: list[str] = []
    assert await run("anything", workspace, runtime=rt, out=lines.append) == 2
    assert "OPENROUTER_API_KEY" in lines[0]


def test_console_sink_prints_public_summaries_only():
    lines: list[str] = []
    Observability([ConsoleSink(lines.append)]).emit(
        EventType.tool_called, "t", "read_file succeeded",
        step_id="s1", metadata={"arguments": {"path": "x"}})
    assert lines == ["  - tool_called [s1]: read_file succeeded"]


async def test_plan_outline_is_printed_and_events_can_be_saved(workspace, tmp_path):
    lines: list[str] = []
    registry = ModelRegistry([spec("fast", "cheap", 0.5, 0.1, 0.4), spec("smart", "strong", 0.9, 3, 15)],
                             {"mock": ProviderConfig(adapter="mock")})
    pool = ProviderPool(registry, overrides={"mock": MockProvider("mock", responder=responder(PLAN))})
    events = tmp_path / "run.jsonl"
    rt = build_runtime(workspace, registry=registry, pool=pool, out=lines.append, events_path=events)
    await run("Summarize", workspace, runtime=rt, ask=lambda _: "y", out=lines.append)
    assert "      s1 (tool: read_file) read the notes" in lines
    assert "      s2 (model: text) summarize" in lines
    assert '"type":"task_finished"' in events.read_text(encoding="utf-8")


async def test_planner_gets_workspace_listing_as_data_without_protected_files(workspace):
    from galliani.cli import workspace_overview

    (workspace / ".env").write_text("API_KEY=x", encoding="utf-8")
    overview = workspace_overview(workspace)
    assert "- notes/q3.md" in overview and ".env" not in overview

    lines: list[str] = []
    rt, mock = runtime(workspace, lines=lines)
    seen = {}
    original = rt.adapter.send

    async def spy(request):
        if request.step_id == "planner":
            seen.update(request.inputs)
        return await original(request)

    rt.adapter.send = spy
    await run("Summarize", workspace, runtime=rt, ask=lambda _: "y", out=lines.append, context="Audience: execs")
    assert "- notes/q3.md" in seen["context"] and "Audience: execs" in seen["context"]


async def test_usage_and_estimated_cost_are_reported(workspace):
    lines: list[str] = []
    rt, mock = runtime(workspace, lines=lines)
    await run("Summarize", workspace, runtime=rt, ask=lambda _: "y", out=lines.append)
    usage = next(line for line in lines if line.startswith("Usage:"))
    assert f"{len(mock.calls)} model call(s)" in usage and "est. $" in usage
    assert rt.console.usage.cost_micro_usd > 0


def test_missing_workspace_folder_gives_a_clear_message(tmp_path, capsys):
    from galliani.cli import main

    assert main(["do something", "--workspace", str(tmp_path / "does-not-exist")]) == 2
    err = capsys.readouterr().err
    assert "Workspace folder not found" in err and "Traceback" not in err


async def test_cli_budget_pauses_for_approval_when_exceeded(workspace):
    lines: list[str] = []
    registry = ModelRegistry([spec("fast", "cheap", 0.5, 0.1, 0.4), spec("smart", "strong", 0.9, 3, 15)],
                             {"mock": ProviderConfig(adapter="mock")})
    pool = ProviderPool(registry, overrides={"mock": MockProvider("mock", responder=responder(PLAN))})
    rt = build_runtime(workspace, registry=registry, pool=pool, out=lines.append, budget_usd=0.000001)
    code = await run("Summarize", workspace, runtime=rt, ask=lambda _: "n", out=lines.append)
    text = "\n".join(lines)
    assert code == 1 and "extend_budget:1" in text and "Status: blocked" in text
    assert not (workspace / "summary.md").exists()


WEB_PLAN = {
    "status": "planned", "reason": "generate the app, then save it",
    "steps": [
        {"step_id": "s1", "kind": "model", "purpose": "write the app", "required_capability": "reasoning",
         "expected_output": "a file bundle", "instruction": "Write index.html, styles.css and app.js as a bundle.",
         "verification_criteria": [{"kind": "contains", "value": "=== app.js ==="}]},
        {"step_id": "s2", "kind": "tool", "purpose": "save the files", "required_capability": "write_files",
         "expected_output": "files written", "tool": {"tool_name": "write_files", "arguments": {"bundle": {"$ref": "s1"}}},
         "verification_criteria": [{"kind": "field_present", "field": "paths"}]},
    ],
}
WEB_BUNDLE = '=== index.html ===\n```html\n<script src="app.js"></script>\n```\n=== styles.css ===\nbody{}\n=== app.js ===\nlet n = 1;\n'


async def test_multi_file_build_fits_the_plan_and_needs_one_approval(workspace):
    registry = ModelRegistry([spec("fast", "cheap", 0.5, 0.1, 0.4), spec("smart", "strong", 0.9, 3, 15)],
                             {"mock": ProviderConfig(adapter="mock")})

    def respond(messages, model) -> str:
        task = messages[-1].content
        if "planning worker" in task:
            return json.dumps(WEB_PLAN)
        if "verification worker" in task:
            return json.dumps({"verdict": "pass", "summary": "ok"})
        return WEB_BUNDLE

    pool = ProviderPool(registry, overrides={"mock": MockProvider("mock", responder=respond)})
    rt = build_runtime(workspace, registry=registry, pool=pool, out=lambda _: None)
    prompts: list[str] = []
    code = await run("Build a counter web app", workspace, runtime=rt, ask=lambda q: prompts.append(q) or "y",
                     out=lambda _: None)
    assert code == 0 and len(prompts) == 1
    assert (workspace / "index.html").read_text(encoding="utf-8") == '<script src="app.js"></script>\n'
    assert (workspace / "app.js").read_text(encoding="utf-8") == "let n = 1;\n"
    assert (workspace / "styles.css").exists()


async def test_accept_edits_flag_and_a_answer(workspace):
    lines: list[str] = []
    rt, _ = runtime(workspace, lines=lines)
    asked: list[str] = []
    code = await run("Summarize", workspace, runtime=rt, ask=lambda q: asked.append(q) or "", out=lines.append,
                     accept_edits=True)
    assert code == 0 and asked == [] and "edits: accepted without asking" in "\n".join(lines)

    (workspace / "summary.md").unlink()
    rt, _ = runtime(workspace)
    prompts: list[str] = []
    code = await run("Summarize", workspace, runtime=rt, ask=lambda q: prompts.append(q) or "a", out=lambda _: None)
    assert code == 0 and "a = yes, and accept edits" in prompts[0] and (workspace / "summary.md").exists()


def test_accept_edits_cli_flag_is_parsed(monkeypatch, tmp_path):
    import galliani.cli as cli

    seen = {}

    async def fake_run(objective, workspace, **kw):
        seen.update(kw)
        return 0

    monkeypatch.setattr(cli, "run", fake_run)
    assert cli.main(["build", "--workspace", str(tmp_path), "--accept-edits"]) == 0
    assert seen["accept_edits"] is True
