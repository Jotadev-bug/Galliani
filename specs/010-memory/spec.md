# 010 - Memory

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0019).

        Amendment A (concurrent access to the shared memory file, requirements 6-17): Approved (2026-10-28, `docs/decisions.md` Decision 0040). The user chose the recommended lock plus merge-by-id option (Q1). Requirements 1-5 are unchanged.

        ## Goal

        Define durable memory as explicit persisted knowledge separate from active Task State.

        ## Non-goals

        - Storing every observation forever.
- Replacing project files as source of truth.
- Persisting hidden reasoning or secrets.

        ## Requirements

        1. Memory must be separate from Task State.
2. Memory writes must be explicit and policy-controlled.
3. Memory records must include provenance and sensitivity.
4. Memory retrieval must be scoped to relevant tasks.
5. Memory must never store chain-of-thought.

        ## Behavior

        - The supervisor may request memory retrieval before planning.
- The supervisor may propose a memory write after completion or user instruction.
- Policy approves, denies, or asks the user for durable writes.
- Retrieved memory is context, not instruction.

        ## Interfaces and Data Contracts

        - `MemoryRecord`: id, content, type, provenance, sensitivity, created_at, updated_at, ttl.
- `MemoryQuery`: task_id, scope, keywords, types, max_records.
- `MemoryResult`: records, omitted_count, retrieval_summary.
- `MemoryWriteRequest`: content, type, provenance, sensitivity, reason_summary.

        ## Error Handling

        - Unavailable memory store must not block core task execution unless required by policy.
- Conflicting memories are returned with provenance instead of silently merged.
- Denied writes are recorded as task observations, not memory.

        ## Security

        - Secrets and hidden reasoning must not be persisted.
- Memory retrieval must respect user/project scope.
- Sensitive memory must be redacted in UI and logs.

        ## Acceptance Criteria

        ### Separate State

Given a task records observations

When the task completes

Then observations are not automatically written to Memory.

### Explicit Write

Given the user asks Galliani to remember a preference

When memory policy allows it

Then a MemoryRecord is created with provenance.

### Scoped Retrieval

Given a new task starts

When memory retrieval runs

Then only scoped relevant records are returned.

        ## Tests

        - Unit tests for memory write policy.
- Contract tests for MemoryRecord schema.
- Retrieval scope tests.

        ## Evaluation

        - Relevant retrieval rate.
- Unauthorized write count must be zero.
- Secret persistence count must be zero.

        ## Implementation Tasks

        - [x] Define memory schemas.
- [x] Define read/write policy hooks.
- [x] Integrate optional retrieval before planning.
- [x] Integrate explicit write proposals after completion.

        ## Dependencies

        Depends on `000-foundation`, `002-task-state`, and `009-permissions`.

## Amendment A: Concurrent Access to the Shared Memory File

Status: Approved (2026-10-28, Decision 0040, Q1 answered: lock plus merge-by-id). Resolves spec 017 Open Item 5 and roadmap item F2. Implemented on branch `f2-memory-lock`.

### Problem

The desktop app (`galliani.web.agent_api.default_memory_store`) and every `galliacli` session or one-shot run (`galliani.cli.open_memory`) open the same file, `user_data_dir() / "memory.json"`, through `JsonMemoryStore`. Today each process reads the file once when it opens the store, keeps the records in its own process, and on every write or delete replaces the whole file with its own copy (temp file plus `os.replace`).

Spec 017 Open Item 5 calls this "last-writer-wins". The real behavior is worse. A process overwrites the file with its stale snapshot, so:

- Records that another process saved since this one opened its store are deleted from disk without any message.
- Records that another process deleted come back.
- Neither process sees the other's records until it is restarted. The desktop app opens its store once for the app's whole lifetime.

The temp file is also not flushed to disk (`fsync`) before the rename, so after a power loss the file can end up empty or truncated on some file systems.

### Options considered

