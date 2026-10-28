"""Spec 010 Amendment A: several processes share one memory file (Decision 0040).

Multi-process tests use the `spawn` context on every OS (the Windows default) and module-level workers that
receive the file path. Every test works in `tmp_path`. Correctness never depends on `sleep`: workers start
together on barriers and events, and every wait has a deadline so a bug fails the test instead of hanging it.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import time
from pathlib import Path

import pytest

from galliani import memory as memory_mod
from galliani.file_lock import file_lock
from galliani.memory import (
    InMemoryMemoryStore,
    JsonMemoryStore,
    MemoryQuery,
    MemoryUnavailable,
    MemoryWriteRequest,
)
from galliani.memory_tool import remember_tool
from galliani.permissions import ApprovalRecord
from galliani.tools import ToolCall, ToolRegistry, ToolStatus, ToolSystem

CTX = multiprocessing.get_context("spawn")
WAIT = 20.0  # generous upper bound for a slow CI machine; the normal run is far below it
PER_WORKER = 25
PRIVATE = "zebra-violet private note"  # must never appear in an error message


def req(content: str, **kw) -> MemoryWriteRequest:
    return MemoryWriteRequest(content=content, provenance="test", **kw)


def file_contents(path: Path) -> list[str]:
    return [r["content"] for r in json.loads(path.read_text(encoding="utf-8"))["records"]]


def temp_files(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.glob(".memory-*.json"))


@pytest.fixture
def path(tmp_path) -> Path:
    return tmp_path / "memory.json"


# ---------------------------------------------------------------------- workers (module level for spawn)


def race_worker(paths: list[str], name: str, barrier, results) -> None:
    """For each round: open the store before anyone writes, write 25 records at once, then list."""
    for round_no, path in enumerate(paths):
        store = JsonMemoryStore(path)
        barrier.wait(WAIT)  # every process has opened its store
        for i in range(PER_WORKER):
            store.write(req(f"round {round_no} {name} record {i}"))
        barrier.wait(WAIT)  # every process has finished writing
        results.put((round_no, name, sorted(r.content for r in store.list())))


def same_text_worker(path: str, barrier, texts: list[str]) -> None:
    store = JsonMemoryStore(path)
    barrier.wait(WAIT)
    for text in texts:
        store.write(req(text))


def hold_lock_worker(lock_path: str, ready, release, crash: bool) -> None:
    """Take the lock, say so, then either die holding it (`os._exit`) or hold it until released."""
    with file_lock(lock_path, WAIT):
        ready.set()
        if crash:
            os._exit(1)
        release.wait(WAIT)


def run_workers(target, args_for: list[tuple], results=None, expected_results: int = 0) -> list:
    """Start every worker, drain `results` (before joining, so a full pipe cannot block a worker), join."""
    procs = [CTX.Process(target=target, args=args) for args in args_for]
    for p in procs:
        p.start()
    collected = []
    try:
        collected = [results.get(timeout=WAIT * 2) for _ in range(expected_results)]
    finally:
        for p in procs:
            p.join(WAIT)
        for p in procs:
            if p.is_alive():
                p.kill()
    assert [p.exitcode for p in procs] == [0] * len(procs)
    return collected


class LockHolder:
    """A helper process holding `memory.json.lock` until `release()`, or crashing while holding it."""

    def __init__(self, path: Path, *, crash: bool = False):
        self.ready, self.done = CTX.Event(), CTX.Event()
        lock_path = str(path.with_name(path.name + ".lock"))
        self.proc = CTX.Process(target=hold_lock_worker, args=(lock_path, self.ready, self.done, crash))

    def __enter__(self) -> LockHolder:
        self.proc.start()
        assert self.ready.wait(WAIT), "the helper never took the lock"
        return self

    def release(self) -> None:
        self.done.set()
        self.proc.join(WAIT)

    def __exit__(self, *exc) -> None:
        self.release()
        if self.proc.is_alive():
            self.proc.kill()


# ---------------------------------------------------------------------- Two-Process Write Race (R6-R8)


@pytest.mark.parametrize(("workers", "rounds"), [(2, 3), (4, 1)])
def test_concurrent_writers_keep_every_record(tmp_path, workers, rounds):
    paths = [str(tmp_path / f"round{n}" / "memory.json") for n in range(rounds)]
    barrier, results = CTX.Barrier(workers), CTX.Queue()
    names = [f"p{n}" for n in range(workers)]
    seen = run_workers(race_worker, [(paths, name, barrier, results) for name in names],
                       results, rounds * workers)

    expected = {n: sorted(f"round {n} {name} record {i}" for name in names for i in range(PER_WORKER))
                for n in range(rounds)}
    for n, path in enumerate(paths):
        on_disk = file_contents(Path(path))  # valid JSON, or this raises
        assert len(on_disk) == len(set(on_disk)), f"round {n}: duplicate records"
        assert sorted(on_disk) == expected[n], f"round {n}: records lost"
    for round_no, name, listed in seen:
        assert listed == expected[round_no], f"round {round_no}: {name}.list() misses records"


# ---------------------------------------------------------------------- Same Text Saved Twice At Once (R8)


def test_same_text_saved_by_two_processes_at_once_is_one_record(path):
    texts = [f"shared preference {i}" for i in range(10)]
    barrier = CTX.Barrier(2)
    run_workers(same_text_worker, [(str(path), barrier, texts)] * 2)
    assert sorted(file_contents(path)) == sorted(texts)


# ---------------------------------------------------------------------- Stale Snapshot, Delete Is Not Undone (R7, R8)


def test_stale_snapshot_does_not_erase_another_process_record(path):
    a, b = JsonMemoryStore(path), JsonMemoryStore(path)
    b.write(req("record X"))
    a.write(req("record Y"))
    assert sorted(file_contents(path)) == ["record X", "record Y"]
    assert sorted(r.content for r in a.list()) == ["record X", "record Y"]


def test_delete_by_another_process_is_not_undone(path):
    x = JsonMemoryStore(path).write(req("record X"))
    a, b = JsonMemoryStore(path), JsonMemoryStore(path)
    assert b.delete(x.id)
    a.write(req("a different record"))
    assert file_contents(path) == ["a different record"]
    assert a.delete(x.id) is False
    assert [r.content for r in a.list()] == ["a different record"]


def test_same_text_in_two_stores_refreshes_the_record_on_disk(path):
    a, b = JsonMemoryStore(path), JsonMemoryStore(path)
    first = a.write(req("Use metric units"))
    second = b.write(req("Use metric units", type="preference"))
    assert second.id == first.id and file_contents(path) == ["Use metric units"]


# ---------------------------------------------------------------------- Lock Timeout Is Visible (R10, R13)


def test_lock_timeout_raises_and_leaves_the_file_unchanged(path, monkeypatch):
    store = JsonMemoryStore(path)
    kept = store.write(req("kept record"))
    other = JsonMemoryStore(path)
    other.write(req("saved by the other window"))  # changes the file before the lock is taken
    before = path.read_bytes()
    monkeypatch.setattr(memory_mod, "LOCK_TIMEOUT_SECONDS", 0.3)
    with LockHolder(path) as holder:
        for change in (lambda: store.write(req(PRIVATE)), lambda: store.delete(kept.id)):
            started = time.monotonic()
            with pytest.raises(MemoryUnavailable) as caught:
                change()
            assert time.monotonic() - started < 3  # bounded wait, not the 5 s default
            assert caught.value.retryable and caught.value.code == "memory_unavailable"
            assert PRIVATE not in str(caught.value) and "kept" not in str(caught.value)
            assert path.read_bytes() == before
        # R13: a reload that cannot take the lock keeps the last good snapshot and reports unavailable.
        assert [r.content for r in store.list()] == ["kept record"]
        assert store.unavailable_reason and "kept" not in store.unavailable_reason
        holder.release()
    assert sorted(r.content for r in store.list()) == ["kept record", "saved by the other window"]
    assert store.unavailable_reason is None


# ---------------------------------------------------------------------- Lock Holder Crashes (R14)


def test_a_crashed_lock_holder_does_not_block_the_next_write(path):
    with LockHolder(path, crash=True) as holder:
        holder.proc.join(WAIT)
        assert holder.proc.exitcode == 1
        started = time.monotonic()
        JsonMemoryStore(path).write(req("after the crash"))
        assert time.monotonic() - started < memory_mod.LOCK_TIMEOUT_SECONDS
    assert file_contents(path) == ["after the crash"]


# ---------------------------------------------------------------------- Unreadable File Is Not Overwritten (R12)


@pytest.mark.parametrize("bad", [
    '{"version": 1, "records": [ {"content": "' + PRIVATE + '"',  # truncated JSON
    '{"version": 1, "records": [{"content": "' + PRIVATE + '"}]}',  # valid JSON, invalid records
    '["' + PRIVATE + '"]',  # wrong top-level shape
])
def test_an_unreadable_file_is_never_overwritten(path, bad):
    store = JsonMemoryStore(path)
    record = store.write(req("kept record"))
    path.write_text(bad, encoding="utf-8")
    before = path.read_bytes()
    for change in (lambda: store.write(req("new record")), lambda: store.delete(record.id)):
        with pytest.raises(MemoryUnavailable) as caught:
            change()
        assert PRIVATE not in str(caught.value) and path.read_bytes() == before
    assert [r.content for r in store.list()] == ["kept record"] and store.unavailable_reason
    with pytest.raises(MemoryUnavailable):
        JsonMemoryStore(path)
    assert path.read_bytes() == before and temp_files(path.parent) == []


def test_a_missing_file_counts_as_empty(path):
    store = JsonMemoryStore(path)
    store.write(req("first"))
    path.unlink()
    assert store.list() == []
    assert store.write(req("second")) and file_contents(path) == ["second"]


# ---------------------------------------------------------------------- Crash Before Replace (R11, R14)


def test_a_failed_replace_keeps_the_previous_file_and_stale_temps_are_cleaned(path, monkeypatch):
    store = JsonMemoryStore(path)
    store.write(req("previous record"))
    real_replace = os.replace
    calls = []

    def fail_once(src, dst):
        calls.append(src)
        if len(calls) == 1:
            raise OSError("simulated crash before replace")
        return real_replace(src, dst)

    monkeypatch.setattr(memory_mod.os, "replace", fail_once)
    with pytest.raises(MemoryUnavailable):
        store.write(req(PRIVATE))
    assert file_contents(path) == ["previous record"]
    assert [r.content for r in JsonMemoryStore(path).list()] == ["previous record"]
    assert temp_files(path.parent) == []

    old, fresh = path.parent / ".memory-old.json", path.parent / ".memory-fresh.json"
    old.write_text("{}", encoding="utf-8")
    fresh.write_text("{}", encoding="utf-8")
    hours_ago = time.time() - 2 * 3600
    os.utime(old, (hours_ago, hours_ago))
    store.write(req("next record"))
    assert temp_files(path.parent) == [fresh.name]  # only temps older than an hour are removed
    assert sorted(file_contents(path)) == ["next record", "previous record"]


# ---------------------------------------------------------------------- Transient PermissionError on replace (R11)


def test_a_transient_permission_error_on_replace_is_retried(path, monkeypatch):
    monkeypatch.setattr(memory_mod, "REPLACE_BACKOFF_SECONDS", 0)
    real_replace = os.replace
    failures = []

    def busy_twice(src, dst):
        if len(failures) < 2:
            failures.append(src)
            raise PermissionError("another program has the file open")
        return real_replace(src, dst)

    monkeypatch.setattr(memory_mod.os, "replace", busy_twice)
    JsonMemoryStore(path).write(req("landed"))
    assert len(failures) == 2 and file_contents(path) == ["landed"]


def test_a_permanent_permission_error_raises_and_leaves_no_temp_file(path, monkeypatch):
    store = JsonMemoryStore(path)
    store.write(req("previous record"))
    before = path.read_bytes()
    monkeypatch.setattr(memory_mod, "REPLACE_BACKOFF_SECONDS", 0)
    attempts = []

    def always_busy(src, dst):
        attempts.append(src)
        raise PermissionError("another program has the file open")

    monkeypatch.setattr(memory_mod.os, "replace", always_busy)
    with pytest.raises(MemoryUnavailable) as caught:
        store.write(req(PRIVATE))
    assert len(attempts) == memory_mod.REPLACE_ATTEMPTS and PRIVATE not in str(caught.value)
    assert path.read_bytes() == before and temp_files(path.parent) == []


def test_fsync_runs_before_replace(path, monkeypatch):
    order = []
    real_fsync, real_replace = os.fsync, os.replace
    monkeypatch.setattr(memory_mod.os, "fsync", lambda fd: order.append("fsync") or real_fsync(fd))
    monkeypatch.setattr(memory_mod.os, "replace", lambda s, d: order.append("replace") or real_replace(s, d))
    JsonMemoryStore(path).write(req("durable"))
    assert order == ["fsync", "replace"]


# ---------------------------------------------------------------------- Reads See Other Writers (R13)


def test_reads_see_another_process_changes_without_a_restart(path):
    desktop, cli = JsonMemoryStore(path), JsonMemoryStore(path)
    assert desktop.list() == []
    pref = cli.write(req("Write summaries in Spanish", type="preference"))
    result = desktop.query(MemoryQuery(keywords=["summary"]))
    assert [r.id for r in result.records] == [pref.id]
    assert [r.content for r in desktop.list()] == ["Write summaries in Spanish"]
    cli.delete(pref.id)
    assert desktop.list() == []


def test_an_unchanged_file_is_not_reread(path, monkeypatch):
    store = JsonMemoryStore(path)
    store.write(req("one"))
    reads = []
    real_read = memory_mod.JsonMemoryStore._read_disk
    monkeypatch.setattr(memory_mod.JsonMemoryStore, "_read_disk", lambda self: reads.append(1) or real_read(self))
    store.list()
    store.list()
    assert reads == []


# ---------------------------------------------------------------------- remember tool (R15)


class BusyStore(InMemoryMemoryStore):
    def write(self, request):
        raise MemoryUnavailable("memory is busy in another Galliani window; try again")


async def test_the_remember_tool_reports_unavailable_memory_as_a_failed_retryable_result():
    system = ToolSystem(ToolRegistry([remember_tool(BusyStore())]))
    call = ToolCall(tool_name="remember", call_id="c", requested_by_step="m",
                    arguments={"content": PRIVATE, "scope": "user"})
    result = await system.execute(call, task_id="t",
                                  approvals=[ApprovalRecord(user_id="u", action="remember", scope="user")])
    assert result.status is ToolStatus.failed
    assert result.error.code == "memory_unavailable" and result.error.retryable
    assert "try again" in result.error.safe_summary
    assert PRIVATE not in result.error.safe_summary and PRIVATE not in result.observation_summary


# ---------------------------------------------------------------------- Lock File Is Empty Of Content (R9)


def test_the_lock_file_holds_no_content(path):
    store = JsonMemoryStore(path)
    for i in range(5):
        record = store.write(req(f"{PRIVATE} {i}"))
    store.delete(record.id)
    store.list()
    lock = path.with_name("memory.json.lock")
    assert lock.exists() and lock.read_bytes() == b""
    assert JsonMemoryStore(path).write(req("the leftover lock file is not a lock"))
