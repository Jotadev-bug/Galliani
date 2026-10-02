"""Runs a routed request against providers, walking the fallback chain on failure."""

from __future__ import annotations

from app.config import RoutingConfig
from app.models.registry import ModelRegistry
from app.models.schemas import ExecutionResult, RouteDecision, RouteRequest
from app.providers.base import ContextOverflow, ProviderError, estimate_tokens
from app.providers.factory import ProviderPool


class Executor:
    def __init__(self, registry: ModelRegistry, pool: ProviderPool, config: RoutingConfig):
        self.registry = registry
        self.pool = pool
        self.config = config

    def _chain(self, decision: RouteDecision, request: RouteRequest) -> list[str]:
        """Selected model first, then fallbacks that respect the per-request cost cap."""
        fb = self.config.fallback
        input_tokens = estimate_tokens(request.prompt_text)
        expected_out = decision.profile.expected_output_tokens if decision.profile else 1000
        chain = [decision.model_id]
        for model_id in decision.fallbacks:
            est = sum(self.registry.get(model_id).pricing.cost(input_tokens, expected_out))
            if est <= fb.max_cost_per_request:
                chain.append(model_id)
        return chain[: fb.max_attempts]

    async def execute(self, request: RouteRequest, decision: RouteDecision) -> ExecutionResult:
        attempts: list[str] = []
        errors: list[str] = []
        min_context = 0
        for model_id in self._chain(decision, request):
            model = self.registry.get(model_id)
            if model.limits.context_window <= min_context:
                continue  # a previous model overflowed; only try models with more room
            attempts.append(model_id)
            try:
                result = await self.pool.for_model(model).generate(
                    request.messages,
                    model,
                    max_output_tokens=request.max_output_tokens,
                    timeout_s=self.config.fallback.request_timeout_s,
                )
                return ExecutionResult(decision=decision, result=result, attempts=attempts, errors=errors)
            except ProviderError as e:
                errors.append(f"{model_id}: {e.kind}: {str(e)[:200]}")
                if isinstance(e, ContextOverflow):
                    min_context = max(min_context, model.limits.context_window)
                if not e.try_other_model:
                    break
        return ExecutionResult(decision=decision, result=None, attempts=attempts, errors=errors)
