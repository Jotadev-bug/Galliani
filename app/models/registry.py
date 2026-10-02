"""Model Registry: the single source of model facts (capabilities, prices, limits)."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.models.schemas import ModelSpec, ProviderConfig, RouteRequest


class RegistryFile(BaseModel):
    providers: dict[str, ProviderConfig]
    models: list[ModelSpec]


class ModelRegistry:
    def __init__(self, models: Iterable[ModelSpec], providers: dict[str, ProviderConfig]):
        self._models: dict[str, ModelSpec] = {}
        for m in models:
            if m.id in self._models:
                raise ValueError(f"Duplicate model id in registry: {m.id}")
            if m.provider not in providers:
                raise ValueError(f"Model {m.id} references unknown provider {m.provider!r}")
            self._models[m.id] = m
        self.providers = providers

    @classmethod
    def from_yaml(cls, path: str | Path) -> ModelRegistry:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        parsed = RegistryFile.model_validate(raw)
        return cls(parsed.models, parsed.providers)

    def get(self, model_id: str) -> ModelSpec:
        try:
            return self._models[model_id]
        except KeyError:
            raise KeyError(f"Model not in registry: {model_id}") from None

    def __contains__(self, model_id: str) -> bool:
        return model_id in self._models

    def all(self) -> list[ModelSpec]:
        return list(self._models.values())

    def candidates(self, request: RouteRequest | None = None, input_tokens: int = 0) -> list[ModelSpec]:
        """Active candidate models that satisfy the request's hard constraints."""
        out = []
        for m in self._models.values():
            if m.status != "active" or not m.candidate:
                continue
            if request is not None:
                if request.allow_vendors is not None and m.vendor not in request.allow_vendors:
                    continue
                if m.vendor in request.block_vendors:
                    continue
                if request.needs_vision and not m.features.vision:
                    continue
                if request.needs_tools and not m.features.tools:
                    continue
            if input_tokens and input_tokens >= m.limits.context_window:
                continue
            out.append(m)
        return out

    def with_overrides(self, model_id: str, **fields: object) -> ModelRegistry:
        """Return a copy with one model's fields replaced (used by pricing sync and tests)."""
        models = [
            ModelSpec.model_validate({**m.model_dump(), **fields}) if m.id == model_id else m
            for m in self._models.values()
        ]
        return ModelRegistry(models, self.providers)
