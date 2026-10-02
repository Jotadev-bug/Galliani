"""Disk cache wrapper for any provider. Used by the benchmark so re-runs cost nothing."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from app.models.schemas import GenerationResult, Message, ModelSpec
from app.providers.base import ModelProvider


class CachingProvider(ModelProvider):
    def __init__(self, inner: ModelProvider, cache_dir: str | Path):
        self.inner = inner
        self.name = f"cached:{inner.name}"
        self.cache_dir = Path(cache_dir)
        self.hits = 0
        self.misses = 0

    def _path(self, model: ModelSpec, payload: dict) -> Path:
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
        return self.cache_dir / re.sub(r"[^\w.-]", "_", model.api_model) / f"{digest}.json"

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
        payload = {
            "provider": self.inner.name,
            "model": model.api_model,
            "messages": [m.model_dump() for m in messages],
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
            "json_mode": json_mode,
        }
        path = self._path(model, payload)
        if path.exists():
            self.hits += 1
            cached = GenerationResult.model_validate_json(path.read_text(encoding="utf-8"))
            # Re-price from the current registry so pricing updates apply to cached runs.
            in_cost, out_cost = model.pricing.cost(cached.usage.input_tokens, cached.usage.output_tokens)
            usage = cached.usage.model_copy(update={"input_cost": in_cost, "output_cost": out_cost})
            return cached.model_copy(update={"usage": usage, "model_id": model.id})
        self.misses += 1
        result = await self.inner.generate(
            messages, model, max_output_tokens=max_output_tokens, temperature=temperature,
            json_mode=json_mode, timeout_s=timeout_s,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.model_dump_json(), encoding="utf-8")
        return result

    async def aclose(self) -> None:
        await self.inner.aclose()
