"""Builders for supervisor-level tests."""

from __future__ import annotations

from typing import Any

from galliani.limits import LoopLimits
from galliani.observability import InMemoryEventSink, Observability
from galliani.permissions import PermissionPolicy
from galliani.planner import StaticPlanner
from galliani.replanning import RetryPolicy
from galliani.router import ModelRouter
from galliani.supervisor import Supervisor
from galliani.testing import FixtureWorld, ScriptedAdapter, fixture_tool_registry
from galliani.tools import ToolSystem


def worker(worker_id: str, cost: str = "low", provider: str = "scripted", caps=("text",), **kw) -> dict:
    return {"worker_id": worker_id, "provider_id": provider, "capabilities": set(caps),
            "limits": {"context_window": 32_000, "max_output_tokens": 2_000},
            "cost_class": cost, "latency_class": "fast", **kw}


def read_step(step_id: str = "s0", note_id: str = "n1") -> dict:
    return {"step_id": step_id, "kind": "tool", "purpose": "read the source note", "required_capability": "read_note",
            "expected_output": "note text", "tool": {"tool_name": "read_note", "arguments": {"note_id": note_id}},
            "verification_criteria": [{"kind": "field_present", "field": "text"}]}


def summarize_step(step_id: str = "s1", refs=("s0",), on_fail: str = "retry", must_contain: str = "budget") -> dict:
    return {"step_id": step_id, "kind": "model", "purpose": "summarize the note", "required_capability": "text",
            "input_refs": list(refs), "expected_output": "a one-line summary", "instruction": "Summarize the note in one line.",
            "verification_criteria": [{"kind": "contains", "value": must_contain, "on_fail": on_fail},
                                      {"kind": "min_length", "value": 10}]}


def tool_step(step_id: str, tool: str, **arguments: Any) -> dict:
    return {"step_id": step_id, "kind": "tool", "purpose": f"run {tool}", "required_capability": tool,
            "expected_output": f"{tool} result", "tool": {"tool_name": tool, "arguments": arguments},
            "verification_criteria": [{"kind": "field_present",
                                       "field": {"write_file": "bytes", "delete_file": "deleted"}.get(tool, "text")}]}


class Harness:
    def __init__(
        self,
        plans: list[dict],
        *,
        script: dict[str, list[dict]] | None = None,
        workers: list[dict] | None = None,
        adapters: list | None = None,
        world: FixtureWorld | None = None,
        policy: PermissionPolicy | None = None,
        retry: RetryPolicy | None = None,
        limits: LoopLimits | None = None,
        sinks: list | None = None,
        verifier=None,
        required_constraints=(),
    ):
        self.world = world or FixtureWorld(notes={"n1": "Q3 budget review: spend is 4% under plan."})
        self.sink = InMemoryEventSink()
        self.adapter = ScriptedAdapter("scripted", script or {})
        self.planner = StaticPlanner(plans, required_constraints=required_constraints)
        kwargs = {"verifier": verifier} if verifier else {}
        self.supervisor = Supervisor(
            planner=self.planner,
            router=ModelRouter(workers or [worker("w1")]),
            adapters=adapters or [self.adapter],
            tools=ToolSystem(fixture_tool_registry(self.world), policy),
            retry_policy=retry,
            limits=limits,
            observability=Observability([*(sinks or []), self.sink]),
            **kwargs,
        )

    def events(self, task_id: str, type_: str | None = None):
        return [e for e in self.sink.for_task(task_id) if type_ is None or e.type.value == type_]

    def statuses(self, task_id: str) -> list[str]:
        return ["created"] + [e.metadata["to"] for e in self.events(task_id, "status_changed")]
