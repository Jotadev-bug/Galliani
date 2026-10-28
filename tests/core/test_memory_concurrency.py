"""Spec 010 Amendment A: several processes share one memory file (Decision 0040).

Multi-process tests use the `spawn` context on every OS (the Windows default) and module-level workers that
receive the file path. Every test works in `tmp_path`. Correctness never depends on `sleep`: workers start
together on barriers and events, and every wait has a deadline so a bug fails the test instead of hanging it.
"""

from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest

from galliani.memory import JsonMemoryStore, MemoryWriteRequest

CTX = multiprocessing.get_context("spawn")
WAIT = 20.0  # generous upper bound for a slow CI machine; the normal run is far below it
PER_WORKER = 25
ROUNDS = 3


def req(content: str, **kw) -> MemoryWriteRequest:
    return MemoryWriteRequest(content=content, provenance="test", **kw)


def file_contents(path: Path) -> list[str]:
    return [r["content"] for r in json.loads(path.read_text(encoding="utf-8"))["records"]]


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


# ---------------------------------------------------------------------- Two-Process Write Race (R6-R8)


@pytest.mark.parametrize("workers", [2, 4])
def test_concurrent_writers_keep_every_record(tmp_path, workers):
    paths = [str(tmp_path / f"round{n}" / "memory.json") for n in range(ROUNDS)]
    barrier, results = CTX.Barrier(workers), CTX.Queue()
    names = [f"p{n}" for n in range(workers)]
    seen = run_workers(race_worker, [(paths, name, barrier, results) for name in names],
                       results, ROUNDS * workers)

    expected = {n: sorted(f"round {n} {name} record {i}" for name in names for i in range(PER_WORKER))
                for n in range(ROUNDS)}
    for n, path in enumerate(paths):
        on_disk = file_contents(Path(path))  # valid JSON, or this raises
        assert len(on_disk) == len(set(on_disk)), f"round {n}: duplicate records"
        assert sorted(on_disk) == expected[n], f"round {n}: records lost"
    for round_no, name, listed in seen:
        assert listed == expected[round_no], f"round {round_no}: {name}.list() misses records"
