"""Shared Agent Worker invocation: route, invoke, and walk fallbacks (003 R4).

Used by the execution engine for model steps and by model-backed supervisor components (planner,
semantic verifier). Emits route events; returns a structured outcome instead of raising.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from pydantic import BaseModel, Field

from galliani.adapters import AdapterError, ProviderAdapter, WorkerRequest, WorkerResponse
from galliani.observability import EventType, Observability
from galliani.router import InputShape, ModelRoute, ModelRouter, ModelWorkRequest, RouteError, RoutingPolicy


class WorkerFailure(BaseModel):
    code: str
    retryable: bool
    safe_summary: str


class WorkerCall(BaseModel):
    response: WorkerResponse | None = None
    route: ModelRoute | None = None
    worker_id: str | None = None
    attempted: list[str] = Field(default_factory=list)
    failure: WorkerFailure | None = None

    @property
    def ok(self) -> bool:
        return self.response is not None


class WorkerClient:
    def __init__(self, router: ModelRouter, adapters: Mapping[str, ProviderAdapter] | Iterable[ProviderAdapter],
                 observability: Observability):
        self.router = router
        self.adapters = dict(adapters) if isinstance(adapters, Mapping) else {a.adapter_id: a for a in adapters}
        self.obs = observability

    async def run(
        self,
        *,
        task_id: str,
        step_id: str,
        capability: set[str],
        instruction: str,
        inputs: dict[str, Any] | None = None,
        policy: RoutingPolicy | None = None,
        plan_id: str | None = None,
        is_canceled: Callable[[], bool] = lambda: False,
    ) -> WorkerCall:
        inputs = inputs or {}
        work = ModelWorkRequest(
            task_id=task_id, step_id=step_id, capability=capability,
            input_shape=InputShape(estimated_tokens=(len(instruction) + len(str(inputs))) // 4),
            policy=policy or RoutingPolicy(),
        )
        try:
            route = self.router.route(work)
        except RouteError as e:
            self.obs.emit(EventType.route_failed, task_id, e.safe_summary, plan_id=plan_id, step_id=step_id,
                          metadata={"code": e.code})
            return WorkerCall(failure=WorkerFailure(code=e.code, retryable=e.retryable, safe_summary=e.safe_summary))
        self.obs.emit(EventType.route_selected, task_id, route.rationale, plan_id=plan_id, step_id=step_id,
                      metadata={"worker_id": route.worker_id, "adapter": route.provider_adapter_id,
                                "fallbacks": route.fallback_worker_ids})

        attempted: list[str] = []
        last: AdapterError | None = None
        for worker_id in [route.worker_id, *route.fallback_worker_ids]:
            if is_canceled():
                return WorkerCall(route=route, attempted=attempted, failure=WorkerFailure(
                    code="canceled", retryable=False, safe_summary="task canceled"))
            if attempted and last is not None:
                self.obs.emit(EventType.route_fallback, task_id,
                              f"falling back to {worker_id} after {attempted[-1]} failed ({last.code})",
                              plan_id=plan_id, step_id=step_id,
                              metadata={"from": attempted[-1], "to": worker_id, "reason": last.code})
            attempted.append(worker_id)
            profile = self.router.profile(worker_id)
            adapter = self.adapters.get(profile.provider_id) if profile else None
            if adapter is None or profile is None:
                last = AdapterError(f"no adapter for {worker_id}", code="provider_unavailable")
                continue
            try:
                response = await adapter.invoke(WorkerRequest(
                    task_id=task_id, step_id=step_id, worker_id=worker_id, instruction=instruction, inputs=inputs,
                    max_output_tokens=profile.limits.max_output_tokens,
                ))
            except AdapterError as e:
                last = e
                if not e.fallback_eligible:
                    break
                continue
            self.obs.emit(EventType.worker_completed, task_id, f"{worker_id} completed", plan_id=plan_id,
                          step_id=step_id, metadata={"worker_id": worker_id, "usage": response.usage})
            return WorkerCall(response=response, route=route, worker_id=worker_id, attempted=attempted)

        assert last is not None
        return WorkerCall(route=route, attempted=attempted, failure=WorkerFailure(
            code=last.code, retryable=last.retryable,
            safe_summary=f"all {len(attempted)} worker(s) failed; last error {last.code}",
        ))
