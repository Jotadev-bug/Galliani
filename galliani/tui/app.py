"""The Textual app for the interactive terminal UI (spec 017 R20-R29, spec 018 R1-R14, R16, R17).

The app reads `Session` (spec 017 Interfaces and Data Contracts) and never owns orchestration: it renders
`session.state` and `session.entries()`, and turns keys into `submit`, `approve`, `deny`, `answer`, `cancel`
and `aclose`. Types from `session.py` are used by duck typing so this module stays independent of it.
Completion candidates come from `commands.complete_command` and `Session.complete`; the app only shows them.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections.abc import Awaitable, Callable, Iterable
from typing import TYPE_CHECKING, Any, Literal

from textual import events
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Input, Static, TextArea

from galliani.tui import styles
from galliani.tui.commands import complete_command
from galliani.tui.widgets import (
    ACTIVE_PLACEHOLDER,
    CARD_ENTER_ROWS,
    CARD_ENTER_SECONDS,
    DOCK_MIN_WIDTH,
    FINISHED_STEPS,
    HIGHLIGHT_SECONDS,
    IDLE_PLACEHOLDER,
    NARROW_MIN_WIDTH,
    SETTLED_PHASES,
    TICK_HZ,
    TICK_HZ_STATIC,
    ApprovalCard,
    Banner,
    CompletionPopup,
    PlanPanel,
    PlanSummary,
    PromptArea,
    QuestionInput,
    StatusBar,
    Ticker,
    TranscriptView,
    WorkingLine,
    build_working_text,
    motion_enabled,
    spinner_frame,
    value_of,
)

if TYPE_CHECKING:
    from galliani.tui.session import Session

QUIT_WINDOW_SECONDS = 2.0
QUIT_TIMEOUT_SECONDS = 3.0
QUIT_HINT = "Press Ctrl+C again to quit"
NARROW_NOTICE = "Terminal is narrow: widen it to at least 60 columns."
NO_KEY_MESSAGE = "No model provider key found. Set a provider key, then restart."
NO_FILES = "no files"


def _no_key_message() -> str:
    try:
        from galliani.tui.session import NO_KEYS    # the R15 message, owned by the headless layer
        return NO_KEYS
    except ImportError:    # pragma: no cover
        return NO_KEY_MESSAGE


class GallianiApp(App[int]):
    """Banner and transcript, plan panel, working line, bordered prompt box and a status line (spec 018 R2-R6)."""

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
        # motion (spec 018 R8-R12, R14)
        self.now: Callable[[], float] = time.monotonic    # tests replace it with a fake clock
        self.motion_failed = False
        self.ticker = Ticker(self, self._on_tick)
        self._task_started = 0.0
        self._flight_until = 0.0           # an entry transition is still in flight
        self._hint_until = 0.0
        self._entering: list[tuple[Any, float]] = []
        self._step_states: dict[str, str] = {}
        self._highlight: dict[str, float] = {}
        # completion (spec 018 R16, R17)
        self._completion: Any = None
        self._completion_stamp = 0
        self._dismissed: str | None = None    # prompt text for which Esc closed the popup

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

    # ---- layout (R2-R6): no header, no footer; borders only on banner, prompt box, plan panel, approval card

    def compose(self) -> ComposeResult:
        yield Static("", id="narrow", markup=False)
        with Horizontal(id="body"):
            yield TranscriptView(id="transcript")
            yield PlanPanel(id="plan-panel")
        yield PlanSummary(id="plan-summary")
        with Vertical(id="dock"):
            yield Static("", id="hint", markup=False)
            yield WorkingLine(id="working")
            yield CompletionPopup(id="popup")
            yield Static("", id="question-text", markup=False)
            yield QuestionInput(id="question")
            with Horizontal(id="promptbox"):
                yield Static(">", id="lead", markup=False)
                yield PromptArea(id="prompt")
            yield StatusBar(id="status")

    @property
    def transcript(self) -> TranscriptView:
        return self.query_one(TranscriptView)

    @property
    def prompt(self) -> PromptArea:
        return self.query_one(PromptArea)

    @property
    def status_bar(self) -> StatusBar:
        return self.query_one(StatusBar)

    @property
    def working_line(self) -> WorkingLine:
        return self.query_one(WorkingLine)

    @property
    def popup(self) -> CompletionPopup:
        return self.query_one(CompletionPopup)

    def on_mount(self) -> None:
        self.query_one("#question-text").display = False
        self.prompt.popup = self.popup
        self._show_banner()
        self._unsubscribe = self.session.subscribe(self._on_session_change)
        self._apply_width(self.size.width)
        self._sync()
        self.prompt.focus()

    def on_unmount(self) -> None:
        self.ticker.stop()
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def _show_banner(self) -> None:
        """R2: once, at the top of the transcript. `/clear` removes entries only, never the banner."""
        provider = getattr(self.session, "banner", None)
        if provider is None:
            return
        try:
            info = provider()
        except Exception:    # the banner is decoration; a failure must not stop the session
            return
        self.transcript.mount(Banner(info, no_key_message=_no_key_message(), id="banner"))

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

    # ---- motion: one gate, one ticker (R8, R9, R14)

    def _task_active(self) -> bool:
        return self._phase not in SETTLED_PHASES

    def _want_ticker(self) -> bool:
        return self._task_active() or self.now() < max(self._flight_until, self._hint_until)

    def _ensure_ticker(self) -> None:
        motion = motion_enabled(self)
        self.ticker.sync(self._want_ticker(), TICK_HZ if motion else TICK_HZ_STATIC)

    def _on_tick(self) -> None:
        """Only the working line, the running plan step and in-flight transitions change on a tick (R14)."""
        try:
            self._tick()
        except Exception:    # a ticker failure turns motion off for the session; the static output remains
            self.motion_failed = True
        self._ensure_ticker()

    def _tick(self) -> None:
        now = self.now()
        self._highlight = {sid: until for sid, until in self._highlight.items() if until > now}
        self._step_entries(now)
        self._refresh_working(now)
        self._refresh_plan(now)
        if self._hint_until and now >= self._hint_until:
            self._hint_until = 0.0
            self._clear_hint()

    def _refresh_working(self, now: float) -> None:
        state = self.session.state
        elapsed = now - self._task_started
        line = build_working_text(state.phase, state.status, state.plan, elapsed, now, motion=motion_enabled(self))
        self.working_line.set_line(line)

    def _refresh_plan(self, now: float) -> None:
        motion = motion_enabled(self)
        frame = spinner_frame(now) if motion and self._task_active() else None
        highlighted = frozenset(self._highlight) if motion else frozenset()
        plan = self.session.state.plan
        self.query_one(PlanPanel).set_plan(plan, frame=frame, highlighted=highlighted)
        self.query_one(PlanSummary).set_plan(plan, frame=frame, highlighted=highlighted)

    def _note_steps(self, plan: Any, now: float) -> None:
        """R11: a step that just finished is shown bold in its status colour for 400 ms (motion on only)."""
        states = {step.step_id: step.state for step in plan.steps} if plan is not None else {}
        if motion_enabled(self):
            for step_id, state in states.items():
                before = self._step_states.get(step_id)
                if before is not None and before != state and state in FINISHED_STEPS:
                    self._highlight[step_id] = now + HIGHLIGHT_SECONDS
                    self._flight_until = max(self._flight_until, now + HIGHLIGHT_SECONDS)
        self._step_states = states

    # ---- syncing with the session

    def _on_session_change(self) -> None:
        if self.is_running:
            self._sync()

    def _sync(self) -> None:
        state = self.session.state
        status = state.status
        now = self.now()
        before = self._phase
        self._phase = value_of(state.phase)
        if before in SETTLED_PHASES and self._phase not in SETTLED_PHASES:
            self._task_started = now
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
        self._note_steps(state.plan, now)
        self._refresh_plan(now)
        self._refresh_working(now)
        self.prompt.placeholder = ACTIVE_PLACEHOLDER if self._task_active() else IDLE_PLACEHOLDER
        self._sync_interaction(state)
        self._ensure_ticker()

    def _sync_interaction(self, state: Any) -> None:
        """Mount the approval card or question field while the session waits, and give focus back after."""
        pending = state.pending_approval
        question = state.question
        prompt = self.prompt
        box = self.query_one("#promptbox")
        dock = self.query_one("#dock")
        if pending is not None and (self._card is None or self._card.pending is not pending):
            self._remove_card()
            self._close_popup()
            self._card = ApprovalCard(pending, id="approval")
            self._prepare_entry(self._card)
            dock.mount(self._card, before=box)
            box.add_class("-hidden")
            prompt.add_class("-hidden")
            self._card.focus()
            self._animate_entry(self._card)
        elif pending is None and self._card is not None:
            self._remove_card()
            box.remove_class("-hidden")
            prompt.remove_class("-hidden")
            prompt.focus()
        question_input = self.query_one(QuestionInput)
        question_text = self.query_one("#question-text", Static)
        if question is not None and self._question != question:
            self._question = question
            self._close_popup()
            question_text.update(f"? {question}")
            question_text.display = True
            question_input.value = ""
            self._prepare_entry(question_input)
            question_input.add_class("-show")
            box.add_class("-hidden")
            prompt.add_class("-hidden")
            question_input.focus()
            self._animate_entry(question_input)
        elif question is None and self._question is not None:
            self._question = None
            question_text.display = False
            question_input.remove_class("-show")
            question_input.value = ""
            if self._card is None:
                box.remove_class("-hidden")
                prompt.remove_class("-hidden")
                prompt.focus()

    def _remove_card(self) -> None:
        if self._card is not None:
            self._card.remove()
            self._card = None

    # ---- approval card and question entry (R12)

    def _prepare_entry(self, widget: Any) -> None:
        """Set the first frame before mount so there is no flash: transparent, a row or two below."""
        if motion_enabled(self):
            widget.styles.opacity = 0.0
            widget.styles.offset = (0, CARD_ENTER_ROWS)

    def _animate_entry(self, widget: Any) -> None:
        """150-200 ms ease-out. Keys are live already: focus was set before the animation began.

        Textual fades the opacity smoothly; the slide is two rows, so the ticker steps it (Textual cannot
        animate an offset)."""
        if not motion_enabled(self):
            return
        now = self.now()
        self._flight_until = max(self._flight_until, now + CARD_ENTER_SECONDS + 0.05)
        self._entering.append((widget, now))
        widget.styles.animate("opacity", 1.0, duration=CARD_ENTER_SECONDS, easing="out_cubic")

    def _step_entries(self, now: float) -> None:
        keep = []
        for widget, started in self._entering:
            progress = min(1.0, (now - started) / CARD_ENTER_SECONDS)
            eased = 1.0 - (1.0 - progress) ** 3
            if widget.is_attached:
                widget.styles.offset = (0, round(CARD_ENTER_ROWS * (1.0 - eased)))
                if progress >= 1.0:
                    widget.styles.opacity = 1.0
            if progress < 1.0:
                keep.append((widget, started))
        self._entering = keep

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

    # ---- completion (spec 018 R16, R17, R21 display)

    def _close_popup(self) -> None:
        self._completion = None
        self._completion_stamp += 1
        self.popup.close()

    def on_text_area_changed(self, message: TextArea.Changed) -> None:
        if message.text_area is self.prompt:
            self._update_completion()

    def _update_completion(self) -> None:
        """A keystroke goes to the pure `complete_command`; folders, files and ids go to `Session.complete`."""
        prompt = self.prompt
        text = prompt.text
        if self._card is not None or self._question is not None:
            self._close_popup()
            return
        if text == self._dismissed:
            return
        self._dismissed = None
        cursor = prompt.cursor_offset()
        try:
            result = complete_command(text, cursor, task_active=self._task_active())
        except Exception:    # completion is a convenience; it must never break typing
            result = None
        self._completion_stamp += 1
        if result is None:
            self._completion = None
            self.popup.close()
        elif result.needs_io is not None:
            self._completion = None
            self.popup.close()
            self.run_worker(self._complete_io(text, cursor, self._completion_stamp, result.needs_io),
                            group="complete", exclusive=True, exit_on_error=False)
        else:
            self._show_completion(result)

    async def _complete_io(self, text: str, cursor: int, stamp: int, kind: str) -> None:
        try:
            result = await self.session.complete(text, cursor)
        except Exception:
            result = None
        if stamp != self._completion_stamp or self.prompt.text != text:
            return    # a late result for stale text is dropped
        if result is None:
            self.popup.close()
            return
        self._show_completion(result, no_files=kind == "file")

    def _show_completion(self, result: Any, *, no_files: bool = False) -> None:
        self._completion = result
        items = tuple(result.items)
        note = NO_FILES if (no_files and not items) else ""
        self.popup.show(items, note=note, truncated=bool(getattr(result, "truncated", False)))

    def on_prompt_area_completion_accept(self, message: PromptArea.CompletionAccept) -> None:
        """R17: Tab inserts. Enter inserts, and also sends when the item is a finished, enabled `submits` one."""
        item = self.popup.current
        result = self._completion
        if item is None or result is None:
            return
        prompt = self.prompt
        prompt.replace_span(result.start, prompt.cursor_offset(), item.insert)
        self._dismissed = None
        if message.enter and item.submits and item.enabled:
            self._close_popup()
            prompt.submit_text(prompt.text)
        elif item.kind in ("file", "memory_id"):
            self._dismissed = prompt.text    # a finished mention or id: the next Enter sends the line
            self._close_popup()
        else:
            self._update_completion()

    # ---- message handlers

    def on_prompt_area_submitted(self, message: PromptArea.Submitted) -> None:
        self._close_popup()
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
        """Spec 018 R17: with the popup open, Esc only closes it. Otherwise R23-R25: Esc denies an approval,
        cancels a question or a running task, and does nothing when idle."""
        if self.popup.display:
            self._dismissed = self.prompt.text
            self._close_popup()
            return
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
        self._hint_until = self.now() + QUIT_WINDOW_SECONDS    # the ticker clears it; no extra timer
        self._ensure_ticker()

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
        self.ticker.stop()
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
