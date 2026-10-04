"""The `remember` tool: the only way an agent can write durable memory (spec 010, Decision 0019).

It is a `sensitive` action, so the permission system always asks the user first, and the approval prompt
shows the exact text to be saved. Provenance names the task and step. Secret-like text is refused.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from galliani.contracts import Sensitivity
from galliani.errors import ContractError
from galliani.memory import (
    MAX_CONTENT,
    USER_SCOPE,
    MemoryDecisionStatus,
    MemoryPolicy,
    MemoryStore,
    MemoryType,
    MemoryWriteRequest,
)
from galliani.permissions import PermissionLevel
from galliani.tools import SideEffect, ToolContext, ToolDefinition, ToolInputRejected


class RememberIn(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_CONTENT)
    type: MemoryType = "preference"
    scope: Literal["user", "project"] = "user"  # "project": only tasks in this folder


class RememberOut(BaseModel):
    id: str
    content: str
    type: str
    scope: str
    provenance: str
    sensitivity: Sensitivity


def remember_tool(store: MemoryStore, *, project_scope: str | None = None,
                  policy: MemoryPolicy | None = None) -> ToolDefinition:
    policy = policy or MemoryPolicy()

    def handler(args: RememberIn, context: ToolContext) -> dict:
        scope = project_scope if args.scope == "project" and project_scope else USER_SCOPE
        request = MemoryWriteRequest(
            content=args.content, type=args.type, scope=scope, source="agent",
            provenance=f"task {context.task_id}, step {context.step_id}, approved by the user",
            reason_summary="the user asked to remember this",
        )
        decision = policy.evaluate(request)
        if decision.status is MemoryDecisionStatus.denied:
            raise ToolInputRejected(f"not saved: {decision.reason}")
        try:
            record = store.write(request)
        except ContractError as e:
            raise ToolInputRejected(f"not saved: {e.safe_summary}") from None
        return {"id": record.id, "content": record.display_content(), "type": record.type, "scope": record.scope,
                "provenance": record.provenance, "sensitivity": record.sensitivity}

    return ToolDefinition(
        name="remember",
        description=("Save a short note to the user's long-term memory so future tasks can use it. Use only when "
                     "the user explicitly asks you to remember something. The user must approve each save."),
        input_schema=RememberIn,
        output_schema=RememberOut,
        permission_level=PermissionLevel.sensitive,
        side_effects=[SideEffect.write],
        handler=handler,
        resource_field="scope",
        describe=lambda args: f'Save to memory ({args.scope}): "{args.content}"',
    )
