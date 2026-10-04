"""Spec 000 - Foundation: provider decoupling and shared vocabulary."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "galliani"
FORBIDDEN_IMPORTS = ("app", "anthropic", "openai", "httpx", "google", "mistralai", "cohere")


@pytest.mark.parametrize("module", sorted(CORE.glob("*.py")), ids=lambda p: p.name)
def test_core_is_provider_neutral(module: Path):
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & set(FORBIDDEN_IMPORTS), f"{module.name} imports {imported & set(FORBIDDEN_IMPORTS)}"
    full = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any(m.startswith("galliani.providers") for m in full), f"{module.name} imports a provider adapter"


def test_required_vocabulary_is_defined_in_foundation_spec():
    spec = (ROOT / "specs" / "000-foundation" / "spec.md").read_text(encoding="utf-8")
    for term in ("Agent Supervisor", "Agent Worker", "Task State", "Memory", "`Objective`", "`Task`", "`Plan`",
                 "`AgentWorker`", "`Observation`", "`TaskState`", "`MemoryRecord`", "`WorkerRequest`",
                 "`WorkerResponse`", "`AdapterError`", "`Criterion`", "`FailureSignal`", "`LoopLimits`",
                 "`ApprovalPrompt`", "`ScriptedAdapter`", "`StaticPlanner`"):
        assert term in spec, term
