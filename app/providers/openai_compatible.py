"""Adapter for any OpenAI-compatible chat-completions API (OpenAI, OpenRouter, vLLM, Ollama...)."""

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


class OpenAICompatibleProvider(ModelProvider):
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str | None,
        client: httpx.AsyncClient | None = None,
        max_tokens_param: str = "max_tokens",
    ):
        self.name = name
        self.max_tokens_param = max_tokens_param
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
        payload: dict = {
            "model": model.api_model,
            "messages": [m.model_dump() for m in messages],
        }
        if max_output_tokens:
            payload[self.max_tokens_param] = max_output_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        start = time.perf_counter()
        try:
            resp = await self._client.post(
                f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=timeout_s
            )
        except httpx.TimeoutException as e:
            raise ProviderTimeout(f"{self.name}: timeout after {timeout_s}s") from e
        except httpx.HTTPError as e:
            raise ProviderOutage(f"{self.name}: {e!r}") from e
        latency_ms = (time.perf_counter() - start) * 1000

        if resp.status_code != 200:
            raise classify_http_error(resp.status_code, resp.text)

        data = resp.json()
        # OpenRouter can return 200 with an error object.
        if "error" in data and not data.get("choices"):
            err = data["error"]
            raise classify_http_error(int(err.get("code", 500) or 500), str(err.get("message", err)))
        try:
            choice = data["choices"][0]
            text = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"{self.name}: malformed response: {str(data)[:300]}") from e

        u = data.get("usage") or {}
        in_tok, out_tok = int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
        in_cost, out_cost = model.pricing.cost(in_tok, out_tok)
        return GenerationResult(
            model_id=model.id,
            text=text,
            usage=Usage(input_tokens=in_tok, output_tokens=out_tok, input_cost=in_cost, output_cost=out_cost),
            latency_ms=latency_ms,
            finish_reason=choice.get("finish_reason"),
        )

    async def aclose(self) -> None:
        await self._client.aclose()
