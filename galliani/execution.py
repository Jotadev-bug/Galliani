"""Spec 006 - Execution Engine: run exactly one plan step through the router or the tool system.

The engine owns no planning, routing or verification policy. It dispatches by step kind, walks the
route's fallback candidates on fallback-eligible provider errors, and returns an `ExecutionResult`
with an observation for every attempted action. Worker and tool output is untrusted data.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from galliani.adapters import AdapterError, ProviderAdapter, WorkerRequest
from galliani.contracts import Sensitivity, new_id
from galliani.observability import EventType, Observability
from galliani.permissions import PermissionDecision, PermissionRequest
from galliani.planner import PlanStep, StepKind
from galliani.router import InputShape, ModelRoute, ModelRouter, ModelWorkRequest, RouteError, RoutingPolicy
from galliani.state import ObservationRecord, TaskState
from galliani.tools import ToolCall, ToolStatus, ToolSystem


class ExecutionStatus(str, Enum):
    succeeded = "succeeded"
    failed = "failed"
    blocked = "blocked"
    canceled = "canceled"
    timed_out = "timed_out"


class ArtifactRef(BaseModel):
    artifact_id: str = Field(default_factory=lambda: new_id("art"))
    kind: str
    uri: str
    sensitivity: Sensitivity = Sensitivity.internal
    produced_by: str


class StepError(BaseModel):
    code: str
    retryable: bool
    safe_summary: str


class ExecutionLimits(BaseModel):
    remaining_actions: int


class ExecutionRequest(BaseModel):
    task_id: str
    plan_id: str
    step: PlanStep
    state_snapshot: TaskState
    limits: ExecutionLimits
    routing_policy: RoutingPolicy = Field(default_factory=RoutingPolicy)


class ExecutionResult(BaseModel):
    step_id: str
    status: ExecutionStatus
    output: Any = None
    output_ref: str | None = None
    observation: ObservationRecord
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    error: StepError | None = None
    route: ModelRoute | None = None
    worker_id: str | None = None
    attempted_workers: list[str] = Field(default_factory=list)
    permission: PermissionDecision | None = None
    permission_request: PermissionRequest | None = None


class _MissingInput(Exception):
    pass


def _resolve_refs(value: Any, state: TaskState) -> Any:
    """Replace ``{"$ref": "step_id"}`` or ``{"$ref": "step_id.field"}`` with an earlier step's output."""
    if isinstance(value, dict):
        if set(value) == {"$ref"}:
            step_id, _, field = str(value["$ref"]).partition(".")
            ref = state.latest_output_ref(step_id)
            if ref is None or ref not in state.outputs:
                raise _MissingInput(step_id)
            out = state.outputs[ref]
            if field:
                if not isinstance(out, dict) or field not in out:
                    raise _MissingInput(f"{step_id}.{field}")
                out = out[field]
            return out
        return {k: _resolve_refs(v, state) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_refs(v, state) for v in value]
    return value


