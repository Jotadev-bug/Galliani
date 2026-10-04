"""Spec 007 - Verification: compare outputs against explicit criteria; pass, fail or inconclusive.

Deterministic criteria run first (007 behavior). `semantic` criteria are delegated to an optional
model-backed `SemanticVerifier`; without one they are inconclusive. The verifier has no access to tools
(007 security) and its summaries name criteria, never copy outputs.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "contains", "not_contains", "equals", "regex", "field_present", "field_equals", "min_length", "semantic"
    ]
    value: Any = None
    field: str | None = None  # dotted path into a structured output
    description: str = ""
    # What a failure of this criterion means: the same step may succeed again (retry),
    # or the approach is wrong and the plan must change (replan). Spec 008 AC Replan.
    on_fail: Literal["retry", "replan"] = "retry"

    def label(self) -> str:
        if self.description:
            return self.description
        target = f"{self.field} " if self.field else ""
        return f"{target}{self.kind} {self.value!r}".strip() if self.value is not None else f"{target}{self.kind}"


class VerificationStatus(str, Enum):
    pass_ = "pass"
    fail = "fail"
    inconclusive = "inconclusive"


class VerificationRecommendation(str, Enum):
    continue_ = "continue"
    retry = "retry"
    replan = "replan"
    ask_user = "ask_user"
    stop = "stop"


class VerificationRequest(BaseModel):
    task_id: str
    step_id: str | None  # None means final, task-level verification
    output_refs: list[str]
    criteria: list[Criterion]
    context_summary: str = ""


class VerificationResult(BaseModel):
    status: VerificationStatus
    satisfied_criteria: list[str] = Field(default_factory=list)
    failed_criteria: list[str] = Field(default_factory=list)
    reason_summary: str
    recommendation: VerificationRecommendation


class VerifierUnavailable(Exception):
    """Raised by a semantic verifier that cannot run right now (retryable)."""


class SemanticVerifier(Protocol):
    """Model-backed verifier boundary. Returns (passed, public_summary); None means cannot judge.
    Raises `VerifierUnavailable` when no verifier worker can run."""

    async def check(self, criterion: Criterion, output: Any, request: VerificationRequest) -> tuple[bool | None, str]: ...


_MISSING = object()


def _get_field(output: Any, path: str) -> Any:
    cur = output
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur


def _text(output: Any) -> str:
    return output if isinstance(output, str) else str(output)


def check_deterministic(criterion: Criterion, output: Any) -> bool:
    target = output
    if criterion.field and criterion.kind not in ("field_present", "field_equals"):
        target = _get_field(output, criterion.field)
        if target is _MISSING:
            return False
    match criterion.kind:
        case "contains":
            return str(criterion.value).lower() in _text(target).lower()
        case "not_contains":
            return str(criterion.value).lower() not in _text(target).lower()
        case "equals":
            return target == criterion.value
        case "regex":
            return re.search(str(criterion.value), _text(target)) is not None
        case "min_length":
            return len(_text(target)) >= int(criterion.value)
        case "field_present":
            return _get_field(output, criterion.field or "") is not _MISSING
        case "field_equals":
            return _get_field(output, criterion.field or "") == criterion.value
    raise ValueError(f"not a deterministic criterion: {criterion.kind}")


class Verifier:
    def __init__(self, semantic: SemanticVerifier | None = None):
        self.semantic = semantic

    async def verify(self, request: VerificationRequest, outputs: Mapping[str, Any]) -> VerificationResult:
        if not request.criteria:
            return VerificationResult(
                status=VerificationStatus.inconclusive,
                reason_summary="No verification criteria were provided; better criteria are needed.",
                recommendation=VerificationRecommendation.ask_user,
            )
        if not request.output_refs or any(ref not in outputs for ref in request.output_refs):
            return VerificationResult(
                status=VerificationStatus.fail,
                failed_criteria=[c.label() for c in request.criteria],
                reason_summary="The output to verify is missing.",
                recommendation=VerificationRecommendation.retry,
            )
        # Criteria apply to the last referenced output (the step's own result).
        output = outputs[request.output_refs[-1]]

        satisfied: list[str] = []
        failed: list[Criterion] = []
        undecided: list[str] = []
        for criterion in request.criteria:
            if criterion.kind != "semantic":
                if check_deterministic(criterion, output):
                    satisfied.append(criterion.label())
                else:
                    failed.append(criterion)
                continue
            if self.semantic is None:
                undecided.append(criterion.label())
                continue
            try:
                passed, _summary = await self.semantic.check(criterion, output, request)
            except VerifierUnavailable:
                return VerificationResult(
                    status=VerificationStatus.inconclusive,
                    satisfied_criteria=satisfied,
                    reason_summary="The semantic verifier is unavailable; verification can be retried.",
                    recommendation=VerificationRecommendation.retry,
                )
            if passed is None:
                undecided.append(criterion.label())
            elif passed:
                satisfied.append(criterion.label())
            else:
                failed.append(criterion)

        total = len(request.criteria)
        if failed:
            labels = [c.label() for c in failed]
            replan = any(c.on_fail == "replan" for c in failed)
            return VerificationResult(
                status=VerificationStatus.fail,
                satisfied_criteria=satisfied,
                failed_criteria=labels,
                reason_summary=f"{len(satisfied)}/{total} criteria satisfied; failed: {'; '.join(labels)}.",
                recommendation=VerificationRecommendation.replan if replan else VerificationRecommendation.retry,
            )
        if undecided:
            return VerificationResult(
                status=VerificationStatus.inconclusive,
                satisfied_criteria=satisfied,
                reason_summary=f"Could not decide: {'; '.join(undecided)}; clarification or better criteria needed.",
                recommendation=VerificationRecommendation.ask_user,
            )
        return VerificationResult(
            status=VerificationStatus.pass_,
            satisfied_criteria=satisfied,
            reason_summary=f"All {total} criteria satisfied.",
            recommendation=VerificationRecommendation.continue_,
        )
