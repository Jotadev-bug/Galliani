"""Shared vocabulary from spec 000: Objective, sensitivity labels, ids and timestamps."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Sensitivity(str, Enum):
    public = "public"
    internal = "internal"
    sensitive = "sensitive"


class Objective(BaseModel):
    """000 `Objective`: user goal plus constraints and context. Context is data, not instruction."""

    model_config = ConfigDict(extra="forbid")

    goal: str
    constraints: dict[str, Any] = Field(default_factory=dict)
    context: str = ""

    def is_valid(self) -> bool:
        return bool(self.goal.strip())
