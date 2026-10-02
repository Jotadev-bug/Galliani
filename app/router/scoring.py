"""Utility scoring: pick the cheapest model that is *sufficiently capable* for a task profile.

Utility = q*P(success) - c*cost_penalty - l*latency_penalty - r*(1-P(success))*precision

Weights and the success bar come from config/routing.yaml (one set per mode).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.config import ModeWeights, SuccessModel
from app.models.schemas import CandidateScore, ModelSpec, TaskProfile

# Profile requirement -> model skill it is checked against.
REQUIREMENT_TO_SKILL = {
    "reasoning": "reasoning",
    "coding": "coding",
    "writing": "writing",
    "knowledge": "knowledge",
    "precision": "instruction_following",
}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def p_success(model: ModelSpec, profile: TaskProfile, sm: SuccessModel) -> float:
    """Prior estimate that `model` solves a task with this profile. Uncalibrated by design."""
    p = 1.0
    for req_name, skill_name in REQUIREMENT_TO_SKILL.items():
        requirement = getattr(profile, req_name)
        skill = getattr(model.skills, skill_name)
        p *= _sigmoid(sm.steepness * (skill - requirement) + sm.bias)
    return p


def _log_penalty(value: float, lo: float, hi: float) -> float:
    if hi <= lo or value <= 0 or lo <= 0:
        return 0.0
    return math.log(value / lo) / math.log(hi / lo)


def score_candidates(
    candidates: Sequence[ModelSpec],
    profile: TaskProfile,
    input_tokens: int,
    weights: ModeWeights,
    sm: SuccessModel,
) -> list[CandidateScore]:
    if not candidates:
        return []
    out_tokens = profile.expected_output_tokens
    costs = [sum(m.pricing.cost(input_tokens, out_tokens)) for m in candidates]
    lats = [m.latency.estimate_ms(out_tokens) for m in candidates]
    lo_c, hi_c, lo_l, hi_l = min(costs), max(costs), min(lats), max(lats)

    scores = []
    for m, cost, lat in zip(candidates, costs, lats, strict=True):
        p = p_success(m, profile, sm)
        utility = (
            weights.quality_weight * p
            - weights.cost_weight * _log_penalty(cost, lo_c, hi_c)
            - weights.latency_weight * _log_penalty(lat, lo_l, hi_l)
            - weights.risk_weight * (1 - p) * profile.precision
        )
        scores.append(CandidateScore(model_id=m.id, p_success=p, est_cost=cost, est_latency_ms=lat, utility=utility))
    return scores


def rank(scores: Sequence[CandidateScore], min_success: float) -> list[CandidateScore]:
    """Order candidates: those clearing the success bar by utility, then the rest by P(success).

    The first element is the selection; the remainder is the fallback order.
    """
    capable = sorted((s for s in scores if s.p_success >= min_success), key=lambda s: -s.utility)
    others = sorted((s for s in scores if s.p_success < min_success), key=lambda s: -s.p_success)
    return capable + others
