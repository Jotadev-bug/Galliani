"""Pilot tests for the Textual layer of spec 017 (R20-R29), driven against `FakeSession`."""

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
    ApprovalCard, PlanPanel, PlanSummary, PromptHistory, QuestionInput, build_status_text,
    plan_summary_text,
)

try:
    from .fake_session import FakeSession, plan_view
except ImportError:
    from fake_session import FakeSession, plan_view  # type: ignore[no-redef]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("NO_COLOR", "GALLIANI_REDUCED_MOTION", "TEXTUAL_ANIMATIONS"):
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------- helpers

def plain(widget) -> str:
    content = getattr(widget, "content", None)
    if isinstance(content, Text):
        return content.plain
    source = getattr(widget, "source", None)
    return source if source is not None else str(content)


def transcript_text(app) -> str:
    return "\n".join(plain(child) for child in app.transcript.children)


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
                 ("> summarize", "= Plan v1", "* read_file", "+ Check passed", "= Result: done", "$ Usage")]
        assert order == sorted(order)
        assert "Files changed: created summary.md" in text
        assert calls(session, "submit") == [("submit", "summarize")]
        assert session.state.phase.value == "idle"
        assert "Ready" in status_line(app)
        assert app.focused is app.prompt and app.prompt.text == ""


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
        assert plain(summary).startswith("Plan v2 - step 2/4 - running")
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
        assert summary.region.height == 5 and "[ok] 1. Read the notes" in plain(summary)
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
        assert "running" in plain(panel) and "2. Draft the summary (running)" in plain(panel)
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
    assert tiny.startswith("...") and tiny.endswith("Ready") and len(tiny) <= 42


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


# ---------------------------------------------------------------- reduced motion (R28)

async def test_spinner_runs_only_while_a_task_is_active():
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    async with app.run_test(size=(100, 30)) as pilot:
        assert not app.status_bar.spinner_active
        await type_and_send(app, pilot, "go")
        await pilot.pause()
        assert app.status_bar.spinner_active
        assert "(working...)" not in status_line(app)
        session.finish_hold()
        await settle(app, pilot)
        assert not app.status_bar.spinner_active


@pytest.mark.parametrize("how", ["animation-level", "env"])
async def test_reduced_motion_has_no_spinner_timer_and_shows_working_text(how, monkeypatch):
    if how == "env":
        monkeypatch.setenv("GALLIANI_REDUCED_MOTION", "1")
    session = FakeSession(scenario="hold")
    app = GallianiApp(session)
    async with app.run_test(size=(120, 30)) as pilot:
        if how == "animation-level":
            app.animation_level = "none"
        await type_and_send(app, pilot, "go")
        await pilot.pause()
        assert not app.status_bar.spinner_active and app.status_bar._timer is None
        assert "(working...)" in status_line(app)
        session.finish_hold()
        await settle(app, pilot)


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
