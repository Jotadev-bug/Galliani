"""API tests with Jev and generation mocked: no network, no cost."""

import pytest
from fastapi.testclient import TestClient

import app.api.routes as routes
from app.models.schemas import CandidateScore, RouteDecision, Usage
from app.providers.base import InsufficientCredits
from app.providers.factory import ProviderPool
from app.providers.mock import MockProvider
from app.router.base import Router
from app.telemetry.costs import JsonlSink

CHEAP = "google/gemini-3.1-flash-lite"


class FakeJev(Router):
    name = "jev-choice"

    def __init__(self):
        self.seen = []

    async def route(self, request, candidates):
        self.seen.append(request)
        ids = [m.id for m in candidates]
        return RouteDecision(
            router=self.name, model_id=CHEAP, confidence=0.93, reason="translation; simple",
            fallbacks=[i for i in ids if i != CHEAP],
            scores=[CandidateScore(model_id=i, p_success=0.9 if i == CHEAP else 0.01, est_cost=0.001,
                                   est_latency_ms=100, utility=0) for i in ids],
            router_usage=Usage(input_tokens=900, input_cost=0.0001), router_latency_ms=120,
        )


@pytest.fixture
def api(monkeypatch, tmp_path):
    jev = FakeJev()
    keys_seen: list[dict] = []
    mock = MockProvider(responder=lambda msgs, model: f"answer from {model.id}")

    def fake_build_router(name, registry, config, keys=None, **kw):
        keys_seen.append(keys)
        return jev

    def fake_pool(registry, keys=None, **kw):
        keys_seen.append(keys)
        return ProviderPool(registry, overrides={"openrouter": mock})

    monkeypatch.setattr(routes, "build_router", fake_build_router)
    monkeypatch.setattr(routes, "ProviderPool", fake_pool)
    monkeypatch.setattr(routes, "SINK", JsonlSink(tmp_path / "log.jsonl"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "server-key")
    client = TestClient(routes.app)
    client.jev, client.mock, client.keys_seen, client.log = jev, mock, keys_seen, tmp_path / "log.jsonl"
    return client


def body(text="Translate 'hola'", **kw):
    return {"messages": [{"role": "user", "content": text}], **kw}


def test_index_and_config(api):
    assert "Jev picks the right model" in api.get("/").text
    cfg = api.get("/api/config").json()
    assert cfg["modes"] == ["auto", "cheapest", "fastest", "best"]
    assert cfg["server_key"] is True and cfg["router_model"] == "typesafe/jev-1.13"
    assert any(m["id"] == "anthropic/claude-fable-5.1" for m in cfg["models"])


def test_route_only_does_not_generate(api):
    r = api.post("/api/route", json=body()).json()
    assert r["model_id"] == CHEAP and r["confidence"] == 0.93 and len(r["options"]) == 7
    assert api.mock.calls == []


def test_chat_routes_generates_and_reports_savings(api):
    r = api.post("/api/chat", json=body(mode="cheapest"))
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] == f"answer from {CHEAP}" and data["model_id"] == CHEAP
    assert data["route"]["reason"] == "translation; simple"
    assert data["total_cost"] == pytest.approx(data["generation_cost"] + 0.0001)
    assert data["frontier_model"] == "anthropic/claude-fable-5.1"
    assert data["frontier_cost"] > data["generation_cost"]
    assert api.jev.seen[0].mode == "cheapest"


def test_chat_with_planned_route_skips_jev(api):
    plan = {"model_id": "anthropic/claude-haiku-4.5", "fallbacks": [CHEAP, "not/a-model"], "confidence": 0.5}
    data = api.post("/api/chat", json=body(route=plan)).json()
    assert data["model_id"] == "anthropic/claude-haiku-4.5" and data["route"] is None
    assert api.jev.seen == []


def test_planned_route_must_be_a_candidate(api):
    r = api.post("/api/chat", json=body(route={"model_id": "evil/model"}))
    assert r.status_code == 422


def test_caller_key_is_used_and_never_logged(api):
    api.post("/api/chat", json=body(), headers={"X-OpenRouter-Key": "sk-or-tester"})
    assert all(k == {"OPENROUTER_API_KEY": "sk-or-tester"} for k in api.keys_seen)
    log = api.log.read_text(encoding="utf-8")
    assert "sk-or-tester" not in log and "Translate" not in log  # neither key nor prompt stored


def test_missing_key_is_401(api, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    r = api.post("/api/route", json=body())
    assert r.status_code == 401 and "Settings" in r.json()["detail"]


def test_all_models_failing_is_502_with_reasons(api):
    api.mock.failures = {m: InsufficientCredits("requires more credits") for m in [
        CHEAP, "google/gemini-3.8-flash", "openai/gpt-5.4-mini", "anthropic/claude-haiku-4.5",
        "anthropic/claude-sonnet-5.5", "anthropic/claude-opus-5.5", "anthropic/claude-fable-5.1"]}
    r = api.post("/api/chat", json=body())
    assert r.status_code == 502
    assert "insufficient_credits" in r.json()["detail"]["errors"][0]


def test_conversation_history_is_passed_through(api):
    msgs = [{"role": "user", "content": "Write a haiku"}, {"role": "assistant", "content": "..."},
            {"role": "user", "content": "Now in Spanish"}]
    api.post("/api/chat", json={"messages": msgs})
    assert [m.content for m in api.jev.seen[0].messages] == ["Write a haiku", "...", "Now in Spanish"]


def test_validation(api):
    assert api.post("/api/chat", json={"messages": []}).status_code == 422
    assert api.post("/api/chat", json=body(mode="free")).status_code == 422
