"""Workspace toolkit (spec 005 tools with 009 permission levels): file access confined to one directory.

- Paths are normalized and checked by the input schema, so traversal (`..`), absolute paths and drive
  letters are rejected as invalid arguments before any permission check or execution, and permission
  scopes are always clean relative paths.
- Symlinks that escape the root are refused at execution time.
- Credential-like files (`.env`, keys, `.git/`) are never read or written, so secrets cannot enter
  Task State (002 security). Env templates such as `.env.example` are ordinary project files.
- `list_files` and `read_file` are read-only; `write_file` and `write_files` are `write` actions that
  need approval. `write_files` writes a whole set of files (e.g. a web page's HTML, CSS and JS) in one
  step and one approval, checking every path before it writes any.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from galliani.permissions import PermissionLevel
from galliani.tools import SideEffect, ToolDefinition, ToolInputRejected, ToolRegistry

MAX_READ_BYTES = 100_000
MAX_WRITE_BYTES = 200_000
MAX_LIST = 200
MAX_READ_MANY_FILES = 30
MAX_READ_MANY_BYTES = 200_000  # total text returned by one read_files call
MAX_READ_MANY_FILE_BYTES = 40_000
MAX_WRITE_MANY_FILES = 50
MAX_WRITE_MANY_BYTES = 400_000  # total content written by one write_files call
BLOCKED_PATTERNS = (".env", ".env.*", "*.pem", "*.key", "id_rsa*", "id_ed25519*", "*.p12", "*.pfx",
                    "credentials*", "secrets*")
TEMPLATE_NAMES = {".env.example", ".env.sample", ".env.template"}  # placeholders, not secrets
BLOCKED_DIRS = {".git", ".venv", "node_modules", "__pycache__"}
BUNDLE_HEADER = re.compile(r"^===\s*(?:file:\s*)?(\S(?:.*\S)?)\s*===\s*$", re.IGNORECASE)
FENCE = re.compile(r"\A```[^\n`]*\n(.*?)\n?```\s*\Z", re.DOTALL)


def parse_bundle(bundle: str) -> list[tuple[str, str]]:
    """Split a file bundle into (path, content) pairs.

    Each file starts with a line `=== path/to/file ===` and runs to the next header. Text before the
    first header is ignored, and a code fence wrapping a whole file is removed, so a model's usual
    framing ("Here are the files", ```html ... ```) never ends up inside the written files.
    """
    files: list[tuple[str, list[str]]] = []
    for line in bundle.replace("\r\n", "\n").split("\n"):
        header = BUNDLE_HEADER.match(line)
        if header:
            files.append((header.group(1), []))
        elif files:
            files[-1][1].append(line)
    out = []
    for path, lines in files:
        body = "\n".join(lines).strip("\n")
        fenced = FENCE.match(body.strip())
        if fenced:
            body = fenced.group(1)
        out.append((path, body + "\n" if body else ""))
    return out


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


class ReadManyIn(_PathArgs):
    path: str = "."  # folder to read from
    pattern: str = Field(default="*", max_length=100)  # file-name glob, e.g. "*.md"
    paths: list[str] = Field(default_factory=list, max_length=50)  # explicit files; overrides path/pattern

    @field_validator("paths")
    @classmethod
    def _relative_paths(cls, v: list[str]) -> list[str]:
        return [normalize_relative(p) for p in v]


class ReadManyOut(BaseModel):
    files: list[ReadOut]
    skipped: list[str]  # matched but not read because the total size limit was reached
    truncated: bool


class WriteIn(_PathArgs):
    path: str
    content: str = Field(max_length=MAX_WRITE_BYTES)


class WriteOut(BaseModel):
    path: str
    bytes: int
    change: Literal["created", "overwritten"]  # 014 R5: overwrites stay visible when no prompt was shown


class WriteManyIn(BaseModel):
    files: list[WriteIn] = Field(default_factory=list, max_length=MAX_WRITE_MANY_FILES)
    bundle: str = Field(default="", max_length=MAX_WRITE_MANY_BYTES)  # text from a model step; see parse_bundle

    @model_validator(mode="after")
    def _one_file_set(self) -> WriteManyIn:
        if self.files and self.bundle.strip():
            raise ValueError("give either files or bundle, not both")
        if self.bundle.strip():
            parsed = parse_bundle(self.bundle)
            if not parsed:
                raise ValueError("bundle has no '=== path ===' file headers")
            if len(parsed) > MAX_WRITE_MANY_FILES:
                raise ValueError(f"at most {MAX_WRITE_MANY_FILES} files per call")
            try:
                self.files = [WriteIn(path=path, content=content) for path, content in parsed]
            except ValidationError as e:
                reason = str(e.errors()[0]["msg"]).removeprefix("Value error, ")
                raise ValueError(f"a bundle file is invalid: {reason}") from None
            self.bundle = ""
        if not self.files:
            raise ValueError("no files to write")
        paths = [f.path for f in self.files]
        if "." in paths:
            raise ValueError("every file needs a file name")
        if len(set(paths)) != len(paths):
            raise ValueError("the same file appears more than once")
        if sum(len(f.content) for f in self.files) > MAX_WRITE_MANY_BYTES:
            raise ValueError(f"files exceed {MAX_WRITE_MANY_BYTES} characters in total")
        return self

    @property
    def folder(self) -> str:
        """Deepest folder holding every file: the permission scope of the call."""
        parents = [PurePosixPath(f.path).parent.parts for f in self.files]
        common = []
        for parts in zip(*parents):
            if len(set(parts)) != 1:
                break
            common.append(parts[0])
        return "/".join(common) or "."


class WriteManyOut(BaseModel):
    paths: list[str]
    bytes: int
    files: list[WriteOut]


def _size(n: int) -> str:
    return f"{n} B" if n < 1024 else f"{n / 1024:.1f} KB"


def describe_write_many(args: WriteManyIn) -> str:
    listed = ", ".join(f"{f.path} ({_size(len(f.content.encode('utf-8')))})" for f in args.files)
    return f"create or overwrite {len(args.files)} file(s): {listed}"


class Workspace:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"workspace {self.root} is not a directory")

    def _blocked(self, rel: str) -> bool:
        parts = rel.split("/")
        if any(p in BLOCKED_DIRS for p in parts):
            return True
        return parts[-1] not in TEMPLATE_NAMES and any(fnmatch.fnmatch(parts[-1], pat) for pat in BLOCKED_PATTERNS)

    def resolve(self, rel: str) -> Path:
        if rel != "." and self._blocked(rel):
            raise ToolInputRejected(f"{rel} is a protected path")
        target = (self.root / rel).resolve()
        if target != self.root and not target.is_relative_to(self.root):
            raise ToolInputRejected(f"{rel} resolves outside the workspace")
        return target

    def _nearby(self, rel: str, limit: int = 10) -> str:
        """Evidence for replanning: what the closest existing folder contains (protected names hidden)."""
        parent = PurePosixPath(rel).parent
        while str(parent) not in (".", "") and not (self.root / parent).is_dir():
            parent = parent.parent
        folder = "." if str(parent) in (".", "") else parent.as_posix()
        entries = sorted(
            p.name + ("/" if p.is_dir() else "") for p in (self.root / folder).iterdir()
            if not self._blocked(p.name if folder == "." else f"{folder}/{p.name}")
        )
        shown = ", ".join(entries[:limit]) + (", ..." if len(entries) > limit else "")
        where = "the workspace root ('.')" if folder == "." else f"'{folder}'"
        return f"{where} contains: {shown or '(nothing)'}"

    def list_files(self, args: ListIn) -> dict:
        base = self.resolve(args.path)
        if not base.is_dir():
            raise ToolInputRejected(f"{args.path} is not a directory in the workspace; {self._nearby(args.path)}")
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
            raise ToolInputRejected(f"{args.path} is not a file in the workspace; {self._nearby(args.path)}")
        data = target.read_bytes()
        text = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
        return {"path": args.path, "text": text, "truncated": len(data) > MAX_READ_BYTES}

    def read_files(self, args: ReadManyIn) -> dict:
        if args.paths:
            names = args.paths
        else:
            listing = self.list_files(ListIn(path=args.path, pattern=args.pattern))
            names = listing["files"]
        files, skipped, used = [], [], 0
        for rel in names:
            target = self.resolve(rel)
            if not target.is_file():
                raise ToolInputRejected(f"{rel} is not a file in the workspace; {self._nearby(rel)}")
            data = target.read_bytes()[:MAX_READ_MANY_FILE_BYTES + 1]
            text = data[:MAX_READ_MANY_FILE_BYTES].decode("utf-8", errors="replace")
            if len(files) >= MAX_READ_MANY_FILES or used + len(text) > MAX_READ_MANY_BYTES:
                skipped.append(rel)
                continue
            used += len(text)
            files.append({"path": rel, "text": text, "truncated": len(data) > MAX_READ_MANY_FILE_BYTES})
        if not files and not skipped:
            raise ToolInputRejected(f"no files match '{args.pattern}' under {args.path}; {self._nearby(args.path + '/x')}")
        return {"files": files, "skipped": skipped, "truncated": bool(skipped) or any(f["truncated"] for f in files)}

    def write_file(self, args: WriteIn) -> dict:
        if args.path == ".":
            raise ToolInputRejected("a file name is required")
        target = self.resolve(args.path)
        if target.is_dir():
            raise ToolInputRejected(f"{args.path} is a directory")
        change = "overwritten" if target.exists() else "created"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(args.content, encoding="utf-8")
        return {"path": args.path, "bytes": len(args.content.encode("utf-8")), "change": change}

    def write_files(self, args: WriteManyIn) -> dict:
        targets = []
        for f in args.files:  # every path is checked before anything is written
            target = self.resolve(f.path)
            if target.is_dir():
                raise ToolInputRejected(f"{f.path} is a directory")
            targets.append(target)
        written = []
        for f, target in zip(args.files, targets):
            change = "overwritten" if target.exists() else "created"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f.content, encoding="utf-8")
            written.append({"path": f.path, "bytes": len(f.content.encode("utf-8")), "change": change})
        return {"paths": [f.path for f in args.files], "bytes": sum(w["bytes"] for w in written), "files": written}

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
            ToolDefinition(name="read_files",
                           description="Read several UTF-8 text files in one step: every file under `path` whose name "
                                       "matches `pattern` (recursive), or the explicit `paths` list. Size-limited.",
                           input_schema=ReadManyIn, output_schema=ReadManyOut,
                           permission_level=PermissionLevel.read_only, side_effects=[SideEffect.read],
                           handler=self.read_files, resource_field="path", idempotent=True),
            ToolDefinition(name="write_file", description="Create or overwrite a UTF-8 text file in the workspace.",
                           input_schema=WriteIn, output_schema=WriteOut, permission_level=PermissionLevel.write,
                           side_effects=[SideEffect.write], handler=self.write_file, resource_field="path",
                           artifact_field="path", workspace_edit=True),
            ToolDefinition(name="write_files",
                           description="Create or overwrite several UTF-8 text files (any type: .html, .css, .js, "
                                       ".py, .json, ...) in one step. Pass `files` as [{path, content}], or pass "
                                       "`bundle`: text where each file starts with a line '=== path/to/file ===' "
                                       "followed by its full content (code fences around a file are removed). "
                                       "Use `bundle` with {\"$ref\": \"<model step>\"} to save files a model step "
                                       "generated.",
                           input_schema=WriteManyIn, output_schema=WriteManyOut,
                           permission_level=PermissionLevel.write, side_effects=[SideEffect.write],
                           handler=self.write_files, resource_field="folder", artifact_field="paths",
                           describe=describe_write_many, timeout_ms=15_000, workspace_edit=True),
        ]

    def registry(self) -> ToolRegistry:
        return ToolRegistry(self.tools())