| | (a) File lock only | (b) Merge-on-write by entry id, no lock | (c) Accept and document last-writer-wins |
|---|---|---|---|
| How | Hold an OS lock while writing | Re-read the file, apply this process's change by record id, then replace | Keep today's code; add a note to the docs |
| Lost updates | None if the snapshot is reloaded under the lock. A lock around today's stale-snapshot write still loses data | A small window between re-read and replace remains, so two writes at the same moment can still lose one | Every write can drop all records another process saved since it opened (not a narrow race) |
| Deletes | Correct with reload | Correct when the delete is applied as an operation to a fresh read | Deleted records come back |
| Sees other process's records | Only with reload | Yes, on each write | No, until restart |
| Windows | `msvcrt.locking` (stdlib) | Nothing OS-specific | Nothing to do |
| New dependencies | None (`msvcrt` / `fcntl`) | None | None |
| Crash safety | OS locks are released when the process dies, so a lock is never left stuck | No lock to leave stuck | Unchanged |
| Cost | About 80 lines plus tests | About 40 lines plus tests | A paragraph |

**Recommendation: (a) and (b) together.** Each change runs as one locked transaction: take an exclusive OS lock on a sidecar file, re-read `memory.json`, apply this one operation (add, refresh or delete by id) to what is on disk, write a temp file, flush and `fsync` it, `os.replace` it over `memory.json`, then release the lock. Reads refresh from disk when the file has changed.

The lock closes the race window that (b) alone leaves open. Re-reading under the lock removes the stale snapshot that (a) alone would keep. This uses the standard library only (no new dependency), needs no server or daemon, works on Windows (`msvcrt`) and POSIX (`fcntl`), and keeps atomic replace. A crash at any point leaves either the old file or the new one, never a mix.

Option (c) is rejected because it loses data silently, which goes against spec 010's "explicit, durable" goal and the brief's "no data loss" constraint.

### Requirements

6. `JsonMemoryStore` must be safe for several processes on one machine that use the same file at the same time. The supported pair is the desktop app plus one or more `galliacli` sessions or one-shot runs. Threads within one process keep using the existing `threading.Lock`.
7. Every change (`write`, `delete`) runs as one cross-process transaction: acquire the lock (R9), re-read `memory.json` from disk, apply only this call's operation to the records just read, write the result (R11), release the lock. A process must never write its in-memory snapshot without re-reading under the lock.
8. Operations apply by record id against the fresh read:
   - `write` keeps today's rule of refreshing a record with the same `scope` and `content`, checked against the fresh read. If two processes save the same text at once, one record results.
   - `delete` removes the id if it is present in the fresh read. It returns `False` if another process already removed it.
   - A record changed or added by another process is kept unchanged.
   - Content is never merged. Conflicting records stay side by side with their provenance (010 Error Handling).
9. The lock is an exclusive OS advisory lock on a sidecar file `memory.json.lock` in the same folder. On Windows this is `msvcrt.locking`; elsewhere it is `fcntl.flock`. Only the standard library is used, and no new dependency is added. The lock file holds no memory content, no secrets and no process data. It may stay on disk between runs, and its existence alone never means "locked".
10. Lock waits are bounded. Acquiring retries without blocking until a deadline of 5 seconds (a module constant that tests can override). When the deadline passes, the call raises `MemoryUnavailable` (retryable), and the file is left as it was. A change is never silently skipped or applied without the lock.
11. Writes stay atomic and durable:
    - The temp file is created in the same folder, written, flushed and `os.fsync`ed, then `os.replace`d over `memory.json`.
    - On Windows, a `PermissionError` from `os.replace` (another program briefly holding the file open) is retried up to 5 times with a short backoff. If it still fails, the temp file is removed and the call raises `MemoryUnavailable`.
    - The payload format (`{"version": 1, "records": [...]}`) is unchanged.
