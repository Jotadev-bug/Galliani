"""Spec 017 R26: slash commands typed into the prompt. Pure parsing, no I/O.

Only text the user typed is parsed here (R34). A line starting with `//` is not a command: the session
sends it as an objective with one `/` removed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandSpec:
    name: str
    usage: str
    summary: str
    allowed_while_active: bool  # per the R26 table; for /memory, decided per sub-command


@dataclass(frozen=True)
class Command:
    name: str
    args: tuple[str, ...]


class CommandError(ValueError):
    """`str(e)` is a safe, user-facing message with the usage line."""


COMMANDS: dict[str, CommandSpec] = {spec.name: spec for spec in (
    CommandSpec("help", "/help", "list commands and keys", True),
    CommandSpec("clear", "/clear", "clear the visible transcript (not history, not the task)", True),
    CommandSpec("workspace", "/workspace [PATH]", "show, or switch to an existing folder", False),
    CommandSpec("edit-mode", "/edit-mode [ask|accept-edits]", "show or set the edit mode", True),
    CommandSpec("budget", "/budget [USD|off]", "show or set the per-task budget", False),
    CommandSpec("memory", "/memory [list|forget ID|on|off]", "list or forget memory records, or turn memory on/off", True),
    CommandSpec("events", "/events [on|off]", "show or hide verbose public events", True),
    CommandSpec("theme", "/theme [dark|light]", "switch the theme for this session", True),
    CommandSpec("quit", "/quit", "quit Galliani", True),
)}

_CHOICES = {"edit-mode": ("ask", "accept-edits"), "events": ("on", "off"), "theme": ("dark", "light")}


def _allowed_while_active(command: Command) -> bool:
    """R26 "While a task is active" column. `/memory` and `/memory list` are allowed; forget/on/off are not."""
    if command.name == "memory":
        return not command.args or command.args[0] == "list"
    return COMMANDS[command.name].allowed_while_active


def _bad(name: str, problem: str) -> CommandError:
    return CommandError(f"{problem}. Usage: {COMMANDS[name].usage}")


def parse_command(text: str) -> Command | None:
    """None if `text` is not a command (including `//...`); raises CommandError for a bad one."""
    line = text.strip()
    if not line.startswith("/") or line.startswith("//"):
        return None
    head, _, rest = line[1:].partition(" ")
    name = head.strip().lower()
    rest = rest.strip()
    if name not in COMMANDS:
        problem = f"Unknown command /{name[:40]}" if name else "Missing command name"
        raise CommandError(f"{problem}. Type /help for the list of commands.")

    if name == "workspace":  # the rest of the line is one path, so folders with spaces work
        path = rest[1:-1] if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "\"'" else rest
        return Command(name, (path,) if path else ())

    args = tuple(rest.split())
    if name in ("help", "clear", "quit"):
        if args:
            raise _bad(name, f"/{name} takes no arguments")
    elif name in _CHOICES:
        if len(args) > 1 or (args and args[0].lower() not in _CHOICES[name]):
            raise _bad(name, f"Invalid argument for /{name}")
        args = tuple(a.lower() for a in args)
    elif name == "budget":
        if len(args) > 1:
            raise _bad(name, "/budget takes one value")
        if args and args[0].lower() != "off":
            try:
                value = float(args[0].lstrip("$"))
            except ValueError:
                raise _bad(name, "Budget must be a number of US dollars or 'off'") from None
            if not math.isfinite(value):
                raise _bad(name, "Budget must be a finite number")
        args = tuple(a.lower() if a.lower() == "off" else a.lstrip("$") for a in args)
    elif name == "memory":
        sub = args[0].lower() if args else None
        if sub is None:
            pass
        elif sub in ("list", "on", "off"):
            if len(args) != 1:
                raise _bad(name, f"/memory {sub} takes no arguments")
        elif sub == "forget":
            if len(args) != 2:
                raise _bad(name, "/memory forget needs one record ID")
        else:
            raise _bad(name, "Invalid argument for /memory")
        args = (sub, *args[1:]) if sub else ()
    return Command(name, args)
