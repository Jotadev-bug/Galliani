"""Spec 003 - Model Router: provider-neutral selection of an Agent Worker.

Filter by capability and limits, then by policy, rank by the configured strategy, and skip unavailable
workers. The rationale is a short public summary of selection factors, never reasoning.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from galliani.errors import GallianiError

log = logging.getLogger(__name__)

CostClass = Literal["low", "medium", "high", "premium"]
LatencyClass = Literal["fast", "medium", "slow"]
_COST_RANK = {"low": 0, "medium": 1, "high": 2, "premium": 3}
_LATENCY_RANK = {"fast": 0, "medium": 1, "slow": 2}


class WorkerLimits(BaseModel):
    context_window: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)


class WorkerProfile(BaseModel):
    worker_id: str
    provider_id: str  # the ProviderAdapter that serves this worker
    capabilities: set[str]
    limits: WorkerLimits
    cost_class: CostClass
    latency_class: LatencyClass
    availability: Literal["available", "degraded", "unavailable"] = "available"
    policy_tags: set[str] = Field(default_factory=set)


class RoutingPolicy(BaseModel):
    allowed_providers: set[str] | None = None
    denied_providers: set[str] = Field(default_factory=set)
    denied_tags: set[str] = Field(default_factory=set)
    strategy: Literal["cheapest", "fastest"] = "cheapest"


class InputShape(BaseModel):
    estimated_tokens: int = Field(default=0, ge=0)


class RouteConstraints(BaseModel):
    max_cost_class: CostClass | None = None
    max_latency_class: LatencyClass | None = None


class ModelWorkRequest(BaseModel):
    task_id: str
    step_id: str
    capability: set[str]
    input_shape: InputShape = Field(default_factory=InputShape)
    constraints: RouteConstraints = Field(default_factory=RouteConstraints)
    policy: RoutingPolicy = Field(default_factory=RoutingPolicy)


class ModelRoute(BaseModel):
    worker_id: str
    provider_adapter_id: str
    rationale: str
    fallback_worker_ids: list[str] = Field(default_factory=list)
    policy_tags: list[str] = Field(default_factory=list)


class RouteError(GallianiError):
    """Codes: `no_route`, `route_denied`, `provider_unavailable`."""

    def __init__(self, safe_summary: str, *, code: str, fallback_eligible: bool = False):
        super().__init__(safe_summary, code=code, retryable=code == "provider_unavailable")
        self.fallback_eligible = fallback_eligible


class ModelRouter:
    def __init__(self, profiles: Iterable[WorkerProfile | dict[str, Any]]):
        self.profiles: dict[str, WorkerProfile] = {}
        self.ignored: list[str] = []
        for raw in profiles:
            try:
                profile = raw if isinstance(raw, WorkerProfile) else WorkerProfile.model_validate(raw)
            except ValidationError as e:
                worker = raw.get("worker_id", "?") if isinstance(raw, dict) else "?"
                message = f"ignored malformed worker profile {worker} ({e.error_count()} errors)"
                self.ignored.append(message)
                log.warning(message)
                continue
            self.profiles[profile.worker_id] = profile

    def profile(self, worker_id: str) -> WorkerProfile | None:
        return self.profiles.get(worker_id)

    def capabilities(self) -> set[str]:
        return set().union(*(p.capabilities for p in self.profiles.values())) if self.profiles else set()

    def route(self, request: ModelWorkRequest) -> ModelRoute:
        need = request.capability
        c = request.constraints
        capable = [
            p for p in self.profiles.values()
            if need <= p.capabilities
            and p.limits.context_window >= request.input_shape.estimated_tokens
            and (c.max_cost_class is None or _COST_RANK[p.cost_class] <= _COST_RANK[c.max_cost_class])
            and (c.max_latency_class is None or _LATENCY_RANK[p.latency_class] <= _LATENCY_RANK[c.max_latency_class])
        ]
        if not capable:
            raise RouteError(f"no worker supports {', '.join(sorted(need))} within the constraints", code="no_route")

        policy = request.policy
        permitted = [
            p for p in capable
            if (policy.allowed_providers is None or p.provider_id in policy.allowed_providers)
            and p.provider_id not in policy.denied_providers
            and not (p.policy_tags & policy.denied_tags)
        ]
        if not permitted:
            raise RouteError("every capable worker is excluded by policy", code="route_denied")

        if policy.strategy == "fastest":
            key = lambda p: (_LATENCY_RANK[p.latency_class], _COST_RANK[p.cost_class], p.worker_id)  # noqa: E731
        else:
            key = lambda p: (_COST_RANK[p.cost_class], _LATENCY_RANK[p.latency_class], p.worker_id)  # noqa: E731
        ranked = sorted(permitted, key=key)
        available = [p for p in ranked if p.availability != "unavailable"]
        if not available:
            raise RouteError("every compatible worker is unavailable", code="provider_unavailable")

        selected = available[0]
        rationale = (
            f"Selected {selected.worker_id}: supports {', '.join(sorted(need))}; "
            f"{selected.cost_class} cost, {selected.latency_class} latency ({policy.strategy} strategy)."
        )
        if ranked[0] is not selected:
            rationale += f" Preferred {ranked[0].worker_id} is unavailable; using fallback."
        return ModelRoute(
            worker_id=selected.worker_id,
            provider_adapter_id=selected.provider_id,
            rationale=rationale,
            fallback_worker_ids=[p.worker_id for p in available[1:]],
            policy_tags=sorted(selected.policy_tags),
        )
