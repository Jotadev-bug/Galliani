"""Spec 017 R26: `parse_command` for every command, every bad argument and the `//` escape."""

from __future__ import annotations

import pytest

from galliani.tui.commands import COMMANDS, Command, CommandError, _allowed_while_active, parse_command


def test_the_command_table_matches_r26():
    assert set(COMMANDS) == {"help", "clear", "workspace", "edit-mode", "budget", "memory", "events", "theme", "quit"}
    refused = {name for name, spec in COMMANDS.items() if not spec.allowed_while_active}
    assert refused == {"workspace", "budget"}
    assert COMMANDS["memory"].usage == "/memory [list|forget ID|on|off]"
    assert all(spec.usage.startswith(f"/{name}") for name, spec in COMMANDS.items())


@pytest.mark.parametrize("text, expected", [
    ("/help", Command("help", ())),
    ("  /clear  ", Command("clear", ())),
    ("/quit", Command("quit", ())),
    ("/HELP", Command("help", ())),
    ("/workspace", Command("workspace", ())),
    ("/workspace ../other", Command("workspace", ("../other",))),
    ("/workspace C:\\My Projects\\site", Command("workspace", ("C:\\My Projects\\site",))),
    ('/workspace "C:\\My Projects"', Command("workspace", ("C:\\My Projects",))),
    ("/edit-mode", Command("edit-mode", ())),
    ("/edit-mode ask", Command("edit-mode", ("ask",))),
    ("/edit-mode Accept-Edits", Command("edit-mode", ("accept-edits",))),
    ("/budget", Command("budget", ())),
    ("/budget 0.75", Command("budget", ("0.75",))),
    ("/budget $2", Command("budget", ("2",))),
    ("/budget off", Command("budget", ("off",))),
    ("/budget 0", Command("budget", ("0",))),
    ("/memory", Command("memory", ())),
    ("/memory list", Command("memory", ("list",))),
    ("/memory forget mem_abc", Command("memory", ("forget", "mem_abc"))),
    ("/memory on", Command("memory", ("on",))),
    ("/memory OFF", Command("memory", ("off",))),
    ("/events", Command("events", ())),
    ("/events on", Command("events", ("on",))),
    ("/events off", Command("events", ("off",))),
    ("/theme", Command("theme", ())),
    ("/theme dark", Command("theme", ("dark",))),
    ("/theme light", Command("theme", ("light",))),
])
def test_valid_commands(text, expected):
    assert parse_command(text) == expected


@pytest.mark.parametrize("text", ["Summarize notes", "", "   ", "//etc/hosts", "  //help", "what is /help?"])
def test_not_a_command(text):
    assert parse_command(text) is None


@pytest.mark.parametrize("text, usage", [
    ("/help me", "/help"),
    ("/clear all", "/clear"),
    ("/quit now", "/quit"),
    ("/edit-mode always", "/edit-mode [ask|accept-edits]"),
    ("/edit-mode ask accept-edits", "/edit-mode [ask|accept-edits]"),
    ("/budget lots", "/budget [USD|off]"),
    ("/budget nan", "/budget [USD|off]"),
    ("/budget inf", "/budget [USD|off]"),
    ("/budget 1 2", "/budget [USD|off]"),
    ("/memory wipe", "/memory [list|forget ID|on|off]"),
    ("/memory forget", "/memory [list|forget ID|on|off]"),
    ("/memory forget a b", "/memory [list|forget ID|on|off]"),
    ("/memory list all", "/memory [list|forget ID|on|off]"),
    ("/memory on now", "/memory [list|forget ID|on|off]"),
    ("/events maybe", "/events [on|off]"),
    ("/events on off", "/events [on|off]"),
    ("/theme blue", "/theme [dark|light]"),
])
def test_bad_arguments_raise_with_the_usage_line(text, usage):
    with pytest.raises(CommandError) as err:
        parse_command(text)
    assert str(err.value).endswith(f"Usage: {usage}")


@pytest.mark.parametrize("text", ["/nope", "/", "/ help", "/edit_mode ask"])
def test_unknown_commands(text):
    with pytest.raises(CommandError) as err:
        parse_command(text)
    assert "Type /help" in str(err.value)


def test_unknown_command_name_is_shortened_in_the_message():
    with pytest.raises(CommandError) as err:
        parse_command("/" + "x" * 500)
    assert len(str(err.value)) < 120


@pytest.mark.parametrize("text, allowed", [
    ("/help", True), ("/clear", True), ("/edit-mode ask", True), ("/events on", True), ("/theme dark", True),
    ("/quit", True), ("/memory", True), ("/memory list", True),
    ("/workspace x", False), ("/workspace", False), ("/budget 1", False),
    ("/memory forget m1", False), ("/memory on", False), ("/memory off", False),
])
def test_allowed_while_a_task_is_active(text, allowed):
    assert _allowed_while_active(parse_command(text)) is allowed
