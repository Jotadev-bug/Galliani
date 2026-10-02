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


class FakeAnthropic:
    """Stands in for anthropic.AsyncAnthropic: records calls, returns or raises what it is given."""

    def __init__(self, response=None, error=None):
        self.calls = []
        self.response, self.error = response, error
        outer = self

        class _Messages:
            async def create(self, **kw):
                outer.calls.append(kw)
                if outer.error:
                    raise outer.error
                return outer.response

        self.messages = _Messages()
        self.beta = type("Beta", (), {"messages": _Messages()})()

    async def close(self):
        pass


def claude_response(text="hey", stop_reason="end_turn"):
    from types import SimpleNamespace as NS
    return NS(
        content=[NS(type="thinking", thinking=""), NS(type="text", text=text)],
        stop_reason=stop_reason, stop_details=NS(category="cyber") if stop_reason == "refusal" else None,
        usage=NS(input_tokens=10, output_tokens=5, cache_read_input_tokens=2, cache_creation_input_tokens=0),
    )


def claude_spec(registry, refusal_fallback=False):
    from app.models.schemas import DirectRoute
    m = registry.get("frontier")
    return m.model_copy(update={"provider_model": "claude-opus-5-5",
                                "direct": DirectRoute(provider="anthropic", model="claude-opus-5-5",
                                                      refusal_fallback=refusal_fallback)})


async def test_anthropic_success_and_system_prompt(registry):
    fake = FakeAnthropic(claude_response())
    r = await AnthropicProvider("anthropic", "https://api.test", "k", client=fake).generate(MSGS, claude_spec(registry))
    call = fake.calls[0]
    assert r.text == "hey" and r.usage.input_tokens == 12  # cache reads counted as input
    assert call["system"] == "be brief" and call["messages"] == [{"role": "user", "content": "hi"}]
    assert call["model"] == "claude-opus-5-5" and call["max_tokens"] >= 8000
    assert "fallbacks" not in call


async def test_anthropic_refusal_fallback_and_refusal_error(registry):
    from app.providers.base import Refused
    fake = FakeAnthropic(claude_response())
    await AnthropicProvider("anthropic", "", "k", client=fake).generate(MSGS, claude_spec(registry, True))
    assert fake.calls[0]["fallbacks"] == "default" and fake.calls[0]["betas"] == ["server-side-fallback-2026-07-01"]
    refusing = FakeAnthropic(claude_response(stop_reason="refusal"))
    with pytest.raises(Refused, match="cyber"):
        await AnthropicProvider("anthropic", "", "k", client=refusing).generate(MSGS, claude_spec(registry))


@pytest.mark.parametrize("status,expected", [(429, RateLimited), (401, AuthError), (404, ModelUnavailable),
                                             (529, ProviderOutage), (400, InvalidRequest)])
async def test_anthropic_errors_are_mapped(registry, status, expected):
    import anthropic
    import httpx2
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    cls = {429: anthropic.RateLimitError, 401: anthropic.AuthenticationError, 404: anthropic.NotFoundError,
           529: anthropic.OverloadedError, 400: anthropic.BadRequestError}[status]
    err = cls("boom", response=httpx2.Response(status, request=req), body=None)
    with pytest.raises(expected):
        await AnthropicProvider("anthropic", "", "k", client=FakeAnthropic(error=err)).generate(MSGS, claude_spec(registry))


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



# --------------------------------------------------------------------------- direct vendor routes


def direct_registry(registry):
    from app.models.schemas import ProviderConfig
    reg = registry.with_overrides("frontier", direct={"provider": "anthropic", "model": "claude-opus-5-5"})
    reg.providers = {**reg.providers, "anthropic": ProviderConfig(adapter="anthropic", api_key_env="ANTHROPIC_API_KEY")}
    return reg


async def test_direct_route_used_only_with_vendor_key(registry, config, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    reg = direct_registry(registry)
    agg, direct = MockProvider("mock"), MockProvider("anthropic")
    without = Executor(reg, ProviderPool(reg, {"mock": agg}), config)
    r = await without.execute(RouteRequest.from_prompt("hi"), decision("frontier", []))
    assert r.result.provider == "mock" and direct.calls == []

    pool = ProviderPool(reg, {"mock": agg, "anthropic": direct})
    seen = []
    direct.responder = lambda msgs, model: seen.append(model.api_model) or "from anthropic"
    r = await Executor(reg, pool, config).execute(RouteRequest.from_prompt("hi"), decision("frontier", []))
    assert r.result.provider == "anthropic" and r.result.model_id == "frontier" and seen == ["claude-opus-5-5"]


async def test_failed_direct_route_retries_same_model_via_aggregator(registry, config):
    reg = direct_registry(registry)
    direct = MockProvider("anthropic", failures={"frontier": AuthError("bad key")})
    pool = ProviderPool(reg, {"mock": MockProvider("mock"), "anthropic": direct})
    r = await Executor(reg, pool, config).execute(RouteRequest.from_prompt("hi"), decision("frontier", ["mid"]))
    assert r.result.model_id == "frontier" and r.result.provider == "mock"
    assert "via anthropic: auth_error" in r.errors[0] and r.attempts == ["frontier"]


async def test_refusal_stops_without_trying_elsewhere(registry, config):
    from app.providers.base import Refused
    reg = direct_registry(registry)
    agg = MockProvider("mock")
    pool = ProviderPool(reg, {"mock": agg, "anthropic": MockProvider("anthropic", failures={"frontier": Refused("no")})})
    r = await Executor(reg, pool, config).execute(RouteRequest.from_prompt("hi"), decision("frontier", ["mid"]))
    assert not r.ok and agg.calls == [] and "refused" in r.errors[0]
