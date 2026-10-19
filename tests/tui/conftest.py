"""Session fixtures: a runtime factory on `galliani.testing` scripted adapters (outputs are SIMULATED).

The factory has the `RuntimeFactory` shape (spec 017 Interfaces), so `Session` rebuilds it exactly as it
rebuilds the real `build_runtime` one. Tests always pass `memory=` explicitly, so the user's real memory
file is never opened.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from galliani.cli import ConsoleSink, Runtime
from galliani.limits import LoopLimits
from galliani.memory import InMemoryMemoryStore
from galliani.observability import Observability
from galliani.planner import StaticPlanner
from galliani.router import ModelRouter
from galliani.supervisor import Supervisor
from galliani.testing import FixtureWorld, ScriptedAdapter, fixture_tool_registry
from galliani.tools import ToolSystem
from galliani.tui.session import Session, SessionConfig
from tests.core.helpers import worker

NOTE = "Q3 budget review: spend is 4% under plan."
SUMMARY = "Q3 spend is under plan."


def read_step(step_id: str = "s1") -> dict:
    return {"step_id": step_id, "kind": "tool", "purpose": "read the notes", "required_capability": "read_file",
            "expected_output": "note text", "tool": {"tool_name": "read_file", "arguments": {"path": "notes.md"}},
            "verification_criteria": [{"kind": "field_present", "field": "text"}]}


def model_step(step_id: str = "s2", refs=("s1",), must_contain: str = "under plan") -> dict:
    return {"step_id": step_id, "kind": "model", "purpose": "summarize", "required_capability": "text",
            "input_refs": list(refs), "expected_output": "a one-line summary",
            "instruction": "Summarize the note in one line.",
            "verification_criteria": [{"kind": "contains", "value": must_contain}]}


def write_step(step_id: str = "s3", path: str = "summary.md", ref: str = "s2") -> dict:
    return {"step_id": step_id, "kind": "tool", "purpose": f"save {path}", "required_capability": "write_file",
            "expected_output": "file written",
            "tool": {"tool_name": "write_file", "arguments": {"path": path, "content": {"$ref": ref}}},
            "verification_criteria": [{"kind": "field_equals", "field": "path", "value": path}]}


BASIC_PLAN = {"steps": [read_step(), model_step(), write_step()]}


class GatedAdapter(ScriptedAdapter):
    """Scripted adapter that can hold a call open (to cancel while running) and records `aclose`."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.gate: asyncio.Event | None = None
        self.entered = asyncio.Event()
        self.closed = False

    async def send(self, request):
        self.entered.set()
        if self.gate is not None:
            await self.gate.wait()
        return await super().send(request)

    async def aclose(self) -> None:
        self.closed = True


class ScriptedRuntimes:
    """A `RuntimeFactory` that records every build: (config, memory, runtime)."""

    def __init__(self, plans: list[dict], *, outputs: list[dict] | None = None, available: bool = True,
                 gate: bool = False):
        self.planner = StaticPlanner(plans)  # shared across rebuilds, so the plan script keeps its place
        self.outputs = outputs if outputs is not None else [{"output": SUMMARY}]
        self.available = available
        self.gate = gate
        self.builds: list[tuple[SessionConfig, object, Runtime]] = []

    def __call__(self, config: SessionConfig, sinks, memory) -> Runtime:
        adapter = GatedAdapter("scripted", {"w1": list(self.outputs)}, default_output=SUMMARY)
        if self.gate:
            adapter.gate = asyncio.Event()
        world = FixtureWorld(workspace=Path(config.workspace))
        limits = LoopLimits(max_cost_usd=config.budget_usd)
        supervisor = Supervisor(planner=self.planner, router=ModelRouter([worker("w1")]), adapters=[adapter],
                                tools=ToolSystem(fixture_tool_registry(world)), limits=limits,
                                observability=Observability(list(sinks)), memory=memory)
        runtime = Runtime(supervisor, adapter, ["w1"] if self.available else [], ConsoleSink(lambda _: None))
        self.builds.append((config, memory, runtime))
        return runtime

    @property
    def runtime(self) -> Runtime:
        return self.builds[-1][2]

    @property
    def adapter(self) -> GatedAdapter:
        return self.runtime.adapter


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "notes.md").write_text(NOTE, encoding="utf-8")
    return ws


def make_session(workspace, plans=None, *, memory="new", factory: ScriptedRuntimes | None = None,
                 **config) -> tuple[Session, ScriptedRuntimes]:
    """`memory="new"` gives each session an empty in-memory store."""
    factory = factory or ScriptedRuntimes(plans if plans is not None else [BASIC_PLAN])
    memory = InMemoryMemoryStore() if memory == "new" else memory
    session = Session(SessionConfig(workspace=workspace, **config), runtime_factory=factory, memory=memory)
    return session, factory


def kinds(session: Session) -> list[str]:
    return [e.kind.value for e in session.entries()]


def all_text(session: Session) -> str:
    return "\n".join("\n".join([e.text, *e.detail, e.body or ""]) for e in session.entries())
