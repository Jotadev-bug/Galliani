"""Spec 005 - Tool System: registered capabilities with schemas, permission metadata and normalized results.

Order for every call (Decision 0010): lookup -> input validation -> permission check -> execute with
timeout -> output validation -> normalized `ToolResult`. A tool never runs unless validation and
permission both pass. Tool output is untrusted data until the supervisor verifies it.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Iterable
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from galliani.contracts import Sensitivity
from galliani.errors import ContractError
from galliani.permissions import (
    ApprovalRecord,
    PermissionDecision,
    PermissionLevel,
    PermissionPolicy,
    PermissionRequest,
    PermissionStatus,
)

ToolHandler = Callable[[BaseModel], Any | Awaitable[Any]]


class ToolInputRejected(Exception):
    """Raised by a handler to refuse a request; the message must be safe to show (no internals)."""


class SideEffect(str, Enum):
    none = "none"
    read = "read"
    write = "write"
    delete = "delete"
    network = "network"
    cost = "cost"


class ToolDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    permission_level: PermissionLevel
    side_effects: list[SideEffect]
    timeout_ms: int = Field(default=5_000, gt=0)
    retryable_on_timeout: bool = True
    idempotent: bool = False
    resource_field: str | None = None  # argument naming the resource; it also becomes the permission scope
    artifact_field: str | None = None  # output field naming a file the call produced (reported as an artifact)
    sensitivity: Sensitivity = Sensitivity.internal
    handler: ToolHandler = Field(exclude=True)


class ToolCall(BaseModel):
    tool_name: str
    call_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    requested_by_step: str


class ToolStatus(str, Enum):
    succeeded = "succeeded"
    failed = "failed"
    blocked = "blocked"
    timed_out = "timed_out"


class ToolError(BaseModel):
    code: str
    message: str
    retryable: bool
    safe_summary: str


class ToolResult(BaseModel):
    call_id: str
    status: ToolStatus
    data: dict[str, Any] | None = None
    error: ToolError | None = None
    observation_summary: str
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    permission: PermissionDecision | None = None
    permission_request: PermissionRequest | None = None


class ToolRegistry:
    def __init__(self, tools: Iterable[ToolDefinition] = ()):
        self._tools: dict[str, ToolDefinition] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: ToolDefinition) -> None:
        if not tool.name or not tool.name.replace("_", "").isalnum():
            raise ContractError(f"invalid tool name {tool.name!r}")
        if tool.name in self._tools:
            raise ContractError(f"tool {tool.name} is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)


def _fail(call: ToolCall, code: str, summary: str, *, retryable: bool = False,
          status: ToolStatus = ToolStatus.failed, **extra: Any) -> ToolResult:
    return ToolResult(
        call_id=call.call_id,
        status=status,
        error=ToolError(code=code, message=summary, retryable=retryable, safe_summary=summary),
        observation_summary=f"{call.tool_name}: {summary}",
        **extra,
    )


class ToolSystem:
    def __init__(self, registry: ToolRegistry, policy: PermissionPolicy | None = None):
        self.registry = registry
        self.policy = policy or PermissionPolicy()

    async def execute(
        self, call: ToolCall, *, task_id: str, approvals: Iterable[ApprovalRecord] = (), reason_summary: str = ""
    ) -> ToolResult:
        tool = self.registry.get(call.tool_name)
        if tool is None:
            return _fail(call, "unknown_tool", f"tool {call.tool_name} is not registered")

        try:
            args = tool.input_schema.model_validate(call.arguments)
        except ValidationError as e:
            # Field names and validator messages only; input values are never echoed back.
            problems = sorted({f"{'.'.join(str(p) for p in err['loc']) or 'arguments'}: "
                               f"{str(err['msg']).removeprefix('Value error, ')[:120]}" for err in e.errors()})
            return _fail(call, "invalid_arguments", f"invalid arguments ({'; '.join(problems[:3])}); tool not run")

        resource = str(getattr(args, tool.resource_field)) if tool.resource_field else tool.name
        request = PermissionRequest(
            task_id=task_id,
            action=tool.name,
            resource=resource,
            scope=resource,
            risk_level=tool.permission_level,
            reason_summary=reason_summary or f"step {call.requested_by_step} requests {tool.name}",
        )
        decision = self.policy.evaluate(request, approvals)
        if decision.status is not PermissionStatus.allowed:
            code = "permission_required" if decision.status is PermissionStatus.needs_user else "permission_denied"
            return _fail(call, code, decision.audit_summary, status=ToolStatus.blocked,
                         permission=decision, permission_request=request)

        try:
            output = await asyncio.wait_for(self._invoke(tool, args), timeout=tool.timeout_ms / 1000)
        except asyncio.TimeoutError:
            return _fail(call, "timeout", f"timed out after {tool.timeout_ms} ms",
                         retryable=tool.retryable_on_timeout, status=ToolStatus.timed_out, permission=decision)
        except ToolInputRejected as e:
            return _fail(call, "rejected_input", str(e)[:200], permission=decision)
        except Exception as e:  # noqa: BLE001 - crashes are normalized without internals
            return _fail(call, "tool_crashed", f"tool crashed ({type(e).__name__})", permission=decision)

        try:
            data = tool.output_schema.model_validate(output).model_dump(mode="json")
        except ValidationError:
            return _fail(call, "invalid_output", "tool returned output that does not match its schema",
                         permission=decision)
        artifacts = ([{"kind": "file", "uri": str(data[tool.artifact_field])}]
                     if tool.artifact_field and data.get(tool.artifact_field) else [])
        return ToolResult(
            call_id=call.call_id,
            status=ToolStatus.succeeded,
            data=data,
            artifacts=artifacts,
            observation_summary=f"{tool.name} succeeded",
            metadata={"side_effects": [s.value for s in tool.side_effects], "resource": resource},
            permission=decision,
        )

    @staticmethod
    async def _invoke(tool: ToolDefinition, args: BaseModel) -> Any:
        if inspect.iscoroutinefunction(tool.handler):
            return await tool.handler(args)
        result = await asyncio.to_thread(tool.handler, args)
        if inspect.isawaitable(result):
            result = await result
        return result
