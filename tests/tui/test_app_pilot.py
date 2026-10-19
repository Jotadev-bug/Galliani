"""Pilot tests for the Textual layer of spec 017 (R20-R29) and spec 018 (R1-R14, R16, R17), driven against `FakeSession`."""

from __future__ import annotations

import asyncio
import contextlib
import os
import time

import pytest

if os.environ.get("GALLIANI_REQUIRE_TUI") == "1":
    import textual  # noqa: F401  (a missing Textual must fail here, not skip)
else:
    pytest.importorskip("textual")

from rich.text import Text  # noqa: E402
from textual.geometry import Region  # noqa: E402
from textual.worker import WorkerCancelled  # noqa: E402

from galliani.permissions import EditMode  # noqa: E402
from galliani.tui import styles  # noqa: E402
from galliani.tui.app import GallianiApp, run_app  # noqa: E402
from galliani.tui.widgets import (  # noqa: E402
    ApprovalCard, Banner, CompletionPopup, EntryRow, PlanPanel, PlanSummary, PromptHistory, QuestionInput,
    StepList, build_status_text, build_working_text, motion_enabled, plan_summary_text, working_verb,
)

try:
    from .fake_session import (
        BannerInfo, Completion, CompletionResult, FakeSession, HAVE_COMPLETION, plan_view,
        stand_in_complete_command,
    )
except ImportError:
    from fake_session import (  # type: ignore[no-redef]
        Completion, CompletionResult, FakeSession, HAVE_COMPLETION, plan_view, stand_in_complete_command,
    )


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("NO_COLOR", "GALLIANI_REDUCED_MOTION", "TEXTUAL_ANIMATIONS"):
        monkeypatch.delenv(name, raising=False)
    if not HAVE_COMPLETION:   # headless layer predates spec 018: use the local copy of the contract
        monkeypatch.setattr("galliani.tui.app.complete_command", stand_in_complete_command)  # pragma: no cover


# ---------------------------------------------------------------- helpers

def plain(widget) -> str:
    content = getattr(widget, "content", None)
    if isinstance(content, Text):
        return content.plain
    source = getattr(widget, "source", None)
    return source if source is not None else str(content)


def tree_text(widget) -> str:
    """All text under a widget: every Static descendant, one per line."""
    return "\n".join(plain(w) for w in widget.query("Static") if plain(w))


def row_text(child) -> str:
    if isinstance(child, EntryRow):
        glyph, text = child.query("Static")
        return f"{plain(glyph)} {plain(text)}"
    if isinstance(child, Banner):
        return tree_text(child)
    return plain(child)


def transcript_text(app, *, banner: bool = False) -> str:
    return "\n".join(row_text(c) for c in app.transcript.children if banner or not isinstance(c, Banner))


async def settle(app, pilot) -> None:
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


async def type_and_send(app, pilot, text: str) -> None:
    app.prompt.focus()
    await pilot.press(*text)
    await pilot.press("enter")


async def send(app, pilot, text: str) -> None:
    await type_and_send(app, pilot, text)
    await settle(app, pilot)


def status_line(app) -> str:
    return plain(app.status_bar)


def calls(session, name: str) -> list[tuple]:
    return [c for c in session.calls if c[0] == name]


# ---------------------------------------------------------------- Send Objective

async def test_send_objective_shows_entries_in_order_and_returns_to_idle():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "summarize")
        text = transcript_text(app)
        order = [text.index(marker) for marker in
                 ("> summarize", "● Plan v1", "● read_file", "● Check passed", "● Result: done", "· Usage")]
        assert order == sorted(order)
        assert "Files changed: created summary.md" in text
        assert calls(session, "submit") == [("submit", "summarize")]
        assert session.state.phase.value == "idle"
        assert "Ready" in status_line(app)
        assert app.focused is app.prompt and app.prompt.text == ""
        assert "  └ Files changed: created summary.md" in transcript_text(app)


async def test_empty_or_blank_prompt_sends_nothing():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "   ")
        await pilot.press("enter")
        await settle(app, pilot)
        assert session.calls == []


async def test_result_markdown_is_literal_and_opens_no_links():
    body = "[bold]markup[/bold] and [x](http://example.com) \x1b]52;c;Zm9v\x07-free"
    session = FakeSession(result_body=body.replace("\x1b]52;c;Zm9v\x07", ""))
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "go")
        markdown = [c for c in app.transcript.children if type(c).__name__ == "EntryMarkdown"][0]
        assert markdown._open_links is False
        assert "[bold]markup[/bold]" in plain(markdown)


async def test_untrusted_square_brackets_in_entries_render_literally():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "[bold]hi[/bold] [red]x")
        assert "> [bold]hi[/bold] [red]x" in transcript_text(app)


# ---------------------------------------------------------------- approvals

async def _to_approval(app, pilot):
    await send(app, pilot, "write it")
    assert app.session.state.phase.value == "awaiting_approval"
    assert isinstance(app.focused, ApprovalCard)


async def test_approval_card_shows_fields_and_a_hint():
    app = GallianiApp(FakeSession(scenario="approval"))
    async with app.run_test(size=(100, 30)) as pilot:
        await _to_approval(app, pilot)
        card = plain(app.focused)
        assert "Write summary.md" in card and "Writes a file in the workspace" in card and "workspace" in card
        assert "[y] approve" in card and "[n] deny" in card and "[a] approve and accept edits" in card
        assert app.prompt.has_class("-hidden")


async def test_approval_y_runs_the_write_and_returns_focus_to_the_prompt():
    session = FakeSession(scenario="approval")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await _to_approval(app, pilot)
        await pilot.press("y")
        await settle(app, pilot)
        assert calls(session, "approve") == [("approve", False)]
        assert session.edit_mode == EditMode.ask
        assert app.focused is app.prompt and not app.prompt.has_class("-hidden")
        assert "Result: done" in transcript_text(app)


async def test_approval_n_denies():
    session = FakeSession(scenario="approval")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await _to_approval(app, pilot)
        await pilot.press("n")
        await settle(app, pilot)
        assert session.calls[-1] == ("deny",)
        assert "Result: blocked" in transcript_text(app)


async def test_approval_a_accepts_edits_for_the_task_only():
    session = FakeSession(scenario="approval")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await _to_approval(app, pilot)
        await pilot.press("a")
        await settle(app, pilot)
        assert calls(session, "approve") == [("approve", True)]
        assert "accept-edits" in status_line(app)


async def test_approval_a_is_not_shown_nor_accepted_when_not_offered():
    session = FakeSession(scenario="approval", can_accept_edits=False)
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await _to_approval(app, pilot)
        assert "[a]" not in plain(app.focused)
        await pilot.press("a")
        await settle(app, pilot)
        assert calls(session, "approve") == []
        assert session.state.phase.value == "awaiting_approval"


