"""Command-line entrypoint: wires real providers, the model planner/verifier and workspace tools.

This is a wiring layer (Decision 0015). It may import provider adapters; core modules never import it.

    python -m galliani.cli "Summarize the notes in docs/ into summary.md" --workspace ./my-project

Restricted actions (writes) pause for a y/N approval; planner questions are asked interactively.
Only public summaries are printed; hidden reasoning never reaches this layer.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

from app.config import CONFIG_DIR
from app.keys import PROVIDERS
from app.models.registry import ModelRegistry
from app.providers.factory import ProviderPool
from galliani.contracts import Objective
from galliani.limits import LoopLimits
from galliani.model_planner import ModelPlanner
from galliani.model_verifier import ModelSemanticVerifier
from galliani.observability import EventType, JsonlEventSink, LifecycleEvent, Observability
from galliani.providers.app_bridge import AppProviderAdapter, worker_profiles
from galliani.router import ModelRouter
from galliani.state import TaskStatus
from galliani.supervisor import StartTaskRequest, Supervisor, TaskResult
from galliani.tools import ToolSystem
from galliani.verification import Verifier
from galliani.workers import WorkerClient
from galliani.workspace import ListIn, Workspace

DEFAULT_BUDGET_USD = 0.50
Ask = Callable[[str], str]
Out = Callable[[str], None]

SHOWN_EVENTS = {
    EventType.plan_created, EventType.plan_revised, EventType.route_selected, EventType.route_fallback,
    EventType.tool_called, EventType.verification_completed, EventType.retry_scheduled, EventType.replan_started,
    EventType.task_finished,
}


class UsageTotals:
    def __init__(self) -> None:
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_micro_usd = 0

    def add(self, usage: dict) -> None:
        self.calls += 1
        self.input_tokens += int(usage.get("input_tokens", 0))
        self.output_tokens += int(usage.get("output_tokens", 0))
        self.cost_micro_usd += int(usage.get("cost_micro_usd", 0))

    def summary(self) -> str:
        return (f"Usage: {self.calls} model call(s), {self.input_tokens} input / {self.output_tokens} output tokens, "
                f"est. ${self.cost_micro_usd / 1_000_000:.4f} (registry prices)")


class ConsoleSink:
    def __init__(self, out: Out = print):
        self.out = out
        self.usage = UsageTotals()

    def write(self, event: LifecycleEvent) -> None:
        if event.type is EventType.worker_completed:
            self.usage.add(event.metadata.get("usage", {}))
        if event.type in SHOWN_EVENTS:
            step = f" [{event.refs.step_id}]" if event.refs.step_id else ""
            self.out(f"  - {event.type.value}{step}: {event.public_summary}")
            if event.type in (EventType.plan_created, EventType.plan_revised):
                for item in event.metadata.get("steps", []):
                    self.out(f"      {item['id']} ({item['kind']}: {item['capability']}) {item['purpose']}")


def load_keys() -> dict[str, str]:
    """Provider keys from the environment, then the OS credential store (desktop installs)."""
    from app import keys as key_store

    found = {}
    for env_name in PROVIDERS.values():
        value = os.environ.get(env_name) or key_store.get(env_name)
        if value:
            found[env_name] = value
    return found


class Runtime:
    def __init__(self, supervisor: Supervisor, adapter: AppProviderAdapter, available_workers: list[str],
                 console: ConsoleSink):
        self.supervisor = supervisor
        self.adapter = adapter
        self.available_workers = available_workers
        self.console = console

    async def aclose(self) -> None:
        await self.adapter.aclose()


def build_runtime(workspace: Path | str, *, registry: ModelRegistry | None = None, pool: ProviderPool | None = None,
                  out: Out = print, capability: str = "reasoning", events_path: Path | str | None = None,
                  budget_usd: float | None = DEFAULT_BUDGET_USD) -> Runtime:
    registry = registry or ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
    pool = pool or ProviderPool(registry, keys=load_keys())
    profiles = worker_profiles(registry, pool)
    available = [p for p in profiles if p.availability != "unavailable"]
    if not any(capability in p.capabilities for p in available):
        capability = "text"  # no stronger worker reachable: plan and judge with what is available
    router = ModelRouter(profiles)
    adapter = AppProviderAdapter(registry, pool)
    console = ConsoleSink(out)
    obs = Observability([console, *([JsonlEventSink(events_path)] if events_path else [])])
    workers = WorkerClient(router, [adapter], obs)
    tools = Workspace(workspace).registry()
    limits = LoopLimits(max_cost_usd=budget_usd)
    supervisor = Supervisor(
        planner=ModelPlanner(workers, tools, capability=capability, limits=limits),
        limits=limits,
        router=router,
        adapters=[adapter],
        tools=ToolSystem(tools),
        verifier=Verifier(ModelSemanticVerifier(workers, capability=capability)),
        observability=obs,
    )
    return Runtime(supervisor, adapter, [p.worker_id for p in available], console)


async def interact(supervisor: Supervisor, result: TaskResult, *, ask: Ask = input, out: Out = print) -> TaskResult:
    """Answer approval prompts and clarification questions until the task stops waiting."""
    while result.status is TaskStatus.waiting_for_user:
        if result.approval_prompt is not None:
            prompt = result.approval_prompt
            out(f"\nApproval needed: {prompt.action_summary}\n  risk: {prompt.risk_summary}; scope: {prompt.scope}")
            if ask("Approve? [y/N] ").strip().lower() in ("y", "yes"):
                result = await supervisor.approve(result.task_id)
            else:
                result = await supervisor.deny(result.task_id)
        elif result.clarification:
            out(f"\nQuestion: {result.clarification}")
            answer = ask("Answer (empty to cancel): ").strip()
            result = await supervisor.clarify(result.task_id, answer) if answer else supervisor.cancel(result.task_id)
        else:
            break
    return result


def workspace_overview(workspace: Path | str, limit: int = 100) -> str:
    """File names the agent may use, given to the planner as data (protected files are never listed)."""
    listing = Workspace(workspace).list_files(ListIn())
    files = listing["files"][:limit]
    more = " (more not shown)" if listing["truncated"] or len(listing["files"]) > limit else ""
    root = Path(workspace).resolve().name or str(Path(workspace).resolve())
    header = (f"Workspace root: the folder '{root}'. Every tool path is relative to it; use '.' for the root "
              f"itself and never an absolute path or a path that starts with '{root}/'.\n")
    return header + f"Workspace files{more}:\n" + ("\n".join(f"- {f}" for f in files) if files else "(empty)")


def format_result(result: TaskResult) -> str:
    lines = [f"\nStatus: {result.status.value}", f"Summary: {result.summary}"]
    if result.verification_result is not None:
        lines.append(f"Verification: {result.verification_result.status.value} - {result.verification_result.reason_summary}")
    if result.output is not None:
        output = result.output if isinstance(result.output, str) else json.dumps(result.output, indent=2, ensure_ascii=False)
        lines.append(f"Output:\n{output}")
    if result.approval_prompt is not None:
        lines.append(f"Waiting for approval: {result.approval_prompt.action_summary}")
    if result.clarification:
        lines.append(f"Waiting for an answer: {result.clarification}")
    return "\n".join(lines)


async def run(objective: str, workspace: Path | str, *, context: str = "", interactive: bool = True,
              ask: Ask = input, out: Out = print, runtime: Runtime | None = None,
              events_path: Path | str | None = None, budget_usd: float | None = DEFAULT_BUDGET_USD) -> int:
    runtime = runtime or build_runtime(workspace, out=out, events_path=events_path, budget_usd=budget_usd)
    try:
        if not runtime.available_workers:
            out("No model provider key found. Set one of: " + ", ".join(sorted(PROVIDERS.values())))
            return 2
        out(f"Galliani: {objective}\n  workspace: {Path(workspace).resolve()}")
        full_context = workspace_overview(workspace) + (f"\n\nUser context:\n{context}" if context else "")
        result = await runtime.supervisor.start(StartTaskRequest(objective=Objective(goal=objective, context=full_context)))
        if interactive:
            result = await interact(runtime.supervisor, result, ask=ask, out=out)
        out(format_result(result))
        out(runtime.console.usage.summary())
        return 0 if result.status is TaskStatus.done else 1
    finally:
        await runtime.aclose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m galliani.cli", description="Run one objective under the Galliani supervisor.")
    parser.add_argument("objective", help="what you want done")
    parser.add_argument("--workspace", default=".", help="directory the agent may read (and, with approval, write)")
    parser.add_argument("--context", default="", help="reference text for the planner (treated as data)")
    parser.add_argument("--non-interactive", action="store_true", help="stop instead of asking for approvals or answers")
    parser.add_argument("--events", default=None, help="append the redacted event log to this JSON Lines file")
    parser.add_argument("--budget", type=float, default=DEFAULT_BUDGET_USD,
                        help=f"estimated USD per task before asking to spend more (default {DEFAULT_BUDGET_USD})")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace)
    if not workspace.is_dir():
        print(f"Workspace folder not found: {workspace.resolve()}\n"
              "Pass --workspace with an existing folder the agent may read (it can only touch files inside it).",
              file=sys.stderr)
        return 2
    return asyncio.run(run(args.objective, args.workspace, context=args.context, interactive=not args.non_interactive,
                           events_path=args.events, budget_usd=args.budget if args.budget > 0 else None))


if __name__ == "__main__":
    sys.exit(main())
