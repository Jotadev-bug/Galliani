"""The Textual app for the interactive terminal UI (spec 017 R20-R29).

The app reads `Session` (spec 017 Interfaces and Data Contracts) and never owns orchestration: it renders
`session.state` and `session.entries()`, and turns keys into `submit`, `approve`, `deny`, `answer`, `cancel`
and `aclose`. Types from `session.py` are used by duck typing so this module stays independent of it.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections.abc import Awaitable, Iterable
from typing import TYPE_CHECKING, Any, Literal

from textual import events
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Input, Static

from galliani.tui import styles
from galliani.tui.widgets import (
    DOCK_MIN_WIDTH,
    NARROW_MIN_WIDTH,
    ApprovalCard,
    PlanPanel,
    PlanSummary,
    PromptArea,
    QuestionInput,
    StatusBar,
    TranscriptView,
    value_of,
)

if TYPE_CHECKING:
    from galliani.tui.session import Session

QUIT_WINDOW_SECONDS = 2.0
QUIT_TIMEOUT_SECONDS = 3.0
QUIT_HINT = "Press Ctrl+C again to quit"
NARROW_NOTICE = "Terminal is narrow: widen it to at least 60 columns."


class GallianiApp(App[int]):
    """Single-column transcript, plan panel, status bar and a multi-line prompt (R20)."""

    TITLE = "Galliani"
    CSS = styles.APP_CSS
    ENABLE_COMMAND_PALETTE = False      # R29
    COMMANDS = set()
    BINDINGS = [
        Binding("ctrl+c", "interrupt", "Cancel", show=False, priority=True),
        Binding("ctrl+q", "quit_app", "Quit", show=False, priority=True),
        Binding("ctrl+t", "toggle_plan", "Plan", show=False, priority=True),
        Binding("escape", "escape", "Stop", show=False),
    ]

    def __init__(self, session: Session, *, theme: Literal["dark", "light"] = "dark",
                 ansi: bool | None = None) -> None:
        # ansi_color must be known before App.__init__ picks its NO_COLOR filter: NoColor strips every colour,
        # while the default Monochrome filter only greys them.
        super().__init__(ansi_color=True if (ansi or os.environ.get("NO_COLOR") is not None) else None)
        self.session = session
        self._wants_ansi = ansi
        for registered in styles.THEMES:
            self.register_theme(registered)
        self.theme = self._theme_name(theme)
        self._theme_choice = theme
        self._last_seq = 0
        self._cleared = 0
        self._verbose: bool | None = None
        self._phase = "idle"
        self._card: ApprovalCard | None = None
        self._question: str | None = None
        self._busy = False                 # an approve/deny/answer is in flight
        self._last_interrupt = 0.0
        self._quitting = False
        self._plan_visible = True          # wide layout: panel shown
        self._plan_expanded = False        # narrow layout: summary expanded
        self._unsubscribe: Any = None
        self.exit_hint_seconds = QUIT_WINDOW_SECONDS

    # ---- theme and colour (R27, R28)

    @property
    def ansi_mode(self) -> bool:
        """True under NO_COLOR and in 16-colour terminals: only ANSI named colours, or none at all."""
        if self._wants_ansi is not None:
            return self._wants_ansi
        if self.no_color:
            return True
        return self.console.color_system in ("standard", "windows")

    def _theme_name(self, theme: str) -> str:
        if self._wants_ansi or self.no_color or self.console.color_system in ("standard", "windows"):
            return styles.ANSI
        return styles.LIGHT if theme == "light" else styles.DARK

    def set_galliani_theme(self, theme: str) -> None:
        if theme in ("dark", "light"):
            self._theme_choice = theme
            self.theme = self._theme_name(theme)

    # ---- no screenshots, no palette (R29)

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        return iter(())

    def action_screenshot(self, filename: str | None = None, path: str | None = None) -> None:
        return None

    def deliver_screenshot(self, *args: Any, **kwargs: Any) -> str | None:
        return None

    def save_screenshot(self, *args: Any, **kwargs: Any) -> str:
        return ""

    # ---- layout

    def compose(self) -> ComposeResult:
        yield Static("", id="narrow", markup=False)
        with Horizontal(id="body"):
            yield TranscriptView(id="transcript")
            yield PlanPanel(id="plan-panel")
        yield PlanSummary(id="plan-summary")
        with Vertical(id="dock"):
            yield StatusBar(id="status")
            yield Static("", id="hint", markup=False)
            yield Static("", id="question-text", markup=False)
            yield QuestionInput(id="question")
            yield PromptArea(id="prompt")

    @property
    def transcript(self) -> TranscriptView:
        return self.query_one(TranscriptView)

    @property
    def prompt(self) -> PromptArea:
        return self.query_one(PromptArea)

    @property
    def status_bar(self) -> StatusBar:
        return self.query_one(StatusBar)

    def on_mount(self) -> None:
        self.query_one("#question-text").display = False
        self._unsubscribe = self.session.subscribe(self._on_session_change)
        self._apply_width(self.size.width)
        self._sync()
        self.prompt.focus()

    def on_unmount(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def on_resize(self, event: events.Resize) -> None:
        self._apply_width(event.size.width)

    def _apply_width(self, width: int) -> None:
        wide = width >= DOCK_MIN_WIDTH
        self.query_one(PlanPanel).set_class(wide and self._plan_visible, "-docked")
        summary = self.query_one(PlanSummary)
        summary.set_class(not wide, "-compact")
        summary.set_expanded(self._plan_expanded and not wide)
        self.query_one("#narrow", Static).update(NARROW_NOTICE if width < NARROW_MIN_WIDTH else "")
        self.query_one("#narrow").set_class(width < NARROW_MIN_WIDTH, "-show")

    # ---- syncing with the session

    def _on_session_change(self) -> None:
        if self.is_running:
            self._sync()

    def _sync(self) -> None:
        state = self.session.state
        status = state.status
        self._phase = value_of(state.phase)
        transcript = self.transcript
        if state.cleared_after != self._cleared or status.verbose_events != self._verbose:
            transcript.clear_entries()
            self._cleared = state.cleared_after
            self._verbose = status.verbose_events
            self._last_seq = state.cleared_after
        for entry in self.session.entries(self._last_seq):
            transcript.add_entry(entry)
            self._last_seq = max(self._last_seq, entry.seq)
        self.status_bar.show(status, state.phase)
        self.query_one(PlanPanel).set_plan(state.plan)
        summary = self.query_one(PlanSummary)
        summary.set_plan(state.plan)
        self._sync_interaction(state)

    def _sync_interaction(self, state: Any) -> None:
        """Mount the approval card or question field while the session waits, and give focus back after."""
        pending = state.pending_approval
        question = state.question
        prompt = self.prompt
        dock = self.query_one("#dock")
        if pending is not None and (self._card is None or self._card.pending is not pending):
            self._remove_card()
            self._card = ApprovalCard(pending, id="approval")
            dock.mount(self._card, before=prompt)
            prompt.add_class("-hidden")
            self._card.focus()
        elif pending is None and self._card is not None:
            self._remove_card()
            prompt.remove_class("-hidden")
            prompt.focus()
        question_input = self.query_one(QuestionInput)
        question_text = self.query_one("#question-text", Static)
        if question is not None and self._question != question:
            self._question = question
            question_text.update(f"? {question}")
            question_text.display = True
            question_input.value = ""
            question_input.add_class("-show")
            prompt.add_class("-hidden")
            question_input.focus()
        elif question is None and self._question is not None:
            self._question = None
            question_text.display = False
            question_input.remove_class("-show")
            question_input.value = ""
            if self._card is None:
                prompt.remove_class("-hidden")
                prompt.focus()

    def _remove_card(self) -> None:
        if self._card is not None:
            self._card.remove()
            self._card = None

    # ---- running session calls

    def _dispatch(self, call: Awaitable[Any], *, gate: bool = False) -> None:
        """Run a session call in a worker. `gate` blocks further decisions until it returns (one key per prompt)."""
        if gate:
            self._busy = True
        self.run_worker(self._run_call(call, gate), group="session", exit_on_error=False)

    async def _run_call(self, call: Awaitable[Any], gate: bool) -> None:
        try:
            result = await call
        except Exception:     # the session never raises (R14); a surprise must not close the app
            result = None
        finally:
            if gate:
                self._busy = False
        if result is not None and getattr(result, "kind", None) is not None:
            self._handle_action(result)
        if self.is_running:
            if gate and self._card is not None:
                self._card.armed = True      # the prompt stayed open (e.g. an ineligible 'a'): decisions work again
            self._sync()

    def _handle_action(self, action: Any) -> None:
        kind = value_of(action.kind)
        if kind == "quit":
            self.action_quit_app()
        elif kind == "theme" and action.value:
            self.set_galliani_theme(value_of(action.value))

    # ---- message handlers

    def on_prompt_area_submitted(self, message: PromptArea.Submitted) -> None:
        self.prompt.clear_prompt()
        self._last_interrupt = 0.0
        self._dispatch(self.session.submit(message.text))

    def on_approval_card_decided(self, message: ApprovalCard.Decided) -> None:
        if message.card is not self._card or self._busy:
            return
        if message.choice == "approve":
            call = self.session.approve()
        elif message.choice == "accept_edits":
            call = self.session.approve(accept_edits=True)
        else:
            call = self.session.deny()
        self._dispatch(call, gate=True)

    def on_input_submitted(self, message: Input.Submitted) -> None:
        if not isinstance(message.input, QuestionInput):
            return
        message.stop()
        answer = message.value.strip()
        if not answer or self._busy or self._phase != "awaiting_answer":
            return        # an empty answer does nothing; Esc cancels (R24)
        message.input.value = ""
        self._dispatch(self.session.answer(answer), gate=True)

    # ---- actions

    def action_escape(self) -> None:
        """R23-R25: Esc denies an approval, cancels a question or a running task, and does nothing when idle."""
        phase = self._phase
        if phase == "awaiting_approval":
            if self._card is not None and self._card.armed and not self._busy:
                self._card.armed = False
                self._dispatch(self.session.deny(), gate=True)
        elif phase in ("awaiting_answer", "running"):
            self.session.cancel()
            self._sync()

    def action_interrupt(self) -> None:
        """R22, R25: Ctrl+C cancels a running task, then a second press within 2 seconds quits."""
        now = time.monotonic()
        again = now - self._last_interrupt <= QUIT_WINDOW_SECONDS and self._last_interrupt > 0
        phase = self._phase
        if phase in ("running", "canceling", "awaiting_approval", "awaiting_answer"):
            if again:
                self.action_quit_app()
                return
            self._last_interrupt = now
            if phase != "canceling":
                self.session.cancel()
            self._sync()
            return
        prompt = self.prompt
        if prompt.text:
            prompt.clear_prompt()
            self._last_interrupt = 0.0
            return
        if again:
            self.action_quit_app()
            return
        self._last_interrupt = now
        self._show_hint(QUIT_HINT)

    def _show_hint(self, text: str) -> None:
        hint = self.query_one("#hint", Static)
        hint.update(text)
        hint.add_class("-show")
        self.set_timer(QUIT_WINDOW_SECONDS, self._clear_hint)

    def _clear_hint(self) -> None:
        hint = self.query_one("#hint", Static)
        hint.remove_class("-show")
        hint.update("")

    def action_toggle_plan(self) -> None:
        if self.size.width >= DOCK_MIN_WIDTH:
            self._plan_visible = not self._plan_visible
        else:
            self._plan_expanded = not self._plan_expanded
        self._apply_width(self.size.width)

    def action_quit_app(self) -> None:
        """R25: cancel any active task, wait at most 3 seconds for it, close the runtime, exit 0."""
        if self._quitting:
            return
        self._quitting = True
        self.run_worker(self._quit(), group="quit", exit_on_error=False)

    async def action_quit(self) -> None:
        self.action_quit_app()

    async def _quit(self) -> None:
        try:
            await asyncio.wait_for(self.session.aclose(timeout=QUIT_TIMEOUT_SECONDS - 0.5), QUIT_TIMEOUT_SECONDS)
        except Exception:
            pass
        self.exit(0)


def run_app(session: Session, *, theme: Literal["dark", "light"] = "dark") -> int:
    """Run the full-screen app and return the exit code. A Textual failure prints only the exception type (spec 017)."""
    app = GallianiApp(session, theme=theme)
    try:
        app.run()
    except Exception as error:
        print(type(error).__name__, file=sys.stderr)
        return 1
    return app.return_code or 0
