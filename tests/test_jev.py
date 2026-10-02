"""Jev router tests. The real DecisionsClient runs against a mocked HTTP transport."""

import json

import httpx
import pytest

from app.models.schemas import RouteRequest
from app.providers.decisions import DecisionsClient
from app.router.baselines import RulesRouter
from app.router.jev import LEVELS, OUTPUT_LENGTH, JevRouter, build_questions, build_state


def answers(level: int, *, task_type="reasoning", length=1, confidence=0.95, sufficient=None) -> dict:
    """Decisions API answers: every requirement at `level` (0-4), plus per-tier Nouls."""
    out = {
        "task_type": {"type": "choice", "choice": task_type, "confidence": confidence,
                      "probabilities": {task_type: 1.0}},
        "output_length": {"type": "score", "score": length, "confidence": confidence},
    }
    for name in LEVELS:
        out[name] = {"type": "score", "score": level, "confidence": confidence}
    for tier, p in (sufficient or {"cheap": 0.5, "mid": 0.5, "frontier": 0.5}).items():
        out[f"sufficient_{tier}"] = {"type": "noul", "noul": p}
    return out


def client(status=200, body=None, seen=None, cache_dir=None) -> DecisionsClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=body)
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return DecisionsClient("https://openrouter.test/api/alpha", "key", client=http, cache_dir=cache_dir)


def response(ans: dict) -> dict:
    return {"id": "gen-dec-1", "model": "typesafe/jev-1.13-20260917", "provider": "TypeSafe", "answers": ans,
            "usage": {"input_tokens": 900, "output_tokens": 80, "cost": 0.0000378}}


def router(registry, config, body, decision="profile", **kw):
    return JevRouter(client(body=body, **kw), registry.get("selector"), config, RulesRouter(config.rules), decision)


async def test_request_shape_follows_decisions_api(registry, config):
    seen: list[httpx.Request] = []
    r = router(registry, config, response(answers(0)), seen=seen)
    await r.route(RouteRequest.from_prompt("Translate 'hola' into English"), registry.candidates())
    req = seen[0]
    sent = json.loads(req.content)
    assert str(req.url) == "https://openrouter.test/api/alpha/decisions"
    assert req.headers["authorization"] == "Bearer key"
    assert sent["model"] == "selector"
    assert sent["state"] == {"user_request": "Translate 'hola' into English"}
    q = sent["questions"]
    assert q["task_type"]["type"] == "choice" and "translation" in q["task_type"]["criteria"]
    assert q["reasoning"]["type"] == "score" and len(q["reasoning"]["criteria"]) == 5
    assert set(k for k in q if k.startswith("sufficient_")) == {"sufficient_cheap", "sufficient_mid", "sufficient_frontier"}
    assert set(q["sufficient_cheap"]["criteria"]) == {"true", "false"}


async def test_profile_mode_easy_task_goes_cheap(registry, config):
    d = await router(registry, config, response(answers(0, task_type="translation"))).route(
        RouteRequest.from_prompt("x"), registry.candidates())
    assert d.model_id == "cheap" and d.router == "jev-profile" and not d.escalated
    assert d.profile.task_type.value == "translation" and d.profile.reasoning == 0
    assert d.router_usage.total_cost == pytest.approx(0.0000378)  # billed cost from the API
    assert d.router_model == "selector"


async def test_profile_mode_hard_task_goes_frontier(registry, config):
    d = await router(registry, config, response(answers(4))).route(RouteRequest.from_prompt("x"), registry.candidates())
    assert d.model_id == "frontier"


async def test_output_length_maps_to_configured_tokens(registry, config):
    d = await router(registry, config, response(answers(0, length=3))).route(
        RouteRequest.from_prompt("x"), registry.candidates())
    assert d.profile.expected_output_tokens == config.jev.output_tokens_by_level[3]


async def test_sufficiency_mode_picks_cheapest_sufficient_tier(registry, config):
    body = response(answers(2, sufficient={"cheap": 0.40, "mid": 0.91, "frontier": 0.99}))
    d = await router(registry, config, body, decision="sufficiency").route(
        RouteRequest.from_prompt("x"), registry.candidates())
    assert d.model_id == "mid" and d.router == "jev-sufficiency"
    assert d.fallbacks[0] == "frontier"
    assert "mid 0.91" in d.reason


async def test_sufficiency_mode_no_tier_sufficient_takes_most_likely(registry, config):
    body = response(answers(2, sufficient={"cheap": 0.2, "mid": 0.5, "frontier": 0.7}))
    d = await router(registry, config, body, decision="sufficiency").route(
        RouteRequest.from_prompt("x"), registry.candidates())
    assert d.model_id == "frontier"


async def test_low_confidence_escalates(registry, config):
    d = await router(registry, config, response(answers(0, confidence=0.5))).route(
        RouteRequest.from_prompt("x"), registry.candidates())
    assert d.model_id == "frontier" and d.escalated and d.fallbacks[0] == "cheap"


async def test_mid_confidence_moves_up_one_tier(registry, config):
    d = await router(registry, config, response(answers(0, confidence=0.8))).route(
        RouteRequest.from_prompt("x"), registry.candidates())
    assert d.model_id == "mid" and d.escalated


@pytest.mark.parametrize("status", [429, 500, 401])
async def test_api_failure_falls_back_to_most_capable(registry, config, status):
    d = await router(registry, config, {"error": {"message": "nope"}}, status=status).route(
        RouteRequest.from_prompt("hello"), registry.candidates())
    assert d.router_error and d.confidence == 0.0 and d.model_id == "frontier"


async def test_missing_or_invalid_answers_fall_back(registry, config):
    ans = answers(0)
    del ans["coding"]
    d = await router(registry, config, response(ans)).route(RouteRequest.from_prompt("x"), registry.candidates())
    assert "missing answers" in d.router_error and d.model_id == "frontier"

    bad = answers(0, task_type="astrology")
    d = await router(registry, config, response(bad)).route(RouteRequest.from_prompt("x"), registry.candidates())
    assert "unknown task_type" in d.router_error


async def test_decisions_cache(registry, config, tmp_path):
    seen: list[httpx.Request] = []
    r = router(registry, config, response(answers(0)), seen=seen, cache_dir=tmp_path)
    for _ in range(2):
        await r.route(RouteRequest.from_prompt("same prompt"), registry.candidates())
    assert len(seen) == 1


def test_state_truncation_and_questions_only_for_present_tiers(config):
    state = build_state(RouteRequest.from_prompt("a" * 50), max_chars=10)
    assert state["user_request"] == "a" * 10 and "cut short" in state["note"]
    q = build_questions(["cheap", "frontier"], config.jev.tier_descriptions)
    assert "sufficient_mid" not in q and "sufficient_frontier" in q
    assert len(q["output_length"].criteria) == len(OUTPUT_LENGTH[1]) == len(config.jev.output_tokens_by_level)
