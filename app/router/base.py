"""Router interface. Jev is one implementation; the product must not depend on it."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.config import RoutingConfig
from app.models.schemas import ModelSpec, RouteDecision, RouteRequest, TaskProfile
from app.providers.base import estimate_tokens
from app.router import scoring


class NoCandidatesError(Exception):
    pass


class Router(ABC):
    name: str

    @abstractmethod
    async def route(self, request: RouteRequest, candidates: Sequence[ModelSpec]) -> RouteDecision:
        """Choose a model for `request` among `candidates` (already filtered for hard constraints)."""


def decide_from_profile(
    router_name: str,
    profile: TaskProfile,
    request: RouteRequest,
    candidates: Sequence[ModelSpec],
    config: RoutingConfig,
    *,
    confidence: float,
    reason: str,
) -> RouteDecision:
    """Shared path for routers that produce a TaskProfile and let the utility function choose."""
    if not candidates:
        raise NoCandidatesError("No candidate model satisfies the request constraints")
    weights = config.modes[request.mode]
    scores = scoring.score_candidates(
        candidates, profile, estimate_tokens(request.prompt_text), weights, config.success_model
    )
    ranked = scoring.rank(scores, weights.min_success)
    return RouteDecision(
        router=router_name,
        model_id=ranked[0].model_id,
        confidence=confidence,
        profile=profile,
        reason=reason,
        fallbacks=[s.model_id for s in ranked[1:]],
        scores=ranked,
    )
