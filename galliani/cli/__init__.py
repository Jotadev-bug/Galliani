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
from galliani.model_planner import ModelPlanner
from galliani.model_verifier import ModelSemanticVerifier
from galliani.observability import EventType, LifecycleEvent, Observability
from galliani.providers.app_bridge import AppProviderAdapter, worker_profiles
from galliani.router import ModelRouter
from galliani.state import TaskStatus
from galliani.supervisor import StartTaskRequest, Supervisor, TaskResult
from galliani.tools import ToolSystem
from galliani.verification import Verifier
from galliani.workers import WorkerClient
from galliani.workspace import Workspace

Ask = Callable[[str], str]
Out = Callable[[str], None]

SHOWN_EVENTS = {
    EventType.plan_created, EventType.plan_revised, EventType.route_selected, EventType.route_fallback,
    EventType.tool_called, EventType.verification_completed, EventType.retry_scheduled, EventType.replan_started,
    EventType.task_finished,
}


class ConsoleSink:
    def __init__(self, out: Out = print):
        self.out = out

    def write(self, event: LifecycleEvent) -> None:
        if event.type in SHOWN_EVENTS:
            step = f" [{event.refs.step_id}]" if event.refs.step_id else ""
            self.out(f"  - {event.type.value}{step}: {event.public_summary}")


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
    def __init__(self, supervisor: Supervisor, adapter: AppProviderAdapter, available_workers: list[str]):
        self.supervisor = supervisor
        self.adapter = adapter
        self.available_workers = available_workers

    async def aclose(self) -> None:
        await self.adapter.aclose()


def build_runtime(workspace: Path | str, *, registry: ModelRegistry | None = None, pool: ProviderPool | None = None,
                  out: Out = print, capability: str = "reasoning") -> Runtime:
    registry = registry or ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
    pool = pool or ProviderPool(registry, keys=load_keys())
    profiles = worker_profiles(registry, pool)
    available = [p for p in profiles if p.availability != "unavailable"]
    if not any(capability in p.capabilities for p in available):
        capability = "text"  # no stronger worker reachable: plan and judge with what is available
    router = ModelRouter(profiles)
    adapter = AppProviderAdapter(registry, pool)
    obs = Observability([ConsoleSink(out)])
    workers = WorkerClient(router, [adapter], obs)
    tools = Workspace(workspace).registry()
    supervisor = Supervisor(
        planner=ModelPlanner(workers, tools, capability=capability),
        router=router,
        adapters=[adapter],
        tools=ToolSystem(tools),
        verifier=Verifier(ModelSemanticVerifier(workers, capability=capability)),
        observability=obs,
    )
    return Runtime(supervisor, adapter, [p.worker_id for p in available])


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
              ask: Ask = input, out: Out = print, runtime: Runtime | None = None) -> int:
    runtime = runtime or build_runtime(workspace, out=out)
    try:
        if not runtime.available_workers:
            out("No model provider key found. Set one of: " + ", ".join(sorted(PROVIDERS.values())))
            return 2
        out(f"Galliani: {objective}\n  workspace: {Path(workspace).resolve()}")
        result = await runtime.supervisor.start(StartTaskRequest(objective=Objective(goal=objective, context=context)))
        if interactive:
            result = await interact(runtime.supervisor, result, ask=ask, out=out)
        out(format_result(result))
        return 0 if result.status is TaskStatus.done else 1
    finally:
        await runtime.aclose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m galliani.cli", description="Run one objective under the Galliani supervisor.")
    parser.add_argument("objective", help="what you want done")
    parser.add_argument("--workspace", default=".", help="directory the agent may read (and, with approval, write)")
    parser.add_argument("--context", default="", help="reference text for the planner (treated as data)")
    parser.add_argument("--non-interactive", action="store_true", help="stop instead of asking for approvals or answers")
    args = parser.parse_args(argv)
    return asyncio.run(run(args.objective, args.workspace, context=args.context, interactive=not args.non_interactive))


if __name__ == "__main__":
    sys.exit(main())
