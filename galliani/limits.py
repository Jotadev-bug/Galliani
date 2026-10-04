"""Hard loop budgets (Decision 0008). Retry and replan budgets live in `replanning.RetryPolicy`."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoopLimits(BaseModel):
    max_plan_steps: int = Field(default=5, ge=1)
    max_total_actions: int = Field(default=10, ge=1)
