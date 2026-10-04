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
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from galliani.contracts import Sensitivity, new_id, utcnow
from galliani.errors import ContractError, GallianiError
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
            for existing in self._records.values():
                if existing.scope == request.scope and existing.content == request.content:
                    updated = existing.model_copy(update={"updated_at": utcnow(), "type": request.type,
                                                          "sensitivity": request.sensitivity, "ttl": request.ttl})
                    self._records[existing.id] = updated
                    self._persist()
                    return updated
            record = MemoryRecord(content=request.content, type=request.type, scope=request.scope,
                                  provenance=request.provenance, sensitivity=request.sensitivity, ttl=request.ttl)
            self._records[record.id] = record
            self._persist()
            return record

    def delete(self, record_id: str) -> bool:
        with self._lock:
            removed = self._records.pop(record_id, None) is not None
            if removed:
                self._persist()
            return removed

    def _persist(self) -> None:  # durable stores override
        pass


class JsonMemoryStore(InMemoryMemoryStore):
    """Durable store: one JSON file, replaced atomically on every change."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        records: list[MemoryRecord] = []
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                records = [MemoryRecord.model_validate(r) for r in raw.get("records", [])]
            except (OSError, ValueError) as e:
                raise MemoryUnavailable(f"memory file is unreadable ({type(e).__name__})") from None
        super().__init__(records)

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "records": [r.model_dump(mode="json") for r in self._records.values()]}
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".memory-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except OSError as e:
            Path(tmp).unlink(missing_ok=True)
            raise MemoryUnavailable(f"memory could not be saved ({type(e).__name__})") from None
