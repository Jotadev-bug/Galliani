"""A scripted stand-in for `galliani.tui.session.Session`, coded against spec 017 Interfaces and Data Contracts.

It lets the Pilot tests drive the Textual layer without a supervisor. It uses the real session types when
`galliani.tui.session` is importable and defines same-shaped local ones otherwise.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from galliani.permissions import EditMode
from galliani.viewmodel import PlanView, StepView

try:  # pragma: no cover - exercised once the controller lands
    from galliani.tui.session import (
        EntryKind, PendingApproval, Phase, SessionState, StatusSnapshot, TranscriptEntry, UiAction,
    )
except ImportError:
    class Phase(str, Enum):
        idle = "idle"
        running = "running"
        awaiting_approval = "awaiting_approval"
        awaiting_answer = "awaiting_answer"
        canceling = "canceling"
        closed = "closed"

    class EntryKind(str, Enum):
        user = "user"; plan = "plan"; route = "route"; tool = "tool"; verification = "verification"
        retry = "retry"; replan = "replan"; approval = "approval"; question = "question"
        edit_mode = "edit_mode"; event = "event"; result = "result"; usage = "usage"
        notice = "notice"; error = "error"

    @dataclass(frozen=True)
    class TranscriptEntry:
        seq: int
        kind: EntryKind
        text: str
        detail: tuple[str, ...] = ()
        body: str | None = None
        markdown: bool = False
        verbose: bool = False
        task_id: str | None = None
        step_id: str | None = None

    @dataclass(frozen=True)
    class PendingApproval:
        action_summary: str
        risk_summary: str
        scope: str
        can_accept_edits: bool

    @dataclass(frozen=True)
    class StatusSnapshot:
        workspace: Path
        route: str | None
        task_cost_usd: float
        session_cost_usd: float
        budget_usd: float | None
        edit_mode: EditMode
        memory: str
        verbose_events: bool
        status_label: str | None

    @dataclass(frozen=True)
    class SessionState:
        phase: Phase
        status: StatusSnapshot
        plan: PlanView | None
        pending_approval: PendingApproval | None
        question: str | None
        cleared_after: int

    @dataclass(frozen=True)
    class UiAction:
        kind: str
        value: str | None = None


try:  # spec 018 contracts; same-shaped local ones keep the Pilot tests independent of the headless layer
    from galliani.tui.commands import Completion, CompletionResult
    HAVE_COMPLETION = True
except ImportError:
    HAVE_COMPLETION = False

    @dataclass(frozen=True)
    class Completion:  # type: ignore[no-redef]
        insert: str
        label: str
        summary: str = ""
        kind: str = "command"
        enabled: bool = True
        submits: bool = False

    @dataclass(frozen=True)
    class CompletionResult:  # type: ignore[no-redef]
        start: int
        items: tuple = ()
        needs_io: str | None = None
        truncated: bool = False

try:
    from galliani.tui.session import BannerInfo
except ImportError:
    @dataclass(frozen=True)
    class BannerInfo:  # type: ignore[no-redef]
        version: str
        workspace: str
        providers: tuple[str, ...]
        wide_workspace: bool
        edit_mode: EditMode
        budget_usd: float | None
        memory: str

_COMMANDS = {  # name -> (summary, takes_no_argument, allowed_while_active)
    "help": ("list commands and keys", True, True), "clear": ("clear the visible transcript", True, True),
    "workspace": ("show, or switch to an existing folder", False, False),
    "edit-mode": ("show or set the edit mode", False, True), "budget": ("show or set the per-task budget", False, False),
    "memory": ("list or forget memory records", False, True), "events": ("show or hide verbose events", False, True),
    "theme": ("switch the theme for this session", False, True), "quit": ("quit Galliani", True, True),
}
_CHOICES = {"theme": ("dark", "light"), "events": ("on", "off"), "edit-mode": ("ask", "accept-edits"),
            "memory": ("list", "forget", "on", "off")}


def stand_in_complete_command(text: str, cursor: int, *, task_active: bool):
    """A small copy of the spec 018 `complete_command` contract, used only while commands.py predates it."""
    head = text[:cursor]
    if head.startswith("//"):
        return None
    if not head.startswith("/"):
        start = max(head.rfind(c) for c in (" ", chr(9), chr(10))) + 1
        return CompletionResult(start=start, items=(), needs_io="file") if head[start:start + 1] == "@" else None
    name, space, rest = head[1:].partition(" ")
    if not space:
        names = [n for n in _COMMANDS if n.startswith(name.lower())] or [n for n in _COMMANDS if name.lower() in n]
        items = tuple(Completion(f"/{n}" if _COMMANDS[n][1] else f"/{n} ", f"/{n}", _COMMANDS[n][0], "command",
                                 not task_active or _COMMANDS[n][2], _COMMANDS[n][1]) for n in names)
        return CompletionResult(start=0, items=items)
    if name == "workspace":
        return CompletionResult(start=cursor - len(rest), items=(), needs_io="folder")
    choices = [c for c in _CHOICES.get(name, ()) if c.startswith(rest)]
    items = tuple(Completion(c, c, "", "argument", True, True) for c in choices)
    return CompletionResult(start=cursor - len(rest), items=items) if items else None


def plan_view(version: int = 1, states: tuple[str, ...] = ("pending", "pending", "pending", "pending")) -> PlanView:
    purposes = ("Read the notes", "Draft the summary", "Write summary.md", "Check the summary")
    steps = [StepView(step_id=f"s{i}", kind="tool", purpose=purposes[i], capability="x", state=state, attempts=1)
             for i, state in enumerate(states)]
    return PlanView(version=version, steps=steps)


@dataclass
class FakeSession:
    """Scenarios: `basic`, `approval`, `question`, `hold`. Calls the UI makes are recorded in `calls`."""

    scenario: str = "basic"
    can_accept_edits: bool = True
    workspace: Path = field(default_factory=lambda: Path("C:/work/notes"))
    result_body: str = "Done.\n\n- one\n- two"
    edit_mode: EditMode = EditMode.ask
    calls: list[tuple] = field(default_factory=list)
    _entries: list[TranscriptEntry] = field(default_factory=list)
    _listeners: list[Callable[[], None]] = field(default_factory=list)
    _phase: Phase = Phase.idle
    _plan: PlanView | None = None
    _pending: PendingApproval | None = None
    _question: str | None = None
    _cleared: int = 0
    _verbose: bool = False
    _status_label: str | None = None
    _cost: float = 0.0
    _release: asyncio.Event = field(default_factory=asyncio.Event)
    banner_info: BannerInfo | None = None
    completions: Callable[[str, int], CompletionResult | None] | None = None
    complete_delay: float = 0.0

    # ---- contract

    @property
    def state(self) -> SessionState:
        status = StatusSnapshot(
            workspace=self.workspace, route="mock-1" if self._cost else None, task_cost_usd=self._cost,
            session_cost_usd=self._cost, budget_usd=0.5, edit_mode=self.edit_mode, memory="on",
            verbose_events=self._verbose, status_label=self._status_label)
        return SessionState(phase=self._phase, status=status, plan=self._plan, pending_approval=self._pending,
                            question=self._question, cleared_after=self._cleared)

    def entries(self, after: int = 0) -> list[TranscriptEntry]:
        return [e for e in self._entries if e.seq > after and (self._verbose or not e.verbose)]

    def subscribe(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener) if listener in self._listeners else None

    async def submit(self, text: str) -> UiAction | None:
        self.calls.append(("submit", text))
        if text.startswith("//"):
            text = text[1:]
        elif text.startswith("/"):
            return self._command(text)
        if self._phase != Phase.idle:
            self._add(EntryKind.notice, "A task is still running. Answer it, wait for it, or press Esc to stop it.")
            return None
        self._add(EntryKind.user, text)
        await self._run()
        return None

    async def approve(self, *, accept_edits: bool = False) -> None:
        self.calls.append(("approve", accept_edits))
        if self._pending is None:
            return
        if accept_edits and not self._pending.can_accept_edits:
            self._add(EntryKind.error, "ContractError: that choice is not offered")
            return
        self._add(EntryKind.approval, "Approved" + (" and accept edits" if accept_edits else ""))
        self._pending = None
        if accept_edits:
            self.edit_mode = EditMode.accept_edits
        self._finish("done", "Wrote summary.md")

    async def deny(self) -> None:
        self.calls.append(("deny",))
        if self._pending is None:
            return
        self._add(EntryKind.approval, "Denied")
        self._pending = None
        self._finish("blocked", "The write was not approved")

    async def answer(self, text: str) -> None:
        self.calls.append(("answer", text))
        if self._question is not None:
            self._question = None
            self._add(EntryKind.question, f"Answer: {text}")
            self._phase = Phase.running
            self._notify()
            await asyncio.sleep(0)
            self._finish("done", f"Summarized {text}")

    def cancel(self) -> None:
        self.calls.append(("cancel",))
        if self._phase in (Phase.running, Phase.awaiting_approval, Phase.awaiting_answer):
            self._pending = None
            self._question = None
            self._phase = Phase.canceling
            if self.scenario != "hold":
                self._finish("canceled", "Canceled")
            self._notify()

    async def aclose(self, timeout: float = 3.0) -> None:
        self.calls.append(("aclose", timeout))
        if self._phase not in (Phase.idle, Phase.closed):
            self.cancel()
        self._phase = Phase.closed
        self._notify()

    def banner(self) -> BannerInfo:
        return self.banner_info or BannerInfo(
            version="0.2.0", workspace="~/projects/notes", providers=("anthropic", "openai"), wide_workspace=False,
            edit_mode=self.edit_mode, budget_usd=0.5, memory="on")

    async def complete(self, text: str, cursor: int) -> CompletionResult | None:
        """Scripted `Session.complete`: `completions(text, cursor)` decides, after an optional delay."""
        self.calls.append(("complete", text))
        if self.complete_delay:
            await asyncio.sleep(self.complete_delay)
        return self.completions(text, cursor) if self.completions else None

    # ---- test helpers

    def set_plan(self, states: tuple[str, ...], phase: Phase | None = None) -> None:
        """Move the plan (and optionally the phase) like the supervisor would, then notify the UI."""
        self._plan = plan_view(1, states)
        if phase is not None:
            self._phase = phase
        self._notify()

    def finish_hold(self) -> None:
        """Let a held run return after `cancel()` (the supervisor reached its next checkpoint)."""
        self._release.set()

    # ---- scripting

    def _command(self, text: str) -> UiAction | None:
        name, _, arg = text[1:].partition(" ")
        arg = arg.strip()
        if name == "quit":
            return UiAction("quit")
        if name == "clear":
            self._cleared = self._entries[-1].seq if self._entries else 0
        elif name == "theme":
            if arg in ("dark", "light"):
                return UiAction("theme", arg)
            self._add(EntryKind.error, "Usage: /theme [dark|light]")
        elif name == "events":
            if arg in ("on", "off", ""):
                self._verbose = arg != "off" if arg else not self._verbose
                self._add(EntryKind.event, "Detail event: route_selected", verbose=True)
                self._add(EntryKind.notice, f"Verbose events {'on' if self._verbose else 'off'}")
            else:
                self._add(EntryKind.error, "Usage: /events [on|off]")
        else:
            self._add(EntryKind.error, f"Unknown command /{name}. Usage: /help")
        self._notify()
        return None

    async def _run(self) -> None:
        self._phase = Phase.running
        self._status_label = "Planning"
        self._plan = plan_view(1)
        self._add(EntryKind.plan, "Plan v1", detail=("1. Read the notes", "2. Draft the summary",
                                                     "3. Write summary.md", "4. Check the summary"))
        await asyncio.sleep(0)
        if self.scenario == "hold":
            self._status_label = "Working"
            self._plan = plan_view(1, ("running", "pending", "pending", "pending"))
            self._notify()
            self._release.clear()
            await self._release.wait()
            self._finish("canceled", "Canceled")
            return
        self._cost = 0.0123
        self._status_label = "Working"
        self._plan = plan_view(1, ("verified", "running", "pending", "pending"))
        self._add(EntryKind.tool, "read_file notes.txt: ok")
        self._add(EntryKind.verification, "Check passed: step 1")
        if self.scenario == "approval":
            self._plan = plan_view(1, ("verified", "verified", "waiting", "pending"))
            self._pending = PendingApproval("Write summary.md", "Writes a file in the workspace",
                                            "workspace", self.can_accept_edits)
            self._phase = Phase.awaiting_approval
            self._status_label = "Needs your input"
            self._add(EntryKind.approval, "Approval needed: Write summary.md")
            self._notify()
            return
        if self.scenario == "question":
            self._question = "Which file should I summarize?"
            self._phase = Phase.awaiting_answer
            self._add(EntryKind.question, "Which file should I summarize?")
            self._notify()
            return
        self._finish("done", "Summary written")

    def _finish(self, status: str, summary: str) -> None:
        self._plan = plan_view(1, ("verified",) * 4 if status == "done" else ("verified", "failed", "canceled", "canceled"))
        self._status_label = None
        self._add(EntryKind.result, f"Result: {status} - {summary}", detail=("Files changed: created summary.md",),
                  body=self.result_body, markdown=True)
        self._add(EntryKind.usage, f"Usage: ${self._cost:.4f}")
        self._phase = Phase.idle
        self._notify()

    def _add(self, kind: EntryKind, text: str, *, detail: tuple[str, ...] = (), body: str | None = None,
             markdown: bool = False, verbose: bool = False) -> None:
        seq = self._entries[-1].seq + 1 if self._entries else 1
        self._entries.append(TranscriptEntry(seq=seq, kind=kind, text=text, detail=detail, body=body,
                                             markdown=markdown, verbose=verbose))
        self._notify()

    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

