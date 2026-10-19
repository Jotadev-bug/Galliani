"""Widgets for the terminal UI (spec 017 R20-R24, R28, R29; spec 018 R1-R14, R16, R17).

Everything shown here arrives already redacted and sanitized by the session (R17, R18). The widgets add a
second line of defence: text is always wrapped in `rich.text.Text` and shown with `markup=False`, so nothing
untrusted is ever parsed as Rich or Textual markup, and Markdown never opens a link.

Colour lives in `styles.py` only (CSS classes on `$g-*` variables). Rich styles here are limited to
`bold`, `dim` and `italic`, so no colour literal exists in this module (spec 018 R1).
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any, Literal

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Input, Markdown, Static, TextArea

MAX_BODY_CHARS = 20_000
HISTORY_LIMIT = 100
DOCK_MIN_WIDTH = 100      # R20: plan panel docks at this width or more
NARROW_MIN_WIDTH = 60     # R20: below this, a one-line notice asks for a wider terminal

# ---- spec 018 R7: every glyph below is in the WGL4 set (Consolas and Cascadia Mono draw it).
SPINNER_FRAMES = ("·", "•", "●", "•")
SPINNER_STATIC = "●"
SPINNER_FPS = 4.0               # calm: a quarter of the 10 Hz ceiling
TICK_HZ = 10.0                  # R9 ceiling while a task is active and motion is on
TICK_HZ_STATIC = 1.0            # R9: elapsed time and cost only, motion off
VERB_SECONDS = 3.0              # R10
HIGHLIGHT_SECONDS = 0.4         # R11
CARD_ENTER_SECONDS = 0.18       # R12: 150-200 ms
CARD_ENTER_ROWS = 2             # R12: from 1-2 rows below
POPUP_ROWS = 8
NOT_WHILE_ACTIVE = "(not while a task runs)"

LEADERS = {
    "user": ">", "plan": "●", "route": "·", "tool": "●", "verification": "●", "retry": "·", "replan": "·",
    "approval": "?", "question": "?", "edit_mode": "·", "event": "·", "result": "●", "usage": "·",
    "notice": "·", "error": "●",
}
GAP_BEFORE = {"user"}
STEP_GLYPHS = {"pending": "...", "running": ">", "waiting": "[?]", "verified": "[ok]", "failed": "[x]",
               "canceled": "[-]"}
FINISHED_STEPS = frozenset({"verified", "failed", "canceled"})
PHASE_LABELS = {
    "idle": "Ready", "running": "Working", "awaiting_approval": "Needs your approval",
    "awaiting_answer": "Needs your input", "canceling": "Canceling", "closed": "Closed",
}
ACTIVE_PHASES = frozenset({"running", "canceling", "awaiting_approval", "awaiting_answer"})
SETTLED_PHASES = frozenset({"idle", "closed"})

# R10: fixed UI strings per phase. They are not model output and imply nothing about reasoning.
VERBS = {
    "planning": ("Planning", "Outlining", "Mapping the steps", "Sequencing"),
    "running": ("Working", "Gathering", "Assembling", "Working through it"),
    "verifying": ("Verifying", "Checking", "Comparing", "Confirming"),
    "waiting": ("Waiting for you",),
    "canceling": ("Canceling", "Stopping safely"),
}
_PLANNING_LABELS = frozenset({"Starting", "Planning", "Revising the plan"})
_VERIFYING_LABELS = frozenset({"Checking the result"})


def value_of(item: Any) -> str:
    """The plain string of an enum member or string."""
    return str(getattr(item, "value", item))


def motion_enabled(app: Any) -> bool:
    """R8: the one gate for every timer-driven or animated effect.

    False under `GALLIANI_REDUCED_MOTION=1`, animation level `none`, `NO_COLOR`, the ANSI theme, or after
    the ticker failed once. `TEXTUAL_ANIMATIONS` alone does not stop `set_interval`, so callers ask here."""
    if os.environ.get("GALLIANI_REDUCED_MOTION") == "1":
        return False
    if getattr(app, "animation_level", "full") == "none":
        return False
    if os.environ.get("NO_COLOR") is not None or getattr(app, "no_color", False):
        return False
    if getattr(app, "theme", "") == "galliani-ansi":
        return False
    return not getattr(app, "motion_failed", False)


# ---------------------------------------------------------------- ticker

class Ticker:
    """R9: the only interval timer the app owns. Stopped (and `running` False) unless `sync` wants it."""

    def __init__(self, app: Any, callback: Callable[[], None]) -> None:
        self._app = app
        self._callback = callback
        self._timer: Timer | None = None
        self.hz = 0.0
        self.ticks = 0

    @property
    def running(self) -> bool:
        return self._timer is not None

    def sync(self, wanted: bool, hz: float) -> None:
        if not wanted:
            self.stop()
        elif self._timer is None or hz != self.hz:
            self.stop()
            self.hz = hz
            self._timer = self._app.set_interval(1.0 / hz, self.fire)

    def fire(self) -> None:
        self.ticks += 1
        self._callback()

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        self.hz = 0.0


# ---------------------------------------------------------------- working line and status line

def edit_mode_word(mode: Any) -> str:
    return value_of(mode).replace("_", "-")


def budget_text(budget_usd: float | None) -> str:
    return "no limit" if budget_usd is None else f"${budget_usd:.2f}"


def phase_text(phase: Any, status_label: str | None) -> str:
    name = value_of(phase)
    if name == "running" and status_label:
        return status_label
    return PHASE_LABELS.get(name, name)


def phase_group(phase: Any, status_label: str | None) -> str:
    name = value_of(phase)
    if name in ("awaiting_approval", "awaiting_answer"):
        return "waiting"
    if name == "canceling":
        return "canceling"
    if status_label in _PLANNING_LABELS:
        return "planning"
    if status_label in _VERIFYING_LABELS:
        return "verifying"
    return "running"


def working_verb(group: str, elapsed: float) -> str:
    verbs = VERBS[group]
    return verbs[int(max(0.0, elapsed) // VERB_SECONDS) % len(verbs)]


def spinner_frame(clock: float) -> str:
    return SPINNER_FRAMES[int(clock * SPINNER_FPS) % len(SPINNER_FRAMES)]


def build_working_text(phase: Any, status: Any, plan: Any, elapsed: float, clock: float, *, motion: bool) -> str:
    """R10, R13: spinner, verb, elapsed seconds, task cost against budget, `step N/M` only when a plan exists.

    Nothing here implies progress or cost the session has not reported."""
    name = value_of(phase)
    if name in SETTLED_PHASES:
        return ""
    label = phase_text(phase, status.status_label)
    group = phase_group(phase, status.status_label)
    if motion:
        glyph = SPINNER_STATIC if group == "waiting" else spinner_frame(clock)
        head = f"{glyph} {working_verb(group, elapsed)}…"
    else:
        head = f"{SPINNER_STATIC} {label}"
    parts = [head, f"{int(max(0.0, elapsed))}s", f"${status.task_cost_usd:.4f} / {budget_text(status.budget_usd)}"]
    if plan is not None and plan.steps:
        number, _ = active_step(plan)
        parts.append(f"step {number}/{len(plan.steps)}")
    return " · ".join(parts)


class WorkingLine(Static):
    """R10: one line above the prompt box while a task is active. Refreshes only when its text changes (R14)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", markup=False, **kwargs)
        self._shown = ""
        self.updates = 0

    def set_line(self, text: str) -> None:
        if text == self._shown:
            return
        self._shown = text
        self.updates += 1
        self.update(Text(text, no_wrap=True, overflow="ellipsis"))


