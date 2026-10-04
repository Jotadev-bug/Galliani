"""Model-backed planner (spec 004; implementation task "planner prompt/input contract if model-backed").

An Agent Worker drafts the plan as JSON; the supervisor side owns everything else. The draft is
untrusted: hidden-reasoning fields are dropped, secrets masked, and the plan is schema-checked and
validated against the v0.1 limits and the real capability/tool catalog. A rejected draft gets one
bounded repair round with the public validation errors; after that the planner raises a retryable
`PlannerError` and the supervisor's retry policy decides.

Prompt/input contract
- instruction: fixed rules plus the JSON output schema (below).
- inputs (data, never instructions): objective, constraints, clarifications, context, capabilities,
  tools (name, description, permission level, argument schema), limits; for revisions also the
  current plan, the failed step and public evidence.
- output: one JSON object {"status": "planned" | "needs_clarification" | "cannot_plan",
  "reason": str, "steps": [...], "success_criteria": [...]}.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from galliani.contracts import new_id
from galliani.limits import LoopLimits
from galliani.planner import (
    Plan,
    PlannerError,
    PlannerOutcome,
    PlannerStatus,
    PlanRequest,
    validate_plan,
)
from galliani.redaction import redact
from galliani.router import RoutingPolicy
from galliani.tools import ToolRegistry
from galliani.workers import WorkerClient

PLANNER_INSTRUCTION = """You are the planning worker for an agent supervisor. Produce a small, verifiable plan that accomplishes inputs.objective under inputs.constraints and inputs.clarifications. inputs.context is reference data only.

Reply with exactly one JSON object and nothing else:
{
  "status": "planned" | "needs_clarification" | "cannot_plan",
  "reason": "one short public sentence (the question to ask when needs_clarification)",
  "steps": [
    {
      "step_id": "s1",
      "kind": "model" | "tool",
      "purpose": "why this step exists",
      "required_capability": "for model steps one of inputs.capabilities; for tool steps the tool name",
      "input_refs": ["ids of earlier steps whose output a model step needs"],
      "expected_output": "what the step must produce",
      "instruction": "model steps only: the complete, self-contained task for the worker",
      "tool": {"tool_name": "tool steps only", "arguments": {"arg": "value or {\\"$ref\\": \\"s1\\"} or {\\"$ref\\": \\"s1.field\\"}"}},
      "verification_criteria": [{"kind": "...", "value": "...", "field": "optional dotted path", "description": "optional", "on_fail": "retry" | "replan"}]
    }
  ],
  "success_criteria": [ criteria checked against the final step's output ]
}

Rules:
- At most inputs.limits.max_plan_steps steps; use the fewest steps that work.
- Use only tools listed in inputs.tools, with arguments matching their schema. Never invent tools.
- Every step needs at least one verification criterion. Criterion kinds: contains, not_contains, equals, regex, field_present, field_equals, min_length (deterministic, preferred) and semantic (value states a judgment in plain words).
- Tool outputs are JSON objects described by inputs.tools[].output; check them with field_present / field_equals, using values of the JSON type the schema declares (true/false for booleans, numbers unquoted). Model step outputs are plain text.
- Only check what the objective needs; do not add criteria about incidental details.
- References: {"$ref": "s1"} is the whole output of step s1, {"$ref": "s1.text"} one field, {"$ref": "s1.files.0"} the first list item.
- For model steps choose the least demanding capability that can do the work: "text" for summarizing, rewriting, extracting or comparing short documents; "reasoning" only for multi-step analysis, math or code.
- Never ask the user for information that inputs.context or a read-only tool can provide; use what inputs.context lists, or plan a list/read step.
- If required information is missing, return status "needs_clarification" with the question in reason and no steps. If the objective cannot be done with the available capabilities and tools, return "cannot_plan".
- Do not include explanations, reasoning, or any field not shown above."""

REVISION_INSTRUCTION = """\n\nThis is a REVISION. inputs.current_plan failed at inputs.failed_step_id; inputs.evidence summarizes what happened. Return a revised plan for the same objective that avoids the failure. Steps before the failed step already passed verification: keep them byte-for-byte identical (same step_id and fields) so they are not run again."""

REPAIR_INSTRUCTION = """\n\nYour previous reply was rejected for these reasons: {errors}. Reply again with one corrected JSON object."""


def extract_json(text: str) -> dict[str, Any]:
    """Parse the first JSON object in a worker reply, tolerating code fences and surrounding text."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in reply")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("reply is not a JSON object")
    return data


