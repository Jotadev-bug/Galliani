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

from galliani.adapters import ProviderAdapter
from galliani.contracts import Sensitivity, new_id
from galliani.observability import EventType, Observability
from galliani.permissions import PermissionDecision, PermissionRequest
from galliani.planner import PlanStep, StepKind
from galliani.router import ModelRoute, ModelRouter, RoutingPolicy
from galliani.state import ObservationRecord, TaskState
from galliani.tools import ToolCall, ToolStatus, ToolSystem
from galliani.workers import WorkerClient


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


def _describe(value: Any) -> str:
    if isinstance(value, dict):
        return f"an object with fields {sorted(map(str, value))[:10]}"
    if isinstance(value, list):
        return f"a list of {len(value)} item(s)"
    return f"a {type(value).__name__}"


def _resolve_refs(value: Any, state: TaskState) -> Any:
    """Replace ``{"$ref": "step_id"}`` or ``{"$ref": "step_id.path"}`` with an earlier step's output.

    The path is dotted; numeric parts index into lists (``s1.files.0``). A failed lookup names what the
    output actually contains (field names or list length only), so replanning gets usable evidence.
    """
    if isinstance(value, dict):
        if set(value) == {"$ref"}:
            step_id, *path = str(value["$ref"]).split(".")
            ref = state.latest_output_ref(step_id)
            if ref is None or ref not in state.outputs:
                raise _MissingInput(f"reference {value['$ref']}: step {step_id} has no successful output")
            out = state.outputs[ref]
            walked = step_id
            for part in path:
                if isinstance(out, dict) and part in out:
                    out = out[part]
                elif isinstance(out, list) and part.lstrip("-").isdigit() and -len(out) <= int(part) < len(out):
                    out = out[int(part)]
                else:
                    raise _MissingInput(f"reference {value['$ref']}: {walked} is {_describe(out)}, no '{part}'")
                walked += f".{part}"
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
        self.workers = WorkerClient(router, adapters, observability)
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
            return self._result(step, ExecutionStatus.failed, "supervisor", str(e),
                                error=StepError(code="missing_input", retryable=False, safe_summary=str(e)))
        call = await self.workers.run(
            task_id=request.task_id, step_id=step.step_id, capability={step.required_capability},
            instruction=step.instruction, inputs=inputs, policy=request.routing_policy, plan_id=request.plan_id,
            is_canceled=is_canceled,
        )
        if call.ok:
            response = call.response
            output = response.structured if response.structured is not None else response.output
            return self._result(step, ExecutionStatus.succeeded, f"worker:{call.worker_id}",
                                f"{call.worker_id} produced {step.expected_output}", output=output, output_ref=output_ref,
                                route=call.route, worker_id=call.worker_id, attempted_workers=call.attempted)
        failure = call.failure
        assert failure is not None
        status = {"canceled": ExecutionStatus.canceled, "timeout": ExecutionStatus.timed_out}.get(
            failure.code, ExecutionStatus.failed)
        source = f"worker:{call.attempted[-1]}" if call.attempted else "router"
        return self._result(step, status, source, failure.safe_summary, route=call.route,
                            attempted_workers=call.attempted,
                            error=StepError(code=failure.code, retryable=failure.retryable,
                                            safe_summary=failure.safe_summary))

    async def _tool_step(self, request: ExecutionRequest, output_ref: str) -> ExecutionResult:
        step, state = request.step, request.state_snapshot
        assert step.tool is not None
        try:
            arguments = _resolve_refs(step.tool.arguments, state)
        except _MissingInput as e:
            return self._result(step, ExecutionStatus.failed, f"tool:{step.tool.tool_name}", str(e),
                                error=StepError(code="missing_input", retryable=False, safe_summary=str(e)))
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
