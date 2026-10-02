import pytest

from app.config import CONFIG_DIR
from app.models.registry import ModelRegistry
from app.models.schemas import ProviderConfig, RouteRequest
from tests.conftest import spec


def test_shipped_registry_is_valid():
    reg = ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
    candidates = reg.candidates()
    assert len(candidates) >= 3
    assert {m.tier for m in candidates} >= {"cheap", "frontier"}
    for m in reg.all():
        assert m.pricing_checked is not None, f"{m.id} has no pricing_checked date"


def test_candidates_exclude_non_candidates_and_disabled(registry):
    assert [m.id for m in registry.candidates()] == ["cheap", "mid", "frontier"]
    disabled = registry.with_overrides("mid", status="disabled")
    assert "mid" not in [m.id for m in disabled.candidates()]


def test_candidates_apply_vendor_policy(registry):
    blocked = RouteRequest.from_prompt("hi", block_vendors=["bigco"])
    assert "frontier" not in [m.id for m in registry.candidates(blocked)]
    allowed = RouteRequest.from_prompt("hi", allow_vendors=["bigco"])
    assert [m.id for m in registry.candidates(allowed)] == ["frontier"]


def test_candidates_respect_context_window(registry):
    big = registry.with_overrides("frontier", limits={"context_window": 10_000_000, "max_output_tokens": 8000})
    assert [m.id for m in big.candidates(input_tokens=500_000)] == ["frontier"]


def test_duplicate_and_unknown_provider_rejected():
    providers = {"mock": ProviderConfig(adapter="mock")}
    with pytest.raises(ValueError, match="Duplicate"):
        ModelRegistry([spec("a", "cheap", 0.5, 1, 1), spec("a", "cheap", 0.5, 1, 1)], providers)
    with pytest.raises(ValueError, match="unknown provider"):
        ModelRegistry([spec("a", "cheap", 0.5, 1, 1).model_copy(update={"provider": "nope"})], providers)


def test_pricing_cost():
    m = spec("a", "cheap", 0.5, 2.0, 10.0)
    assert m.pricing.cost(1_000_000, 500_000) == (2.0, 5.0)
