"""Memory contracts (000 vocabulary; spec 010 stays Draft, Decision 0006).

v0.1 defines only the data shapes. There is no memory store, and the supervisor has no Memory
dependency, so runtime observations can never be written to Memory automatically (010 AC Separate State).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from galliani.contracts import Sensitivity, new_id, utcnow


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("mem"))
    content: str
    type: str
    provenance: str
    sensitivity: Sensitivity = Sensitivity.internal
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    ttl: int | None = None  # seconds


class MemoryWriteRequest(BaseModel):
    content: str
    type: str
    provenance: str
    sensitivity: Sensitivity = Sensitivity.internal
    reason_summary: str
