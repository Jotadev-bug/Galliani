"""Widgets for the terminal UI (spec 017 R20-R24, R28, R29).

Everything shown here arrives already redacted and sanitized by the session (R17, R18). The widgets add a
second line of defence: text is always wrapped in `rich.text.Text` and shown with `markup=False`, so nothing
untrusted is ever parsed as Rich or Textual markup, and Markdown never opens a link.
"""

from __future__ import annotations

import os
from typing import Any, Literal

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Input, Markdown, Static, TextArea

MAX_BODY_CHARS = 20_000
HISTORY_LIMIT = 100
SPINNER_FRAMES = "|/-\\"
SPINNER_INTERVAL = 0.12
DOCK_MIN_WIDTH = 100      # R20: plan panel docks at this width or more
NARROW_MIN_WIDTH = 60     # R20: below this, a one-line notice asks for a wider terminal

LEADERS = {
    "user": "> ", "plan": "= ", "route": "~ ", "tool": "* ", "verification": "+ ", "retry": "r ",
    "replan": "= ", "approval": "? ", "question": "? ", "edit_mode": "~ ", "event": ". ",
    "result": "= ", "usage": "$ ", "notice": "i ", "error": "! ",
}
GAP_BEFORE = {"user", "result"}
STEP_GLYPHS = {"pending": "...", "running": ">", "waiting": "[?]", "verified": "[ok]", "failed": "[x]",
               "canceled": "[-]"}
PHASE_LABELS = {
    "idle": "Ready", "running": "Working", "awaiting_approval": "Needs your approval",
    "awaiting_answer": "Needs your input", "canceling": "Canceling", "closed": "Closed",
}
ACTIVE_PHASES = frozenset({"running", "canceling"})


def value_of(item: Any) -> str:
    """The plain string of an enum member or string."""
    return str(getattr(item, "value", item))


def animations_enabled(app_animation_level: str) -> bool:
    """R28: the spinner is the only animation; it is off at animation level `none` or when reduced motion is set."""
    return app_animation_level != "none" and os.environ.get("GALLIANI_REDUCED_MOTION") != "1"


# ---------------------------------------------------------------- status bar

def edit_mode_word(mode: Any) -> str:
    return value_of(mode).replace("_", "-")


def budget_text(budget_usd: float | None) -> str:
    return "no limit" if budget_usd is None else f"${budget_usd:.2f}"


def phase_text(phase: Any, status_label: str | None) -> str:
    name = value_of(phase)
    if name == "running" and status_label:
        return status_label
    return PHASE_LABELS.get(name, name)


def build_status_text(status: Any, phase: Any, width: int, *, frame: str | None = None,
                      animated: bool = True) -> Text:
    """One line that fits `width`: drops `working...`, then memory, then route, then trims the workspace from the left."""
    phase_name = value_of(phase)
    active = phase_name in ACTIVE_PHASES
    workspace = status.workspace.name or str(status.workspace)
    cost = f"${status.task_cost_usd:.4f} / {budget_text(status.budget_usd)}"
    mode = edit_mode_word(status.edit_mode)
    memory = f"memory {status.memory}"
    label = phase_text(phase, status.status_label)
    lead = f"{frame} " if active and animated and frame else ""
    tail = " (working...)" if active and not animated else ""

    def parts(drop: frozenset[str], ws: str) -> list[tuple[str, str]]:
        out = [(ws, "")]
        if "route" not in drop and status.route:
            out.append((f"route {status.route}", ""))
        out.append((cost, ""))
        out.append((mode, "bold" if mode == "accept-edits" else ""))
        if "memory" not in drop:
            out.append((memory, ""))
        shown_tail = "" if "working" in drop else tail
        out.append((f"{lead}{label}{shown_tail}", "bold"))
        return out

    def joined(items: list[tuple[str, str]]) -> int:
        return sum(len(t) for t, _ in items) + 3 * (len(items) - 1)

    room = max(1, width - 2)  # the bar has one column of padding either side
    items: list[tuple[str, str]] = []
    for drop in (frozenset(), frozenset({"working"}), frozenset({"working", "memory"}),
                 frozenset({"working", "memory", "route"})):
        items = parts(drop, workspace)
        if joined(items) <= room:
            break
    else:
        overflow = joined(items) - room
        keep = max(1, len(workspace) - overflow - 3)
        trimmed = "..." + workspace[-keep:] if len(workspace) > keep else workspace
        items[0] = (trimmed, "")
    text = Text(no_wrap=True, overflow="ellipsis")
    for index, (piece, style) in enumerate(items):
        if index:
            text.append(" | ")
        text.append(piece, style=style or None)
    return text


