"""Workspace toolkit (spec 005 tools with 009 permission levels): file access confined to one directory.

- Paths are normalized and checked by the input schema, so traversal (`..`), absolute paths and drive
  letters are rejected as invalid arguments before any permission check or execution, and permission
  scopes are always clean relative paths.
- Symlinks that escape the root are refused at execution time.
- Credential-like files (`.env`, keys, `.git/`) are never read or written, so secrets cannot enter
  Task State (002 security).
- `list_files` and `read_file` are read-only; `write_file` is a `write` action that needs approval.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, Field, field_validator

from galliani.permissions import PermissionLevel
from galliani.tools import SideEffect, ToolDefinition, ToolInputRejected, ToolRegistry

MAX_READ_BYTES = 100_000
MAX_WRITE_BYTES = 200_000
MAX_LIST = 200
BLOCKED_PATTERNS = (".env", ".env.*", "*.pem", "*.key", "id_rsa*", "id_ed25519*", "*.p12", "*.pfx",
                    "credentials*", "secrets*")
BLOCKED_DIRS = {".git", ".venv", "node_modules", "__pycache__"}


def normalize_relative(path: str) -> str:
    raw = path.strip().replace("\\", "/")
    if not raw or raw == ".":
        return "."
    if raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
        raise ValueError("path must be relative to the workspace")
    parts = [p for p in PurePosixPath(raw).parts if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError("path may not leave the workspace")
    return "/".join(parts) or "."


class _PathArgs(BaseModel):
    @field_validator("path", check_fields=False)
    @classmethod
    def _relative(cls, v: str) -> str:
        return normalize_relative(v)


class ListIn(_PathArgs):
    path: str = "."
    pattern: str = Field(default="*", max_length=100)


class ListOut(BaseModel):
    files: list[str]
    truncated: bool


class ReadIn(_PathArgs):
    path: str


class ReadOut(BaseModel):
    path: str
    text: str
    truncated: bool


class WriteIn(_PathArgs):
    path: str
    content: str = Field(max_length=MAX_WRITE_BYTES)


class WriteOut(BaseModel):
    path: str
    bytes: int


class Workspace:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"workspace {self.root} is not a directory")

    def _blocked(self, rel: str) -> bool:
        parts = rel.split("/")
        return any(p in BLOCKED_DIRS for p in parts) or any(fnmatch.fnmatch(parts[-1], pat) for pat in BLOCKED_PATTERNS)

    def resolve(self, rel: str) -> Path:
        if rel != "." and self._blocked(rel):
            raise ToolInputRejected(f"{rel} is a protected path")
        target = (self.root / rel).resolve()
        if target != self.root and not target.is_relative_to(self.root):
            raise ToolInputRejected(f"{rel} resolves outside the workspace")
        return target

    def list_files(self, args: ListIn) -> dict:
        base = self.resolve(args.path)
        if not base.is_dir():
            raise ToolInputRejected(f"{args.path} is not a directory")
        files: list[str] = []
        truncated = False
        for item in sorted(base.rglob("*")):
            rel = item.relative_to(self.root).as_posix()
            if not item.is_file() or self._blocked(rel) or not fnmatch.fnmatch(item.name, args.pattern):
                continue
            if not item.resolve().is_relative_to(self.root):
                continue
            if len(files) >= MAX_LIST:
                truncated = True
                break
            files.append(rel)
        return {"files": files, "truncated": truncated}

    def read_file(self, args: ReadIn) -> dict:
        target = self.resolve(args.path)
        if not target.is_file():
            raise ToolInputRejected(f"{args.path} does not exist")
        data = target.read_bytes()
        text = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
        return {"path": args.path, "text": text, "truncated": len(data) > MAX_READ_BYTES}

    def write_file(self, args: WriteIn) -> dict:
        if args.path == ".":
            raise ToolInputRejected("a file name is required")
        target = self.resolve(args.path)
        if target.is_dir():
            raise ToolInputRejected(f"{args.path} is a directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(args.content, encoding="utf-8")
        return {"path": args.path, "bytes": len(args.content.encode("utf-8"))}

    def tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(name="list_files", description="List files under a workspace directory (recursive).",
                           input_schema=ListIn, output_schema=ListOut, permission_level=PermissionLevel.read_only,
                           side_effects=[SideEffect.read], handler=self.list_files, resource_field="path",
                           idempotent=True),
            ToolDefinition(name="read_file", description="Read a UTF-8 text file from the workspace.",
                           input_schema=ReadIn, output_schema=ReadOut, permission_level=PermissionLevel.read_only,
                           side_effects=[SideEffect.read], handler=self.read_file, resource_field="path",
                           idempotent=True),
            ToolDefinition(name="write_file", description="Create or overwrite a UTF-8 text file in the workspace.",
                           input_schema=WriteIn, output_schema=WriteOut, permission_level=PermissionLevel.write,
                           side_effects=[SideEffect.write], handler=self.write_file, resource_field="path"),
        ]

    def registry(self) -> ToolRegistry:
        return ToolRegistry(self.tools())