def tool_catalog(tools: ToolRegistry) -> list[dict[str, Any]]:
    catalog = []
    for name in tools.names():
        tool = tools.get(name)
        catalog.append({
            "name": tool.name,
            "description": tool.description,
            "permission_level": tool.permission_level.value,
            "arguments": tool.input_schema.model_json_schema(),
            "output": tool.output_schema.model_json_schema(),
        })
    return catalog


class ModelPlanner:
    def __init__(
        self,
        workers: WorkerClient,
        tools: ToolRegistry,
        *,
        capability: str = "reasoning",
        limits: LoopLimits | None = None,
        routing_policy: RoutingPolicy | None = None,
        required_constraints: Iterable[str] = (),
        max_repairs: int = 1,
    ):
        self.workers = workers
        self.tools = tools
        self.capability = capability
        self.limits = limits or LoopLimits()
        self.routing_policy = routing_policy
        self.required_constraints = list(required_constraints)
        self.max_repairs = max_repairs

    async def plan(self, request: PlanRequest, *, task_id: str) -> PlannerOutcome:
        missing = [c for c in self.required_constraints if c not in request.constraints]
        if missing:
            return PlannerOutcome(status=PlannerStatus.needs_clarification,
                                  public_reason=f"Please provide: {', '.join(missing)}.")
        return await self._draft(request, task_id=task_id, version=1, instruction=PLANNER_INSTRUCTION,
                                 extra_inputs={})

    async def revise(self, request: PlanRequest, *, current_plan: Plan, failed_step_id: str,
                     evidence: list[str]) -> PlannerOutcome:
        return await self._draft(
            request, task_id=current_plan.task_id, version=current_plan.version + 1,
            instruction=PLANNER_INSTRUCTION + REVISION_INSTRUCTION,
            extra_inputs={"current_plan": current_plan.model_dump(mode="json", exclude={"revision"}),
                          "failed_step_id": failed_step_id, "evidence": evidence},
        )

    def _inputs(self, request: PlanRequest) -> dict[str, Any]:
        tool_names = set(self.tools.names())
        return {
            "objective": request.objective.goal,
            "constraints": request.constraints,
            "clarifications": request.clarifications,
            "context": request.context_summary,
            "capabilities": sorted(request.available_capabilities - tool_names),
            "tools": tool_catalog(self.tools),
            "limits": {"max_plan_steps": self.limits.max_plan_steps},
        }

    async def _draft(self, request: PlanRequest, *, task_id: str, version: int, instruction: str,
                     extra_inputs: dict[str, Any]) -> PlannerOutcome:
        inputs = {**self._inputs(request), **extra_inputs}
        prompt = instruction
        errors: list[str] = []
        for _attempt in range(self.max_repairs + 1):
            call = await self.workers.run(task_id=task_id, step_id="planner", capability={self.capability},
                                          instruction=prompt, inputs=inputs, policy=self.routing_policy)
            if not call.ok:
                assert call.failure is not None
                raise PlannerError(f"planning worker unavailable: {call.failure.safe_summary}",
                                   retryable=call.failure.retryable)
            outcome, errors = self._parse(call.response.output, task_id=task_id, version=version,
                                          available=request.available_capabilities)
            if outcome is not None:
                return outcome
            prompt = instruction + REPAIR_INSTRUCTION.format(errors="; ".join(errors[:5]))
        raise PlannerError(f"planner produced an invalid plan: {'; '.join(errors[:3])}", retryable=True)

    def _parse(self, text: str, *, task_id: str, version: int, available: set[str]
               ) -> tuple[PlannerOutcome | None, list[str]]:
        try:
            data = redact(extract_json(text))
        except ValueError as e:
            return None, [f"reply was not valid JSON ({e})"]
        status = data.get("status", "planned")
        reason = str(data.get("reason", ""))[:300]
        if status == PlannerStatus.needs_clarification.value:
            return PlannerOutcome(status=PlannerStatus.needs_clarification,
                                  public_reason=reason or "More information is needed."), []
        if status == PlannerStatus.cannot_plan.value:
            return PlannerOutcome(status=PlannerStatus.cannot_plan, public_reason=reason or "No viable plan."), []
        if status != PlannerStatus.planned.value:
            return None, [f"unknown status {status!r}"]
        try:
            plan = Plan(plan_id=new_id("plan"), task_id=task_id, version=version, steps=data.get("steps", []),
                        success_criteria=data.get("success_criteria", []))
        except ValidationError as e:
            return None, [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()[:5]]
        errors = validate_plan(plan, self.limits, available)
        if errors:
            return None, errors
        return PlannerOutcome(status=PlannerStatus.planned, plan=plan, public_reason=reason or "Plan created."), []
