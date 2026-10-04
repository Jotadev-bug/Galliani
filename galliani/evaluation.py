"""Spec 013 - Evaluation: deterministic fixtures that run the real supervisor loop and enforce v0.1 gates.

Run:  python -m galliani.evaluation [evals/cases]

Each case runs twice; differing outcomes are flagged `non_deterministic` for manual review. Invalid
fixtures fail fast. Runner crashes are reported as `error` (runner failure), not as product failures.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from galliani.contracts import Objective
from galliani.limits import LoopLimits
from galliani.model_planner import ModelPlanner
from galliani.observability import InMemoryEventSink, Observability
from galliani.permissions import PermissionLevel, PermissionPolicy, PermissionStatus
from galliani.planner import StaticPlanner
from galliani.replanning import RetryPolicy
from galliani.router import ModelRouter, RoutingPolicy
from galliani.state import TaskStatus
from galliani.supervisor import StartTaskRequest, Supervisor, TaskResult, UserPolicy
from galliani.testing import FixtureWorld, ScriptedAdapter, fixture_tool_registry
from galliani.tools import ToolRegistry, ToolSystem
from galliani.workers import WorkerClient

DEFAULT_CASES = Path(__file__).resolve().parent.parent / "evals" / "cases"
REASONING_MARKER = "EVAL-HIDDEN-REASONING"
MAX_USER_TURNS = 3


class FixtureError(Exception):
    """An eval fixture is invalid; the suite stops before running anything."""


class ExpectedOutcome(BaseModel):
    status: TaskStatus
    verification: Literal["pass", "fail", "inconclusive"] | None = None
    events_include: list[str] = Field(default_factory=list)
    tools_executed: list[str] | None = None
    workers_used: list[str] | None = None
    retries: int | None = None
    replans: int | None = None


class InitialState(BaseModel):
    notes: dict[str, str] = Field(default_factory=dict)
    files: dict[str, str] = Field(default_factory=dict)
    pages: dict[str, str] = Field(default_factory=dict)
    flaky_timeouts: int = 0


class EvalCase(BaseModel):
    """013 `EvalCase`, with the scripts that make the run deterministic."""

    id: str
    spec_refs: list[str] = Field(min_length=1)
    objective: str
    constraints: dict[str, Any] = Field(default_factory=dict)
    initial_state: InitialState = Field(default_factory=InitialState)
    available_workers: list[dict[str, Any]]
    available_tools: list[str]
    worker_script: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    planner_script: list[dict[str, Any]] = Field(default_factory=list)
    required_constraints: list[str] = Field(default_factory=list)
    permission_rules: dict[PermissionLevel, PermissionStatus] | None = None
    routing_policy: RoutingPolicy = Field(default_factory=RoutingPolicy)
    user_action: Literal["approve", "deny"] | None = None  # answer to every pending approval prompt
    user_answer: str | None = None  # answer to a clarification question
    # "model": ModelPlanner drafts plans through the worker named by planner_worker; its scripted replies
    # are `plan_reply` objects (JSON-encoded by the runner) or raw `output` strings in worker_script.
    planner: Literal["static", "model"] = "static"
    planner_worker: str = "planner"
    limits: LoopLimits = Field(default_factory=LoopLimits)
    negative: bool = False  # must never end in `done`
    expected_outcome: ExpectedOutcome

    @field_validator("spec_refs")
    @classmethod
    def _spec_refs_point_at_specs(cls, refs: list[str]) -> list[str]:
        bad = [r for r in refs if not re.fullmatch(r"(\d{3}|Decision \d{4})(\s.*)?", r)]
        if bad:
            raise ValueError(f"spec_refs must start with a spec number or 'Decision NNNN', got {bad}")
        return refs


class EvalResult(BaseModel):
    case_id: str
    status: Literal["pass", "fail", "error"]
    spec_refs: list[str]
    metrics: dict[str, float] = Field(default_factory=dict)
    failure_category: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)


class QualityGate(BaseModel):
    name: str
    threshold: float
    blocking: bool = True
    owner: str = "galliani-core"


class GateResult(BaseModel):
    gate: QualityGate
    value: float
    passed: bool


class EvalSuite(BaseModel):
    name: str
    cases: list[EvalCase]
    required_pass_rate: float = 1.0
    blockers: list[QualityGate] = Field(default_factory=lambda: [
        QualityGate(name="loop_pass_rate", threshold=1.0),
        QualityGate(name="permission_bypasses", threshold=0),
        QualityGate(name="hidden_reasoning_leaks", threshold=0),
        QualityGate(name="false_done_on_negative", threshold=0),
    ])


class EvalReport(BaseModel):
    suite: str
    results: list[EvalResult]
    gates: list[GateResult]

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates if g.gate.blocking)


def load_suite(path: Path = DEFAULT_CASES, name: str = "v0.1 loop") -> EvalSuite:
    files = sorted(path.glob("*.yaml")) if path.is_dir() else [path]
    if not files:
        raise FixtureError(f"no eval fixtures found at {path}")
    cases: list[EvalCase] = []
    for file in files:
        data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
        for raw in data.get("cases", []):
            try:
                cases.append(EvalCase.model_validate(raw))
            except ValidationError as e:
                raise FixtureError(f"{file.name}: invalid case {raw.get('id', '?')}: {e.error_count()} error(s)\n{e}") from None
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise FixtureError("duplicate eval case ids")
    known_tools = set(fixture_tool_registry(FixtureWorld()).names())
    for case in cases:
        unknown = sorted(set(case.available_tools) - known_tools)
        if unknown:
            raise FixtureError(f"{case.id}: unknown tools {unknown}")
    return EvalSuite(name=name, cases=cases)


class _Run(BaseModel):
    result: TaskResult
    events: list[dict[str, Any]]
    blobs: list[str]
    executed: list[str]
    allowed_actions: list[str]
    restricted_tools: list[str]
    retries: int
    replans: int


async def _run_once(case: EvalCase) -> _Run:
    world = FixtureWorld(**case.initial_state.model_dump())
    full = fixture_tool_registry(world)
    registry = ToolRegistry([full.get(t) for t in case.available_tools])
    script = {w: [{"reasoning": REASONING_MARKER, **_encode_reply(entry)} for entry in entries]
              for w, entries in case.worker_script.items()}
    sink = InMemoryEventSink()
    obs = Observability([sink])
    router = ModelRouter(case.available_workers)
    adapter = ScriptedAdapter("scripted", script)
    if case.planner == "model":
        planner = ModelPlanner(WorkerClient(router, [adapter], obs), registry, limits=case.limits,
                               required_constraints=case.required_constraints)
    else:
        planner = StaticPlanner(case.planner_script, required_constraints=case.required_constraints)
    supervisor = Supervisor(
        planner=planner,
        router=router,
        adapters=[adapter],
        tools=ToolSystem(registry, PermissionPolicy(case.permission_rules)),
        retry_policy=RetryPolicy(),
        limits=case.limits,
        observability=obs,
    )
    result = await supervisor.start(StartTaskRequest(
        objective=Objective(goal=case.objective, constraints=case.constraints),
        user_policy=UserPolicy(routing=case.routing_policy),
    ))
    for _ in range(MAX_USER_TURNS):  # bounded, like a person answering prompts
        if result.status is not TaskStatus.waiting_for_user:
            break
        if result.approval_prompt and case.user_action == "approve":
            result = await supervisor.approve(result.task_id)
        elif result.approval_prompt and case.user_action == "deny":
            result = await supervisor.deny(result.task_id)
        elif result.clarification and case.user_answer:
            result = await supervisor.clarify(result.task_id, case.user_answer)
        else:
            break
    state = supervisor.store.get(result.task_id)
    events = sink.for_task(result.task_id)
    return _Run(
        result=result,
        events=[{"type": e.type.value, "metadata": e.metadata} for e in events],
        blobs=[result.model_dump_json(), state.model_dump_json(), *(e.model_dump_json() for e in events),
               *(h.model_dump_json() for h in supervisor.store.history(result.task_id))],
        executed=list(world.executed),
        allowed_actions=[d.action for d in state.permission_decisions if d.status is PermissionStatus.allowed],
        restricted_tools=[t for t in case.available_tools if full.get(t).permission_level is not PermissionLevel.read_only],
        retries=sum(state.retry_counts.values()),
        replans=state.replan_count,
    )


def _encode_reply(entry: dict[str, Any]) -> dict[str, Any]:
    if "plan_reply" in entry:
        entry = {**{k: v for k, v in entry.items() if k != "plan_reply"}, "output": json.dumps(entry["plan_reply"])}
    return entry


def _fingerprint(run: _Run) -> tuple:
    return (run.result.status, tuple(e["type"] for e in run.events), tuple(run.executed))


def _check(case: EvalCase, run: _Run) -> tuple[list[str], dict[str, float]]:
    exp = case.expected_outcome
    problems: list[str] = []
    result = run.result
    if result.status is not exp.status:
        problems.append(f"status {result.status.value} != expected {exp.status.value}")
    if exp.verification is not None:
        got = result.verification_result.status.value if result.verification_result else None
        if got != exp.verification:
            problems.append(f"final verification {got} != expected {exp.verification}")
    types = {e["type"] for e in run.events}
    missing = [t for t in exp.events_include if t not in types]
    if missing:
        problems.append(f"missing events {missing}")
    if exp.tools_executed is not None and run.executed != exp.tools_executed:
        problems.append(f"tools executed {run.executed} != expected {exp.tools_executed}")
    if exp.workers_used is not None:
        used = [e["metadata"].get("worker") for e in run.events if e["type"] == "step_executed" and e["metadata"].get("worker")]
        if used != exp.workers_used:
            problems.append(f"workers used {used} != expected {exp.workers_used}")
    if exp.retries is not None and run.retries != exp.retries:
        problems.append(f"retries {run.retries} != expected {exp.retries}")
    if exp.replans is not None and run.replans != exp.replans:
        problems.append(f"replans {run.replans} != expected {exp.replans}")

    bypasses = sum(max(0, run.executed.count(t) - run.allowed_actions.count(t)) for t in run.restricted_tools)
    leaks = sum(REASONING_MARKER in blob for blob in run.blobs)
    false_done = int(case.negative and result.status is TaskStatus.done)
    if bypasses:
        problems.append(f"{bypasses} restricted tool execution(s) without an allowed permission decision")
    if leaks:
        problems.append(f"hidden reasoning leaked into {leaks} artifact(s)")
    if false_done:
        problems.append("negative fixture ended in done")
    metrics = {"permission_bypasses": bypasses, "hidden_reasoning_leaks": leaks, "false_done": false_done,
               "retries": run.retries, "replans": run.replans, "events": len(run.events)}
    return problems, metrics


async def run_case(case: EvalCase) -> EvalResult:
    try:
        first, second = await _run_once(case), await _run_once(case)
    except Exception as e:  # noqa: BLE001 - runner failure, separated from product failure
        return EvalResult(case_id=case.id, status="error", spec_refs=case.spec_refs, failure_category="runner_error",
                          messages=[f"runner crashed: {type(e).__name__}: {e}"])
    if _fingerprint(first) != _fingerprint(second):
        return EvalResult(case_id=case.id, status="error", spec_refs=case.spec_refs,
                          failure_category="non_deterministic", messages=["outcomes differ between runs; review manually"])
    problems, metrics = _check(case, first)
    category = None
    if problems:
        category = ("permission_bypass" if metrics["permission_bypasses"] else
                    "reasoning_leak" if metrics["hidden_reasoning_leaks"] else
                    "false_done" if metrics["false_done"] else "unexpected_outcome")
    return EvalResult(case_id=case.id, status="fail" if problems else "pass", spec_refs=case.spec_refs, metrics=metrics,
                      failure_category=category, evidence_refs=[first.result.task_id], messages=problems)


async def run_suite(suite: EvalSuite) -> EvalReport:
    results = [await run_case(case) for case in suite.cases]
    totals = {
        "loop_pass_rate": sum(r.status == "pass" for r in results) / max(1, len(results)),
        "permission_bypasses": sum(r.metrics.get("permission_bypasses", 0) for r in results),
        "hidden_reasoning_leaks": sum(r.metrics.get("hidden_reasoning_leaks", 0) for r in results),
        "false_done_on_negative": sum(r.metrics.get("false_done", 0) for r in results),
    }
    gates = []
    for gate in suite.blockers:
        value = totals[gate.name]
        passed = value >= gate.threshold if gate.name.endswith("rate") else value <= gate.threshold
        gates.append(GateResult(gate=gate, value=value, passed=passed))
    return EvalReport(suite=suite.name, results=results, gates=gates)


def format_report(report: EvalReport) -> str:
    lines = [f"Eval suite: {report.suite}"]
    for r in report.results:
        lines.append(f"  [{r.status.upper():5}] {r.case_id}  ({', '.join(r.spec_refs)})")
        lines.extend(f"          - {m}" for m in r.messages)
    lines.append("Quality gates:")
    for g in report.gates:
        lines.append(f"  [{'PASS' if g.passed else 'FAIL'}] {g.gate.name} = {g.value:g} (threshold {g.gate.threshold:g})")
    lines.append(f"Result: {'PASS' if report.passed else 'FAIL'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else DEFAULT_CASES
    try:
        suite = load_suite(path)
    except FixtureError as e:
        print(f"Invalid fixtures: {e}", file=sys.stderr)
        return 2
    report = asyncio.run(run_suite(suite))
    print(format_report(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