class StatusBar(Static):
    """R21 fields on one line. The spinner timer exists only while a task is active and motion is allowed."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", markup=False, **kwargs)
        self._status: Any = None
        self._phase: Any = "idle"
        self._frame = 0
        self._timer: Timer | None = None

    @property
    def spinner_active(self) -> bool:
        return self._timer is not None

    def show(self, status: Any, phase: Any) -> None:
        self._status, self._phase = status, phase
        active = value_of(phase) in ACTIVE_PHASES
        if active and animations_enabled(self.app.animation_level):
            if self._timer is None:
                self._timer = self.set_interval(SPINNER_INTERVAL, self._tick)
        elif self._timer is not None:
            self._timer.stop()
            self._timer = None
        self._redraw()

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(SPINNER_FRAMES)
        self._redraw()

    def _redraw(self) -> None:
        if self._status is None:
            return
        animated = self._timer is not None
        width = self.size.width or self.app.size.width
        self.update(build_status_text(self._status, self._phase, width,
                                      frame=SPINNER_FRAMES[self._frame], animated=animated))

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


def plan_step_lines(plan: Any) -> list[str]:
    lines = []
    for index, step in enumerate(plan.steps, start=1):
        retry = f" x{step.attempts}" if step.attempts > 1 else ""
        lines.append(f"{STEP_GLYPHS.get(step.state, '?'):<4} {index}. {step.purpose} ({step.state}){retry}")
    return lines


class PlanPanel(Static, can_focus=True):
    """R20: the plan, docked on the right at 100 columns or more."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", markup=False, **kwargs)
        self.border_title = "Plan"
        self._plan: Any = None
        self._render_plan()

    def set_plan(self, plan: Any) -> None:
        self._plan = plan
        self._render_plan()

    def _render_plan(self) -> None:
        plan = self._plan
        if plan is None:
            self.update(Text("No plan yet."))
            return
        text = Text(plan_summary_text(plan), style="bold")
        for line in plan_step_lines(plan):
            text.append("\n" + line)
        if getattr(plan, "revision_reason", None):
            text.append("\nRevised: " + plan.revision_reason)
        self.update(text)


class PlanSummary(Static, can_focus=True):
    """R20: below 100 columns the plan is a one-line summary that expands in place."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", markup=False, **kwargs)
        self._plan: Any = None
        self.expanded = False

    def set_plan(self, plan: Any) -> None:
        self._plan = plan
        self._render_plan()

    def set_expanded(self, expanded: bool) -> None:
        self.expanded = expanded
        self._render_plan()

    def _render_plan(self) -> None:
        plan = self._plan
        if plan is None:
            self.update(Text("No plan yet.", no_wrap=True, overflow="ellipsis"))
            return
        if not self.expanded:
            self.update(Text(plan_summary_text(plan) + " (Ctrl+T)", no_wrap=True, overflow="ellipsis"))
            return
        text = Text(plan_summary_text(plan), style="bold")
        for line in plan_step_lines(plan):
            text.append("\n" + line)
        self.update(text)


# ---------------------------------------------------------------- transcript

def entry_widgets(entry: Any) -> list[Widget]:
    """Widgets for one transcript entry. Untrusted text is never parsed as markup (R18)."""
    kind = value_of(entry.kind)
    classes = f"entry -{kind}" + (" -gap" if kind in GAP_BEFORE else "") + (" -verbose" if entry.verbose else "")
    head = Text(LEADERS.get(kind, "") + entry.text)
    for line in entry.detail:
        head.append("\n    " + line)
    widgets: list[Widget] = [Static(head, markup=False, classes=classes)]
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
        self.remove_children()


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


class PromptArea(TextArea):
    """R22: Enter sends; Shift+Enter, Alt+Enter and Ctrl+J add a newline; Up/Down on the edge lines walk history."""

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", soft_wrap=True, show_line_numbers=False, tab_behavior="focus", **kwargs)
        self.recall = PromptHistory()
        self.border_title = "Objective or /command"
        self.border_subtitle = "Enter send | Alt+Enter newline"

    async def _on_key(self, event: events.Key) -> None:
        key = event.key
        if key == "enter":
            event.stop()
            event.prevent_default()
            text = self.text.strip()
            if text:
                self.recall.push(text)
                self.post_message(self.Submitted(text))
            return
        if key in ("shift+enter", "alt+enter", "ctrl+j"):
            event.stop()
            event.prevent_default()
            self.insert("\n")

    def _recall(self, text: str) -> None:
        self.load_text(text)
        self.move_cursor(self.document.end)

    def action_cursor_up(self, select: bool = False) -> None:
        if not select and self.cursor_location[0] == 0:
            recalled = self.recall.previous(self.text)
            if recalled is not None:
                self._recall(recalled)
            return
        super().action_cursor_up(select)

    def action_cursor_down(self, select: bool = False) -> None:
        if not select and self.cursor_location[0] >= self.document.line_count - 1:
            following = self.recall.next()
            if following is not None:
                self._recall(following)
            return
        super().action_cursor_down(select)

    def clear_prompt(self) -> None:
        self.load_text("")
        self.recall.reset()


# ---------------------------------------------------------------- inline prompts

Choice = Literal["approve", "deny", "accept_edits"]


class ApprovalCard(Static, can_focus=True):
    """R23: an inline card; y approve, n deny, a approve and accept edits (only when offered). No default on Enter."""

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