def build_status_text(status: Any, phase: Any, width: int) -> Text:
    """R21 fields on one dim line that fits `width`: drops memory, then route, then trims the workspace from the left."""
    workspace = status.workspace.name or str(status.workspace)
    cost = f"${status.task_cost_usd:.4f} / {budget_text(status.budget_usd)}"
    mode = edit_mode_word(status.edit_mode)
    memory = f"memory {status.memory}"
    label = phase_text(phase, status.status_label)

    def parts(drop: frozenset[str], ws: str) -> list[tuple[str, str]]:
        out = [(ws, "")]
        if "route" not in drop and status.route:
            out.append((f"route {status.route}", ""))
        out.append((cost, ""))
        out.append((mode, "bold" if mode == "accept-edits" else ""))
        if "memory" not in drop:
            out.append((memory, ""))
        out.append((label, ""))
        return out

    def joined(items: list[tuple[str, str]]) -> int:
        return sum(len(t) for t, _ in items) + 3 * (len(items) - 1)

    room = max(1, width - 2)  # the line has one column of padding either side
    items: list[tuple[str, str]] = []
    for drop in (frozenset(), frozenset({"memory"}), frozenset({"memory", "route"})):
        items = parts(drop, workspace)
        if joined(items) <= room:
            break
    else:
        overflow = joined(items) - room
        keep = max(1, len(workspace) - overflow - 1)
        trimmed = "…" + workspace[-keep:] if len(workspace) > keep else workspace
        items[0] = (trimmed, "")
    text = Text(no_wrap=True, overflow="ellipsis")
    for index, (piece, style) in enumerate(items):
        if index:
            text.append(" · ")
        text.append(piece, style=style or None)
    return text


