from __future__ import annotations

import pytest

from app.config import CONFIG_DIR, load_routing_config
from app.models.registry import ModelRegistry
from app.models.schemas import ModelSpec, ProviderConfig


def spec(model_id: str, tier: str, skill: float, price_in: float, price_out: float, **kw) -> ModelSpec:
    return ModelSpec.model_validate({
        "id": model_id, "provider": "mock", "vendor": kw.pop("vendor", "acme"), "tier": tier,
        "skills": {d: skill for d in ("reasoning", "coding", "writing", "knowledge", "instruction_following")},
        "pricing": {"input_per_million": price_in, "output_per_million": price_out},
        "latency": {"ttft_ms": 300 + 1000 * skill, "tokens_per_second": 200 - 100 * skill},
        "limits": {"context_window": kw.pop("context_window", 100_000), "max_output_tokens": 8000},
        **kw,
    })


@pytest.fixture
def registry() -> ModelRegistry:
    models = [
        spec("cheap", "cheap", 0.55, 0.1, 0.4),
        spec("mid", "mid", 0.75, 0.75, 4.0),
        spec("frontier", "frontier", 0.95, 4.0, 20.0, vendor="bigco"),
        spec("selector", "cheap", 0.5, 0.05, 0.4, candidate=False),
    ]
    return ModelRegistry(models, {"mock": ProviderConfig(adapter="mock")})


@pytest.fixture
def config():
    return load_routing_config(CONFIG_DIR / "routing.yaml").model_copy(deep=True)
