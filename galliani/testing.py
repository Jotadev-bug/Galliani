"""Deterministic test doubles (000 vocabulary: ScriptedAdapter). Their outputs are SIMULATED.

Two adapters with deliberately different native response shapes demonstrate that providers can be
swapped without changing supervisor behavior (PROJECT.md success criteria). Both emit hidden-reasoning
fields that normalization must discard.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from galliani.adapters import AdapterError, ProviderAdapter, WorkerRequest, WorkerResponse
from galliani.contracts import Sensitivity
from galliani.permissions import PermissionLevel
from galliani.tools import SideEffect, ToolDefinition, ToolRegistry

# Each script entry is one call: {"output": str, "structured": dict?, "reasoning": str?} or {"error": code}.
Script = dict[str, list[dict[str, Any]]]


class _Scripted(ProviderAdapter):
    def __init__(self, adapter_id: str, script: Script, default_output: str = "ok"):
        self.adapter_id = adapter_id
        self.script = {worker: list(entries) for worker, entries in script.items()}
        self.default_output = default_output
        self.calls: list[WorkerRequest] = []

    def _entry(self, request: WorkerRequest) -> dict[str, Any]:
        self.calls.append(request)
        entries = self.script.get(request.worker_id)
        entry = entries.pop(0) if entries else {"output": self.default_output}
        if "error" in entry:
            raise AdapterError(f"{request.worker_id} failed: {entry['error']}", code=str(entry["error"]))
        return entry


class ScriptedAdapter(_Scripted):
    """Native shape: {"text": ..., "json": ..., "reasoning": ..., "usage": {...}}."""

    async def send(self, request: WorkerRequest) -> dict[str, Any]:
        entry = self._entry(request)
        return {
            "text": entry.get("output", ""),
            "json": entry.get("structured"),
            "reasoning": entry.get("reasoning", "simulated private reasoning"),
            "usage": {"input_tokens": len(request.instruction) // 4, "output_tokens": 8},
        }

    def normalize(self, raw: dict[str, Any]) -> WorkerResponse:
        return WorkerResponse(output=raw["text"], structured=raw.get("json"), usage=raw.get("usage", {}),
                              finish_reason="stop")


class ScriptedChatAdapter(_Scripted):
    """Native shape mimicking chat-completion APIs, with `reasoning_content` on the message."""

    async def send(self, request: WorkerRequest) -> dict[str, Any]:
        entry = self._entry(request)
        return {
            "choices": [{
                "message": {"content": entry.get("output", ""),
                            "reasoning_content": entry.get("reasoning", "simulated private reasoning")},
                "finish_reason": "stop",
                "parsed": entry.get("structured"),
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8},
        }

    def normalize(self, raw: dict[str, Any]) -> WorkerResponse:
        choice = raw["choices"][0]
        usage = raw.get("usage", {})
        return WorkerResponse(
            output=choice["message"]["content"],
            structured=choice.get("parsed"),
            usage={"input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)},
            finish_reason=choice.get("finish_reason"),
        )


# --------------------------------------------------------------------------- fixture tools


class NoteIn(BaseModel):
    note_id: str


class TextOut(BaseModel):
    text: str


class WriteIn(BaseModel):
    path: str
    content: str


class WriteOut(BaseModel):
    path: str
    bytes: int


class PathIn(BaseModel):
    path: str


class DeleteOut(BaseModel):
    deleted: bool


class FetchIn(BaseModel):
    url: str


@dataclass
class FixtureWorld:
    """In-memory world the fixture tools act on. `executed` records every handler that actually ran."""

    notes: dict[str, str] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)
    pages: dict[str, str] = field(default_factory=dict)
    flaky_timeouts: int = 0  # how many fetch_page calls time out before one succeeds
    executed: list[str] = field(default_factory=list)


def fixture_tool_registry(world: FixtureWorld) -> ToolRegistry:
    def read_note(args: NoteIn) -> dict:
        world.executed.append("read_note")
        if args.note_id not in world.notes:
            raise KeyError(args.note_id)
        return {"text": world.notes[args.note_id]}

    def write_file(args: WriteIn) -> dict:
        world.executed.append("write_file")
        world.files[args.path] = args.content
        return {"path": args.path, "bytes": len(args.content)}

    def delete_file(args: PathIn) -> dict:
        world.executed.append("delete_file")
        return {"deleted": world.files.pop(args.path, None) is not None}

    async def fetch_page(args: FetchIn) -> dict:
        world.executed.append("fetch_page")
        if world.flaky_timeouts > 0:
            world.flaky_timeouts -= 1
            await asyncio.sleep(5)
        return {"text": world.pages.get(args.url, "")}

    return ToolRegistry([
        ToolDefinition(name="read_note", description="Read a note by id.", input_schema=NoteIn, output_schema=TextOut,
                       permission_level=PermissionLevel.read_only, side_effects=[SideEffect.read], handler=read_note,
                       resource_field="note_id", idempotent=True),
        ToolDefinition(name="write_file", description="Write a file.", input_schema=WriteIn, output_schema=WriteOut,
                       permission_level=PermissionLevel.write, side_effects=[SideEffect.write], handler=write_file,
                       resource_field="path"),
        ToolDefinition(name="delete_file", description="Delete a file.", input_schema=PathIn, output_schema=DeleteOut,
                       permission_level=PermissionLevel.destructive, side_effects=[SideEffect.delete],
                       handler=delete_file, resource_field="path"),
        ToolDefinition(name="fetch_page", description="Fetch a page.", input_schema=FetchIn, output_schema=TextOut,
                       permission_level=PermissionLevel.read_only, side_effects=[SideEffect.network],
                       handler=fetch_page, resource_field="url", timeout_ms=50, idempotent=True,
                       sensitivity=Sensitivity.internal),
    ])