class StatusBar(Static):
    """R4: the 017 R21 fields on one dim line directly under the prompt box. It owns no timer."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", markup=False, **kwargs)
        self._status: Any = None
        self._phase: Any = "idle"
        self.updates = 0

    def show(self, status: Any, phase: Any) -> None:
        if status == self._status and phase == self._phase:
            return
        self._status, self._phase = status, phase
        self._redraw()

    def _redraw(self) -> None:
        if self._status is None:
            return
        self.updates += 1
        width = self.size.width or self.app.size.width
        self.update(build_status_text(self._status, self._phase, width))

    def on_resize(self, event: events.Resize) -> None:
        self._redraw()


# ---------------------------------------------------------------- plan

def active_step(plan: Any) -> tuple[int, str]:
    """(1-based step number, state word) of the step the summary line points at."""
    steps = list(plan.steps)
    if not steps:
        return 0, "empty"
    for wanted in ("running", "waiting", "failed", "pending"):
        for index, step in enumerate(steps):
            if step.state == wanted:
                return index + 1, wanted
    if all(step.state == "verified" for step in steps):
        return len(steps), "done"
    return len(steps), steps[-1].state


def plan_summary_text(plan: Any) -> str:
    number, word = active_step(plan)
    return f"Plan v{plan.version} - step {number}/{len(plan.steps)} - {word}"


def step_line(index: int, step: Any, frame: str | None = None) -> str:
    """R11: the glyph changes at once; with motion on the running step shows the spinner frame."""
    retry = f" x{step.attempts}" if step.attempts > 1 else ""
    glyph = frame if (frame and step.state == "running") else STEP_GLYPHS.get(step.state, "?")
    return f"{glyph:<4} {index}. {step.purpose} ({step.state}){retry}"


def plan_step_lines(plan: Any) -> list[str]:
    return [step_line(index, step) for index, step in enumerate(plan.steps, start=1)]


class StepList(Vertical):
    """One row per plan step. Rows are rebuilt when the plan changes and edited in place on a tick (R14)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._structure: Any = None
        self._dynamic: Any = None
        self._rows: list[Static] = []
        self.renders = 0

    def set_plan(self, plan: Any, *, frame: str | None = None, highlighted: frozenset[str] = frozenset()) -> None:
        steps = list(plan.steps) if plan is not None else []
        reason = getattr(plan, "revision_reason", None) if plan is not None else None
        structure = (getattr(plan, "version", None), tuple((s.step_id, s.purpose) for s in steps), reason)
        has_running = any(s.state == "running" for s in steps)
        fresh = frozenset(s.step_id for s in steps if s.step_id in highlighted and s.state in FINISHED_STEPS)
        dynamic = (tuple((s.state, s.attempts) for s in steps), frame if has_running else None, fresh)
        if structure == self._structure and dynamic == self._dynamic:
            return
        self.renders += 1
        rebuild = structure != self._structure
        self._structure, self._dynamic = structure, dynamic
        lines = [(step_line(i, s, dynamic[1]), s, s.step_id in fresh) for i, s in enumerate(steps, start=1)]
        if rebuild:
            self.remove_children()
            self._rows = [Static(Text(line, no_wrap=True, overflow="ellipsis"), markup=False,
                                 classes=self._row_classes(step, is_fresh)) for line, step, is_fresh in lines]
            rows: list[Widget] = list(self._rows)
            if reason:
                note = Static(Text("Revised: " + reason), markup=False, classes="revised")
                rows.append(note)
            if rows:
                self.mount(*rows)
            return
        for row, (line, step, is_fresh) in zip(self._rows, lines):
            row.update(Text(line, no_wrap=True, overflow="ellipsis"))
            row.set_classes(self._row_classes(step, is_fresh))

    @staticmethod
    def _row_classes(step: Any, fresh: bool) -> str:
        return f"step -{step.state}" + (" -fresh" if fresh else "")


