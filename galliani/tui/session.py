"""Spec 017 R6-R19, R30-R34: the headless session controller behind the terminal UI.

This module imports nothing from Textual or Rich (R1). It drives one `Supervisor` through its public
methods only (R6), turns redacted lifecycle events and `build_task_view` into sanitized transcript
entries (R16-R18), and never raises to the UI (R14). Cancellation is cooperative: `Supervisor.cancel`
only, never `asyncio` cancellation of a supervisor call (R11, Decision 0034). Nothing is written to disk
here (R31); the only files are those the existing stack writes (approved memory, `--events`).
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Literal

import galliani
from app.keys import PROVIDERS
from galliani.cli import (
    DEFAULT_BUDGET_USD,
    SHOWN_EVENTS,
    Runtime,
    UsageTotals,
    build_runtime,
    load_keys,
    memory_scopes,
    open_memory,
    workspace_overview,
)
from galliani.contracts import Objective
from galliani.errors import GallianiError
from galliani.memory import MemoryStore
from galliani.observability import EventSink, EventType, LifecycleEvent
from galliani.permissions import ACCEPT_EDITS_CHOICE, EditMode
from galliani.state import TERMINAL_STATUSES, TaskStatus
from galliani.supervisor import StartTaskRequest, TaskResult, UserPolicy
from galliani.tui.commands import (
    COMMANDS,
    Command,
    CommandError,
    CompletionResult,
    _allowed_while_active,
    complete_command,
    parse_command,
    safe_completion,
    sanitize,
)
from galliani.tui.entry import is_wide_workspace
from galliani.viewmodel import STATUS_LABELS, PlanView, TaskViewModel, build_task_view
from galliani.workspace import BLOCKED_DIRS, ListIn, Workspace

MAX_BODY_CHARS = 20_000  # R19
EARLIER_TASKS = 3  # R9, the desktop's rule (Decision 0020)
BUSY_NOTICE = "A task is still running. Answer it, wait for it, or press Esc to stop it."
NO_KEYS = "No model provider key found. Set one of: " + ", ".join(sorted(PROVIDERS.values()))
KEYS_HELP = ("Keys: Enter send - Alt+Enter or Ctrl+J newline - Up/Down history - Esc or Ctrl+C stop a task - "
             "y/n/a answer an approval - Ctrl+T plan panel - Ctrl+C twice or Ctrl+Q quit")

MAX_FOLDERS = 50  # 018 R19
LISTING_TIMEOUT = 0.5  # seconds, 018 R19
FILE_LISTING_TIMEOUT = 2.0  # seconds; a slower R20 listing keeps running and fills the cache for a later key
FILE_CACHE_SECONDS = 30.0  # 018 R20
WIDE_WORKSPACE_WARNING = ("This workspace is your whole home folder (or drive). The agent can read any file in it "
                          "that is not protected. Start galliacli in a project folder, or use /workspace.")


@dataclass(frozen=True)
class BannerInfo:
    """018 R2 and R25: what the welcome banner shows. Never key material."""
    version: str
    workspace: str               # absolute, home shown as "~", sanitized
    providers: tuple[str, ...]   # provider names with a key; never key material
    wide_workspace: bool         # R25
    edit_mode: EditMode
    budget_usd: float | None
    memory: Literal["on", "off", "unavailable"]


def display_path(path: Path) -> str:
    """018 R2: the absolute path, with the home folder shown as `~`, sanitized."""
    resolved = Path(path).expanduser().resolve()
    try:
        rel = resolved.relative_to(Path.home().resolve())
    except (ValueError, RuntimeError, OSError):
        return sanitize(str(resolved))
    return sanitize("~" if rel == Path(".") else str(Path("~") / rel))


def _list_folders(base: Path, typed: str, blocked: Callable[[str], bool], deadline: float) -> tuple[list[str], bool]:
    """018 R19: subfolders of `base` whose names start with `typed` (case-insensitive). Dot-folders only when
    `typed` starts with `.`; names `Workspace._blocked` refuses are skipped. Stops at MAX_FOLDERS or the
    deadline. Returns (names, truncated)."""
    names, truncated = [], False
    folded = typed.casefold()
    with os.scandir(base) as entries:
        for entry in entries:
            if time.monotonic() > deadline:
                return sorted(names, key=str.casefold), True
            name = entry.name
            if not name.casefold().startswith(folded) or (name.startswith(".") and not typed.startswith(".")):
                continue
            if blocked(name):
                continue
            try:
                if not entry.is_dir():
                    continue
            except OSError:
                continue
            if len(names) >= MAX_FOLDERS:
                truncated = True
                break
            names.append(name)
    return sorted(names, key=str.casefold), truncated


def _in_daemon_thread(work: Callable[[], object]) -> asyncio.Future:
    """Run `work` on a daemon thread; the future gets its result. Unlike `asyncio.to_thread`, a listing still
    running when the session ends is abandoned at exit instead of joined (a home-folder walk can take minutes)."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def settle(ok: bool, value) -> None:
        if not future.done():
            future.set_result(value) if ok else future.set_exception(value)

    def run() -> None:
        try:
            ok, value = True, work()
        except BaseException as e:  # noqa: BLE001 - handed to the awaiting coroutine
            ok, value = False, e
        try:
            loop.call_soon_threadsafe(settle, ok, value)
        except RuntimeError:  # the loop closed meanwhile: nobody is waiting
            pass

    # An abandoned listing that fails later must not log "exception was never retrieved" over the screen.
    future.add_done_callback(lambda f: f.cancelled() or f.exception())
    threading.Thread(target=run, name="galliani-listing", daemon=True).start()
    return future


