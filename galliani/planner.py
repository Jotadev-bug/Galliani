"""Spec 004 - Planner: turn a normalized objective into a small, verifiable, revisable plan.

v0.1 ships `StaticPlanner`, a deterministic planner driven by fixtures (README: "small, deterministic
core"). A model-backed planner can implement the same `Planner` protocol later without changing the
supervisor.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from galliani.contracts import Objective, new_id
from galliani.errors import GallianiError
from galliani.limits import LoopLimits
from galliani.redaction import contains_secret
from galliani.verification import Criterion


class StepKind(str, Enum):
    model = "model"
    tool = "tool"


class ToolInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    """004 `PlanStep`. For model steps `required_capability` is a worker capability; for tool steps it
    names the tool. `extra="forbid"` keeps hidden-reasoning fields out of plans (004 security)."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    kind: StepKind
    purpose: str
    required_capability: str
    input_refs: list[str] = Field(default_factory=list)  # step_ids whose outputs this step consumes
    expected_output: str
    verification_criteria: list[Criterion]
    instruction: str = ""  # model steps: the bounded task given to the Agent Worker
    tool: ToolInvocation | None = None  # tool steps


class PlanRevision(BaseModel):
    previous_plan_id: str
    reason: str
    changed_steps: list[str]


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    task_id: str
    version: int = Field(ge=1)
    steps: list[PlanStep]
    success_criteria: list[Criterion] = Field(default_factory=list)
    revision: PlanRevision | None = None


class PlanRequest(BaseModel):
    objective: Objective
    constraints: dict[str, Any] = Field(default_factory=dict)
    available_capabilities: set[str] = Field(default_factory=set)
    context_summary: str = ""
    clarifications: list[str] = Field(default_factory=list)  # user answers; instructions, unlike context


class PlannerStatus(str, Enum):
    planned = "planned"
    needs_clarification = "needs_clarification"
    cannot_plan = "cannot_plan"


class PlannerOutcome(BaseModel):
    status: PlannerStatus
    plan: Plan | None = None
    public_reason: str = ""


class PlannerError(GallianiError):
    code = "planner_error"


class Planner(Protocol):
    async def plan(self, request: PlanRequest, *, task_id: str) -> PlannerOutcome: ...

    async def revise(
        self, request: PlanRequest, *, current_plan: Plan, failed_step_id: str, evidence: list[str]
    ) -> PlannerOutcome: ...


def validate_plan(plan: Plan, limits: LoopLimits, available_capabilities: Iterable[str] | None = None) -> list[str]:
    """Return public validation errors; an empty list means the plan is valid (004 R1-R4)."""
    errors: list[str] = []
    if not plan.steps:
        errors.append("plan has no steps")
    if len(plan.steps) > limits.max_plan_steps:
        errors.append(f"plan has {len(plan.steps)} steps; the v0.1 limit is {limits.max_plan_steps}")
    seen: set[str] = set()
    available = set(available_capabilities) if available_capabilities is not None else None
    for step in plan.steps:
        if step.step_id in seen:
            errors.append(f"duplicate step id {step.step_id}")
        for ref in step.input_refs:
            if ref not in seen:
                errors.append(f"step {step.step_id} consumes {ref}, which does not run before it")
        seen.add(step.step_id)
        if not step.purpose.strip() or not step.expected_output.strip():
            errors.append(f"step {step.step_id} needs a purpose and an expected output")
        if not step.verification_criteria:
            errors.append(f"step {step.step_id} has no verification criteria")
        if step.kind is StepKind.model and not step.instruction.strip():
            errors.append(f"model step {step.step_id} has no instruction")
        if step.kind is StepKind.tool:
            if step.tool is None:
                errors.append(f"tool step {step.step_id} has no tool invocation")
            elif step.tool.tool_name != step.required_capability:
                errors.append(f"tool step {step.step_id} must name its tool as required_capability")
        if available is not None and step.required_capability not in available:
            errors.append(f"step {step.step_id} needs unavailable capability {step.required_capability}")
    if contains_secret(plan):
        errors.append("plan contains secret-like values")
    return errors


class StaticPlanner:
    """Deterministic planner that replays a script of outcomes, one per plan/revise call.

    Script entries: a plan body ``{"steps": [...], "success_criteria": [...]}``,
    ``{"clarify": "question"}``, ``{"cannot_plan": "reason"}`` or ``{"error": "msg", "retryable": bool}``.
    """

    def __init__(self, script: list[dict[str, Any]], *, required_constraints: Iterable[str] = ()):
        self.script = list(script)
        self.required_constraints = list(required_constraints)
        self.calls = 0

    async def plan(self, request: PlanRequest, *, task_id: str) -> PlannerOutcome:
        missing = [c for c in self.required_constraints if c not in request.constraints]
        if missing:
            return PlannerOutcome(
                status=PlannerStatus.needs_clarification,
                public_reason=f"Please provide: {', '.join(missing)}.",
            )
        return self._next(task_id, version=1)

    async def revise(
        self, request: PlanRequest, *, current_plan: Plan, failed_step_id: str, evidence: list[str]
    ) -> PlannerOutcome:
        return self._next(current_plan.task_id, version=current_plan.version + 1)

    def _next(self, task_id: str, *, version: int) -> PlannerOutcome:
        if self.calls >= len(self.script):
            return PlannerOutcome(status=PlannerStatus.cannot_plan, public_reason="No alternative plan is available.")
        entry = self.script[self.calls]
        self.calls += 1
        if "error" in entry:
            raise PlannerError(str(entry["error"]), retryable=bool(entry.get("retryable", False)))
        if "clarify" in entry:
            return PlannerOutcome(status=PlannerStatus.needs_clarification, public_reason=str(entry["clarify"]))
        if "cannot_plan" in entry:
            return PlannerOutcome(status=PlannerStatus.cannot_plan, public_reason=str(entry["cannot_plan"]))
        try:
            plan = Plan(
                plan_id=new_id("plan"),
                task_id=task_id,
                version=version,
                steps=entry["steps"],
                success_criteria=entry.get("success_criteria", []),
            )
        except (ValidationError, KeyError) as e:
            raise PlannerError(f"planner produced a malformed plan ({type(e).__name__})") from None
        return PlannerOutcome(status=PlannerStatus.planned, plan=plan, public_reason="Plan created.")