async def test_approval_esc_denies_and_other_keys_do_nothing():
    session = FakeSession(scenario="approval")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await _to_approval(app, pilot)
        await pilot.press("enter", "x", "space", "Y", "1")
        await settle(app, pilot)
        assert [c for c in session.calls if c[0] != "submit"] == []
        assert session.state.phase.value == "awaiting_approval"
        await pilot.press("escape")
        await settle(app, pilot)
        assert session.calls[-1] == ("deny",)
        assert "Result: blocked" in transcript_text(app)


async def test_one_key_press_decides_only_one_prompt():
    session = FakeSession(scenario="approval")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await _to_approval(app, pilot)
        await pilot.press("y", "y", "n")
        await settle(app, pilot)
        assert [c[0] for c in session.calls if c[0] in ("approve", "deny")] == ["approve"]


# ---------------------------------------------------------------- clarification

async def test_clarification_answer_continues_the_task():
    session = FakeSession(scenario="question")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "summarize")
        assert session.state.phase.value == "awaiting_answer"
        assert isinstance(app.focused, QuestionInput)
        assert "Which file should I summarize?" in plain(app.query_one("#question-text"))
        await pilot.press("enter")                       # empty answer: nothing happens
        await pilot.press(*"notes.txt")
        await pilot.press("enter")
        await settle(app, pilot)
        assert calls(session, "answer") == [("answer", "notes.txt")]
        assert "Summarized notes.txt" in transcript_text(app)
        assert app.focused is app.prompt


async def test_clarification_esc_cancels_the_task():
    session = FakeSession(scenario="question")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "summarize")
        await pilot.press("escape")
        await settle(app, pilot)
        assert calls(session, "cancel") and not calls(session, "answer")
        assert "Result: canceled" in transcript_text(app)
        assert app.focused is app.prompt


# ---------------------------------------------------------------- cancel and quit

@pytest.mark.parametrize("key", ["escape", "ctrl+c"])
async def test_cancel_while_running(key):
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await type_and_send(app, pilot, "long job")
        await pilot.pause()
        assert session.state.phase.value == "running"
        await pilot.press(key)
        await pilot.pause()
        assert calls(session, "cancel") == [("cancel",)]
        assert "Canceling" in status_line(app)
        session.finish_hold()
        await settle(app, pilot)
        assert "Result: canceled" in transcript_text(app)
        assert "Ready" in status_line(app)
        assert not calls(session, "aclose")


async def test_esc_and_single_ctrl_c_do_nothing_harmful_when_idle():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("escape")
        assert session.calls == []
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert plain(app.query_one("#hint")) == "Press Ctrl+C again to quit"
        assert app.is_running and session.calls == []


async def test_second_ctrl_c_while_running_cancels_then_quits_with_exit_code_zero():
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    started = None
    async with app.run_test(size=(100, 30)) as pilot:
        await type_and_send(app, pilot, "long job")
        await pilot.pause()
        await pilot.press("ctrl+c")
        started = time.monotonic()
        await pilot.press("ctrl+c")
        await app.workers.wait_for_complete()
        await pilot.pause()
    assert time.monotonic() - started < 3
    assert app.return_code == 0
    assert calls(session, "cancel") and calls(session, "aclose") == [("aclose", 2.5)]


async def test_quit_returns_within_three_seconds_when_closing_hangs():
    class HangingSession(FakeSession):
        async def aclose(self, timeout: float = 3.0) -> None:
            self.calls.append(("aclose", timeout))
            await asyncio.Event().wait()  # never returns

    session = HangingSession(scenario="hold")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await type_and_send(app, pilot, "long job")
        await pilot.pause()
        await pilot.press("ctrl+c")
        started = time.monotonic()
        await pilot.press("ctrl+c")
        with contextlib.suppress(WorkerCancelled):  # the held run is left behind when the app exits
            await app.workers.wait_for_complete()
    assert time.monotonic() - started <= 3.2  # R25: at most 3 seconds, plus test-loop slack
    assert app.return_code == 0


async def test_second_ctrl_c_after_the_window_does_not_quit():
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await type_and_send(app, pilot, "long job")
        await pilot.pause()
        await pilot.press("ctrl+c")
        app._last_interrupt -= 5
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.is_running and not calls(session, "aclose")
        session.finish_hold()
        await settle(app, pilot)


async def test_idle_ctrl_c_clears_text_then_needs_a_double_press_to_quit():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press(*"draft")
        await pilot.press("ctrl+c")
        assert app.prompt.text == "" and app.is_running
        await pilot.press("ctrl+c", "ctrl+c")
        await app.workers.wait_for_complete()
        await pilot.pause()
    assert app.return_code == 0 and calls(session, "aclose")


async def test_ctrl_q_and_slash_quit_exit_zero():
    for how in ("ctrl+q", "/quit"):
        session = FakeSession()
        app = GallianiApp(session)
        async with app.run_test(size=(100, 30)) as pilot:
            if how == "ctrl+q":
                await pilot.press("ctrl+q")
            else:
                await type_and_send(app, pilot, how)
            await app.workers.wait_for_complete()
            await pilot.pause()
        assert app.return_code == 0 and calls(session, "aclose")


async def test_second_objective_while_running_is_refused_with_a_notice():
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await type_and_send(app, pilot, "first")
        await pilot.pause()
        await type_and_send(app, pilot, "second")
        await pilot.pause()
        assert "A task is still running" in transcript_text(app)
        assert "> second" not in transcript_text(app)
        session.finish_hold()
        await settle(app, pilot)


# ---------------------------------------------------------------- prompt keys

async def test_history_up_and_down_recall_and_restore_the_draft():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "one")
        await send(app, pilot, "two")
        await pilot.press(*"draft")
        await pilot.press("up")
        assert app.prompt.text == "two"
        await pilot.press("up")
        assert app.prompt.text == "one"
        await pilot.press("up")                      # oldest: stays
        assert app.prompt.text == "one"
        await pilot.press("down", "down")
        assert app.prompt.text == "draft"
        await pilot.press("down")                    # past the newest: stays
        assert app.prompt.text == "draft"


async def test_history_with_nothing_recorded_leaves_the_prompt_alone():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press(*"abc")
        await pilot.press("up", "down")
        assert app.prompt.text == "abc"


def test_history_keeps_at_most_100_entries_in_memory():
    history = PromptHistory()
    for number in range(130):
        history.push(f"item {number}")
    assert len(history.items) == 100 and history.items[0] == "item 30"
    history.push("item 129")                         # consecutive duplicate is not stored again
    assert len(history.items) == 100


@pytest.mark.parametrize("key", ["alt+enter", "ctrl+j", "shift+enter"])
async def test_newline_keys_insert_a_newline_and_do_not_send(key):
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press("a", key, "b")
        assert app.prompt.text == "a\nb"
        assert session.calls == []
        await pilot.press("enter")
        await settle(app, pilot)
        assert calls(session, "submit") == [("submit", "a\nb")]


async def test_up_inside_a_multiline_draft_moves_the_cursor_not_history():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "old")
        app.prompt.focus()
        await pilot.press("a", "alt+enter", "b")
        await pilot.press("up")
        assert app.prompt.text == "a\nb"