def _folder_refused(base: Path, root: Path) -> bool:
    """018 R19: whether the resolved folder must not be listed. Links, junctions and 8.3 short names (`GIT~1`)
    resolve to the real name, so protected names are checked again on the resolved path. Folders outside the
    workspace stay listable (`/workspace` chooses a new one), but never inside .git and the like."""
    try:
        resolved = base.resolve()
    except (OSError, RuntimeError):
        return True
    if resolved == root:
        return False
    if resolved.is_relative_to(root):
        return Workspace._blocked(resolved.relative_to(root).as_posix())
    return any(part.casefold() in BLOCKED_DIRS for part in resolved.parts)


def sanitize_plan(plan: PlanView | None) -> PlanView | None:
    """R18: a copy of the plan whose model-written text (step purposes, revision reason) is sanitized."""
    if plan is None:
        return None
    steps = [step.model_copy(update={"step_id": sanitize(step.step_id), "kind": sanitize(step.kind),
                                     "purpose": sanitize(step.purpose), "capability": sanitize(step.capability)})
             for step in plan.steps]
    reason = None if plan.revision_reason is None else sanitize(plan.revision_reason)
    return plan.model_copy(update={"steps": steps, "revision_reason": reason})


class Phase(str, Enum):
    idle = "idle"
    running = "running"
    awaiting_approval = "awaiting_approval"
    awaiting_answer = "awaiting_answer"
    canceling = "canceling"
    closed = "closed"


class EntryKind(str, Enum):
    user = "user"; plan = "plan"; route = "route"; tool = "tool"; verification = "verification"  # noqa: E702
    retry = "retry"; replan = "replan"; approval = "approval"; question = "question"; edit_mode = "edit_mode"  # noqa: E702
    event = "event"  # any other public event (verbose)
    result = "result"; usage = "usage"; notice = "notice"; error = "error"  # noqa: E702


@dataclass(frozen=True)
class TranscriptEntry:
    seq: int                      # 1-based, strictly increasing for the session
    kind: EntryKind
    text: str                     # sanitized (R18); one line or a short paragraph
    detail: tuple[str, ...] = ()  # extra sanitized lines (plan steps, files changed)
    body: str | None = None       # sanitized long text: the result output
    markdown: bool = False        # render `body` as Markdown (result only)
    verbose: bool = False         # shown only while verbose events are on
    task_id: str | None = None
    step_id: str | None = None


@dataclass(frozen=True)
class PendingApproval:
    action_summary: str
    risk_summary: str
    scope: str
    can_accept_edits: bool  # "approve_and_accept_edits" in allowed_choices


@dataclass(frozen=True)
class StatusSnapshot:
    workspace: Path
    route: str | None
    task_cost_usd: float
    session_cost_usd: float
    budget_usd: float | None  # None = no limit
    edit_mode: EditMode       # active task's mode, else the session default
    memory: Literal["on", "off", "unavailable"]
    verbose_events: bool
    status_label: str | None  # viewmodel.STATUS_LABELS value while a task is active


@dataclass(frozen=True)
class SessionState:
    phase: Phase
    status: StatusSnapshot
    plan: PlanView | None
    pending_approval: PendingApproval | None
    question: str | None
    cleared_after: int  # entries with seq <= this are hidden (/clear)


@dataclass(frozen=True)
class UiAction:
    kind: Literal["quit", "theme"]
    value: str | None = None  # theme name for "theme"


@dataclass
class SessionConfig:
    workspace: Path
    budget_usd: float | None = DEFAULT_BUDGET_USD
    memory_on: bool = True
    edit_mode: EditMode = EditMode.ask
    verbose_events: bool = False
    events_path: Path | None = None


RuntimeFactory = Callable[[SessionConfig, Sequence[EventSink], MemoryStore | None], Runtime]
Listener = Callable[[], None]  # "state or entries changed"; called on the event loop thread


def default_runtime(config: SessionConfig, sinks: Sequence[EventSink], memory: MemoryStore | None) -> Runtime:
    """R7: `build_runtime` with output discarded; keys come from `load_keys` inside it."""
    return build_runtime(config.workspace, out=lambda _: None, events_path=config.events_path,
                         budget_usd=config.budget_usd, sinks=sinks, memory=memory)


