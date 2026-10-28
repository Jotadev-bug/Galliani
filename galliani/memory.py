"""Spec 010 - Memory: explicit, durable knowledge kept separate from Task State (Decision 0019).

- `MemoryRecord` carries provenance, sensitivity and a scope (`user` or `project:<folder>`).
- `MemoryPolicy` decides writes: a user's own write is allowed, an agent's write needs the user's
  approval, and anything containing a secret-like value is denied.
- Stores never persist secret-like content, whoever asks (defense in depth).
- `retrieve` is deterministic: in-scope preferences/instructions always, facts/notes by keyword.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from galliani.contracts import Sensitivity, new_id, utcnow
from galliani.errors import ContractError, GallianiError
from galliani.file_lock import LockTimeout, file_lock
from galliani.redaction import REDACTED, contains_secret

MemoryType = Literal["preference", "instruction", "fact", "note"]
ALWAYS_RELEVANT: frozenset[str] = frozenset({"preference", "instruction"})
USER_SCOPE = "user"
MAX_CONTENT = 1_000
STOP_WORDS = frozenset("""
the and for with that this from into your you are was were will would should could have has had not but all any
can its our their them they what when where which who why how about after before over under then than also just
only very more most some such each other these those there here use using make made please file files folder
""".split())


def project_scope(workspace: str | Path) -> str:
    return f"project:{Path(workspace).resolve()}"


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("mem"))
    content: str
    type: MemoryType
    scope: str = USER_SCOPE
    provenance: str
    sensitivity: Sensitivity = Sensitivity.internal
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    ttl: int | None = Field(default=None, gt=0)  # seconds

    def expired(self, now: datetime) -> bool:
        return self.ttl is not None and now >= self.updated_at + timedelta(seconds=self.ttl)

    def display_content(self) -> str:
        """Sensitive memory is redacted in UI and logs (010 security)."""
        return REDACTED if self.sensitivity is Sensitivity.sensitive else self.content


class MemoryWriteRequest(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_CONTENT)
    type: MemoryType = "note"
    scope: str = USER_SCOPE
    provenance: str
    sensitivity: Sensitivity = Sensitivity.internal
    reason_summary: str = ""
    source: Literal["user", "agent"] = "user"
    ttl: int | None = Field(default=None, gt=0)

    @field_validator("content")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content is empty")
        return v

    @field_validator("scope")
    @classmethod
    def _scope(cls, v: str) -> str:
        if v != USER_SCOPE and not v.startswith("project:"):
            raise ValueError("scope must be 'user' or 'project:<folder>'")
        return v


class MemoryQuery(BaseModel):
    task_id: str | None = None
    scope: list[str] = Field(default_factory=lambda: [USER_SCOPE])
    keywords: list[str] = Field(default_factory=list)
    types: list[MemoryType] | None = None
    max_records: int = Field(default=5, ge=1, le=50)


class MemoryResult(BaseModel):
    records: list[MemoryRecord]
    omitted_count: int = 0
    retrieval_summary: str


class MemoryDecisionStatus(str, Enum):
    allowed = "allowed"
    denied = "denied"
    needs_user = "needs_user"


class MemoryWriteDecision(BaseModel):
    status: MemoryDecisionStatus
    reason: str


class MemoryUnavailable(GallianiError):
    code = "memory_unavailable"
    retryable = True


class MemoryPolicy:
    """010 R2: writes are explicit and policy-controlled."""

    def evaluate(self, request: MemoryWriteRequest) -> MemoryWriteDecision:
        if contains_secret(request.content):
            return MemoryWriteDecision(status=MemoryDecisionStatus.denied,
                                       reason="the text contains a secret-like value; secrets are never saved")
        if request.source == "agent":
            return MemoryWriteDecision(status=MemoryDecisionStatus.needs_user,
                                       reason="an agent may only save to memory with your approval")
        return MemoryWriteDecision(status=MemoryDecisionStatus.allowed, reason="saved at your request")


def keywords_of(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z0-9áéíóúñü]{3,}", text.lower())
    return [w for w in dict.fromkeys(words) if w not in STOP_WORDS]


def _stem(word: str) -> str:
    return word[:5]


def relevance(record: MemoryRecord, keywords: list[str]) -> int:
    """Keyword overlap on 5-character prefixes (so "summary" matches "summaries" and "summarize")."""
    wanted = {_stem(k) for k in keywords}
    return len(wanted & {_stem(w) for w in keywords_of(record.content)})


def retrieve(records: list[MemoryRecord], query: MemoryQuery, now: datetime | None = None) -> MemoryResult:
    now = now or utcnow()
    in_scope = [r for r in records if r.scope in query.scope and not r.expired(now)
                and (query.types is None or r.type in query.types)]
    scored = []
    for record in in_scope:
        score = relevance(record, query.keywords)
        if record.type in ALWAYS_RELEVANT or score > 0:
            scored.append((record.type in ALWAYS_RELEVANT, score, record.updated_at, record))
    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    picked = [item[3] for item in scored[:query.max_records]]
    omitted = len(scored) - len(picked)
    summary = (f"{len(picked)} relevant record(s) from {len(in_scope)} in scope"
               + (f"; {omitted} more omitted" if omitted else ""))
    return MemoryResult(records=picked, omitted_count=omitted, retrieval_summary=summary)


class MemoryStore(Protocol):
    def list(self, scopes: list[str] | None = None) -> list[MemoryRecord]: ...
    def query(self, query: MemoryQuery) -> MemoryResult: ...
    def write(self, request: MemoryWriteRequest) -> MemoryRecord: ...
    def delete(self, record_id: str) -> bool: ...


class InMemoryMemoryStore:
    def __init__(self, records: list[MemoryRecord] | None = None):
        self._records: dict[str, MemoryRecord] = {r.id: r for r in records or []}
        self._lock = threading.Lock()

    def list(self, scopes: list[str] | None = None) -> list[MemoryRecord]:
        now = utcnow()
        with self._lock:
            records = [r for r in self._records.values() if not r.expired(now)]
        if scopes is not None:
            records = [r for r in records if r.scope in scopes]
        return sorted(records, key=lambda r: r.updated_at, reverse=True)

    def query(self, query: MemoryQuery) -> MemoryResult:
        return retrieve(self.list(), query)

    def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        if contains_secret(request.content):
            raise ContractError("memory content contains a secret-like value; not saved")
        with self._lock:
            return _upsert(self._records, request)

    def delete(self, record_id: str) -> bool:
        with self._lock:
            return self._records.pop(record_id, None) is not None


def _upsert(records: dict[str, MemoryRecord], request: MemoryWriteRequest) -> MemoryRecord:
    """Add the record, or refresh the one with the same scope and content (one record per text)."""
    for existing in records.values():
        if existing.scope == request.scope and existing.content == request.content:
            updated = existing.model_copy(update={"updated_at": utcnow(), "type": request.type,
                                                  "sensitivity": request.sensitivity, "ttl": request.ttl})
            records[existing.id] = updated
            return updated
    record = MemoryRecord(content=request.content, type=request.type, scope=request.scope,
                          provenance=request.provenance, sensitivity=request.sensitivity, ttl=request.ttl)
    records[record.id] = record
    return record


# Amendment A storage tuning; module constants so tests can shorten them.
LOCK_TIMEOUT_SECONDS = 5.0
REPLACE_ATTEMPTS = 5
REPLACE_BACKOFF_SECONDS = 0.05
STALE_TEMP_SECONDS = 3600
TEMP_PREFIX, TEMP_SUFFIX = ".memory-", ".json"

Identity = tuple[int, int] | None  # (st_mtime_ns, st_size), or None when the file does not exist


class JsonMemoryStore(InMemoryMemoryStore):
    """Durable store: one JSON file shared by several processes on one machine (spec 010 Amendment A).

    Every change is one cross-process transaction under an OS lock on `<file>.lock`: re-read the file, apply
    only this call's operation by record id, write a temp file, `fsync` it and `os.replace` it. Reads reload
    when the file changed. Failures raise `MemoryUnavailable` (retryable) and never name memory content.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self._identity: Identity = None
        # Why the last reload failed, or None. Reads keep the last good snapshot meanwhile (R13).
        self.unavailable_reason: str | None = None
        super().__init__()
        with self._lock:
            if self._stat() is not None:  # a missing file is empty; nothing to lock for
                with self._transaction():
                    self._records, self._identity = self._read_disk()

    # ------------------------------------------------------------------ reads (R13)

    def list(self, scopes: list[str] | None = None) -> list[MemoryRecord]:
        self._refresh()
        return super().list(scopes)

    def _refresh(self) -> None:
        with self._lock:
            if self._stat() == self._identity and self.unavailable_reason is None:
                return
            try:
                with self._transaction():
                    self._records, self._identity = self._read_disk()
            except MemoryUnavailable as e:
                self.unavailable_reason = e.safe_summary
                return
            self.unavailable_reason = None

    # ------------------------------------------------------------------ changes (R7, R8)

    def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        if contains_secret(request.content):
            raise ContractError("memory content contains a secret-like value; not saved")
        with self._lock, self._transaction():
            records, _ = self._read_disk()
            record = _upsert(records, request)
            self._commit(records)
            return record

    def delete(self, record_id: str) -> bool:
        with self._lock, self._transaction():
            records, identity = self._read_disk()
            if records.pop(record_id, None) is None:
                self._records, self._identity, self.unavailable_reason = records, identity, None
                return False
            self._commit(records)
            return True

    # ------------------------------------------------------------------ storage details (R9-R12, R14)

    def _stat(self) -> Identity:
        try:
            st = self.path.stat()
        except FileNotFoundError:
            return None
        except OSError:
            return (-1, -1)  # cannot stat: force a (failing, reported) reload rather than trust the snapshot
        return (st.st_mtime_ns, st.st_size)

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        stack = ExitStack()
        try:  # only acquiring is translated here; errors raised by the caller's body pass through unchanged
            self.path.parent.mkdir(parents=True, exist_ok=True)
            stack.enter_context(file_lock(self.lock_path, LOCK_TIMEOUT_SECONDS))
        except LockTimeout:
            raise MemoryUnavailable("memory is busy in another Galliani window; try again") from None
        except OSError as e:
            raise MemoryUnavailable(f"memory lock could not be opened ({type(e).__name__}); try again") from None
        with stack:
            yield

    def _read_disk(self) -> tuple[dict[str, MemoryRecord], Identity]:
        """The records on disk now (call under the lock). A missing file is empty; a bad one raises (R12)."""
        identity = self._stat()
        if identity is None:
            return {}, None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("records"), list):
                # Not the {"version": 1, "records": [...]} format (a newer version included): never treat it as
                # empty and never rewrite it, so a downgrade cannot drop fields this version does not know.
                raise TypeError
            records = [MemoryRecord.model_validate(r) for r in raw["records"]]
        except FileNotFoundError:
            return {}, None
        except (OSError, ValueError, AttributeError, TypeError) as e:
            # Only the exception type: pydantic and JSON messages can quote file content.
            raise MemoryUnavailable(f"memory file is unreadable ({type(e).__name__})") from None
        return {r.id: r for r in records}, identity

    def _commit(self, records: dict[str, MemoryRecord]) -> None:
        """Write `records` durably and adopt them as this process's snapshot (call under the lock)."""
        self._remove_stale_temps()
        payload = {"version": 1, "records": [r.model_dump(mode="json") for r in records.values()]}
        tmp = ""
        try:
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=TEMP_PREFIX, suffix=TEMP_SUFFIX)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=1)
                fh.flush()
                os.fsync(fh.fileno())
            self._replace(tmp)
        except OSError as e:
            if tmp:
                Path(tmp).unlink(missing_ok=True)
            raise MemoryUnavailable(f"memory could not be saved ({type(e).__name__}); try again") from None
        self._records, self._identity, self.unavailable_reason = records, self._stat(), None

    def _replace(self, tmp: str) -> None:
        """`os.replace`, retrying a transient `PermissionError` (another program briefly holding the file)."""
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                os.replace(tmp, self.path)
                return
            except PermissionError:
                if attempt == REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(REPLACE_BACKOFF_SECONDS * (attempt + 1))

    def _remove_stale_temps(self) -> None:
        cutoff = time.time() - STALE_TEMP_SECONDS
        for leftover in self.path.parent.glob(f"{TEMP_PREFIX}*{TEMP_SUFFIX}"):
            try:
                if leftover.stat().st_mtime < cutoff:
                    leftover.unlink()
            except OSError:
                pass
