"""Offline provider for tests and pipeline dry-runs. Its outputs are SIMULATED, not real."""

from __future__ import annotations

from collections.abc import Callable

from app.models.schemas import GenerationResult, Message, ModelSpec, Usage
from app.providers.base import ModelProvider, ProviderError, estimate_tokens

# (messages, model) -> response text
Responder = Callable[[list[Message], ModelSpec], str]


class MockProvider(ModelProvider):
    def __init__(
        self,
        name: str = "mock",
        responder: Responder | None = None,
        failures: dict[str, ProviderError] | None = None,
    ):
        self.name = name
        self.responder = responder or (lambda messages, model: f"[{model.id}] mock response")
        self.failures = failures or {}
        self.calls: list[str] = []

    async def generate(
        self,
        messages: list[Message],
        model: ModelSpec,
        *,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        json_mode: bool = False,
        timeout_s: float = 120,
    ) -> GenerationResult:
        self.calls.append(model.id)
        if model.id in self.failures:
            raise self.failures[model.id]
        text = self.responder(messages, model)
        in_tok = sum(estimate_tokens(m.content) for m in messages)
        out_tok = estimate_tokens(text)
        in_cost, out_cost = model.pricing.cost(in_tok, out_tok)
        return GenerationResult(
            model_id=model.id,
            text=text,
            usage=Usage(input_tokens=in_tok, output_tokens=out_tok, input_cost=in_cost, output_cost=out_cost),
            latency_ms=model.latency.estimate_ms(out_tok),
            finish_reason="stop",
        )
