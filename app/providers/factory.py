"""Builds provider adapters from registry config. Adding a provider = add an adapter + a branch here."""

from __future__ import annotations

import os
from collections.abc import Callable

from app.models.registry import ModelRegistry
from app.models.schemas import ModelSpec, ProviderConfig
from app.providers.anthropic import AnthropicProvider
from app.providers.base import ModelProvider
from app.providers.mock import MockProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


def build_provider(name: str, cfg: ProviderConfig) -> ModelProvider:
    api_key = os.environ.get(cfg.api_key_env) if cfg.api_key_env else None
    if cfg.adapter == "openai_compatible":
        return OpenAICompatibleProvider(name, cfg.base_url or "", api_key)
    if cfg.adapter == "anthropic":
        return AnthropicProvider(name, cfg.base_url or "https://api.anthropic.com", api_key)
    if cfg.adapter == "mock":
        return MockProvider(name)
    raise ValueError(f"Unknown adapter {cfg.adapter!r}")


class ProviderPool:
    """Lazily instantiates one adapter per provider and resolves the adapter for a model."""

    def __init__(
        self,
        registry: ModelRegistry,
        overrides: dict[str, ModelProvider] | None = None,
        wrapper: Callable[[ModelProvider], ModelProvider] | None = None,
    ):
        """`overrides` replace adapters by provider name; `wrapper` decorates every built adapter (e.g. caching)."""
        self.registry = registry
        self._providers: dict[str, ModelProvider] = dict(overrides or {})
        self._wrapper = wrapper

    def wrap(self, provider: ModelProvider) -> ModelProvider:
        return self._wrapper(provider) if self._wrapper else provider

    def for_model(self, model: ModelSpec) -> ModelProvider:
        if model.provider not in self._providers:
            built = build_provider(model.provider, self.registry.providers[model.provider])
            self._providers[model.provider] = self.wrap(built)
        return self._providers[model.provider]

    def missing_keys(self, models: list[ModelSpec]) -> list[str]:
        missing = set()
        for m in models:
            if m.provider in self._providers:
                continue
            cfg = self.registry.providers[m.provider]
            if cfg.api_key_env and not os.environ.get(cfg.api_key_env):
                missing.add(cfg.api_key_env)
        return sorted(missing)

    async def aclose(self) -> None:
        for p in self._providers.values():
            await p.aclose()
