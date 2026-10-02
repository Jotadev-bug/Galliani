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


def resolve_key(cfg: ProviderConfig, keys: dict[str, str] | None = None) -> str | None:
    """A caller-supplied key (by env-var name, e.g. a tester's own OPENROUTER_API_KEY) wins over the environment."""
    if not cfg.api_key_env:
        return None
    return (keys or {}).get(cfg.api_key_env) or os.environ.get(cfg.api_key_env)


def build_provider(name: str, cfg: ProviderConfig, keys: dict[str, str] | None = None) -> ModelProvider:
    api_key = resolve_key(cfg, keys)
    if cfg.adapter == "openai_compatible":
        return OpenAICompatibleProvider(name, cfg.base_url or "", api_key, max_tokens_param=cfg.max_tokens_param)
    if cfg.adapter == "anthropic":
        return AnthropicProvider(name, cfg.base_url or "https://api.anthropic.com", api_key)
    if cfg.adapter == "mock":
        return MockProvider(name)
    if cfg.adapter == "decisions":
        raise ValueError(f"Provider {name!r} serves decision models (e.g. Jev); they cannot be generation candidates")
    raise ValueError(f"Unknown adapter {cfg.adapter!r}")


class ProviderPool:
    """Lazily instantiates one adapter per provider and resolves the adapter for a model."""

    def __init__(
        self,
        registry: ModelRegistry,
        overrides: dict[str, ModelProvider] | None = None,
        wrapper: Callable[[ModelProvider], ModelProvider] | None = None,
        keys: dict[str, str] | None = None,
    ):
        """`overrides` replace adapters by provider name; `wrapper` decorates every built adapter (e.g. caching);
        `keys` maps api_key_env names to caller-supplied keys that take precedence over the environment."""
        self.registry = registry
        self._providers: dict[str, ModelProvider] = dict(overrides or {})
        self._wrapper = wrapper
        self._keys = keys or {}

    def wrap(self, provider: ModelProvider) -> ModelProvider:
        return self._wrapper(provider) if self._wrapper else provider

    def _provider(self, name: str) -> ModelProvider:
        if name not in self._providers:
            built = build_provider(name, self.registry.providers[name], self._keys)
            self._providers[name] = self.wrap(built)
        return self._providers[name]

    def for_model(self, model: ModelSpec) -> ModelProvider:
        return self._provider(model.provider)

    def routes(self, model: ModelSpec) -> list[tuple[ModelProvider, ModelSpec]]:
        """Ways to call `model`, in order: the vendor's own API when the caller has that key, then the default.

        The direct route sends the vendor's model id (e.g. claude-sonnet-5-5) instead of the registry id.
        """
        out = []
        d = model.direct
        if d and (d.provider in self._providers or resolve_key(self.registry.providers[d.provider], self._keys)):
            out.append((self._provider(d.provider), model.model_copy(update={"provider_model": d.model})))
        out.append((self.for_model(model), model))
        return out

    def missing_keys(self, models: list[ModelSpec]) -> list[str]:
        missing = set()
        for m in models:
            if m.provider in self._providers:
                continue
            cfg = self.registry.providers[m.provider]
            if cfg.api_key_env and not resolve_key(cfg, self._keys):
                missing.add(cfg.api_key_env)
        return sorted(missing)

    async def aclose(self) -> None:
        for p in self._providers.values():
            await p.aclose()