class PlanPanel(Vertical, can_focus=True):
    """R20: the plan, docked on the right at 100 columns or more."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.border_title = "Plan"
        self._plan: Any = None

    def compose(self):
        yield Static(Text("No plan yet."), markup=False, id="plan-head")
        yield StepList(id="plan-steps")

    def set_plan(self, plan: Any, *, frame: str | None = None, highlighted: frozenset[str] = frozenset()) -> None:
        self._plan = plan
        head = self.query_one("#plan-head", Static)
        head.update(Text("No plan yet." if plan is None else plan_summary_text(plan), style="bold" if plan else ""))
        self.query_one(StepList).set_plan(plan, frame=frame, highlighted=highlighted)


class PlanSummary(Vertical, can_focus=True):
    """R20: below 100 columns the plan is a one-line summary that expands in place."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._plan: Any = None
        self._frame: str | None = None
        self._highlighted: frozenset[str] = frozenset()
        self.expanded = False
        self.task_active = False

    def compose(self):
        yield Static("", markup=False, id="summary-head")
        yield StepList(id="summary-steps")

    def set_plan(self, plan: Any, *, frame: str | None = None, highlighted: frozenset[str] = frozenset()) -> None:
        self._plan, self._frame, self._highlighted = plan, frame, highlighted
        self._render_plan()

    def set_expanded(self, expanded: bool) -> None:
        self.expanded = expanded
        self._render_plan()

    def _render_plan(self) -> None:
        plan = self._plan
        head = self.query_one("#summary-head", Static)
        steps = self.query_one(StepList)
        if plan is None:
            head.update(Text("No plan yet.", no_wrap=True, overflow="ellipsis") if self.task_active else Text(""))
        elif self.expanded:
            head.update(Text(plan_summary_text(plan), style="bold", no_wrap=True, overflow="ellipsis"))
        else:
            head.update(Text(plan_summary_text(plan) + " (Ctrl+T)", no_wrap=True, overflow="ellipsis"))
        steps.display = self.expanded and plan is not None
        if self.expanded and plan is not None:
            steps.set_plan(plan, frame=self._frame, highlighted=self._highlighted)


# ---------------------------------------------------------------- banner

def trim_left(text: str, width: int) -> str:
    """Keep the end of a path (the informative part) when it does not fit."""
    return text if len(text) <= width else "…" + text[-max(1, width - 1):]


class PathLine(Static):
    """A path that keeps its end when the width is short."""

    def __init__(self, path: str, **kwargs: Any) -> None:
        super().__init__(Text(path, no_wrap=True, overflow="ellipsis"), markup=False, **kwargs)
        self._path = path

    def on_resize(self, event: events.Resize) -> None:
        if event.size.width > 0:
            self.update(Text(trim_left(self._path, event.size.width), no_wrap=True, overflow="ellipsis"))


