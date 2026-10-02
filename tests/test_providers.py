import json

import httpx
import pytest

from app.executor import Executor
from app.models.schemas import Message, RouteDecision, RouteRequest
from app.providers.anthropic import AnthropicProvider
from app.providers.base import (
    AuthError,
    ContextOverflow,
    InvalidRequest,
    ModelUnavailable,
    ProviderOutage,
    RateLimited,
    classify_http_error,
)
from app.providers.caching import CachingProvider
from app.providers.factory import ProviderPool
from app.providers.mock import MockProvider
from app.providers.openai_compatible import OpenAICompatibleProvider

MSGS = [Message(role="system", content="be brief"), Message(role="user", content="hi")]


def transport(status: int, body: dict, seen: list | None = None) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=body)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_openai_compatible_success(registry):
    seen: list[httpx.Request] = []
    body = {"choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}}
    p = OpenAICompatibleProvider("x", "https://api.test/v1", "k", transport(200, body, seen))
    r = await p.generate(MSGS, registry.get("mid"), json_mode=True, max_output_tokens=50)
    assert r.text == "hello" and r.usage.total_cost == pytest.approx(4.75)
    sent = json.loads(seen[0].content)
    assert seen[0].url == "https://api.test/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer k"
    assert sent["response_format"] == {"type": "json_object"} and sent["max_tokens"] == 50


async def test_openai_compatible_error_in_200_body(registry):
    p = OpenAICompatibleProvider("x", "https://api.test/v1", "k",
                                 transport(200, {"error": {"code": 429, "message": "busy"}}))
    with pytest.raises(RateLimited):
        await p.generate(MSGS, registry.get("mid"))


async def test_anthropic_success_and_system_prompt(registry):
    seen: list[httpx.Request] = []
    body = {"content": [{"type": "text", "text": "hey"}], "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 5}}
    p = AnthropicProvider("a", "https://api.test", "k", transport(200, body, seen))
    r = await p.generate(MSGS, registry.get("frontier"))
    sent = json.loads(seen[0].content)
    assert r.text == "hey" and r.usage.input_tokens == 10
    assert sent["system"] == "be brief" and sent["messages"] == [{"role": "user", "content": "hi"}]
    assert seen[0].headers["x-api-key"] == "k"


async def test_anthropic_overloaded_is_outage(registry):
    p = AnthropicProvider("a", "https://api.test", "k", transport(529, {"error": "overloaded"}))
    with pytest.raises(ProviderOutage):
        await p.generate(MSGS, registry.get("frontier"))


@pytest.mark.parametrize("status,body,expected", [
    (429, "", RateLimited), (401, "", AuthError), (404, "", ModelUnavailable), (503, "", ProviderOutage),
    (400, "prompt is too long", ContextOverflow), (400, "bad field", InvalidRequest),
])
def test_classify_http_error(status, body, expected):
    assert isinstance(classify_http_error(status, body), expected)


# --------------------------------------------------------------------------- executor / fallbacks


def decision(model_id, fallbacks):
    return RouteDecision(router="t", model_id=model_id, confidence=1, reason="", fallbacks=fallbacks)


async def test_executor_falls_back_on_outage(registry, config):
    mock = MockProvider(failures={"cheap": ProviderOutage("down")})
    ex = Executor(registry, ProviderPool(registry, {"mock": mock}), config)
    r = await ex.execute(RouteRequest.from_prompt("hi"), decision("cheap", ["mid", "frontier"]))
    assert r.ok and r.result.model_id == "mid" and r.fallback_used
    assert r.attempts == ["cheap", "mid"] and "provider_outage" in r.errors[0]


async def test_executor_stops_on_invalid_request(registry, config):
    mock = MockProvider(failures={"cheap": InvalidRequest("bad")})
    ex = Executor(registry, ProviderPool(registry, {"mock": mock}), config)
    r = await ex.execute(RouteRequest.from_prompt("hi"), decision("cheap", ["mid"]))
    assert not r.ok and r.attempts == ["cheap"]


async def test_executor_context_overflow_skips_smaller_models(registry, config):
    reg = registry.with_overrides("frontier", limits={"context_window": 1_000_000, "max_output_tokens": 8000})
    mock = MockProvider(failures={"cheap": ContextOverflow("too long")})
    ex = Executor(reg, ProviderPool(reg, {"mock": mock}), config)
    r = await ex.execute(RouteRequest.from_prompt("hi"), decision("cheap", ["mid", "frontier"]))
    assert r.result.model_id == "frontier" and r.attempts == ["cheap", "frontier"]


async def test_executor_respects_cost_cap_and_max_attempts(registry, config):
    config.fallback.max_cost_per_request = 0.001
    mock = MockProvider(failures={"cheap": ProviderOutage("x"), "mid": ProviderOutage("x")})
    ex = Executor(registry, ProviderPool(registry, {"mock": mock}), config)
    r = await ex.execute(RouteRequest.from_prompt("hi"), decision("cheap", ["mid", "frontier"]))
    assert "frontier" not in r.attempts  # too expensive under the cap
    assert not r.ok


async def test_caching_provider_reuses_responses(registry, tmp_path):
    mock = MockProvider()
    cached = CachingProvider(mock, tmp_path)
    a = await cached.generate(MSGS, registry.get("mid"))
    b = await cached.generate(MSGS, registry.get("mid"))
    assert a.text == b.text and mock.calls == ["mid"] and cached.hits == 1
    # Prices are re-applied from the current registry on cache hits.
    repriced = registry.with_overrides("mid", pricing={"input_per_million": 0, "output_per_million": 0}).get("mid")
    c = await cached.generate(MSGS, repriced)
    assert c.usage.total_cost == 0