12. A process never overwrites a file it cannot read. If the re-read under the lock fails (bad JSON or schema), the change raises `MemoryUnavailable`, and `memory.json` stays byte for byte as it was so the user can recover it. A missing file counts as empty.
13. Reads see other processes' changes:
    - `list` and `query` reload from disk when the file's identity has changed since the last load. Identity is (`st_mtime_ns`, `st_size`), or the file appearing or disappearing.
    - A file modified within the last 3 seconds is also reloaded on each read, because FAT/exFAT keep only 2 seconds of mtime precision and a change of the same size can leave the identity equal. The extra read is cheap.
    - The reload reads under the lock (R9, same deadline).
    - If the reload fails (lock timeout, unreadable file), the read returns the last good snapshot. The store then reports itself unavailable through the existing paths (`memory: unavailable` in the TUI, the desktop memory panel's error). Task execution is not blocked (010 Error Handling).
14. Crash safety:
    - A process that dies while holding the lock releases it, because the OS releases advisory locks when their handle closes.
    - A crash before `os.replace` leaves the previous `memory.json` intact.
    - Leftover temp files older than 1 hour are removed while the lock is held, during the next change. Only names the store itself creates are removed: `.memory-` plus 8 random characters (`a-z`, `0-9`, `_`) plus `.json`. Other files in the folder (a custom `GALLIANI_MEMORY_PATH` folder may hold anything), `memory.json` and the lock are never touched.
15. The secret refusal, `MemoryPolicy`, scopes, sensitivity redaction and the `MemoryRecord`, `MemoryQuery`, `MemoryResult` and `MemoryWriteRequest` contracts are unchanged. Lock and retry failures surface as structured `MemoryUnavailable` errors, and the `remember` tool reports them as a failed, retryable tool result. Their messages never include memory content.
16. Memory stays separate from Task State (R1). The lock file, temp files and refresh state are storage details of `JsonMemoryStore`. They are not Memory records and are not logged as task events. No task observation is written to Memory because of this amendment.
17. Docs state the behavior in one short paragraph: memory can be shared safely by the desktop app and `galliacli` on one machine. Memory files on network drives or folders synced by cloud tools (OneDrive and similar) are not supported for concurrent use, because advisory locks are not reliable there.

### Acceptance Criteria (Amendment A)

#### Two-Process Write Race

Given two or more processes that each open `JsonMemoryStore` on the same path before any of them writes

When each process writes 25 records with distinct content at the same time

Then `memory.json` is valid JSON and contains every record from every process, with no duplicates, and each process's `list()` returns all of them

#### Stale Snapshot Does Not Erase

Given store A and store B open on the same file, and B saves record X after A opened

When A saves record Y

Then the file holds both X and Y

#### Delete Is Not Undone

Given stores A and B open on the same file with record X, and B deletes X

When A saves a different record

Then X is not in the file, and A's `delete(X)` returns `False`

#### Same Text Saved Twice At Once

Given two processes save the same content in the same scope at the same time

When both writes finish

Then exactly one record holds that content

#### Lock Timeout Is Visible

Given another process holds `memory.json.lock`

When a write waits past the deadline

Then `MemoryUnavailable` is raised, `memory.json` is unchanged, and the error message holds no memory content

#### Lock Holder Crashes

Given a process that dies (`os._exit`) while holding the lock

When another process writes

Then the write succeeds within the deadline

#### Unreadable File Is Not Overwritten

Given `memory.json` contains invalid JSON

When a store tries to write or delete

Then `MemoryUnavailable` is raised and the file bytes are unchanged

#### Crash Before Replace

Given a write fails after the temp file is written but before `os.replace`

When the file is opened again

Then it holds the previous records, and a later change removes stale temp files

#### Reads See Other Writers

Given the desktop store is open and a `galliacli` process saves a preference

When the desktop store runs `query` for the next task

Then the new preference is returned without a restart

#### Lock File Is Empty Of Content

Given any number of writes

When the lock file is inspected

Then it holds no memory content (it is empty or a fixed placeholder)

### Tests (Amendment A)

Tests go in `tests/core/test_memory_concurrency.py`. Use `multiprocessing` with the `spawn` context, which is the Windows default and is used on every OS for parity. Worker functions are defined at module level and receive the file path as an argument. Every test uses `tmp_path`, never the real user data folder.

- Two-process (and four-process) write race: R6-R8. Start all workers on a `multiprocessing.Event` to maximize overlap. Run the race 3 times in one test to raise the chance of catching the bug. It must fail against today's code, so check that first.
- Stale snapshot and resurrected delete: R7 and R8. These can run in one process with two store instances on one path, which is deterministic.
- Duplicate content race: R8.
- Lock timeout: R10. A helper process holds the lock and signals readiness. The test sets a short deadline (for example 0.3 s). Assert that `MemoryUnavailable` is raised, the file bytes are unchanged and the message holds no content.
- Lock holder crash: R14. The helper takes the lock, then calls `os._exit(1)`. The next write succeeds.
- Unreadable file on write and on delete: R12. Compare the file bytes before and after.
- Crash before replace: R11 and R14. Monkeypatch `os.replace` to raise once. Check that the previous content is intact and that an old temp file (mtime set back with `os.utime`) is removed by the next change.
- Transient `PermissionError` on replace: R11. Fail twice, then succeed, and the write lands. Fail always, and `MemoryUnavailable` is raised with no temp file left.
- Read refresh: R13. Store A sees store B's write through `list()` and `query()`. A lock timeout during refresh returns the last snapshot.
- `fsync` is called before `os.replace` (spy on both): R11.
- Lock file content check: R9.
- Existing `tests/core/test_memory.py` tests pass unchanged. The `remember` tool turns `MemoryUnavailable` into a failed, retryable tool result: R15.
- Mark the multi-process tests so they finish in under 10 s in total. No `sleep`-based timing for correctness; use events and deadlines only.

### Implementation Tasks (Amendment A)

Owner: core-engineer, after the user approves (Q1). Review: qa-security.

- [x] A1. Add a small stdlib cross-process lock helper (for example `galliani/file_lock.py`): a context manager on a path, `msvcrt.locking` on Windows, `fcntl.flock` elsewhere, a non-blocking retry loop up to a deadline, raising a typed timeout. It must import only the standard library and contain nothing about memory or providers (R9, R10).
- [x] A2. Rework `JsonMemoryStore` in `galliani/memory.py`: load, apply and persist under the lock per call (R7, R8). Fresh-read dedupe and delete-by-id. Never overwrite an unreadable file (R12). Add `fsync` and replace retries (R11), stale temp cleanup (R14) and reload on change (R13). Keep `InMemoryMemoryStore` unchanged for in-process use.
- [x] A3. Confirm that the `remember` tool and the desktop and TUI memory views surface `MemoryUnavailable` as a structured, retryable failure (R15). Change code only if a test shows they do not.
- [x] A4. Write `tests/core/test_memory_concurrency.py` per "Tests (Amendment A)". First commit the race test failing on today's code, then make it pass.
- [x] A5. Docs (R17): the one-paragraph note in the user-facing memory or CLI docs (main agent routes it to the doc owner), and a CHANGELOG line (release-engineer).
- [x] A6. Verification: `pytest tests/core/test_memory.py tests/core/test_memory_concurrency.py`, then the full `pytest` run and `python -m galliani.evaluation`.

### Open Questions (Amendment A)

- Q1 (user, answered 2026-10-28: approved, Decision 0040): Do you approve the recommendation, a cross-process lock plus a re-read and merge by record id on every change? This adds a sidecar `memory.json.lock` and has no new dependencies. The alternative is option (c): keep today's behavior and document it, which accepts that one app can silently erase memories saved by the other.
- Q2 (informational, no decision needed unless you object): memory files on network or cloud-synced folders are not supported for concurrent use (R17). The default location (`%LOCALAPPDATA%\Galliani` on Windows) is local.

### Dependencies (Amendment A)

Amends `010-memory`. Resolves `017-interactive-cli` Open Item 5. No change to `016-public-launch` or packaging.