class Banner(Vertical):
    """R2: one bordered welcome banner at the top of the transcript, shown once. Built from `BannerInfo` only."""

    TIPS = ("/help for commands · / to complete commands", "Esc to stop a task · @ to mention a file")

    def __init__(self, info: Any, *, no_key_message: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.info = info
        self._no_key_message = no_key_message

    def compose(self):
        info = self.info
        yield Static(Text(f"Galliani {info.version}", style="bold"), markup=False, classes="b-title")
        yield PathLine(info.workspace, classes="b-workspace")
        if info.providers:
            routing = "routing: auto · " + " · ".join(info.providers)
        else:
            routing = self._no_key_message
        yield Static(Text(routing), markup=False, classes="b-routing")
        settings = (f"edit mode: {edit_mode_word(info.edit_mode)} · budget: {budget_text(info.budget_usd)}"
                    f" · memory: {info.memory}")
        yield Static(Text(settings), markup=False, classes="b-settings")
        for tip in self.TIPS:
            yield Static(Text(tip), markup=False, classes="b-tip")
        if info.wide_workspace:
            yield Static(Text("This workspace is your whole home folder (or drive). The agent can read any file in "
                              "it that is not protected. Start galliacli in a project folder, or use /workspace."),
                         markup=False, classes="b-warn")


# ---------------------------------------------------------------- transcript

class EntryRow(Horizontal):
    """R5: one lead glyph plus one line of text."""

    def __init__(self, kind: str, text: str, *, classes: str) -> None:
        super().__init__(Static(LEADERS.get(kind, "·"), markup=False, classes="glyph"),
                         Static(Text(text), markup=False, classes="text"), classes=classes)


class DetailRow(Horizontal):
    """R5: a detail line under its entry. The corner glyph sits in its own column, so a wrapped line
    continues indented under the text instead of under the glyph."""

    def __init__(self, lead: str, line: str, *, classes: str) -> None:
        super().__init__(Static(lead, markup=False, classes="lead"),
                         Static(Text(line), markup=False, classes="text"), classes=classes)


def entry_widgets(entry: Any) -> list[Widget]:
    """Widgets for one transcript entry. Untrusted text is never parsed as markup (R18)."""
    kind = value_of(entry.kind)
    classes = f"entry -{kind}" + (" -gap" if kind in GAP_BEFORE else "") + (" -verbose" if entry.verbose else "")
    widgets: list[Widget] = [EntryRow(kind, entry.text, classes=classes)]
    for index, line in enumerate(entry.detail):
        lead = "  └ " if index == 0 else "    "
        widgets.append(DetailRow(lead, line, classes=f"entry detail -{kind}"))
    if entry.body:
        body = entry.body
        if len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS] + f"\n\n({len(entry.body) - MAX_BODY_CHARS} more characters not shown)"
        if entry.markdown:
            widgets.append(EntryMarkdown(body, classes="entry body"))
        else:
            widgets.append(Static(Text(body), markup=False, classes="entry body"))
    return widgets


class EntryMarkdown(Markdown):
    """Result body as Markdown: links are not opened (R19) and Textual loads no images."""

    can_focus = False

    def __init__(self, markdown: str, **kwargs: Any) -> None:
        super().__init__(markdown, open_links=False, **kwargs)

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        event.stop()


class TranscriptView(VerticalScroll, can_focus=True):
    """R20: the single-column transcript; PageUp/PageDown/Home/End scroll it while focused (R29)."""

    def add_entry(self, entry: Any) -> None:
        near_end = self.max_scroll_y - self.scroll_y <= 2
        self.mount(*entry_widgets(entry))
        if near_end:
            self.call_after_refresh(self.scroll_end, animate=False)

    def clear_entries(self) -> None:
        """`/clear` hides entries; the welcome banner is shown once and stays (R2)."""
        self.query(".entry").remove()


# ---------------------------------------------------------------- completion popup