# ---------------------------------------------------------------- slash commands

async def test_clear_hides_the_transcript_but_not_the_task():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "first")
        assert "> first" in transcript_text(app)
        await send(app, pilot, "/clear")
        assert transcript_text(app) == ""
        await send(app, pilot, "second")
        assert "> second" in transcript_text(app) and "> first" not in transcript_text(app)


async def test_theme_switches_and_an_invalid_theme_changes_nothing():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.theme == styles.DARK
        await send(app, pilot, "/theme light")
        assert app.theme == styles.LIGHT
        await send(app, pilot, "/theme neon")
        assert app.theme == styles.LIGHT and "Usage: /theme" in transcript_text(app)
        await send(app, pilot, "/theme dark")
        assert app.theme == styles.DARK


async def test_events_toggle_adds_and_removes_verbose_entries():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "/events on")
        assert "Detail event: route_selected" in transcript_text(app)
        await send(app, pilot, "/events off")
        assert "Detail event: route_selected" not in transcript_text(app)
        assert "Verbose events off" in transcript_text(app)


async def test_unknown_command_shows_an_error_and_changes_nothing():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "/nope")
        assert "Unknown command /nope" in transcript_text(app)
        assert app.is_running and app.theme == styles.DARK


async def test_double_slash_is_sent_as_an_objective():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "//etc/hosts")
        assert "> /etc/hosts" in transcript_text(app)


# ---------------------------------------------------------------- layout and width

def overflows(app) -> list[str]:
    width = app.size.width
    return [f"{w!r} {w.region}" for w in app.screen.query("*")
            if w.display and w.region.width and w.region.x + w.region.width > width]


@pytest.mark.parametrize("width", [80, 60])
async def test_narrow_layout_has_a_one_line_plan_summary_and_a_one_line_status_bar(width):
    session = FakeSession()
    session._plan = plan_view(2, ("verified", "running", "pending", "pending"))
    app = GallianiApp(session)
    async with app.run_test(size=(width, 24)) as pilot:
        await pilot.pause()
        summary, panel = app.query_one(PlanSummary), app.query_one(PlanPanel)
        assert summary.display and not panel.display
        assert summary.region.height == 1
        assert plain(summary.query_one("#summary-head")).startswith("Plan v2 - step 2/4 - running")
        assert app.status_bar.region.height == 1
        assert len(status_line(app)) <= width - 2
        assert overflows(app) == []
        assert app.transcript.max_scroll_x == 0
        assert not app.query_one("#narrow").has_class("-show") or width < 60
        await send(app, pilot, "go")
        assert overflows(app) == [] and app.status_bar.region.height == 1


async def test_ctrl_t_expands_the_summary_in_place():
    session = FakeSession()
    session._plan = plan_view(2, ("verified", "running", "pending", "pending"))
    app = GallianiApp(session)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        summary = app.query_one(PlanSummary)
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert summary.region.height == 5 and "[ok] 1. Read the notes" in tree_text(summary)
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert summary.region.height == 1


async def test_wide_layout_docks_the_plan_panel_and_ctrl_t_hides_it():
    session = FakeSession()
    session._plan = plan_view(2, ("verified", "running", "pending", "pending"))
    app = GallianiApp(session)
    async with app.run_test(size=(110, 30)) as pilot:
        await pilot.pause()
        panel = app.query_one(PlanPanel)
        assert panel.display and not app.query_one(PlanSummary).display
        assert panel.region.x > app.transcript.region.x
        assert "running" in tree_text(panel) and "2. Draft the summary (running)" in tree_text(panel)
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert not panel.display


async def test_below_60_columns_a_notice_asks_for_a_wider_terminal_and_the_app_keeps_working():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(50, 24)) as pilot:
        await pilot.pause()
        assert app.query_one("#narrow").has_class("-show")
        assert "60 columns" in plain(app.query_one("#narrow"))
        await send(app, pilot, "go")
        assert "Result: done" in transcript_text(app)


async def test_resize_across_the_breakpoint_switches_layouts():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.query_one(PlanSummary).display
        await pilot.resize_terminal(120, 30)
        await pilot.pause()
        assert app.query_one(PlanPanel).display and not app.query_one(PlanSummary).display


def _snapshot(workspace="C:/work/a-very-long-project-folder-name"):
    from pathlib import Path
    session = FakeSession(workspace=Path(workspace))
    session._cost = 0.0123
    return session.state.status


def test_status_fields_drop_in_order_and_workspace_trims_last():
    status = _snapshot()
    full = build_status_text(status, "running", 200).plain
    assert all(part in full for part in ("a-very-long-project-folder-name", "route mock-1", "$0.0123 / $0.50",
                                          "ask", "memory on"))
    mid = build_status_text(status, "idle", 83).plain
    assert "memory on" not in mid and "route mock-1" in mid
    short = build_status_text(status, "idle", 70).plain
    assert "route" not in short and "$0.0123 / $0.50" in short and "ask" in short and "Ready" in short
    tiny = build_status_text(status, "idle", 44).plain
    assert tiny.startswith("…") and tiny.endswith("Ready") and len(tiny) <= 42


def test_plan_summary_text_covers_each_state():
    assert plan_summary_text(plan_view(3, ("verified",) * 4)) == "Plan v3 - step 4/4 - done"
    assert plan_summary_text(plan_view(1, ("failed", "pending", "pending", "pending"))) == "Plan v1 - step 1/4 - failed"


# ---------------------------------------------------------------- focus and keyboard (R29)

async def test_tab_cycles_prompt_transcript_and_plan_and_focus_is_visible():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        seen = [app.focused]
        for _ in range(3):
            await pilot.press("tab")
            seen.append(app.focused)
        assert seen[0] is app.prompt
        assert {type(w).__name__ for w in seen} >= {"PromptArea", "TranscriptView", "PlanPanel"}
        await pilot.press("shift+tab")
        assert app.focused is not seen[-1]


async def test_transcript_scrolls_with_page_keys_and_home_end():
    session = FakeSession(result_body="\n\n".join(f"line {i}" for i in range(80)))
    app = GallianiApp(session)
    async with app.run_test(size=(100, 20)) as pilot:
        await send(app, pilot, "go")
        app.transcript.focus()
        await pilot.press("home")
        await pilot.wait_for_scheduled_animations()
        assert app.transcript.scroll_y == 0
        await pilot.press("pagedown")
        await pilot.wait_for_scheduled_animations()
        assert app.transcript.scroll_y > 0
        await pilot.press("end")
        await pilot.wait_for_scheduled_animations()
        assert app.transcript.scroll_y == app.transcript.max_scroll_y


async def test_command_palette_and_screenshots_are_disabled():
    app = GallianiApp(FakeSession())
    assert app.ENABLE_COMMAND_PALETTE is False and not app.COMMANDS
    async with app.run_test(size=(100, 30)) as pilot:
        depth = len(app.screen_stack)
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert len(app.screen_stack) == depth and not app.use_command_palette
        assert list(app.get_system_commands(app.screen)) == []
        assert app.action_screenshot() is None
        keys = {binding.action for _, binding in app._bindings} | {b.action for b in app.screen.BINDINGS}
        assert not any("screenshot" in action or "palette" in action for action in keys)


