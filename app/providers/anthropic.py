"""Adapter for the Anthropic Messages API, via the official `anthropic` SDK."""

from __future__ import annotations

import time

import anthropic

from app.models.schemas import GenerationResult, Message, ModelSpec, Usage
from app.providers.base import (
    AuthError,
    ContextOverflow,
    InvalidRequest,
    ModelProvider,
    ModelUnavailable,
    ProviderError,
    ProviderOutage,
    ProviderTimeout,
    RateLimited,
    Refused,
)

# Current models think adaptively by default, and thinking tokens count toward max_tokens, so a
# small cap can truncate the answer. Direct Anthropic billing is on actual usage (nothing is
# reserved up front), so a generous floor costs nothing extra.
MIN_MAX_TOKENS = 16_000
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"


def map_error(e: Exception) -> ProviderError:
    """Typed SDK exceptions -> the router's failure taxonomy (most specific first)."""
    msg = str(e)[:500]
    if isinstance(e, anthropic.APITimeoutError):
        return ProviderTimeout(msg)
    if isinstance(e, anthropic.APIConnectionError):
        return ProviderOutage(msg)
    if isinstance(e, anthropic.RateLimitError):
        return RateLimited(msg, status=429)
    if isinstance(e, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return AuthError(msg, status=getattr(e, "status_code", None))
    if isinstance(e, anthropic.NotFoundError):
        return ModelUnavailable(msg, status=404)
    if isinstance(e, anthropic.RequestTooLargeError):
        return ContextOverflow(msg, status=413)
    if isinstance(e, anthropic.BadRequestError):
        lowered = msg.lower()
        if "prompt is too long" in lowered or "context" in lowered:
            return ContextOverflow(msg, status=400)
        return InvalidRequest(msg, status=400)
    if isinstance(e, anthropic.APIStatusError):
        return ProviderOutage(msg, status=e.status_code) if e.status_code >= 500 else ProviderError(msg, status=e.status_code)
    return ProviderError(msg)


class AnthropicProvider(ModelProvider):
    def __init__(self, name: str, base_url: str, api_key: str | None, client: anthropic.AsyncAnthropic | None = None):
        self.name = name
        # max_retries=0: the executor owns retries and fallbacks across models.
        self._client = client or anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url, max_retries=0)

    async def generate(
        self,
        messages: list[Message],
        model: ModelSpec,
        *,
        max_output_tokens: int | None = None,
        temperature: float | None = None,  # unsupported on current Claude models; ignored
        json_mode: bool = False,  # no direct equivalent; prompts ask for JSON where needed
        timeout_s: float = 120,
    ) -> GenerationResult:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        params: dict = {
            "model": model.api_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages if m.role != "system"],
            "max_tokens": min(max(max_output_tokens or 0, MIN_MAX_TOKENS), model.limits.max_output_tokens),
            "timeout": timeout_s,
        }
        if system:
            params["system"] = system

        start = time.perf_counter()
        try:
            if model.direct and model.direct.refusal_fallback:
                # On a safety decline, Anthropic re-runs the request on a suitable model in the same call.
                response = await self._client.beta.messages.create(
                    **params, betas=[REFUSAL_FALLBACK_BETA], fallbacks="default"
                )
            else:
                response = await self._client.messages.create(**params)
        except anthropic.APIError as e:
            raise map_error(e) from e
        latency_ms = (time.perf_counter() - start) * 1000

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise Refused(f"The model declined this request{f' ({category})' if category else ''}.")

        text = "".join(block.text for block in response.content if block.type == "text")
        u = response.usage
        in_tok = (u.input_tokens or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) + (
            getattr(u, "cache_creation_input_tokens", 0) or 0
        )
        out_tok = u.output_tokens or 0
        in_cost, out_cost = model.pricing.cost(in_tok, out_tok)
        return GenerationResult(
            model_id=model.id,
            text=text,
            usage=Usage(input_tokens=in_tok, output_tokens=out_tok, input_cost=in_cost, output_cost=out_cost),
            latency_ms=latency_ms,
            finish_reason=response.stop_reason,
        )

    async def aclose(self) -> None:
        await self._client.close()
