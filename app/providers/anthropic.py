"""Adapter for the Anthropic Messages API."""

from __future__ import annotations

import time

import httpx

from app.models.schemas import GenerationResult, Message, ModelSpec, Usage
from app.providers.base import (
    ModelProvider,
    ProviderError,
    ProviderOutage,
    ProviderTimeout,
    classify_http_error,
)

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(ModelProvider):
    def __init__(self, name: str, base_url: str, api_key: str | None, client: httpx.AsyncClient | None = None):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = client or httpx.AsyncClient()

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
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        turns = [m.model_dump() for m in messages if m.role != "system"]
        payload: dict = {
            "model": model.api_model,
            "messages": turns,
            "max_tokens": max_output_tokens or min(DEFAULT_MAX_TOKENS, model.limits.max_output_tokens),
        }
        if system:
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature
        # json_mode has no direct equivalent; the router prompt already demands JSON only.

        headers = {
            "content-type": "application/json",
            "anthropic-version": ANTHROPIC_VERSION,
            "x-api-key": self.api_key or "",
        }
        start = time.perf_counter()
        try:
            resp = await self._client.post(
                f"{self.base_url}/v1/messages", json=payload, headers=headers, timeout=timeout_s
            )
        except httpx.TimeoutException as e:
            raise ProviderTimeout(f"{self.name}: timeout after {timeout_s}s") from e
        except httpx.HTTPError as e:
            raise ProviderOutage(f"{self.name}: {e!r}") from e
        latency_ms = (time.perf_counter() - start) * 1000

        if resp.status_code == 529:
            raise ProviderOutage(resp.text[:500], status=529)
        if resp.status_code != 200:
            raise classify_http_error(resp.status_code, resp.text)

        data = resp.json()
        try:
            text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        except (KeyError, TypeError) as e:
            raise ProviderError(f"{self.name}: malformed response: {str(data)[:300]}") from e

        u = data.get("usage") or {}
        in_tok = int(u.get("input_tokens", 0)) + int(u.get("cache_read_input_tokens", 0) or 0) + int(
            u.get("cache_creation_input_tokens", 0) or 0
        )
        out_tok = int(u.get("output_tokens", 0))
        in_cost, out_cost = model.pricing.cost(in_tok, out_tok)
        return GenerationResult(
            model_id=model.id,
            text=text,
            usage=Usage(input_tokens=in_tok, output_tokens=out_tok, input_cost=in_cost, output_cost=out_cost),
            latency_ms=latency_ms,
            finish_reason=data.get("stop_reason"),
        )

    async def aclose(self) -> None:
        await self._client.aclose()
