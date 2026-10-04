"""HTTP API behind the agent page of the desktop app (spec 012, Decision 0018).

    POST /api/agent/tasks                       start a task (returns the view in created/planning status)
    GET  /api/agent/tasks                       recent tasks
    GET  /api/agent/tasks/{id}                  current TaskViewModel
    GET  /api/agent/tasks/{id}/events?after=N   long poll: new EventFeedItems plus the current view
    POST /api/agent/tasks/{id}/approve|deny     answer an approval prompt
    POST /api/agent/tasks/{id}/clarify          answer a question
    POST /api/agent/tasks/{id}/cancel           stop the task

Each task gets its own runtime (workspace, caller keys, budget) and runs as a background task on the
server's event loop. Tasks live in memory only. Everything returned is a 012 view model, built from
redacted state and events.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from galliani.contracts import Objective, utcnow
from galliani.errors import ContractError
from galliani.observability import LifecycleEvent
from galliani.state import TERMINAL_STATUSES, TaskStatus
from galliani.supervisor import StartTaskRequest
from galliani.viewmodel import EventFeedItem, TaskViewModel, build_feed, build_task_view

ROOT_ENV = "GALLIANI_AGENT_WORKSPACE_ROOT"
DEFAULT_BUDGET_USD = 0.50
MAX_WAIT_S = 25.0
MAX_TASKS = 50


class TaskEventSink:
    """Keeps one task's redacted events and wakes long-polling readers when a new one arrives."""

    def __init__(self) -> None:
        self.events: list[LifecycleEvent] = []
        self._changed = asyncio.Event()

    def write(self, event: LifecycleEvent) -> None:
        self.events.append(event)
        changed, self._changed = self._changed, asyncio.Event()
        changed.set()

    async def wait_beyond(self, seq: int, timeout: float) -> None:
        if len(self.events) > seq or timeout <= 0:
            return
        try:
            await asyncio.wait_for(self._changed.wait(), timeout)
        except asyncio.TimeoutError:
            pass


class AgentTask:
    def __init__(self, task_id: str, runtime: Any, sink: TaskEventSink, objective: str, workspace: str):
        self.task_id = task_id
        self.runtime = runtime
        self.sink = sink
        self.objective = objective
        self.workspace = workspace
        self.created_at = utcnow()
        self.job: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self.job is not None and not self.job.done()


# (workspace, caller keys, budget in USD or None, extra event sinks) -> runtime with .supervisor, .aclose()
RuntimeFactory = Callable[[Path, dict[str, str], float | None, list], Any]


def default_runtime_factory(workspace: Path, keys: dict[str, str], budget: float | None, sinks: list) -> Any:
    from galliani.cli import build_runtime

    return build_runtime(workspace, keys=keys, out=lambda _line: None, budget_usd=budget, sinks=sinks)


class StartBody(BaseModel):
    objective: str = Field(min_length=1, max_length=4_000)
    workspace: str = Field(min_length=1, max_length=1_000)
    context: str = Field(default="", max_length=4_000)
    budget_usd: float | None = Field(default=DEFAULT_BUDGET_USD, gt=0, le=100)


class AnswerBody(BaseModel):
    answer: str = Field(min_length=1, max_length=4_000)


class TaskSummary(BaseModel):
    task_id: str
    objective: str
    status: TaskStatus
    status_label: str
    workspace: str
    created_at: datetime


class EventsPage(BaseModel):
    events: list[EventFeedItem]
    seq: int
    view: TaskViewModel


