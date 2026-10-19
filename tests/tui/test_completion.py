"""Spec 018 R15-R21: completion. `complete_command` (pure) and `Session.complete` (folders, files, memory ids)."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import pytest

from galliani.memory import InMemoryMemoryStore, MemoryRecord, project_scope
from galliani.tui import session as session_mod
from galliani.tui.commands import COMMANDS, Completion, CompletionResult, complete_command, safe_completion, sanitize
from galliani.tui.session import FILE_CACHE_SECONDS, MAX_FOLDERS, Phase
from tests.tui.conftest import make_session

KEY = "sk-abcdefghijklmnopqrstuvwx"


def complete(text: str, *, task_active: bool = False, cursor: int | None = None) -> CompletionResult | None:
    return complete_command(text, len(text) if cursor is None else cursor, task_active=task_active)


def labels(result: CompletionResult | None) -> list[str]:
    assert result is not None
    return [item.label for item in result.items]


def apply(text: str, result: CompletionResult, item: Completion, cursor: int | None = None) -> str:
    cursor = len(text) if cursor is None else cursor
    return text[:result.start] + item.insert + text[cursor:]


# ---------------------------------------------------------------------- R16 command names


def test_slash_lists_every_command_with_its_summary():
    result = complete("/")
    assert result.start == 0 and result.needs_io is None and not result.truncated
    assert labels(result) == [f"/{name}" for name in COMMANDS]
    assert [i.summary for i in result.items] == [spec.summary for spec in COMMANDS.values()]
    assert {i.kind for i in result.items} == {"command"} and all(i.enabled for i in result.items)


@pytest.mark.parametrize("text, expected", [
    ("/me", ["/memory"]),
    ("/MEM", ["/memory"]),
    ("/e", ["/edit-mode", "/events"]),
    ("/q", ["/quit"]),
    ("/mode", ["/edit-mode"]),       # no prefix match: substring
    ("/ear", ["/clear"]),
])
def test_prefix_then_substring_filtering(text, expected):
    assert labels(complete(text)) == expected


def test_unknown_command_filters_to_empty_not_none():
    result = complete("/zzz")
    assert result is not None and result.items == () and result.needs_io is None


def test_insert_text_and_submits_flags_r17():
    items = {i.label: i for i in complete("/").items}
    for name in ("help", "clear", "quit"):  # no argument: Enter sends at once
        assert items[f"/{name}"].insert == f"/{name}" and items[f"/{name}"].submits
    for name in ("workspace", "edit-mode", "budget", "memory", "events", "theme"):  # takes an argument: insert only
        assert items[f"/{name}"].insert == f"/{name} " and not items[f"/{name}"].submits
    assert all(i.insert.rstrip(" ") == i.label for i in items.values())


def test_tab_on_memory_gives_its_argument_choices():
    result = complete("/me")
    text = apply("/me", result, result.items[0])
    assert text == "/memory "
    assert labels(complete(text)) == ["list", "forget", "on", "off"]


def test_task_active_dims_refused_commands_but_keeps_them_listed():
    items = {i.label: i for i in complete("/", task_active=True).items}
    assert len(items) == len(COMMANDS)
    assert {label for label, i in items.items() if not i.enabled} == {"/workspace", "/budget"}


# ---------------------------------------------------------------------- R18 finite arguments


@pytest.mark.parametrize("text, expected", [
    ("/edit-mode ", ["ask", "accept-edits"]),
    ("/edit-mode a", ["ask", "accept-edits"]),
    ("/edit-mode acc", ["accept-edits"]),
    ("/theme ", ["dark", "light"]),
    ("/theme L", ["light"]),
    ("/events ", ["on", "off"]),
    ("/events of", ["off"]),
    ("/budget ", ["off"]),
    ("/budget o", ["off"]),
    ("/memory ", ["list", "forget", "on", "off"]),
    ("/memory f", ["forget"]),
    ("/Theme  d", ["dark"]),
])
def test_argument_choices(text, expected):
    result = complete(text)
    assert labels(result) == expected and {i.kind for i in result.items} == {"argument"}
    assert text[:result.start].endswith(" ")


def test_finished_arguments_submit_and_forget_waits_for_an_id():
    result = complete("/theme d")
    assert apply("/theme d", result, result.items[0]) == "/theme dark" and result.items[0].submits
    forget = complete("/memory fo").items[0]
    assert forget.insert == "forget " and not forget.submits
    assert all(i.submits for i in complete("/memory ").items if i.label != "forget")


def test_memory_sub_commands_refused_while_a_task_runs_are_dimmed():
    items = {i.label: i.enabled for i in complete("/memory ", task_active=True).items}
    assert items == {"list": True, "forget": False, "on": False, "off": False}
    assert all(not i.enabled for i in complete("/budget ", task_active=True).items)
    assert all(i.enabled for i in complete("/theme ", task_active=True).items)


@pytest.mark.parametrize("text", [
    "/budget 2", "/budget $1", "/theme dark extra", "/events on off", "/memory list x",
    "/help ", "/clear ", "/quit x", "/nope arg",
])
def test_free_values_and_no_argument_commands_give_no_popup(text):
    assert complete(text) is None


def test_unmatched_finite_argument_gives_an_empty_list():
    assert complete("/theme blue").items == ()


@pytest.mark.parametrize("text, needs, start", [
    ("/workspace ", "folder", 11),
    ("/workspace ../a", "folder", 11),
    ("/workspace  C:\\My Projects", "folder", 12),
    ("/memory forget ", "memory_id", 15),
    ("/memory forget mem_a", "memory_id", 15),
    ("@", "file", 0),
    ("summarize @no", "file", 10),
    ("line one\n@src/m", "file", 9),
])
def test_io_tokens_are_left_to_the_session(text, needs, start):
    result = complete(text)
    assert result.needs_io == needs and result.start == start and result.items == ()


def test_io_completion_is_not_offered_for_refused_commands_while_a_task_runs():
    assert complete("/workspace ", task_active=True) is None
    assert complete("/memory forget m", task_active=True) is None


@pytest.mark.parametrize("text", [
    "", "Summarize notes", "//help", "//workspace ", "e-mail me@example.com", "x@y", "/memory\nlist",
])
def test_no_popup_for_objectives_escapes_and_mid_word_at(text):
    assert complete(text) is None


def test_cursor_limits_what_is_completed():
    assert labels(complete("/theme dark", cursor=3)) == ["/theme"]
    assert complete("/me now", cursor=99) is None  # the cursor is clamped to the end
    assert complete("hello @x", cursor=5) is None


# ---------------------------------------------------------------------- R21 safe text


@pytest.mark.parametrize("name", ["evil\u202etxt.md", f"{KEY}.txt", "a\x1b[31mb", "tab\tname", "line\nbreak", ""])
def test_safe_completion_omits_names_sanitize_would_change(name):
    assert safe_completion(name) is None


def test_safe_completion_keeps_plain_names_and_sanitizes_summaries():
    item = safe_completion("notes.md", f"one\n\x1b[2Jtwo {KEY}", kind="file")
    assert item.insert == item.label == "notes.md"
    assert "\n" not in item.summary and "\x1b" not in item.summary and "sk-" not in item.summary
    assert item.summary == sanitize(item.summary)


def test_every_command_completion_is_already_sanitized():
    for item in complete("/").items:
        assert sanitize(item.label) == item.label and sanitize(item.summary) == item.summary


# ---------------------------------------------------------------------- Session.complete: /workspace (R19)


@pytest.fixture
def tree(tmp_path):
    """Folders a/, .git/, .hidden/, node_modules/ and Zeta/, a file b.txt, inside the workspace."""
    ws = tmp_path / "ws"
    ws.mkdir()
    for name in ("a", ".git", ".hidden", "node_modules", "Zeta"):
        (ws / name).mkdir()
    (ws / "a" / "inner").mkdir()
    (ws / ".git" / "objects").mkdir()
    (ws / "b.txt").write_text("b", encoding="utf-8")
    (ws / "notes.md").write_text("n", encoding="utf-8")
    return ws


async def test_workspace_completion_lists_only_folders(tree):
    session, _ = make_session(tree)
    result = await session.complete("/workspace ", 11)
    assert labels(result) == ["a/", "Zeta/"] and result.needs_io is None
    assert {i.kind for i in result.items} == {"folder"} and not any(i.submits for i in result.items)


async def test_dot_folders_only_when_typed_and_never_git(tree):
    session, _ = make_session(tree)
    assert labels(await session.complete("/workspace .", 12)) == [".hidden/"]
    assert labels(await session.complete("/workspace .g", 13)) == []


async def test_workspace_completion_follows_the_typed_parent(tree, tmp_path):
    session, _ = make_session(tree)
    text = "/workspace a/"
    result = await session.complete(text, len(text))
    assert labels(result) == ["a/inner/"] and apply(text, result, result.items[0]) == "/workspace a/inner/"
    absolute = f"/workspace {tmp_path}{os.sep}"
    assert labels(await session.complete(absolute, len(absolute))) == [f"{tmp_path}{os.sep}ws/"]
    z = "/workspace z"
    assert labels(await session.complete(z, len(z))) == ["Zeta/"]  # case-insensitive


async def test_workspace_completion_resolves_home(tree, monkeypatch):
    monkeypatch.setenv("HOME", str(tree.parent))
    monkeypatch.setenv("USERPROFILE", str(tree.parent))
    session, _ = make_session(tree)
    assert labels(await session.complete("/workspace ~/", 13)) == ["~/ws/"]


async def test_never_lists_inside_a_protected_folder(tree):
    session, _ = make_session(tree)
    for text in ("/workspace .git/", "/workspace a/../.git/", "/workspace node_modules/"):
        assert (await session.complete(text, len(text))).items == ()


async def test_workspace_completion_caps_at_50(tree):
    many = tree / "many"
    many.mkdir()
    for i in range(MAX_FOLDERS + 10):
        (many / f"d{i:03}").mkdir()
    session, _ = make_session(tree)
    result = await session.complete("/workspace many/", 16)
    assert len(result.items) == MAX_FOLDERS and result.truncated


async def test_missing_parent_gives_an_empty_truncated_result(tree):
    session, _ = make_session(tree)
    result = await session.complete("/workspace nope/", 16)
    assert result.items == () and result.truncated and result.needs_io is None


async def test_unsafe_folder_names_are_not_offered(tree):
    (tree / "ev\u202eil").mkdir()
    session, _ = make_session(tree)
    assert labels(await session.complete("/workspace e", 12)) == []


async def test_listing_deadline_returns_what_it_has(tree, monkeypatch):
    monkeypatch.setattr(session_mod, "LISTING_TIMEOUT", -1.0)  # already past the deadline
    session, _ = make_session(tree)
    result = await session.complete("/workspace ", 11)
    assert result.truncated and result.items == ()


async def test_a_hung_listing_times_out_without_blocking(tree, monkeypatch):
    def hang(*args):
        time.sleep(2)
        return ["a"], False
    monkeypatch.setattr(session_mod, "_list_folders", hang)
    monkeypatch.setattr(session_mod, "LISTING_TIMEOUT", 0.05)
    session, _ = make_session(tree)
    started = time.monotonic()
    result = await session.complete("/workspace ", 11)
    assert time.monotonic() - started < 1.5 and result.items == () and result.truncated


# ---------------------------------------------------------------------- Session.complete: @file (R20)


@pytest.fixture
def seeded(tmp_path):
    """The File Mention criterion: .env, .git/config, server.key, notes.md and a link to a file outside."""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / ".git").mkdir()
    (ws / ".git" / "config").write_text("[core]", encoding="utf-8")
    (ws / ".env").write_text(f"OPENAI_API_KEY={KEY}", encoding="utf-8")
    (ws / "server.key").write_text("-----BEGIN PRIVATE KEY-----", encoding="utf-8")
    (ws / "notes.md").write_text("notes", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        (ws / "link.txt").symlink_to(outside)
    except OSError:  # symlinks need developer mode or admin on Windows; the rest of the case still runs
        pass
    return ws


async def test_file_mention_offers_only_unprotected_files(seeded):
    session, _ = make_session(seeded)
    result = await session.complete("@", 1)
    assert labels(result) == ["@notes.md"] and result.items[0].insert == "@notes.md"
    assert result.items[0].kind == "file" and not result.items[0].submits and result.needs_io is None


async def test_file_mention_filters_and_inserts_a_relative_path(tree):
    (tree / "a" / "inner" / "main.py").write_text("x", encoding="utf-8")
    session, _ = make_session(tree)
    text = "explain @a/in"
    result = await session.complete(text, len(text))
    assert labels(result) == ["@a/inner/main.py"]
    assert apply(text, result, result.items[0]) == "explain @a/inner/main.py"
    assert labels(await session.complete("@main", 5)) == ["@a/inner/main.py"]  # substring fallback


@pytest.mark.parametrize("name", ["evil\u202etxt.md", f"{KEY}.txt"])
async def test_unsafe_file_names_are_not_offered(tree, name):
    try:
        (tree / name).write_text("x", encoding="utf-8")
    except OSError:
        pytest.skip("the filesystem refuses this name")
    session, _ = make_session(tree)
    shown = labels(await session.complete("@", 1))
    assert shown == ["@b.txt", "@notes.md"]


async def test_no_files_gives_an_empty_result(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    session, _ = make_session(empty)
    result = await session.complete("@", 1)
    assert result is not None and result.items == () and not result.truncated


async def test_file_listing_is_cached_for_30_seconds_and_dropped_on_workspace(tree, tmp_path, monkeypatch):
    calls = []
    original = session_mod.Workspace.list_files

    def counting(self, args):
        calls.append(self.root)
        return original(self, args)
    monkeypatch.setattr(session_mod.Workspace, "list_files", counting)
    session, _ = make_session(tree)
    await session.complete("@", 1)
    (tree / "late.md").write_text("x", encoding="utf-8")
    assert "@late.md" not in labels(await session.complete("@", 1)) and len(calls) == 1  # cached

    now = time.monotonic()
    monkeypatch.setattr(session_mod.time, "monotonic", lambda: now + FILE_CACHE_SECONDS + 1)
    assert "@late.md" in labels(await session.complete("@", 1)) and len(calls) == 2  # expired

    other = tmp_path / "other"
    other.mkdir()
    (other / "x.md").write_text("x", encoding="utf-8")
    await session.submit(f"/workspace {other}")
    assert labels(await session.complete("@", 1)) == ["@x.md"] and len(calls) == 3


async def test_file_listing_error_is_an_empty_truncated_result(tree, monkeypatch):
    def broken(self, args):
        raise PermissionError("denied")
    monkeypatch.setattr(session_mod.Workspace, "list_files", broken)
    session, _ = make_session(tree)
    before = len(session.entries())
    result = await session.complete("@", 1)
    assert result.items == () and result.truncated and len(session.entries()) == before  # no error entry


async def test_slow_file_listing_times_out_then_fills_the_cache(tree, monkeypatch):
    gate = asyncio.Event()
    loop = asyncio.get_running_loop()
    original = session_mod.Workspace.list_files

    def slow(self, args):
        asyncio.run_coroutine_threadsafe(gate.wait(), loop).result(5)
        return original(self, args)
    monkeypatch.setattr(session_mod.Workspace, "list_files", slow)
    monkeypatch.setattr(session_mod, "FILE_LISTING_TIMEOUT", 0.05)
    session, _ = make_session(tree)
    first = await session.complete("@", 1)
    assert first.items == () and first.truncated
    gate.set()
    await asyncio.wait_for(session._files_pending[1], 5)
    assert labels(await session.complete("@", 1)) == ["@b.txt", "@notes.md"]


# ---------------------------------------------------------------------- Session.complete: memory ids (R18)


def memory_store(workspace: Path) -> InMemoryMemoryStore:
    return InMemoryMemoryStore([
        MemoryRecord(id="mem_user1", content="prefers short answers", type="preference", provenance="test"),
        MemoryRecord(id="mem_proj1", content="uses pytest", type="fact", scope=project_scope(workspace),
                     provenance="test"),
        MemoryRecord(id="mem_secret", content=f"key is {KEY}", type="note", provenance="test",
                     sensitivity="sensitive"),
        MemoryRecord(id="mem_other", content="another project", type="fact", scope=project_scope("/elsewhere"),
                     provenance="test"),
    ])


async def test_memory_ids_are_scoped_and_redacted_like_memory_list(workspace):
    session, _ = make_session(workspace, memory=memory_store(workspace))
    result = await session.complete("/memory forget ", 15)
    items = {i.label: i for i in result.items}
    assert set(items) == {"mem_user1", "mem_proj1", "mem_secret"}  # never another workspace's records
    assert items["mem_user1"].summary == "[preference, user] prefers short answers"
    assert items["mem_proj1"].summary == "[fact, project] uses pytest"
    assert "sk-" not in items["mem_secret"].summary and "key is" not in items["mem_secret"].summary
    assert all(i.kind == "memory_id" and i.submits for i in result.items)
    await session.submit("/memory list")
    shown = session.entries()[-1].detail
    for item in result.items:
        assert any(line == f"{item.label} {item.summary}" for line in shown)


async def test_memory_id_prefix_and_memory_off(workspace):
    session, _ = make_session(workspace, memory=memory_store(workspace))
    assert labels(await session.complete("/memory forget mem_p", 20)) == ["mem_proj1"]
    assert labels(await session.complete("/memory forget zzz", 18)) == []
    await session.submit("/memory off")
    assert (await session.complete("/memory forget ", 15)).items == ()


async def test_memory_completion_with_no_store(workspace):
    session, _ = make_session(workspace, memory=None)
    assert (await session.complete("/memory forget ", 15)).items == ()


# ---------------------------------------------------------------------- Session.complete: general


async def test_session_complete_passes_pure_results_through(workspace):
    session, _ = make_session(workspace)
    assert await session.complete("/me", 3) == complete_command("/me", 3, task_active=False)
    assert await session.complete("hello", 5) is None


async def test_session_complete_dims_by_phase(workspace):
    session, _ = make_session(workspace)
    session._phase = Phase.running
    items = {i.label: i.enabled for i in (await session.complete("/", 1)).items}
    assert items["/workspace"] is False and items["/help"] is True
    assert await session.complete("/workspace ", 11) is None


async def test_session_complete_never_raises(workspace, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bug")
    session, _ = make_session(workspace)
    monkeypatch.setattr(session_mod, "complete_command", boom)
    assert await session.complete("/", 1) is None
    monkeypatch.undo()
    monkeypatch.setattr(session_mod, "_list_folders", boom)
    result = await session.complete("/workspace ", 11)
    assert result.items == () and result.truncated


async def test_completion_writes_nothing_and_adds_no_entries(tree):
    session, _ = make_session(tree)
    before = (sorted(p.relative_to(tree) for p in tree.rglob("*")), len(session.entries()))
    for text in ("/", "/workspace ", "@", "/memory forget "):
        await session.complete(text, len(text))
    assert (sorted(p.relative_to(tree) for p in tree.rglob("*")), len(session.entries())) == before
