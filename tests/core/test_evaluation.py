"""Spec 013 - Evaluation: fixture validation, end-to-end smoke run, and gates that can actually fail."""

from __future__ import annotations

import pytest

import galliani.evaluation as ev
from galliani.evaluation import EvalCase, EvalSuite, FixtureError, load_suite, run_case, run_suite

W1 = {"worker_id": "w1", "provider_id": "scripted", "capabilities": ["text"],
      "limits": {"context_window": 32000, "max_output_tokens": 2000}, "cost_class": "low", "latency_class": "fast"}
STEP = {"step_id": "s1", "kind": "model", "purpose": "answer", "required_capability": "text",
        "expected_output": "an answer", "instruction": "Answer.",
        "verification_criteria": [{"kind": "contains", "value": "42"}]}


def case(**kw) -> EvalCase:
    base = dict(id="c", spec_refs=["001 Happy Path"], objective="answer", available_workers=[W1], available_tools=[],
                worker_script={"w1": [{"output": "it is 42"}]}, planner_script=[{"steps": [STEP]}],
                expected_outcome={"status": "done"})
    return EvalCase.model_validate({**base, **kw})


async def test_v0_1_suite_passes_all_gates():
    report = await run_suite(load_suite())
    assert report.passed, ev.format_report(report)
    gate_names = {g.gate.name for g in report.gates}
    assert gate_names == {"loop_pass_rate", "permission_bypasses", "hidden_reasoning_leaks", "false_done_on_negative",
                          "unauthorized_memory_writes", "secret_memory_persistence"}


def test_suite_covers_minimum_gate_scenarios():
    ids = {c.id for c in load_suite().cases}
    assert {"success_tool_then_model", "tool_timeout_retried", "verification_failure_retried",
            "permission_denied_by_user", "provider_fallback"} <= ids


def test_invalid_fixtures_fail_fast(tmp_path):
    (tmp_path / "bad.yaml").write_text("cases:\n  - id: x\n    objective: y\n", encoding="utf-8")
    with pytest.raises(FixtureError):
        load_suite(tmp_path)
    with pytest.raises(ValueError):
        case(spec_refs=["not a spec"])
    (tmp_path / "bad.yaml").write_text(
        "cases:\n  - id: x\n    spec_refs: ['001']\n    objective: y\n    available_workers: []\n"
        "    available_tools: [rm_rf]\n    planner_script: []\n    expected_outcome: {status: done}\n",
        encoding="utf-8")
    with pytest.raises(FixtureError, match="unknown tools"):
        load_suite(tmp_path)


async def test_wrong_expectation_is_reported_as_failure():
    result = await run_case(case(expected_outcome={"status": "failed"}))
    assert result.status == "fail" and result.failure_category == "unexpected_outcome"


async def test_false_done_on_negative_fixture_fails_gate():
    report = await run_suite(EvalSuite(name="neg", cases=[case(negative=True)]))
    assert not report.passed
    assert report.results[0].failure_category == "false_done"


def test_reasoning_leak_and_permission_bypass_are_detected():
    leaky = ev._Run(result=ev.TaskResult(task_id="t", status="done", summary="x"), events=[],
                    blobs=[f"... {ev.REASONING_MARKER} ..."], executed=["delete_file"], allowed_actions=[],
                    restricted_tools=["delete_file"], retries=0, replans=0)
    problems, metrics = ev._check(case(), leaky)
    assert metrics["hidden_reasoning_leaks"] == 1 and metrics["permission_bypasses"] == 1
    assert len(problems) == 2


async def test_runner_crash_is_separated_from_product_failure(monkeypatch):
    async def boom(case):
        raise RuntimeError("runner bug")

    monkeypatch.setattr(ev, "_run_once", boom)
    result = await run_case(case())
    assert result.status == "error" and result.failure_category == "runner_error"


def test_cli_exit_code():
    assert ev.main([]) == 0