class AgentService:
    def __init__(self, runtime_factory: RuntimeFactory = default_runtime_factory):
        self.runtime_factory = runtime_factory
        self.tasks: dict[str, AgentTask] = {}

    # ------------------------------------------------------------------ availability

    @staticmethod
    def availability() -> tuple[bool, str | None, Path | None]:
        """(enabled, reason when disabled, allowed workspace root or None for any folder)."""
        root = os.environ.get(ROOT_ENV)
        if root:
            return True, None, Path(root).resolve()
        if os.environ.get("ROUTER_DESKTOP") == "1":
            return True, None, None
        return False, (f"The agent can read and write files, so it only runs in the desktop app or when {ROOT_ENV} "
                       "limits it to one folder."), None

    def check_workspace(self, raw: str) -> Path:
        enabled, reason, root = self.availability()
        if not enabled:
            raise HTTPException(403, reason)
        path = Path(raw).expanduser()
        if root is not None and not path.is_absolute():
            path = root / path
        path = path.resolve()
        if not path.is_dir():
            raise HTTPException(400, f"Folder not found: {path}")
        if root is not None and path != root and not path.is_relative_to(root):
            raise HTTPException(403, f"The workspace must be inside {root}.")
        return path

    # ------------------------------------------------------------------ tasks

    def get(self, task_id: str) -> AgentTask:
        task = self.tasks.get(task_id)
        if task is None:
            raise HTTPException(404, "Task not found.")
        return task

    def view(self, task: AgentTask) -> TaskViewModel:
        supervisor = task.runtime.supervisor
        result = supervisor.get(task.task_id)
        artifacts = [{"kind": a.kind, "uri": a.uri} for a in result.artifacts]
        return build_task_view(supervisor.store.get(task.task_id), artifacts=artifacts, usage=result.usage)

    async def start(self, body: StartBody, keys: dict[str, str]) -> TaskViewModel:
        from galliani.cli import workspace_overview

        workspace = self.check_workspace(body.workspace)
        sink = TaskEventSink()
        runtime = self.runtime_factory(workspace, keys, body.budget_usd, [sink])
        if not getattr(runtime, "available_workers", ["?"]):
            await runtime.aclose()
            raise HTTPException(400, "No model provider key found. Add one under API Keys.")
        context = workspace_overview(workspace) + (f"\n\nUser context:\n{body.context}" if body.context else "")
        created = runtime.supervisor.create(StartTaskRequest(objective=Objective(goal=body.objective, context=context)))
        task = AgentTask(created.task_id, runtime, sink, body.objective, str(workspace))
        self.tasks[task.task_id] = task
        self._trim()
        view = self.view(task)  # captured before the loop starts: the task view opens in `created` (012 AC)
        self._launch(task, runtime.supervisor.run(task.task_id))
        return view

    def _launch(self, task: AgentTask, coro) -> None:
        async def job() -> None:
            try:
                await coro
            finally:
                state = task.runtime.supervisor.store.get(task.task_id)
                if state.status in TERMINAL_STATUSES or state.status is TaskStatus.blocked:
                    await task.runtime.aclose()

        task.job = asyncio.create_task(job())

    def _trim(self) -> None:
        for task_id in list(self.tasks)[:-MAX_TASKS]:
            if not self.tasks[task_id].running:
                del self.tasks[task_id]

    async def events(self, task_id: str, after: int, wait: float) -> EventsPage:
        task = self.get(task_id)
        await task.sink.wait_beyond(after, min(max(wait, 0.0), MAX_WAIT_S))
        feed = build_feed(task.sink.events, after=after)
        return EventsPage(events=feed, seq=len(task.sink.events), view=self.view(task))

    async def act(self, task_id: str, action: str, answer: str | None = None) -> TaskViewModel:
        task = self.get(task_id)
        supervisor = task.runtime.supervisor
        if action == "cancel":
            supervisor.cancel(task_id)
            return self.view(task)
        if task.running:
            raise HTTPException(409, "The task is still running.")
        state = supervisor.store.get(task_id)
        try:
            if action in ("approve", "deny"):
                if state.status is not TaskStatus.waiting_for_user or state.pending_permission is None:
                    raise ContractError("there is no approval to answer")
                coro = supervisor.approve(task_id) if action == "approve" else supervisor.deny(task_id)
            elif action == "clarify":
                if state.status is not TaskStatus.waiting_for_user or not state.clarification:
                    raise ContractError("there is no question to answer")
                coro = supervisor.clarify(task_id, answer or "")
            else:
                raise HTTPException(404, "Unknown action.")
        except ContractError as e:
            raise HTTPException(409, e.safe_summary) from None
        self._launch(task, coro)
        await asyncio.sleep(0)
        return self.view(task)

    def summaries(self) -> list[TaskSummary]:
        out = []
        for task in reversed(self.tasks.values()):
            view = self.view(task)
            out.append(TaskSummary(task_id=task.task_id, objective=task.objective, status=view.status,
                                   status_label=view.status_label, workspace=task.workspace,
                                   created_at=task.created_at))
        return out


def agent_router(keys_for: Callable[[Request], dict[str, str]], service: AgentService | None = None) -> APIRouter:
    svc = service or AgentService()
    router = APIRouter(prefix="/api/agent")
    router.service = svc  # exposed for tests

    @router.get("/config")
    def config() -> dict:
        enabled, reason, root = svc.availability()
        return {"enabled": enabled, "reason": reason, "workspace_root": str(root) if root else None,
                "default_budget_usd": DEFAULT_BUDGET_USD}

    @router.post("/tasks")
    async def start(body: StartBody, request: Request) -> TaskViewModel:
        return await svc.start(body, keys_for(request))

    @router.get("/tasks")
    def tasks() -> list[TaskSummary]:
        return svc.summaries()

    @router.get("/tasks/{task_id}")
    def task(task_id: str) -> TaskViewModel:
        return svc.view(svc.get(task_id))

    @router.get("/tasks/{task_id}/events")
    async def events(task_id: str, after: int = 0, wait: float = 20.0) -> EventsPage:
        return await svc.events(task_id, after, wait)

    @router.post("/tasks/{task_id}/approve")
    async def approve(task_id: str) -> TaskViewModel:
        return await svc.act(task_id, "approve")

    @router.post("/tasks/{task_id}/deny")
    async def deny(task_id: str) -> TaskViewModel:
        return await svc.act(task_id, "deny")

    @router.post("/tasks/{task_id}/clarify")
    async def clarify(task_id: str, body: AnswerBody) -> TaskViewModel:
        return await svc.act(task_id, "clarify", body.answer)

    @router.post("/tasks/{task_id}/cancel")
    async def cancel(task_id: str) -> TaskViewModel:
        return await svc.act(task_id, "cancel")

    return router
