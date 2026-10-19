"""Spec 017 R26: slash commands typed into the prompt. Pure parsing and completion, no I/O.

Only text the user typed is parsed here (R34). A line starting with `//` is not a command: the session
sends it as an objective with one `/` removed. Spec 018 R15-R21: `complete_command` completes command
names and finite arguments; folders, files and memory ids need I/O and are left to `Session.complete`.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

from galliani.redaction import redact_text

# 017 R18: terminal escape sequences (CSI, OSC, other ESC sequences), then any remaining C0/C1 control
# character except \n and \t, DEL, and bidirectional override and isolate characters.
_ESCAPE_SEQUENCES = re.compile(
    r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?"   # OSC ... BEL or ST (OSC 8 links, OSC 52 clipboard, titles)
    r"|\x1b\[[0-?]*[ -/]*[@-~]?"             # CSI (colors, cursor movement)
    r"|\x1b[PX^_][^\x1b]*(?:\x1b\\)?"        # DCS, SOS, PM, APC strings
    r"|\x1b[ -/]*[0-~]?"                     # other two-character escapes
)
_UNSAFE_CHARS = re.compile("[\x00-\x08\x0b-\x1f\x7f-\x9f‪-‮⁦-⁩]")


def sanitize(text: str) -> str:
    """017 R18: redact secrets, strip terminal control and bidi characters, then redact again so a secret split
    by a stripped character is masked once rejoined. Markup stays literal text. Lives here so completion
    (018 R21) stays pure; `galliani.tui.session` re-exports it."""
    text = redact_text(str(text))
    return redact_text(_UNSAFE_CHARS.sub("", _ESCAPE_SEQUENCES.sub("", text)))


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


# ---------------------------------------------------------------------- completion (spec 018 R15-R21)

CompletionKind = Literal["command", "argument", "folder", "file", "memory_id"]
NeedsIo = Literal["folder", "file", "memory_id"]
NO_ARGUMENT = ("help", "clear", "quit")


@dataclass(frozen=True)
class Completion:
    insert: str                  # replaces CompletionResult.start..cursor; equals the shown label's text
    label: str                   # sanitized
    summary: str = ""            # sanitized, one line
    kind: CompletionKind = "command"
    enabled: bool = True         # False: shown dimmed, "(not while a task runs)"
    submits: bool = False        # R17: Enter on this item also sends the line


@dataclass(frozen=True)
class CompletionResult:
    start: int                   # index in text where the completed token begins
    items: tuple[Completion, ...]
    needs_io: NeedsIo | None = None   # ask Session.complete
    truncated: bool = False


def safe_completion(insert: str, summary: str = "", **kw) -> Completion | None:
    """R21: None when `sanitize()` would change the inserted text, so what is inserted is exactly what is shown.
    The label is the insert without its trailing space; the summary is sanitized onto one line."""
    label = insert.rstrip(" ")
    if not label or sanitize(label) != label or any(c in label for c in "\n\t"):
        return None
    return Completion(insert=insert, label=label, summary=" ".join(sanitize(summary).split()), **kw)


def _matching(names, typed: str) -> list[str]:
    """R16: prefix matches; when there are none, substring matches. Case-insensitive."""
    typed = typed.lower()
    prefix = [n for n in names if n.lower().startswith(typed)]
    return prefix or [n for n in names if typed in n.lower()]


def _arguments(name: str, typed: str, *, task_active: bool) -> tuple[Completion, ...]:
    """R18: the finite argument choices of one command, filtered by what was typed. `/memory forget` needs an
    id after it, so it inserts a trailing space and does not submit; every other choice is a finished argument."""
    items = []
    for choice in _matching(("off",) if name == "budget" else _CHOICES.get(name, ("list", "forget", "on", "off")),
                            typed):
        done = not (name == "memory" and choice == "forget")
        allowed = _allowed_while_active(Command(name, (choice,) if name == "memory" else ()))
        items.append(safe_completion(choice if done else choice + " ", kind="argument", submits=done,
                                     enabled=not task_active or allowed))
    return tuple(item for item in items if item is not None)


def mention_start(text: str, cursor: int) -> int | None:
    """R20: where the `@` token before the cursor starts (at the prompt start or after whitespace), or None."""
    head = text[:max(0, min(cursor, len(text)))]
    start = max(head.rfind(c) for c in " \t\n") + 1
    return start if head[start:start + 1] == "@" else None


def complete_command(text: str, cursor: int, *, task_active: bool) -> CompletionResult | None:
    """R15-R18, R20: what to offer for the token before `cursor`. Pure: folders, files and memory ids come back
    empty with `needs_io` set, for `Session.complete`. None: no popup (not a `/` line or an `@` mention, the `//`
    escape, a command that takes no argument, or a free-value argument)."""
    cursor = max(0, min(cursor, len(text)))
    head = text[:cursor]
    if not head.startswith("/") or head.startswith("//"):
        start = mention_start(text, cursor)
        return None if start is None else CompletionResult(start=start, items=(), needs_io="file")
    if "\n" in head:
        return None
    name, space, rest = head[1:].partition(" ")
    if not space:  # R16: still typing the command name
        items = []
        for match in _matching(COMMANDS, name):
            spec, done = COMMANDS[match], match in NO_ARGUMENT
            items.append(safe_completion(f"/{match}" if done else f"/{match} ", spec.summary, kind="command",
                                         enabled=not task_active or spec.allowed_while_active, submits=done))
        return CompletionResult(start=0, items=tuple(i for i in items if i is not None))
    name = name.lower()
    if name not in COMMANDS or name in NO_ARGUMENT:
        return None
    arg = rest.lstrip(" ")
    arg_start = cursor - len(arg)
    if name == "workspace":  # R19: the rest of the line is one path
        return None if task_active else CompletionResult(start=arg_start, items=(), needs_io="folder")
    words = arg.split(" ")
    if name == "memory" and len(words) == 2 and words[0].lower() == "forget":
        return None if task_active else CompletionResult(start=cursor - len(words[1]), items=(), needs_io="memory_id")
    if len(words) > 1:
        return None
    items = _arguments(name, words[0], task_active=task_active)
    return CompletionResult(start=arg_start, items=items) if items or name != "budget" else None