def _budget_label(budget: float | None) -> str:
    return "no limit" if budget is None else f"${budget:.2f} per task"


def _workspace_missing(path: Path) -> str:
    """The one-shot's message (galliani.cli.main)."""
    return (f"Workspace folder not found: {path.resolve()}\n"
            "Pass --workspace with an existing folder the agent may read (it can only touch files inside it).")


class _Sink:
    def __init__(self, session: Session):
        self.session = session

    def write(self, event: LifecycleEvent) -> None:
        self.session._on_event(event)


class Session:
    def __init__(self, config: SessionConfig, *, runtime_factory: RuntimeFactory | None = None,
                 memory: MemoryStore | None | Literal["open"] = "open") -> None:
        self.config = replace(config, workspace=Path(config.workspace))
        self._factory = runtime_factory or default_runtime
        self._memory_pending = memory == "open"  # opened once, the first time memory is needed (R7)
        self._memory: MemoryStore | None = None if memory == "open" else memory
        self._entries: list[TranscriptEntry] = []
        self._listeners: list[Listener] = []
        self._sink = _Sink(self)
        self._phase = Phase.idle
        self._runtime: Runtime | None = None
        self._runtime_stale = True
        self._idle = asyncio.Event()
        self._idle.set()  # no supervisor call in flight
        self._cleared_after = 0
        self._history: list[str] = []  # "- objective -> status: summary" lines for R9
        self._session_micro = 0
        self._files: tuple[Path, float, list[str], bool] | None = None  # 018 R20 cache: root, time, files, truncated
        self._files_pending: tuple[Path, asyncio.Future] | None = None  # the one file listing in flight
        self._reset_task()

        notes: list[str] = []
        if self.config.memory_on:
            self._ensure_memory(notes)
            if self._memory is None and not notes:
                notes.append("Memory is unavailable; continuing without it.")
        for note in notes:  # 018 R2: the banner (`banner()`) replaces 017's start notice
            self._add(EntryKind.notice, note)
        self._build_runtime()
        if self._runtime is not None and not self._runtime.available_workers:
            self._add(EntryKind.error, NO_KEYS)

    # ------------------------------------------------------------------ read side

    @property
    def state(self) -> SessionState:
        active = self._active
        status = StatusSnapshot(
            workspace=self.config.workspace,
            route=self._route,
            task_cost_usd=self._usage.cost_micro_usd / 1_000_000,
            session_cost_usd=self._session_micro / 1_000_000,
            budget_usd=self.config.budget_usd,
            edit_mode=self._task_mode if active else self.config.edit_mode,
            memory=self._memory_label(),
            verbose_events=self.config.verbose_events,
            status_label=self._status_label if active else None,
        )
        return SessionState(phase=self._phase, status=status, plan=self._plan, pending_approval=self._pending,
                            question=self._question, cleared_after=self._cleared_after)

    def entries(self, after: int = 0) -> list[TranscriptEntry]:
        """Entries with seq > `after` (and after the last /clear); verbose ones only while /events is on."""
        after = max(after, self._cleared_after)
        return [e for e in self._entries if e.seq > after and (self.config.verbose_events or not e.verbose)]

    def banner(self) -> BannerInfo:
        """018 R2, R25: the welcome banner. Provider names come from `load_keys().keys()` only, never values."""
        names = {env: name for name, env in PROVIDERS.items()}
        try:
            providers = tuple(sorted(names[env] for env in load_keys() if env in names))
        except Exception:  # noqa: BLE001 - an unreadable credential store means no provider is shown
            providers = ()
        workspace = self.config.workspace
        return BannerInfo(version=galliani.__version__, workspace=display_path(workspace), providers=providers,
                          wide_workspace=is_wide_workspace(workspace), edit_mode=self.config.edit_mode,
                          budget_usd=self.config.budget_usd, memory=self._memory_label())

    async def complete(self, text: str, cursor: int) -> CompletionResult | None:
        """018 R18-R21: `complete_command`, then the folders, files or memory ids it asks for. Listings run off the
        event loop thread with the R19/R20 bounds. Never raises: an error gives an empty, truncated result."""
        try:
            result = complete_command(text, cursor, task_active=self._active)
        except Exception:  # noqa: BLE001
            return None
        if result is None or result.needs_io is None:
            return result
        typed = text[result.start:max(result.start, min(cursor, len(text)))]
        try:
            if result.needs_io == "folder":
                filled = await self._complete_folders(result, typed)
            elif result.needs_io == "file":
                filled = await self._complete_files(result, typed[1:])
            else:
                filled = self._complete_memory_ids(result, typed)
        except Exception:  # noqa: BLE001 - permission denied, folder vanished, timeout (Error Handling)
            filled = replace(result, items=(), truncated=True)
        return replace(filled, needs_io=None)  # answered: nothing more to ask

    async def _complete_folders(self, result: CompletionResult, typed: str) -> CompletionResult:
        """018 R19: existing folders under the typed parent (workspace-relative, absolute or `~`), never files."""
        cut = max(typed.rfind("/"), typed.rfind("\\")) + 1
        parent, segment = typed[:cut], typed[cut:]
        if any(Workspace._blocked(part) for part in parent.replace("\\", "/").split("/") if part):
            return replace(result, items=())  # never list inside .git and the like
        base = Path(parent).expanduser() if parent else Path()
        if not base.is_absolute():
            base = self.config.workspace / base
        root = self.config.workspace
        deadline = time.monotonic() + LISTING_TIMEOUT

        def listing() -> tuple[list[str], bool]:
            if _folder_refused(base, root.resolve()):
                return [], False
            return _list_folders(base, segment, Workspace._blocked, deadline)
        try:
            names, truncated = await asyncio.wait_for(_in_daemon_thread(listing), LISTING_TIMEOUT + 0.5)
        except asyncio.TimeoutError:
            return replace(result, items=(), truncated=True)
        items = (safe_completion(f"{parent}{name}/", kind="folder") for name in names)
        return replace(result, items=tuple(i for i in items if i is not None), truncated=truncated)

    async def _complete_files(self, result: CompletionResult, typed: str) -> CompletionResult:
        """018 R20: workspace files from `Workspace.list_files` only (protected files and escaping links are never
        listed; 200 at most), prefix then substring matches."""
        files, truncated = await self._workspace_files()
        folded = typed.casefold()
        matches = [f for f in files if f.casefold().startswith(folded)] or \
                  [f for f in files if folded in f.casefold()]
        items = (safe_completion("@" + rel, kind="file") for rel in matches)
        return replace(result, items=tuple(i for i in items if i is not None), truncated=truncated)

    async def _workspace_files(self) -> tuple[list[str], bool]:
        """018 R20: the listing, cached in memory per workspace for 30 s. One listing runs at a time per workspace,
        however fast the typing, on a daemon thread so a slow one never delays exit."""
        root = self.config.workspace.resolve()
        cached = self._files
        if cached is not None and cached[0] == root and time.monotonic() - cached[1] < FILE_CACHE_SECONDS:
            return cached[2], cached[3]
        pending = self._files_pending
        if pending is None or pending[0] != root:
            future = _in_daemon_thread(lambda: Workspace(root).list_files(ListIn(path=".", pattern="*")))
            pending = self._files_pending = (root, future)
        try:
            listing = await asyncio.wait_for(asyncio.shield(pending[1]), FILE_LISTING_TIMEOUT)
        except asyncio.TimeoutError:
            return [], True
        finally:
            if pending[1].done() and self._files_pending is pending:
                self._files_pending = None
        files, truncated = list(listing["files"]), bool(listing["truncated"])
        if self.config.workspace.resolve() == root:  # not switched by /workspace meanwhile
            self._files = (root, time.monotonic(), files, truncated)
        return files, truncated

    def _complete_memory_ids(self, result: CompletionResult, typed: str) -> CompletionResult:
        """018 R18: ids of records in this session's scopes, with the summary `/memory list` shows (redacted)."""
        store = self._memory if self.config.memory_on else None
        if store is None:
            return replace(result, items=())
        records = [r for r in store.list(memory_scopes(self.config.workspace)) if r.id.startswith(typed)]
        items = (safe_completion(r.id, f"[{r.type}, {'user' if r.scope == 'user' else 'project'}] "
                                       f"{r.display_content()}", kind="memory_id", submits=True) for r in records)
        return replace(result, items=tuple(i for i in items if i is not None))

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)
        return unsubscribe

    # ------------------------------------------------------------------ actions

    async def submit(self, text: str) -> UiAction | None:
        """A slash command or an objective. Returns when the task stops running (finished or paused)."""
        if self._phase is Phase.closed:
            return None
        try:
            command = parse_command(text)
        except CommandError as e:
            self._add(EntryKind.error, str(e))
            return None
        if command is not None:
            try:
                return await self._command(command)
            except Exception as e:  # noqa: BLE001 - the controller never raises to the UI (R14)
                self._error(e)
                return None
        goal = text.strip()
        goal = goal[1:] if goal.startswith("//") else goal
        if not goal:
            return None
        if self._phase is not Phase.idle:
            self._add(EntryKind.notice, BUSY_NOTICE)
            return None
        await self._start(goal)
        return None

    async def approve(self, *, accept_edits: bool = False) -> None:
        if not self._expect(Phase.awaiting_approval, "There is no approval to answer."):
            return
        self._add(EntryKind.approval, "You approved and turned on accept-edits for this task." if accept_edits
                  else "You approved.", task_id=self._task_id)
        await self._call(lambda sup: sup.approve(self._task_id, accept_edits=accept_edits))

    async def deny(self) -> None:
        if not self._expect(Phase.awaiting_approval, "There is no approval to answer."):
            return
        self._add(EntryKind.approval, "You denied.", task_id=self._task_id)
        await self._call(lambda sup: sup.deny(self._task_id))

    async def answer(self, text: str) -> None:
        if not self._expect(Phase.awaiting_answer, "There is no question to answer."):
            return
        answer = text.strip()
        if not answer:
            self._add(EntryKind.notice, "Type an answer, or press Esc to cancel the task.")
            return
        self._add(EntryKind.question, f"You answered: {answer}", task_id=self._task_id)
        await self._call(lambda sup: sup.clarify(self._task_id, answer))

    def cancel(self) -> None:
        """Cooperative (R11): asks the supervisor to stop at its next checkpoint. Safe in any phase."""
        phase = self._phase
        if phase in (Phase.closed, Phase.canceling):
            return
        if phase is Phase.idle:
            self._add(EntryKind.notice, "No task is running.")
            return
        if self._task_id is None:  # not started yet; `_start` sees the request before calling the supervisor
            self._cancel_requested = True
            self._set_phase(Phase.canceling)
            return
        if phase is Phase.awaiting_answer:
            self._add(EntryKind.question, "You canceled the task.", task_id=self._task_id)
        try:
            result = self._supervisor.cancel(self._task_id)
        except Exception as e:  # noqa: BLE001
            self._error(e)
            return
        if phase is Phase.running:
            self._cancel_requested = True
            self._set_phase(Phase.canceling)
        else:  # paused: nothing is running, so the supervisor finished the task right away
            self._settle(result)

    async def aclose(self, timeout: float = 3.0) -> None:
        """R25 quit path: cancel an active task, wait at most `timeout` for the run to return, close."""
        if self._phase is Phase.closed:
            return
        if self._active:
            self.cancel()
        try:
            await asyncio.wait_for(self._idle.wait(), timeout)
        except asyncio.TimeoutError:
            pass  # the supervisor call is left to finish on its own; it is never asyncio-canceled (R11)
        await self._close_runtime()
        self._set_phase(Phase.closed)

    # ------------------------------------------------------------------ tasks

    @property
    def _active(self) -> bool:
        return self._phase in (Phase.running, Phase.awaiting_approval, Phase.awaiting_answer, Phase.canceling)

    def _reset_task(self) -> None:
        self._task_id: str | None = None
        self._supervisor = None  # the supervisor running this task, kept even if the runtime is closed
        self._goal = ""
        self._task_mode = self.config.edit_mode
        self._usage = UsageTotals()
        self._route: str | None = None
        self._plan: PlanView | None = None
        self._pending: PendingApproval | None = None
        self._question: str | None = None
        self._status_label: str | None = None
        self._cancel_requested = False

    async def _start(self, goal: str) -> None:
        self._reset_task()
        self._goal = goal
        self._add(EntryKind.user, goal)
        self._set_phase(Phase.running)
        self._idle.clear()
        try:
            await self._ensure_runtime()
            if self._runtime is None:
                self._set_phase(Phase.idle)
                return
            if not self._runtime.available_workers:
                self._add(EntryKind.error, NO_KEYS)
                self._runtime_stale = True  # a key may be added before the next try
                self._set_phase(Phase.idle)
                return
            if self._cancel_requested:
                self._add(EntryKind.notice, "Task canceled before it started.")
                self._set_phase(Phase.idle)
                return
            self._supervisor = self._runtime.supervisor
            request = StartTaskRequest(
                objective=Objective(goal=goal, context=self._context()),
                user_policy=UserPolicy(edit_mode=self.config.edit_mode),
                memory_scopes=memory_scopes(self.config.workspace))
            await self._call(lambda sup: sup.start(request), track=False)
        finally:
            self._idle.set()

    def _context(self) -> str:
        """R9: the workspace listing, then up to 3 earlier tasks of this session, as data."""
        context = workspace_overview(self.config.workspace)
        if self._history:
            context += "\n\nEarlier tasks in this session:\n" + "\n".join(self._history[-EARLIER_TASKS:])
        return context

    async def _call(self, call: Callable, *, track: bool = True) -> None:
        """Run one supervisor call; settle the result; turn any exception into an error entry (R14)."""
        supervisor = self._supervisor
        resume = self._phase
        self._set_phase(Phase.running)
        if track:
            self._idle.clear()
        try:
            result = await call(supervisor)
            if self._phase is Phase.closed:
                return  # returned after the quit timeout: the session is gone
            if self._cancel_requested and result.status is TaskStatus.waiting_for_user:
                result = supervisor.cancel(result.task_id)  # paused before the checkpoint saw the cancel
            self._settle(result)
        except Exception as e:  # noqa: BLE001 - the controller never raises to the UI (R14)
            if self._phase is not Phase.closed:
                self._error(e)
                self._recover(resume)
        finally:
            if track:
                self._idle.set()

    def _recover(self, resume: Phase) -> None:
        """After an exception: stay paused if the supervisor still waits, else finish or go idle."""
        try:
            result = self._supervisor.get(self._task_id) if self._task_id else None
        except Exception:  # noqa: BLE001
            result = None
        if result is not None and (result.status is TaskStatus.waiting_for_user
                                   or result.status in TERMINAL_STATUSES or result.status is TaskStatus.blocked):
            if result.status is TaskStatus.waiting_for_user and resume in (Phase.awaiting_approval, Phase.awaiting_answer):
                self._set_phase(resume)  # e.g. accept-edits on an ineligible prompt: the prompt stays open
            else:
                self._settle(result)
            return
        self._runtime_stale = True  # the next submit rebuilds the runtime (Error Handling)
        self._pending = self._question = None
        self._set_phase(Phase.idle)

    def _view(self, task_id: str) -> TaskViewModel:
        supervisor = self._supervisor
        return build_task_view(supervisor.store.get(task_id), usage=supervisor.ledger.totals(task_id),
                               memory_used=supervisor.memory_used(task_id))

    def _settle(self, result: TaskResult) -> None:
        self._task_id = result.task_id
        view = self._view(result.task_id)
        self._plan = sanitize_plan(view.plan)
        self._task_mode = view.edit_mode
        self._status_label = view.status_label
        self._pending = self._question = None
        if result.status is TaskStatus.waiting_for_user and view.approval_prompt is not None:
            prompt = view.approval_prompt  # from TaskState.for_display(): redacted (R17)
            self._pending = PendingApproval(
                action_summary=sanitize(prompt.action_summary), risk_summary=sanitize(prompt.risk_summary),
                scope=sanitize(prompt.scope), can_accept_edits=ACCEPT_EDITS_CHOICE in prompt.allowed_choices)
            self._add(EntryKind.approval, f"Approval needed: {prompt.action_summary}",
                      detail=(f"risk: {prompt.risk_summary}", f"scope: {prompt.scope}"), task_id=result.task_id)
            self._set_phase(Phase.awaiting_approval)
        elif result.status is TaskStatus.waiting_for_user and view.clarification:
            self._question = sanitize(view.clarification)
            self._add(EntryKind.question, f"Question: {view.clarification}", task_id=result.task_id)
            self._set_phase(Phase.awaiting_answer)
        elif view.terminal:
            self._finish(view)
        else:  # not paused and not finished: nothing more will happen for this task
            self._add(EntryKind.notice, f"The task stopped while {view.status.value}.", task_id=result.task_id)
            self._set_phase(Phase.idle)

    def _finish(self, view: TaskViewModel) -> None:
        """R19: the result entry and a usage line; the task's outcome becomes context for later tasks (R9)."""
        result = view.result
        summary = result.summary if result else view.status_label
        detail = []
        if result is not None and result.verification is not None:
            detail.append(f"Verification: {result.verification.status} - {result.verification.reason_summary}")
        detail += [f"{f.change}: {f.path}" for f in view.files_changed]
        if view.edits_auto_approved:
            detail.append(f"edits auto-approved: {view.edits_auto_approved}")
        body = None
        if result is not None:
            # Built from TaskState.for_display(); the raw TaskResult.output is never rendered (R17).
            body = result.output if result.output_kind == "text" else result.preview
        if body is not None:
            body = sanitize(body)
            if len(body) > MAX_BODY_CHARS:
                body = body[:MAX_BODY_CHARS] + f"\n\n({len(body) - MAX_BODY_CHARS} more characters not shown)"
        self._add(EntryKind.result, f"Status: {view.status.value} - {summary}", detail=tuple(detail), body=body,
                  markdown=body is not None, task_id=view.task_id)
        self._add(EntryKind.usage, self._usage.summary(), task_id=view.task_id)
        self._history.append(f"- {self._goal} -> {view.status.value}: {summary}")
        self._set_phase(Phase.idle)

    # ------------------------------------------------------------------ events

    def _on_event(self, event: LifecycleEvent) -> None:
        """Lifecycle events are already redacted (011); entries are sanitized on top (R18)."""
        if self._task_id is None and event.type is EventType.task_created:
            self._task_id = event.task_id
        if event.task_id != self._task_id:
            return
        meta = event.metadata
        step = event.refs.step_id
        if event.type is EventType.worker_completed:
            usage = meta.get("usage") or {}
            self._usage.add(usage)
            self._session_micro += int(usage.get("cost_micro_usd", 0))
        elif event.type is EventType.route_selected and meta.get("worker_id"):
            self._route = sanitize(str(meta["worker_id"]))
        elif event.type is EventType.edit_mode_changed and meta.get("edit_mode") in {m.value for m in EditMode}:
            self._task_mode = EditMode(meta["edit_mode"])
        elif event.type is EventType.status_changed and meta.get("to") in {s.value for s in TaskStatus}:
            self._status_label = STATUS_LABELS[TaskStatus(meta["to"])]
        if event.type in (EventType.plan_created, EventType.plan_revised, EventType.status_changed):
            self._refresh_plan()

        if event.type in (EventType.plan_created, EventType.plan_revised):
            verb = "Plan" if event.type is EventType.plan_created else "Revised plan"
            steps = tuple(f"{s.get('id')} ({s.get('kind')}: {s.get('capability')}) {s.get('purpose')}"
                          for s in meta.get("steps", []) if isinstance(s, dict))
            self._add(EntryKind.plan, f"{verb} v{meta.get('version', '?')}: {event.public_summary}", detail=steps,
                      task_id=event.task_id, step_id=step)
        elif event.type is EventType.task_finished:
            pass  # shown as the result entry once the supervisor call returns (R19)
        elif event.type in SHOWN_EVENTS:
            kind = {EventType.route_selected: EntryKind.route, EventType.route_fallback: EntryKind.route,
                    EventType.tool_called: EntryKind.tool, EventType.verification_completed: EntryKind.verification,
                    EventType.retry_scheduled: EntryKind.retry, EventType.replan_started: EntryKind.replan}[event.type]
            self._add(kind, event.public_summary, task_id=event.task_id, step_id=step)
        elif event.type is EventType.edit_mode_changed:
            self._add(EntryKind.edit_mode, event.public_summary, task_id=event.task_id)
        else:
            self._add(EntryKind.event, f"{event.type.value}: {event.public_summary}", verbose=True,
                      task_id=event.task_id, step_id=step)

    def _refresh_plan(self) -> None:
        try:
            self._plan = sanitize_plan(self._view(self._task_id).plan)
        except Exception:  # noqa: BLE001 - a view refresh never breaks the run
            pass

    # ------------------------------------------------------------------ commands

    async def _command(self, command: Command) -> UiAction | None:
        if self._active and not _allowed_while_active(command):
            shown = " ".join(("/" + command.name, *command.args[:1]))
            self._add(EntryKind.notice, f"{shown} is not available while a task is active. "
                                        "Wait for it, answer it, or press Esc to stop it.")
            return None
        name, args = command.name, command.args
        if name == "help":
            self._add(EntryKind.notice, "Commands (start a line with // to send it as an objective):",
                      detail=(*(f"{c.usage} - {c.summary}" for c in COMMANDS.values()), KEYS_HELP))
        elif name == "clear":
            self._cleared_after = self._entries[-1].seq if self._entries else 0
            self._changed()
        elif name == "quit":
            return UiAction("quit")
        elif name == "theme":
            if not args:
                self._add(EntryKind.notice, "Themes: /theme dark or /theme light.")
                return None
            return UiAction("theme", args[0])
        elif name == "events":
            if args:
                self.config.verbose_events = args[0] == "on"
            self._add(EntryKind.notice, f"Verbose events: {'on' if self.config.verbose_events else 'off'}.")
        elif name == "edit-mode":
            self._edit_mode(args)
        elif name == "workspace":
            self._workspace(args)
        elif name == "budget":
            if args:
                value = None if args[0] == "off" else float(args[0])
                if value is not None and value < 0:
                    self._add(EntryKind.notice, "Budget cannot be negative. Use /budget off for no limit.")
                    return None
                self.config.budget_usd = value if value is not None and value > 0 else None
                self._runtime_stale = True
            self._add(EntryKind.notice, f"Budget: {_budget_label(self.config.budget_usd)}"
                                        + (" (applies to the next task)." if args else "."))
        elif name == "memory":
            self._memory_command(args)
        return None

    def _edit_mode(self, args: tuple[str, ...]) -> None:
        if not args:
            current = f"Edit mode: {self._mode_label(self.config.edit_mode)} for new tasks"
            if self._active:
                current += f"; this task: {self._mode_label(self._task_mode)}"
            self._add(EntryKind.notice, current + ".")
            return
        mode = EditMode.accept_edits if args[0] == "accept-edits" else EditMode.ask
        self.config.edit_mode = mode  # this session only, never persisted (014 R9)
        message = f"Edit mode for new tasks: {self._mode_label(mode)}"
        if self._active and self._task_id is not None:
            try:
                self._supervisor.set_edit_mode(self._task_id, mode)  # 014 R7
                self._task_mode = mode
                message += " (this task too)"
            except GallianiError as e:
                self._error(e)
        self._add(EntryKind.notice, message + ".")

    def _workspace(self, args: tuple[str, ...]) -> None:
        if args:
            path = Path(args[0]).expanduser()
            if not path.is_dir():
                self._add(EntryKind.error, _workspace_missing(path))
                return
            self.config.workspace = path
            self._runtime_stale = True
            self._files = self._files_pending = None  # 018 R20: the file cache belongs to the old workspace
        self._add(EntryKind.notice, f"Workspace: {self.config.workspace.resolve()}"
                                    + (" (applies to the next task)." if args else "."))

    def _memory_command(self, args: tuple[str, ...]) -> None:
        sub = args[0] if args else "list"
        if sub in ("on", "off"):
            self.config.memory_on = sub == "on"
            if self.config.memory_on:
                self._ensure_memory()
            self._runtime_stale = True
            self._add(EntryKind.notice, f"Memory: {self._memory_label()} (applies to the next task).")
            return
        store = self._ensure_memory()
        if store is None:
            self._add(EntryKind.error, "Memory is unavailable in this session.")
            return
        scopes = memory_scopes(self.config.workspace)
        records = store.list(scopes)
        if sub == "list":
            if not records:
                self._add(EntryKind.notice, "No memory records for you or this workspace.")
                return
            self._add(EntryKind.notice, f"{len(records)} memory record(s) for you and this workspace:",
                      detail=tuple(f"{r.id} [{r.type}, {'user' if r.scope == 'user' else 'project'}] "
                                   f"{r.display_content()}" for r in records))  # sensitive ones redacted (010)
            return
        record_id = args[1]
        if not any(r.id == record_id for r in records):
            self._add(EntryKind.error, f"No memory record {record_id} for you or this workspace; nothing deleted.")
            return
        if store.delete(record_id):
            self._add(EntryKind.notice, f"Forgot memory record {record_id}.")
        else:
            self._add(EntryKind.error, f"Memory record {record_id} could not be deleted.")

    # ------------------------------------------------------------------ runtime and memory

    def _ensure_memory(self, notes: list[str] | None = None) -> MemoryStore | None:
        """Open memory once per session (R7); `open_memory`'s message becomes a notice."""
        if self._memory_pending:
            self._memory_pending = False
            messages: list[str] = []
            self._memory = open_memory(out=messages.append)
            if notes is not None:
                notes.extend(messages)
            else:
                for message in messages:
                    self._add(EntryKind.notice, message)
        return self._memory

    def _memory_label(self) -> Literal["on", "off", "unavailable"]:
        if not self.config.memory_on:
            return "off"
        return "unavailable" if self._memory is None and not self._memory_pending else "on"

    def _build_runtime(self) -> None:
        memory = self._memory if self.config.memory_on else None
        try:
            self._runtime = self._factory(replace(self.config), [self._sink], memory)
            self._runtime_stale = False
        except Exception as e:  # noqa: BLE001
            self._runtime = None
            self._error(e)

    async def _ensure_runtime(self) -> None:
        """R8: settings `build_runtime` fixes apply to the next task by rebuilding while idle."""
        if self._runtime is not None and not self._runtime_stale:
            return
        await self._close_runtime()
        self._build_runtime()

    async def _close_runtime(self) -> None:
        runtime, self._runtime = self._runtime, None
        if runtime is not None:
            try:
                await runtime.aclose()
            except Exception:  # noqa: BLE001 - closing never fails the session
                pass

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _mode_label(mode: EditMode) -> str:
        return "accept-edits" if mode is EditMode.accept_edits else "ask"

    def _expect(self, phase: Phase, message: str) -> bool:
        if self._phase is phase:
            return True
        if self._phase is not Phase.closed:
            self._add(EntryKind.notice, message)
        return False

    def _error(self, e: Exception) -> None:
        """Only the exception type, plus `safe_summary` for GallianiError (R14)."""
        text = f"{type(e).__name__}: {e.safe_summary}" if isinstance(e, GallianiError) else \
            f"Unexpected error ({type(e).__name__})."
        self._add(EntryKind.error, text, task_id=self._task_id)

    def _set_phase(self, phase: Phase) -> None:
        if self._phase is Phase.closed:
            return  # a supervisor call that outlived the quit timeout cannot reopen the session
        self._phase = phase
        self._changed()

    def _add(self, kind: EntryKind, text: str, *, detail: Sequence[str] = (), body: str | None = None,
             markdown: bool = False, verbose: bool = False, task_id: str | None = None,
             step_id: str | None = None) -> None:
        seq = self._entries[-1].seq + 1 if self._entries else 1
        self._entries.append(TranscriptEntry(
            seq=seq, kind=kind, text=sanitize(text), detail=tuple(sanitize(d) for d in detail),
            body=body if body is None else sanitize(body), markdown=markdown, verbose=verbose,
            task_id=task_id, step_id=step_id))
        self._changed()

    def _changed(self) -> None:
        for listener in list(self._listeners):
            try:
                listener()
            except Exception:  # noqa: BLE001 - a UI callback never breaks the controller (R14)
                pass