class CompletionPopup(Static):
    """R16, R17, R21: candidates above the prompt box. It computes nothing: it shows what it is given.

    Every label and summary arrives sanitized (R21); this widget only lays them out."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", markup=False, **kwargs)
        self.items: tuple[Any, ...] = ()
        self.selected = 0
        self.note = ""
        self.truncated = False
        self.display = False

    @property
    def is_shown(self) -> bool:
        return bool(self.display and self.items)

    @property
    def current(self) -> Any | None:
        return self.items[self.selected] if self.is_shown else None

    def show(self, items: tuple[Any, ...], *, note: str = "", truncated: bool = False) -> None:
        keep = self.current.insert if self.current is not None else None
        self.items, self.note, self.truncated = tuple(items), note, truncated
        self.selected = next((i for i, item in enumerate(self.items) if item.insert == keep), 0)
        self.display = bool(self.items or self.note)
        self._redraw()

    def close(self) -> None:
        self.items, self.note, self.truncated, self.selected = (), "", False, 0
        self.display = False

    def move(self, step: int) -> None:
        if self.items:
            self.selected = (self.selected + step) % len(self.items)
            self._redraw()

    def on_resize(self, event: events.Resize) -> None:
        self._redraw()

    def _redraw(self) -> None:
        text = Text(no_wrap=True, overflow="ellipsis")
        if not self.items:
            text.append("  " + self.note, style="dim")
            self.update(text)
            return
        top = min(max(0, self.selected - POPUP_ROWS + 1), max(0, len(self.items) - POPUP_ROWS))
        window = self.items[top:top + POPUP_ROWS]
        column = min(28, max(len(item.label) for item in window)) + 2
        width = max(1, self.size.width or 80)
        for offset, item in enumerate(window):
            current = top + offset == self.selected
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append("› " if current else "  ", style="bold" if current else "")
            row.append(item.label.ljust(column), style="bold" if current else "")
            summary = item.summary
            if not item.enabled:
                summary = (summary + " " + NOT_WHILE_ACTIVE).strip()
            if summary:
                row.append(summary, style="" if current else "dim")
            if not item.enabled:
                row.stylize("dim")
            row.truncate(width, overflow="ellipsis", pad=False)
            if offset:
                text.append("\n")
            text.append_text(row)
        if self.truncated or len(self.items) > top + POPUP_ROWS:
            text.append("\n  …", style="dim")
        self.update(text)


# ---------------------------------------------------------------- prompt

class PromptHistory:
    """R22: session history in memory only, at most 100 entries, never written to disk."""

    def __init__(self, limit: int = HISTORY_LIMIT) -> None:
        self.limit = limit
        self.items: list[str] = []
        self._index = 0
        self._draft = ""

    def push(self, text: str) -> None:
        if text and (not self.items or self.items[-1] != text):
            self.items.append(text)
            del self.items[:-self.limit]
        self.reset()

    def reset(self) -> None:
        self._index = len(self.items)
        self._draft = ""

    def previous(self, draft: str) -> str | None:
        if self._index == len(self.items):
            self._draft = draft
        if self._index == 0:
            return None
        self._index -= 1
        return self.items[self._index]

    def next(self) -> str | None:
        if self._index >= len(self.items):
            return None
        self._index += 1
        return self.items[self._index] if self._index < len(self.items) else self._draft


IDLE_PLACEHOLDER = "Type an objective, or / for commands"
ACTIVE_PLACEHOLDER = "Esc to stop"


class PromptArea(TextArea):
    """R22: Enter sends; Shift+Enter, Alt+Enter and Ctrl+J add a newline; Up/Down on the edge lines walk history.

    While the completion popup is open (spec 018 R17) Up/Down move its selection, Tab inserts and Enter
    inserts (and sends when the item says so). Esc is handled by the app."""

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class CompletionAccept(Message):
        def __init__(self, enter: bool) -> None:
            super().__init__()
            self.enter = enter

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", soft_wrap=True, show_line_numbers=False, tab_behavior="focus",
                         placeholder=IDLE_PLACEHOLDER, **kwargs)
        self.recall = PromptHistory()
        self.popup: CompletionPopup | None = None

    @property
    def popup_showing(self) -> bool:
        return self.popup is not None and self.popup.is_shown

    async def _on_key(self, event: events.Key) -> None:
        key = event.key
        if self.popup_showing and key in ("tab", "enter"):
            event.stop()
            event.prevent_default()
            self.post_message(self.CompletionAccept(enter=key == "enter"))
            return
        if key == "enter":
            event.stop()
            event.prevent_default()
            self.submit_text(self.text)
            return
        if key in ("shift+enter", "alt+enter", "ctrl+j"):
            event.stop()
            event.prevent_default()
            self.insert("\n")

    def submit_text(self, raw: str) -> None:
        text = raw.strip()
        if text:
            self.recall.push(text)
            self.post_message(self.Submitted(text))

    def _recall(self, text: str) -> None:
        self.load_text(text)
        self.move_cursor(self.document.end)

    def action_cursor_up(self, select: bool = False) -> None:
        if not select and self.popup_showing:
            self.popup.move(-1)
            return
        if not select and self.cursor_location[0] == 0:
            recalled = self.recall.previous(self.text)
            if recalled is not None:
                self._recall(recalled)
            return
        super().action_cursor_up(select)

    def action_cursor_down(self, select: bool = False) -> None:
        if not select and self.popup_showing:
            self.popup.move(1)
            return
        if not select and self.cursor_location[0] >= self.document.line_count - 1:
            following = self.recall.next()
            if following is not None:
                self._recall(following)
            return
        super().action_cursor_down(select)

    def clear_prompt(self) -> None:
        self.load_text("")
        self.recall.reset()

    def cursor_offset(self) -> int:
        """The cursor as an index into `self.text`."""
        row, column = self.cursor_location
        lines = self.text.split("\n")
        return sum(len(line) + 1 for line in lines[:row]) + column

    def replace_span(self, start: int, end: int, insert: str) -> None:
        """Replace text[start:end] and put the cursor after the insertion."""
        text = self.text
        updated = text[:start] + insert + text[end:]
        self.load_text(updated)
        before = updated[:start + len(insert)].split("\n")
        self.move_cursor((len(before) - 1, len(before[-1])))


# ---------------------------------------------------------------- inline prompts

Choice = Literal["approve", "deny", "accept_edits"]


class ApprovalCard(Static, can_focus=True):
    """R23: an inline card; y approve, n deny, a approve and accept edits (only when offered). No default on Enter.

    Keys are live from the first frame: the entry animation (spec 018 R12) only moves pixels."""

    BINDINGS = [
        Binding("y", "decide('approve')", "Approve", show=False),
        Binding("n", "decide('deny')", "Deny", show=False),
        Binding("a", "decide('accept_edits')", "Approve and accept edits", show=False),
    ]

    class Decided(Message):
        def __init__(self, card: ApprovalCard, choice: Choice) -> None:
            super().__init__()
            self.card, self.choice = card, choice

    def __init__(self, pending: Any, **kwargs: Any) -> None:
        super().__init__("", markup=False, **kwargs)
        self.pending = pending
        self.armed = True      # one key per prompt: disarmed while a decision is being sent
        self.border_title = "Approval needed"
        text = Text()
        text.append("Action: ", style="bold")
        text.append(pending.action_summary)
        text.append("\nRisk:   ", style="bold")
        text.append(pending.risk_summary)
        text.append("\nScope:  ", style="bold")
        text.append(pending.scope)
        text.append("\n[y] approve   [n] deny")
        if pending.can_accept_edits:
            text.append("   [a] approve and accept edits")
        text.append("   [Esc] deny")
        self.update(text)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "decide" and parameters == ("accept_edits",) and not self.pending.can_accept_edits:
            return None
        return True

    def action_decide(self, choice: Choice) -> None:
        if not self.armed:
            return
        if choice == "accept_edits" and not self.pending.can_accept_edits:
            return
        self.armed = False
        self.post_message(self.Decided(self, choice))


class QuestionInput(Input):
    """R24: a single-line answer field; Enter sends a non-empty answer, Esc cancels the task (handled by the app)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.border_title = "Your answer | Enter send | Esc cancel"


def monotonic() -> float:
    return time.monotonic()