# ---------------------------------------------------------------- colour (R27, R28)

def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("palette", [styles.DARK_PALETTE, styles.LIGHT_PALETTE], ids=["dark", "light"])
def test_text_colours_meet_4_5_to_1_on_both_surfaces(palette):
    for name in ("fg", "muted", "accent", "good", "warn", "bad", "agent"):
        for surface in ("bg", "surface"):
            assert contrast(palette[name], palette[surface]) >= 4.5, (name, surface)


def test_dark_theme_uses_the_decision_0025_background():
    assert styles.DARK_PALETTE["bg"] == "#121318"


def _rendered_styles(app):
    """Segments of the whole screen after the app's colour filters, as the terminal would receive them."""
    background = app.screen.styles.background
    found = []
    for widget in app.screen.query("*"):
        if not widget.display or not widget.region.area:
            continue
        for strip in widget.render_lines(Region(0, 0, widget.size.width, widget.size.height)):
            for flt in app._filters:
                strip = strip.apply_filter(flt, background)
            found.extend(segment.style for segment in strip if segment.style)
    return found


async def test_no_color_emits_no_color_and_state_stays_readable_from_text():
    session = FakeSession(scenario="approval")
    os.environ["NO_COLOR"] = "1"
    try:
        app = GallianiApp(session)
        async with app.run_test(size=(100, 30)) as pilot:
            await _to_approval(app, pilot)
            assert app.no_color and app.ansi_mode and app.theme == styles.ANSI
            colored = [s for s in _rendered_styles(app)
                       if (s.color is not None and s.color.name != "default")
                       or (s.bgcolor is not None and s.bgcolor.name != "default")]
            assert colored == []
            screen_text = transcript_text(app) + status_line(app) + plain(app.focused)
            assert "ask" in status_line(app) and "Needs your approval" in status_line(app)
            assert "[y] approve" in screen_text and "Approval needed" in screen_text
            await pilot.press("y")
            await settle(app, pilot)
    finally:
        del os.environ["NO_COLOR"]


async def test_colour_is_emitted_when_no_color_is_not_set():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert not app.no_color and app.theme == styles.DARK
        assert any(s.bgcolor is not None and s.bgcolor.name != "default" for s in _rendered_styles(app))


async def test_sixteen_colour_terminals_get_the_ansi_theme():
    app = GallianiApp(FakeSession(), ansi=True)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.theme == styles.ANSI
        await send(app, pilot, "/theme light")
        assert app.theme == styles.ANSI


async def test_light_theme_flag_starts_light():
    app = GallianiApp(FakeSession(), theme="light")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.theme == styles.LIGHT


# ---------------------------------------------------------------- motion (spec 018 R8-R14): see the section below


def test_textual_reads_animation_level_from_the_environment(monkeypatch):
    import importlib

    from textual import constants
    monkeypatch.setenv("TEXTUAL_ANIMATIONS", "none")
    try:
        importlib.reload(constants)
        assert constants.TEXTUAL_ANIMATIONS == "none"
    finally:
        monkeypatch.delenv("TEXTUAL_ANIMATIONS", raising=False)
        importlib.reload(constants)


# ================================================================ spec 018: look and feel (R1-R7)

