"""Spec 005 - Tool System acceptance criteria."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from galliani.errors import ContractError
from galliani.permissions import ApprovalRecord, PermissionLevel
from galliani.tools import SideEffect, ToolCall, ToolDefinition, ToolRegistry, ToolStatus, ToolSystem


class PathIn(BaseModel):
    path: str


class TextOut(BaseModel):
    text: str


class DeletedOut(BaseModel):
    deleted: bool


def build(handler_calls: list[str]) -> ToolSystem:
    def read(args: PathIn) -> dict:
        handler_calls.append("read")
        return {"text": f"contents of {args.path}"}

    def delete(args: PathIn) -> dict:
        handler_calls.append("delete")
        return {"deleted": True}

    async def slow(args: PathIn) -> dict:
        await asyncio.sleep(1)
        return {"text": "late"}

    def crash(args: PathIn) -> dict:
        raise RuntimeError("internal path /etc/secret leaked")

    def bad_output(args: PathIn) -> dict:
        return {"wrong": 1}

    common = dict(input_schema=PathIn, resource_field="path")
    return ToolSystem(ToolRegistry([
        ToolDefinition(name="read_file", description="read", output_schema=TextOut, handler=read,
                       permission_level=PermissionLevel.read_only, side_effects=[SideEffect.read], **common),
        ToolDefinition(name="delete_file", description="delete", output_schema=DeletedOut, handler=delete,
                       permission_level=PermissionLevel.destructive, side_effects=[SideEffect.delete], **common),
        ToolDefinition(name="slow", description="slow", output_schema=TextOut, handler=slow, timeout_ms=20,
                       permission_level=PermissionLevel.read_only, side_effects=[SideEffect.read], **common),
        ToolDefinition(name="crash", description="crash", output_schema=TextOut, handler=crash,
                       permission_level=PermissionLevel.read_only, side_effects=[SideEffect.read], **common),
        ToolDefinition(name="bad_output", description="bad", output_schema=TextOut, handler=bad_output,
                       permission_level=PermissionLevel.read_only, side_effects=[SideEffect.read], **common),
    ]))


def call(name: str, **arguments) -> ToolCall:
    return ToolCall(tool_name=name, call_id=f"{name}-1", arguments=arguments, requested_by_step="s1")


def test_registry_lookup_and_duplicates():
    system = build([])
    assert "read_file" in system.registry.names()
    assert system.registry.get("missing") is None
    with pytest.raises(ContractError):
        system.registry.register(system.registry.get("read_file"))


# AC: Schema Validation
async def test_invalid_arguments_prevent_execution():
    calls: list[str] = []
    result = await build(calls).execute(call("read_file", nope=1), task_id="t")
    assert result.status is ToolStatus.failed and result.error.code == "invalid_arguments"
    assert calls == []


# AC: Permission Required
async def test_destructive_tool_without_approval_blocks_and_does_not_run():
    calls: list[str] = []
    result = await build(calls).execute(call("delete_file", path="notes/a.txt"), task_id="t")
    assert result.status is ToolStatus.blocked and result.error.code == "permission_required"
    assert result.permission_request.scope == "notes/a.txt"
    assert calls == []


async def test_destructive_tool_with_approval_runs():
    calls: list[str] = []
    approval = ApprovalRecord(user_id="u", action="delete_file", scope="notes/a.txt")
    result = await build(calls).execute(call("delete_file", path="notes/a.txt"), task_id="t", approvals=[approval])
    assert result.status is ToolStatus.succeeded and calls == ["delete"]


# AC: Tool Success
async def test_valid_call_produces_structured_result():
    result = await build([]).execute(call("read_file", path="a.txt"), task_id="t")
    assert result.status is ToolStatus.succeeded
    assert result.data == {"text": "contents of a.txt"}
    assert result.observation_summary == "read_file succeeded"


async def test_timeout_is_retryable_by_policy():
    result = await build([]).execute(call("slow", path="a"), task_id="t")
    assert result.status is ToolStatus.timed_out
    assert result.error.code == "timeout" and result.error.retryable


async def test_crash_is_normalized_without_internals():
    result = await build([]).execute(call("crash", path="a"), task_id="t")
    assert result.error.code == "tool_crashed"
    assert "/etc/secret" not in result.model_dump_json()


async def test_output_schema_violation_is_an_error():
    result = await build([]).execute(call("bad_output", path="a"), task_id="t")
    assert result.error.code == "invalid_output"


async def test_unknown_tool():
    result = await build([]).execute(call("nope"), task_id="t")
    assert result.error.code == "unknown_tool"
