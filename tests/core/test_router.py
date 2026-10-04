"""Spec 003 - Model Router and provider adapter acceptance criteria."""

from __future__ import annotations

import pytest

from galliani.adapters import AdapterError, WorkerRequest
from galliani.router import InputShape, ModelRouter, ModelWorkRequest, RouteError, RoutingPolicy, WorkerProfile
from galliani.testing import ScriptedAdapter, ScriptedChatAdapter


def profile(worker_id: str, caps: set[str], cost: str = "low", latency: str = "fast", **kw) -> dict:
    return {"worker_id": worker_id, "provider_id": kw.pop("provider_id", "p1"), "capabilities": caps,
            "limits": {"context_window": kw.pop("context_window", 8_000), "max_output_tokens": 1_000},
            "cost_class": cost, "latency_class": latency, **kw}


def req(*caps: str, **kw) -> ModelWorkRequest:
    return ModelWorkRequest(task_id="t", step_id="s1", capability=set(caps), **kw)


# AC: Capability Match
def test_selects_worker_advertising_all_required_capabilities():
    router = ModelRouter([
        profile("text_only", {"text"}),
        profile("tools_short", {"text", "tool_use"}),
        profile("tools_long", {"text", "tool_use", "long_context"}, cost="high", context_window=200_000),
    ])
    route = router.route(req("tool_use", "long_context"))
    assert route.worker_id == "tools_long"
    assert "tool_use" in route.rationale and "long_context" in route.rationale


def test_ranks_by_strategy():
    router = ModelRouter([profile("cheap_slow", {"text"}, "low", "slow"), profile("pricey_fast", {"text"}, "high", "fast")])
    assert router.route(req("text")).worker_id == "cheap_slow"
    assert router.route(req("text", policy=RoutingPolicy(strategy="fastest"))).worker_id == "pricey_fast"


def test_context_size_filters_workers():
    router = ModelRouter([profile("small", {"text"}, context_window=1_000)])
    with pytest.raises(RouteError) as e:
        router.route(req("text", input_shape=InputShape(estimated_tokens=5_000)))
    assert e.value.code == "no_route"


# AC: Fallback
def test_unavailable_preferred_worker_falls_back_and_records_reason():
    router = ModelRouter([
        profile("preferred", {"text"}, "low", availability="unavailable"),
        profile("backup", {"text"}, "medium"),
        profile("backup2", {"text"}, "high"),
    ])
    route = router.route(req("text"))
    assert route.worker_id == "backup" and route.fallback_worker_ids == ["backup2"]
    assert "Preferred preferred is unavailable" in route.rationale


# AC: No Route
def test_no_compatible_worker_is_structured_no_route():
    with pytest.raises(RouteError) as e:
        ModelRouter([profile("w", {"text"})]).route(req("vision"))
    assert e.value.code == "no_route" and e.value.safe_summary


def test_policy_violation_is_route_denied():
    router = ModelRouter([profile("w", {"text"}, policy_tags={"external"})])
    with pytest.raises(RouteError) as e:
        router.route(req("text", policy=RoutingPolicy(denied_tags={"external"})))
    assert e.value.code == "route_denied"


def test_all_unavailable_is_provider_unavailable():
    with pytest.raises(RouteError) as e:
        ModelRouter([profile("w", {"text"}, availability="unavailable")]).route(req("text"))
    assert e.value.code == "provider_unavailable"


def test_malformed_profiles_are_ignored_and_logged():
    router = ModelRouter([profile("good", {"text"}), {"worker_id": "bad", "capabilities": "nope"}])
    assert list(router.profiles) == ["good"]
    assert "bad" in router.ignored[0]


def test_profile_accepts_model_instances():
    p = WorkerProfile.model_validate(profile("w", {"text"}))
    assert ModelRouter([p]).route(req("text")).provider_adapter_id == "p1"


# Adapter normalization contract (000 AC Privacy Boundary)
@pytest.mark.parametrize("adapter_cls", [ScriptedAdapter, ScriptedChatAdapter])
async def test_adapters_normalize_and_discard_hidden_reasoning(adapter_cls):
    adapter = adapter_cls("a", {"w": [{"output": "hello", "structured": {"x": 1, "thinking": "hidden"},
                                       "reasoning": "TOP SECRET REASONING"}]})
    response = await adapter.invoke(WorkerRequest(task_id="t", step_id="s", worker_id="w", instruction="hi"))
    assert response.output == "hello" and response.structured == {"x": 1}
    assert "TOP SECRET REASONING" not in response.model_dump_json()


async def test_adapter_errors_are_normalized_with_fallback_eligibility():
    adapter = ScriptedAdapter("a", {"w": [{"error": "provider_unavailable"}, {"error": "invalid_request"}]})
    request = WorkerRequest(task_id="t", step_id="s", worker_id="w", instruction="hi")
    with pytest.raises(AdapterError) as e1:
        await adapter.invoke(request)
    assert e1.value.fallback_eligible
    with pytest.raises(AdapterError) as e2:
        await adapter.invoke(request)
    assert not e2.value.fallback_eligible


async def test_native_exceptions_and_unreadable_responses_are_normalized():
    class Broken(ScriptedAdapter):
        async def send(self, request):
            raise ConnectionError("socket to https://internal-host refused")

    class Garbled(ScriptedAdapter):
        async def send(self, request):
            return {"unexpected": True}

    request = WorkerRequest(task_id="t", step_id="s", worker_id="w", instruction="hi")
    with pytest.raises(AdapterError) as e:
        await Broken("b", {}).invoke(request)
    assert "internal-host" not in e.value.safe_summary
    with pytest.raises(AdapterError) as e:
        await Garbled("g", {}).invoke(request)
    assert e.value.code == "malformed_response"