class Clock:
    """A fake monotonic clock: tests move `t` and then call `app.ticker.fire()`."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _borders(app) -> set[str]:
    kinds = set()
    for widget in app.screen.query("*"):
        if not widget.display or not widget.region.area:
            continue
        if any(edge[0] not in ("", "none", "blank") for edge in
               (widget.styles.border_top, widget.styles.border_left, widget.styles.border_bottom,
                widget.styles.border_right)):
            kinds.add(type(widget).__name__ + ("#" + widget.id if widget.id else ""))
    return kinds


async def test_banner_shows_version_workspace_providers_settings_and_tips_once():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        banner = app.query_one(Banner)
        text = tree_text(banner)
        for part in ("Galliani 0.2.0", "~/projects/notes", "routing: auto · anthropic · openai",
                     "edit mode: ask · budget: $0.50 · memory: on", "/help for commands", "/ to complete commands",
                     "Esc to stop a task", "@ to mention a file"):
            assert part in text, part
        assert "whole home folder" not in text
        assert banner.styles.border_top[0] == "round"
        await send(app, pilot, "/clear")
        await send(app, pilot, "hello")
        assert len(app.query(Banner)) == 1 and banner.is_attached      # /clear does not show or drop it again


async def test_banner_without_a_key_shows_the_no_key_message_and_the_wide_workspace_warning():
    info = BannerInfo(version="0.2.0", workspace="~", providers=(), wide_workspace=True,
                      edit_mode=EditMode.accept_edits, budget_usd=None, memory="unavailable")
    app = GallianiApp(FakeSession(banner_info=info))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        text = tree_text(app.query_one(Banner))
        assert "No model provider key found" in text and "routing: auto" not in text
        assert "edit mode: accept-edits · budget: no limit · memory: unavailable" in text
        assert "This workspace is your whole home folder (or drive)" in text and "galliacli" in text


async def test_banner_trims_a_long_workspace_from_the_left():
    info = BannerInfo(version="0.2.0", workspace="~/" + "deep/" * 30 + "project", providers=("anthropic",),
                      wide_workspace=False, edit_mode=EditMode.ask, budget_usd=0.5, memory="on")
    app = GallianiApp(FakeSession(banner_info=info))
    async with app.run_test(size=(60, 24)) as pilot:
        await pilot.pause()
        await pilot.pause()
        line = plain(app.query_one(".b-workspace"))
        assert line.startswith("…") and line.endswith("project") and len(line) <= 60 - 6


async def test_no_header_or_footer_and_borders_only_where_the_spec_allows():
    app = GallianiApp(FakeSession(scenario="approval"))
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert not app.screen.query("Header, Footer")
        assert _borders(app) == {"Banner#banner", "Horizontal#promptbox", "PlanPanel#plan-panel"}
        await _to_approval(app, pilot)
        assert _borders(app) == {"Banner#banner", "PlanPanel#plan-panel", "ApprovalCard#approval"}
    narrow = GallianiApp(FakeSession())
    async with narrow.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert _borders(narrow) == {"Banner#banner", "Horizontal#promptbox"}


async def test_prompt_box_has_a_lead_glyph_placeholder_and_a_heavier_border_when_focused():
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        box = app.query_one("#promptbox")
        assert plain(app.query_one("#lead")) == ">"
        assert app.focused is app.prompt and box.styles.border_top[0] == "heavy"      # visible under NO_COLOR too
        app.transcript.focus()
        await pilot.pause()
        assert box.styles.border_top[0] == "round"
        app.prompt.focus()
        assert app.prompt.placeholder == "Type an objective, or / for commands"
        await type_and_send(app, pilot, "go")
        await pilot.pause()
        assert app.prompt.placeholder == "Esc to stop"
        session.finish_hold()
        await settle(app, pilot)
        assert app.prompt.placeholder == "Type an objective, or / for commands"


async def test_status_line_sits_directly_under_the_prompt_box():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        box, status = app.query_one("#promptbox"), app.status_bar
        assert status.region.y == box.region.y + box.region.height
        assert status.region.y + status.region.height == app.size.height
        assert status.region.height == 1


async def test_entries_are_compact_with_one_blank_line_between_turns_only():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 40)) as pilot:
        await send(app, pilot, "first")
        await send(app, pilot, "second")
        rows = [c for c in app.transcript.children if isinstance(c, EntryRow)]
        users = [r for r in rows if r.has_class("-user")]
        assert [r.styles.margin.top for r in users] == [1, 1]
        assert all(r.styles.margin.top == 0 for r in rows if not r.has_class("-user"))
        glyphs = {kind: plain(next(r for r in rows if r.has_class(f"-{kind}")).query_one(".glyph"))
                  for kind in ("user", "tool", "verification", "result", "usage")}
        assert glyphs == {"user": ">", "tool": "●", "verification": "●", "result": "●", "usage": "·"}
        detail = [c for c in app.transcript.children if c.has_class("detail")]
        assert detail and plain(detail[-1]).startswith("  └ ")


async def test_error_entries_use_the_error_glyph_and_style():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "/nope")
        row = next(c for c in app.transcript.children if isinstance(c, EntryRow) and c.has_class("-error"))
        assert plain(row.query_one(".glyph")) == "●" and "Unknown command /nope" in row_text(row)


async def test_file_mentions_show_as_plain_text_in_the_user_turn():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "summarize @notes/q3.md please")
        assert "> summarize @notes/q3.md please" in transcript_text(app)


# ---------------------------------------------------------------- widths 80 and 60 with everything open

@pytest.mark.parametrize("width", [80, 60])
async def test_banner_working_line_popup_and_card_fit_at_80_and_60_columns(width):
    session = FakeSession(scenario="approval")
    app = GallianiApp(session)
    async with app.run_test(size=(width, 24)) as pilot:
        await pilot.pause()
        assert overflows(app) == []
        app.prompt.focus()
        await pilot.press("/")
        await pilot.pause()
        assert app.popup.display and overflows(app) == []
        await pilot.press("escape", "backspace")
        await _to_approval(app, pilot)
        assert overflows(app) == []
        assert app.working_line.region.height == 1 and app.status_bar.region.height == 1
        assert len(plain(app.working_line)) <= width - 2


# ================================================================ spec 018: motion (R8-R14)

@pytest.mark.parametrize("setup, expected", [
    ({}, True),
    ({"env": {"GALLIANI_REDUCED_MOTION": "1"}}, False),
    ({"env": {"GALLIANI_REDUCED_MOTION": "0"}}, True),
    ({"animation_level": "none"}, False),
    ({"animation_level": "basic"}, True),
    ({"env": {"NO_COLOR": "1"}}, False),
    ({"ansi": True}, False),
], ids=["default", "reduced-env", "reduced-env-off", "level-none", "level-basic", "no-color", "ansi-theme"])
async def test_motion_enabled_is_the_single_gate(setup, expected, monkeypatch):
    for name, value in setup.get("env", {}).items():
        monkeypatch.setenv(name, value)
    app = GallianiApp(FakeSession(), ansi=setup.get("ansi"))
    async with app.run_test(size=(100, 30)) as pilot:
        if "animation_level" in setup:
            app.animation_level = setup["animation_level"]
        await pilot.pause()
        assert motion_enabled(app) is expected


async def test_motion_turns_off_after_the_ticker_fails_once():
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await type_and_send(app, pilot, "go")
        await pilot.pause()
        assert motion_enabled(app)

        def boom(now):
            raise RuntimeError("boom")

        app._refresh_working = boom                                                   # a ticker failure
        app.ticker.fire()
        assert not motion_enabled(app) and app.ticker.running and app.ticker.hz == 1.0
        assert app.is_running
        session.finish_hold()
        with contextlib.suppress(Exception):
            await settle(app, pilot)


async def test_ticker_runs_only_while_a_task_is_active_and_at_most_ten_times_a_second():
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert not app.ticker.running
        await type_and_send(app, pilot, "go")
        await pilot.pause()
        assert app.ticker.running and 0 < app.ticker.hz <= 10
        session.finish_hold()
        await settle(app, pilot)


async def test_idle_means_no_timers_and_no_widget_refresh():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        assert not app.ticker.running
        await send(app, pilot, "go")
        await asyncio.sleep(0.8)         # the 400 ms step highlight has settled
        await pilot.pause()
        assert not app.ticker.running
        counts = (app.working_line.updates, app.status_bar.updates, app.ticker.ticks,
                  sum(w.renders for w in app.query(StepList)))
        await asyncio.sleep(2.0)
        await pilot.pause()
        assert not app.ticker.running and app.ticker._timer is None
        assert (app.working_line.updates, app.status_bar.updates, app.ticker.ticks,
                sum(w.renders for w in app.query(StepList))) == counts
        assert plain(app.working_line) == ""


async def test_a_tick_that_changes_nothing_refreshes_nothing():
    clock = Clock()
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    app.now = clock
    async with app.run_test(size=(100, 30)) as pilot:
        await type_and_send(app, pilot, "go")
        await pilot.pause()
        app.ticker.fire()
        before = (app.working_line.updates, sum(w.renders for w in app.query(StepList)))
        app.ticker.fire()
        app.ticker.fire()
        assert (app.working_line.updates, sum(w.renders for w in app.query(StepList))) == before
        clock.t += 1.0
        app.ticker.fire()
        assert app.working_line.updates == before[0] + 1          # the elapsed second changed
        session.finish_hold()
        await settle(app, pilot)


async def test_working_line_has_a_spinner_rotating_verbs_elapsed_cost_and_step_progress():
    clock = Clock()
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    app.now = clock
    async with app.run_test(size=(100, 30)) as pilot:
        await type_and_send(app, pilot, "go")
        await pilot.pause()
        seen = []
        for advance in (0.0, 3.1, 3.1, 3.1):
            clock.t += advance
            app.ticker.fire()
            seen.append(plain(app.working_line))
        verbs = [working_verb("running", e) for e in (0.0, 3.1, 6.2, 9.3)]
        assert len(set(verbs)) == 4
        for line, verb in zip(seen, verbs):
            assert f" {verb}… · " in line, (line, verb)
            assert line[0] in "·•●" and "$0.0000 / $0.50" in line and line.endswith("step 1/4")
        assert "9s" in seen[-1]
        session.finish_hold()
        await settle(app, pilot)
        assert plain(app.working_line) == ""


def test_working_text_hides_what_it_cannot_know():
    class S:
        status_label = "Planning"
        task_cost_usd = 0.0
        budget_usd = None

    line = build_working_text("running", S, None, 4.0, 1000.0, motion=True)
    assert "step" not in line and "$0.0000 / no limit" in line and " 4s " in line
    waiting = build_working_text("awaiting_approval", S, None, 0.0, 1000.0, motion=True)
    assert waiting.startswith("● Waiting for you…")
    assert build_working_text("idle", S, None, 0.0, 0.0, motion=True) == ""
    assert build_working_text("closed", S, None, 0.0, 0.0, motion=False) == ""


async def test_plan_step_glyph_changes_at_once_then_the_finished_step_is_bold_for_400ms():
    clock = Clock()
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    app.now = clock
    async with app.run_test(size=(120, 30)) as pilot:
        await type_and_send(app, pilot, "go")
        await pilot.pause()
        rows = list(app.query_one(PlanPanel).query(".step"))
        assert plain(rows[0]).startswith(("·", "•", "●")) and "(running)" in plain(rows[0])   # spinner frame
        session.set_plan(("verified", "running", "pending", "pending"))
        await pilot.pause()
        rows = list(app.query_one(PlanPanel).query(".step"))
        assert plain(rows[0]).startswith("[ok]") and rows[0].has_class("-fresh")
        assert not rows[1].has_class("-fresh") and not rows[3].has_class("-fresh")
        clock.t += 0.2
        app.ticker.fire()
        assert rows[0].has_class("-fresh")
        clock.t += 0.3
        app.ticker.fire()
        assert not rows[0].has_class("-fresh") and plain(rows[0]).startswith("[ok]")      # settled, glyph kept
        session.finish_hold()
        await settle(app, pilot)


async def test_a_failed_step_is_highlighted_too():
    clock = Clock()
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    app.now = clock
    async with app.run_test(size=(120, 30)) as pilot:
        await type_and_send(app, pilot, "go")
        await pilot.pause()
        session.set_plan(("failed", "running", "pending", "pending"))
        await pilot.pause()
        assert list(app.query_one(PlanPanel).query(".step"))[0].has_class("-fresh")
        session.finish_hold()
        await settle(app, pilot)


@pytest.mark.parametrize("how", ["env", "animation-level", "no-color"])
async def test_reduced_motion_is_static(how, monkeypatch):
    if how == "env":
        monkeypatch.setenv("GALLIANI_REDUCED_MOTION", "1")
    if how == "no-color":
        monkeypatch.setenv("NO_COLOR", "1")
    clock = Clock()
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    app.now = clock
    async with app.run_test(size=(120, 30)) as pilot:
        if how == "animation-level":
            app.animation_level = "none"
        await type_and_send(app, pilot, "go")
        await pilot.pause()
        assert not motion_enabled(app)
        assert app.ticker.running and app.ticker.hz <= 1                      # elapsed time and cost only
        lines = []
        for advance in (0.0, 3.5, 7.0):
            clock.t += advance
            app.ticker.fire()
            lines.append(plain(app.working_line))
        assert all(line.startswith("● Working · ") for line in lines)          # static glyph, verb does not rotate
        assert "10s" in lines[-1] and "…" not in lines[-1]
        session.set_plan(("verified", "running", "pending", "pending"))
        await pilot.pause()
        rows = list(app.query_one(PlanPanel).query(".step"))
        assert plain(rows[1]).startswith(">") and not any(r.has_class("-fresh") for r in rows)
        session.finish_hold()
        await settle(app, pilot)
        assert not app.ticker.running


@pytest.mark.parametrize("how", ["env", "animation-level"])
async def test_reduced_motion_shows_the_approval_card_without_a_transition(how, monkeypatch):
    if how == "env":
        monkeypatch.setenv("GALLIANI_REDUCED_MOTION", "1")
    app = GallianiApp(FakeSession(scenario="approval"))
    async with app.run_test(size=(100, 30)) as pilot:
        if how == "animation-level":
            app.animation_level = "none"
        await _to_approval(app, pilot)
        card = app.focused
        assert card.styles.opacity == 1.0 and card.styles.offset.y.value == 0
        assert app._flight_until == 0.0
        await pilot.press("y")
        await settle(app, pilot)
        assert calls(app.session, "approve") == [("approve", False)]


async def test_approval_card_fades_in_but_its_keys_are_live_from_the_first_frame():
    session = FakeSession(scenario="approval")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await type_and_send(app, pilot, "write it")
        await pilot.pause()
        assert isinstance(app.focused, ApprovalCard)
        assert app._flight_until > app.now()                                  # a transition is in flight
        await pilot.press("y")                                               # no wait: the key is not swallowed
        await settle(app, pilot)
        assert calls(session, "approve") == [("approve", False)]
        assert "Result: done" in transcript_text(app)


async def test_approval_card_ends_fully_opaque_in_place():
    app = GallianiApp(FakeSession(scenario="approval"))
    async with app.run_test(size=(100, 30)) as pilot:
        await _to_approval(app, pilot)
        await asyncio.sleep(0.5)                       # 180 ms of motion plus slack
        await pilot.pause()
        assert app.focused.styles.opacity == 1.0 and app.focused.styles.offset.y.value == 0


async def test_question_field_gets_the_same_entry_transition_and_keys_stay_live():
    session = FakeSession(scenario="question")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "summarize")
        assert isinstance(app.focused, QuestionInput)
        await pilot.press(*"a.txt")
        await pilot.press("enter")
        await settle(app, pilot)
        assert calls(session, "answer") == [("answer", "a.txt")]


async def test_the_ticker_also_covers_a_transition_in_flight_after_the_task_ends():
    clock = Clock()
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    app.now = clock
    async with app.run_test(size=(120, 30)) as pilot:
        await type_and_send(app, pilot, "go")
        await pilot.pause()
        session._plan = plan_view(1, ("verified",) * 4)
        session._phase = type(session._phase).idle
        session._notify()
        await pilot.pause()
        assert app.ticker.running                                            # idle, but a highlight is in flight
        clock.t += 1.0
        app.ticker.fire()
        assert not app.ticker.running
        session._release.set()
        with contextlib.suppress(Exception):
            await settle(app, pilot)


async def test_ctrl_c_hint_clears_through_the_ticker_without_its_own_timer():
    clock = Clock()
    app = GallianiApp(FakeSession())
    app.now = clock
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+c")
        assert app.query_one("#hint").has_class("-show") and app.ticker.running
        clock.t += 2.5
        app.ticker.fire()
        assert not app.query_one("#hint").has_class("-show") and not app.ticker.running


# ================================================================ spec 018: completion popup (R16, R17)

def popup_text(app) -> str:
    return plain(app.popup)


async def test_slash_opens_a_popup_with_summaries_filtered_by_what_is_typed():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press("/")
        await pilot.pause()
        assert app.popup.display and "/help" in popup_text(app) and "list commands and keys" in popup_text(app)
        assert popup_text(app).splitlines()[0].startswith("› /")
        await pilot.press("m", "e")
        assert "/memory" in popup_text(app) and "/help" not in popup_text(app)
        assert app.popup.region.y + app.popup.region.height <= app.query_one("#promptbox").region.y     # above it


async def test_slash_me_down_tab_inserts_memory_and_switches_to_argument_choices():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press("/", "m", "e", "down", "tab")
        await pilot.pause()
        assert app.prompt.text == "/memory "
        for word in ("list", "forget", "on", "off"):
            assert word in popup_text(app)
        await pilot.press("escape")
        assert not app.popup.display and app.prompt.text == "/memory "          # Esc closes and leaves the text


async def test_up_and_down_move_the_selection_not_history_while_the_popup_is_open():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "one")
        app.prompt.focus()
        await pilot.press("/", "down")
        assert app.prompt.text == "/" and popup_text(app).splitlines()[1].startswith("› ")
        await pilot.press("up", "up")
        assert app.prompt.text == "/"                                              # wrapped, never history
        await pilot.press("down", "down", "tab")                                   # last -> first -> second
        assert app.prompt.text == "/clear" and calls(app.session, "submit") == [("submit", "one")]


async def test_up_and_down_recall_history_again_once_the_popup_is_closed():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "one")
        app.prompt.focus()
        await pilot.press("/", "escape")
        assert not app.popup.display
        await pilot.press("backspace")
        await pilot.press("up")
        assert app.prompt.text == "one"


async def test_enter_sends_a_command_that_takes_no_argument_at_once():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press("/", "h", "e", "l", "enter")
        await settle(app, pilot)
        assert calls(session, "submit") == [("submit", "/help")] and app.prompt.text == ""
        assert not app.popup.display


async def test_enter_only_inserts_a_command_with_an_argument_and_sends_a_finished_argument():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press("/", "t", "h", "enter")
        await pilot.pause()
        assert app.prompt.text == "/theme " and calls(session, "submit") == []
        assert "dark" in popup_text(app) and "light" in popup_text(app)
        await pilot.press("down", "enter")                                         # a finished argument: sent
        await settle(app, pilot)
        assert calls(session, "submit") == [("submit", "/theme light")]
        assert app.theme == styles.LIGHT


async def test_esc_closes_the_popup_first_and_a_second_esc_cancels_the_task():
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await type_and_send(app, pilot, "long job")
        await pilot.pause()
        app.prompt.focus()
        await pilot.press("/")
        assert app.popup.display
        await pilot.press("escape")
        assert not app.popup.display and calls(session, "cancel") == []             # the task keeps running
        assert session.state.phase.value == "running"
        await pilot.press("escape")
        await pilot.pause()
        assert calls(session, "cancel") == [("cancel",)]
        session.finish_hold()
        await settle(app, pilot)


async def test_commands_refused_while_a_task_runs_stay_listed_dimmed_and_marked():
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await type_and_send(app, pilot, "long job")
        await pilot.pause()
        app.prompt.focus()
        await pilot.press("/", "w", "o", "r", "k")
        text = popup_text(app)
        assert "/workspace" in text and "(not while a task runs)" in text
        session.finish_hold()
        await settle(app, pilot)


async def test_a_disabled_item_is_inserted_but_never_sent_by_enter():
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await type_and_send(app, pilot, "long job")
        await pilot.pause()
        app.prompt.focus()
        await pilot.press("/", "q")
        item = Completion("/quit", "/quit", "quit", "command", enabled=False, submits=True)
        app._completion = CompletionResult(start=0, items=(item,))
        app.popup.show((item,))
        await pilot.press("enter")
        await pilot.pause()
        assert [c for c in session.calls if c[0] == "submit"] == [("submit", "long job")]
        assert app.prompt.text.startswith("/quit")
        session.finish_hold()
        await settle(app, pilot)


async def test_an_unknown_command_filters_the_popup_to_nothing_and_enter_sends_it():
    session = FakeSession()
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press(*"/zzzq")
        assert not app.popup.display
        await pilot.press("enter")
        await settle(app, pilot)
        assert "Unknown command /zzzq" in transcript_text(app)


async def test_double_slash_and_plain_text_open_no_popup():
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press(*"//etc")
        assert not app.popup.display
        app.prompt.clear_prompt()
        await pilot.press(*"hello")
        assert not app.popup.display


def _files(text: str, cursor: int) -> CompletionResult:
    start = text.rfind("@")
    name = f"@{text[start + 1:cursor]}.md"
    return CompletionResult(start=start, items=(Completion(name, name, kind="file"),))


async def test_at_sign_lists_files_from_the_session_and_tab_inserts_plain_text():
    session = FakeSession(completions=lambda text, cursor: CompletionResult(
        start=text.rfind("@"), items=(Completion("@notes.md", "@notes.md", kind="file"),
                                       Completion("@src/app.py", "@src/app.py", kind="file"))))
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press(*"read @")
        await settle(app, pilot)
        assert "@notes.md" in popup_text(app) and "@src/app.py" in popup_text(app)
        await pilot.press("tab")
        await pilot.pause()
        assert app.prompt.text == "read @notes.md" and not app.popup.display       # a finished mention
        await pilot.press("enter")
        await settle(app, pilot)
        assert calls(session, "submit") == [("submit", "read @notes.md")]
        assert "> read @notes.md" in transcript_text(app)


async def test_a_late_completion_result_for_stale_text_is_dropped():
    session = FakeSession(completions=_files, complete_delay=0.25)
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press("@", "a")
        await asyncio.sleep(0.05)
        await pilot.press("b")
        await asyncio.sleep(0.6)
        await settle(app, pilot)
        assert app.popup.current.label == "@ab.md"
        assert "@a.md" not in popup_text(app)


async def test_an_at_sign_with_no_files_says_so_and_the_next_key_closes_it():
    def listing(text, cursor):
        return CompletionResult(start=text.rfind("@"), items=()) if text.endswith("@") else None

    session = FakeSession(completions=listing)
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press("@")
        await settle(app, pilot)
        assert app.popup.display and "no files" in popup_text(app) and app.popup.current is None
        await pilot.press("x")
        await settle(app, pilot)
        assert not app.popup.display


async def test_a_listing_error_gives_no_popup_no_error_entry_and_no_crash():
    def broken(text, cursor):
        raise PermissionError("denied")

    session = FakeSession(completions=broken)
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press(*"look at @")
        await settle(app, pilot)
        assert app.is_running and not app.popup.display and app.prompt.text == "look at @"
        assert "error" not in transcript_text(app).lower()


async def test_a_truncated_listing_ends_with_an_ellipsis_row():
    items = tuple(Completion(f"/d{i}/", f"/d{i}/", kind="folder") for i in range(5))
    session = FakeSession(completions=lambda text, cursor: CompletionResult(start=11, items=items, truncated=True))
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press(*"/workspace ")
        await settle(app, pilot)
        assert popup_text(app).splitlines()[-1].strip() == "…" and "/d0/" in popup_text(app)


async def test_the_popup_is_not_offered_once_an_approval_card_is_showing():
    session = FakeSession(scenario="approval")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await _to_approval(app, pilot)
        assert not app.popup.display and app.prompt.has_class("-hidden")
        await pilot.press("/", "q")
        assert not app.popup.display and app.prompt.text == ""
        await pilot.press("escape")
        await settle(app, pilot)


async def test_nothing_in_the_popup_can_answer_a_prompt():
    session = FakeSession(scenario="question")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        await send(app, pilot, "summarize")
        await pilot.press("/", "tab", "enter")
        assert not app.popup.display and [c for c in session.calls if c[0] == "answer"] == []


async def test_no_color_keeps_the_popup_selection_and_the_focus_border_readable(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    app = GallianiApp(FakeSession())
    async with app.run_test(size=(100, 30)) as pilot:
        app.prompt.focus()
        await pilot.press("/")
        await pilot.pause()
        colored = [s for s in _rendered_styles(app)
                   if (s.color is not None and s.color.name != "default")
                   or (s.bgcolor is not None and s.bgcolor.name != "default")]
        assert colored == []
        assert popup_text(app).splitlines()[0].startswith("› ")                     # marker, not colour
        assert app.query_one("#promptbox").styles.border_top[0] == "heavy"


# ================================================================ spec 018 R1/R7: palette frozen, glyph set

FROZEN_DARK = {"bg": "#121318", "surface": "#1a1c23", "border": "#444856", "fg": "#e4e6ea", "muted": "#9ba1ae",
               "accent": "#c3c7d0", "good": "#5ec49a", "warn": "#e0b04f", "bad": "#ec6f78", "agent": "#4cc2bd"}
FROZEN_LIGHT = {"bg": "#f7f8fa", "surface": "#eceef2", "border": "#8c92a0", "fg": "#1a1c22", "muted": "#555b69",
                "accent": "#343944", "good": "#1d7a55", "warn": "#8a5a00", "bad": "#b3262f", "agent": "#0f6f6c"}
FROZEN_ANSI = {"g-bg": "ansi_default", "g-surface": "ansi_default", "g-border": "ansi_bright_black",
               "g-fg": "ansi_default", "g-muted": "ansi_bright_black", "g-accent": "ansi_bright_white",
               "g-good": "ansi_green", "g-warn": "ansi_yellow", "g-bad": "ansi_red", "g-agent": "ansi_cyan"}


def _source(name: str) -> str:
    from pathlib import Path
    return (Path(styles.__file__).parent / name).read_text(encoding="utf-8")


def _without_palettes(source: str) -> str:
    import re
    for name in ("DARK_PALETTE", "LIGHT_PALETTE", "_ANSI_VARIABLES"):
        source = re.sub(rf"^{name} = \{{.*?^\}}", "", source, flags=re.S | re.M)
    return source


def test_the_three_palette_dicts_keep_their_exact_values():
    assert styles.DARK_PALETTE == FROZEN_DARK
    assert styles.LIGHT_PALETTE == FROZEN_LIGHT
    assert styles._ANSI_VARIABLES == FROZEN_ANSI


_COLOR_WORDS = ("black", "white", "red", "green", "blue", "yellow", "cyan", "magenta", "grey", "gray", "orange",
                "purple", "pink", "brown", "silver", "gold", "teal", "navy", "lime", "maroon", "olive")


def test_no_colour_literal_exists_outside_the_palette_dicts():
    import re
    for name in ("styles.py", "widgets.py", "app.py"):
        source = _without_palettes(_source(name))
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", source), f"hex colour in {name}"
        assert not re.search(r"\b(?:rgb|rgba|hsl|hsla)\(", source), f"rgb() in {name}"
        assert not re.search(r"\bcolor\s*=\s*[\"']", source), f"colour argument in {name}"
        assert not re.search(r"style=[\"'][^\"']*\b(?:%s)\b" % "|".join(_COLOR_WORDS), source), f"colour style in {name}"


def test_every_colour_in_the_css_is_a_g_variable():
    import re
    allowed = {"transparent", "none", "auto", "tall", "round", "heavy", "solid", "thick", "double", "ascii",
               "dashed", "hkey", "vkey", "wide", "blank", "inner", "outer", "tab", "panel"}
    colour_props = re.compile(r"^(color|background|border(-top|-left|-right|-bottom)?|outline|scrollbar-[a-z-]*color[a-z-]*"
                              r"|border-title-color|border-subtitle-color|tint)$")
    checked = 0
    for prop, value in re.findall(r"([a-z-]+)\s*:\s*([^;{}]+);", styles.APP_CSS):
        if not colour_props.match(prop):
            continue
        for token in value.split():
            if re.fullmatch(r"[\d.]+%?", token):
                continue
            assert token.startswith("$g-") or token in allowed, f"{prop}: {value}"
            checked += token.startswith("$g-")
    assert checked > 30


def test_every_non_ascii_glyph_is_in_the_wgl4_set_consolas_and_cascadia_draw():
    wgl4 = {"·", "•", "●", "└", "…", "›"}          # the only non-ASCII characters the UI modules may use
    for name in ("styles.py", "widgets.py", "app.py"):
        extra = {c for c in _source(name) if ord(c) > 127} - wgl4
        assert extra == set(), f"{name}: {sorted(extra)}"


# ---------------------------------------------------------------- run_app

def test_run_app_prints_only_the_exception_type_and_returns_one(monkeypatch, capsys):
    class Boom(RuntimeError):
        pass

    def broken_run(self, *args, **kwargs):
        raise Boom("secret detail sk-should-not-print")

    monkeypatch.setattr(GallianiApp, "run", broken_run)
    assert run_app(FakeSession()) == 1
    captured = capsys.readouterr()
    assert captured.err.strip() == "Boom" and "secret" not in captured.err + captured.out


# ================================================================ against the real Session (spec 018 R15-R21 display)

async def test_real_session_banner_and_slash_popup_and_file_mentions(tmp_path):
    from .conftest import make_session
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "notes.md").write_text("n", encoding="utf-8")
    (ws / ".env").write_text("SECRET=1", encoding="utf-8")
    (ws / "sub").mkdir()
    session, _ = make_session(ws)
    app = GallianiApp(session)
    async with app.run_test(size=(80, 30)) as pilot:
        await pilot.pause()
        text = tree_text(app.query_one(Banner))
        assert "Galliani " in text and "memory:" in text and "sk-" not in text
        app.prompt.focus()
        await pilot.press("/", "m", "e", "tab")
        await pilot.pause()
        assert app.prompt.text == "/memory " and "list" in popup_text(app)
        app.prompt.clear_prompt()
        await pilot.press("escape")
        await pilot.press("@")
        await settle(app, pilot)
        shown = popup_text(app)
        assert "notes.md" in shown and ".env" not in shown                           # protected names never listed
        await pilot.press("tab")
        await pilot.pause()
        assert app.prompt.text == "@notes.md" and not app.popup.display
        app.prompt.clear_prompt()
        await pilot.press(*"/workspace ")
        await settle(app, pilot)
        assert "sub" in popup_text(app) and "notes.md" not in popup_text(app)        # folders only
        assert overflows(app) == []