class ExecutionEngine:
    def __init__(
        self,
        router: ModelRouter,
        adapters: Mapping[str, ProviderAdapter] | Iterable[ProviderAdapter],
        tools: ToolSystem,
        observability: Observability,
    ):
        self.router = router
        self.adapters = dict(adapters) if isinstance(adapters, Mapping) else {a.adapter_id: a for a in adapters}
        self.tools = tools
        self.obs = observability

    async def execute(self, request: ExecutionRequest, *, is_canceled: Callable[[], bool] = lambda: False) -> ExecutionResult:
        step = request.step
        state = request.state_snapshot
        output_ref = f"out:{step.step_id}:{state.action_count + 1}"
        if is_canceled() or state.status.value == "canceled":
            return self._result(step, ExecutionStatus.canceled, "supervisor", "canceled before start; no action taken",
                                error=StepError(code="canceled", retryable=False, safe_summary="task canceled"))
        if request.limits.remaining_actions <= 0:
            return self._result(step, ExecutionStatus.failed, "supervisor", "action budget exhausted; not started",
                                error=StepError(code="budget_exhausted", retryable=False,
                                                safe_summary="action budget exhausted"))
        if step.kind is StepKind.model:
            return await self._model_step(request, output_ref, is_canceled)
        return await self._tool_step(request, output_ref)

    async def _model_step(self, request: ExecutionRequest, output_ref: str, is_canceled: Callable[[], bool]) -> ExecutionResult:
        step, state = request.step, request.state_snapshot
        try:
            inputs = {ref: _resolve_refs({"$ref": ref}, state) for ref in step.input_refs}
        except _MissingInput as e:
            return self._result(step, ExecutionStatus.failed, "supervisor", f"input {e} is missing",
                                error=StepError(code="missing_input", retryable=False, safe_summary=f"input {e} is missing"))
        work = ModelWorkRequest(
            task_id=request.task_id, step_id=step.step_id, capability={step.required_capability},
            input_shape=InputShape(estimated_tokens=(len(step.instruction) + len(str(inputs))) // 4),
            policy=request.routing_policy,
        )
        try:
            route = self.router.route(work)
        except RouteError as e:
            self.obs.emit(EventType.route_failed, request.task_id, e.safe_summary, plan_id=request.plan_id,
                          step_id=step.step_id, metadata={"code": e.code})
            return self._result(step, ExecutionStatus.failed, "router", e.safe_summary,
                                error=StepError(code=e.code, retryable=e.retryable, safe_summary=e.safe_summary))
        self.obs.emit(EventType.route_selected, request.task_id, route.rationale, plan_id=request.plan_id,
                      step_id=step.step_id, metadata={"worker_id": route.worker_id, "adapter": route.provider_adapter_id,
                                                      "fallbacks": route.fallback_worker_ids})

        attempted: list[str] = []
        last_error: AdapterError | None = None
        for worker_id in [route.worker_id, *route.fallback_worker_ids]:
            if is_canceled():
                return self._result(step, ExecutionStatus.canceled, "supervisor", "canceled; no further workers started",
                                    route=route, attempted_workers=attempted,
                                    error=StepError(code="canceled", retryable=False, safe_summary="task canceled"))
            profile = self.router.profile(worker_id)
            adapter = self.adapters.get(profile.provider_id) if profile else None
            if attempted:
                self.obs.emit(EventType.route_fallback, request.task_id,
                              f"falling back to {worker_id} after {attempted[-1]} failed ({last_error.code})",
                              plan_id=request.plan_id, step_id=step.step_id,
                              metadata={"from": attempted[-1], "to": worker_id, "reason": last_error.code})
            attempted.append(worker_id)
            if adapter is None:
                last_error = AdapterError(f"no adapter for {worker_id}", code="provider_unavailable")
                continue
            try:
                response = await adapter.invoke(WorkerRequest(
                    task_id=request.task_id, step_id=step.step_id, worker_id=worker_id,
                    instruction=step.instruction, inputs=inputs,
                    max_output_tokens=profile.limits.max_output_tokens,
                ))
            except AdapterError as e:
                last_error = e
                if not e.fallback_eligible:
                    break
                continue
            output = response.structured if response.structured is not None else response.output
            return self._result(step, ExecutionStatus.succeeded, f"worker:{worker_id}",
                                f"{worker_id} produced {step.expected_output}", output=output, output_ref=output_ref,
                                route=route, worker_id=worker_id, attempted_workers=attempted)

        assert last_error is not None
        status = ExecutionStatus.timed_out if last_error.code == "timeout" else ExecutionStatus.failed
        summary = f"all {len(attempted)} worker(s) failed; last error {last_error.code}"
        return self._result(step, status, f"worker:{attempted[-1]}", summary, route=route, attempted_workers=attempted,
                            error=StepError(code=last_error.code, retryable=last_error.retryable, safe_summary=summary))

    async def _tool_step(self, request: ExecutionRequest, output_ref: str) -> ExecutionResult:
        step, state = request.step, request.state_snapshot
        assert step.tool is not None
        try:
            arguments = _resolve_refs(step.tool.arguments, state)
        except _MissingInput as e:
            return self._result(step, ExecutionStatus.failed, f"tool:{step.tool.tool_name}", f"input {e} is missing",
                                error=StepError(code="missing_input", retryable=False, safe_summary=f"input {e} is missing"))
        call = ToolCall(tool_name=step.tool.tool_name, call_id=new_id("call"), arguments=arguments,
                        idempotency_key=f"{request.task_id}:{step.step_id}:{state.action_count + 1}",
                        requested_by_step=step.step_id)
        result = await self.tools.execute(call, task_id=request.task_id, approvals=state.approvals,
                                          reason_summary=step.purpose)
        if result.permission is not None:
            self.obs.emit(EventType.permission_decided, request.task_id, result.permission.audit_summary,
                          plan_id=request.plan_id, step_id=step.step_id, call_id=call.call_id,
                          metadata={"status": result.permission.status.value, "scope": result.permission.scope})
        self.obs.emit(EventType.tool_called, request.task_id, result.observation_summary, plan_id=request.plan_id,
                      step_id=step.step_id, call_id=call.call_id,
                      metadata={"tool": call.tool_name, "status": result.status.value, "arguments": call.arguments,
                                "error": result.error.code if result.error else None})
        tool = self.tools.registry.get(call.tool_name)
        sensitivity = tool.sensitivity if tool else Sensitivity.internal
        status = {
            ToolStatus.succeeded: ExecutionStatus.succeeded,
            ToolStatus.failed: ExecutionStatus.failed,
            ToolStatus.blocked: ExecutionStatus.blocked,
            ToolStatus.timed_out: ExecutionStatus.timed_out,
        }[result.status]
        error = (StepError(code=result.error.code, retryable=result.error.retryable, safe_summary=result.error.safe_summary)
                 if result.error else None)
        artifacts = [ArtifactRef(kind=a.get("kind", "file"), uri=a["uri"], produced_by=call.call_id, sensitivity=sensitivity)
                     for a in result.artifacts if "uri" in a]
        succeeded = status is ExecutionStatus.succeeded
        return self._result(
            step, status, f"tool:{call.tool_name}", result.observation_summary,
            output=result.data if succeeded else None, output_ref=output_ref if succeeded else None,
            error=error, artifacts=artifacts, permission=result.permission,
            permission_request=result.permission_request, sensitivity=sensitivity,
        )

    @staticmethod
    def _result(step: PlanStep, status: ExecutionStatus, source: str, summary: str, *,
                sensitivity: Sensitivity = Sensitivity.internal, output_ref: str | None = None, **kw: Any) -> ExecutionResult:
        observation = ObservationRecord(source=source, step_id=step.step_id, kind="execution", outcome=status.value,
                                        summary=summary, data_ref=output_ref, sensitivity=sensitivity)
        return ExecutionResult(step_id=step.step_id, status=status, observation=observation, output_ref=output_ref, **kw)
