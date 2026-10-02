"""Decision policies applied after a router proposes a model: confidence escalation and budget limits."""

from __future__ import annotations

from collections.abc import Sequence

from app.config import ConfidencePolicy
from app.models.schemas import TIER_ORDER, CandidateScore, ModelSpec


def most_capable(candidates: Sequence[ModelSpec]) -> ModelSpec:
    def capability(m: ModelSpec) -> tuple[int, float]:
        skills = m.skills.model_dump().values()
        return TIER_ORDER[m.tier], sum(skills) / len(skills)

    return max(candidates, key=capability)


def apply_confidence(
    chosen_id: str,
    confidence: float,
    ranked: Sequence[CandidateScore],
    candidates: Sequence[ModelSpec],
    policy: ConfidencePolicy,
) -> tuple[str, str | None]:
    """Return (model_id, escalation_note). Low router confidence moves the choice to safer models.

    Thresholds are uncalibrated: a router's stated confidence is not assumed to be a true
    probability of success. See docs/routing.md.
    """
    if confidence >= policy.execute_threshold:
        return chosen_id, None

    by_id = {m.id: m for m in candidates}
    if confidence < policy.safer_threshold:
        top = most_capable(candidates)
        if top.id == chosen_id:
            return chosen_id, None
        return top.id, f"confidence {confidence:.2f} < {policy.safer_threshold}: fell back to most capable model"

    # Middle band: one step up in tier, picking the best-ranked model in the nearest higher tier.
    chosen_tier = TIER_ORDER[by_id[chosen_id].tier]
    higher = [s for s in ranked if TIER_ORDER[by_id[s.model_id].tier] > chosen_tier]
    if not higher:
        return chosen_id, None
    next_tier = min(TIER_ORDER[by_id[s.model_id].tier] for s in higher)
    safer = next(s for s in higher if TIER_ORDER[by_id[s.model_id].tier] == next_tier)
    return safer.model_id, f"confidence {confidence:.2f} < {policy.execute_threshold}: escalated one tier"


def within_budget(scores: Sequence[CandidateScore], max_cost: float) -> list[str]:
    return [s.model_id for s in scores if s.est_cost <= max_cost]
