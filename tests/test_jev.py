"""Jev router tests. The real DecisionsClient runs against a mocked HTTP transport."""

import json

import httpx
import pytest

from app.models.schemas import RouteRequest
from app.providers.decisions import DecisionsClient
from app.router.baselines import RulesRouter
from app.router.jev import LEVELS, OUTPUT_LENGTH, JevRouter, build_questions, build_state, model_choice


def answers(level: int, *, task_type="reasoning", length=1, confidence=0.95, sufficient=None,
            model="mid", model_probs=None, model_confidence=0.9) -> dict:
    """Decisions API answers: every requirement at `level` (0-4), per-tier Nouls and a model Choice."""
    out = {
        "model": {"type": "choice", "choice": model, "confidence": model_confidence,
                  "probabilities": model_probs or {model: 1.0}},
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
    assert q["model"]["type"] == "choice"
    assert list(q["model"]["criteria"]) == ["cheap", "mid", "frontier"]  # cheapest first


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


# --------------------------------------------------------------------------- choice style


async def test_choice_mode_uses_jevs_pick_and_probability_order(registry, config):
    body = response(answers(2, model="mid", model_probs={"mid": 0.7, "frontier": 0.25, "cheap": 0.05}))
    d = await router(registry, config, body, decision="choice").route(
        RouteRequest.from_prompt("x"), registry.candidates())
    assert d.router == "jev-choice" and d.model_id == "mid" and not d.escalated
    assert d.fallbacks == ["frontier", "cheap"]
    assert d.confidence == 0.9 and "Jev chose mid" in d.reason


async def test_choice_mode_low_confidence_escalates_within_plausible(registry, config):
    probs = {"cheap": 0.6, "mid": 0.3, "frontier": 0.1}
    body = response(answers(0, model="cheap", model_probs=probs, model_confidence=0.6))
    d = await router(registry, config, body, decision="choice").route(
        RouteRequest.from_prompt("x"), registry.candidates())
    assert d.model_id == "frontier" and d.escalated

    probs = {"cheap": 0.7, "mid": 0.28, "frontier": 0.02}  # Jev ruled frontier out
    body = response(answers(0, model="cheap", model_probs=probs, model_confidence=0.6))
    d = await router(registry, config, body, decision="choice").route(
        RouteRequest.from_prompt("x"), registry.candidates())
    assert d.model_id == "mid" and "plausible" in d.reason


async def test_choice_mode_unknown_model_falls_back(registry, config):
    body = response(answers(0, model="gpt-99"))
    d = await router(registry, config, body, decision="choice").route(
        RouteRequest.from_prompt("x"), registry.candidates())
    assert "unknown model" in d.router_error and d.model_id == "frontier"


def test_model_choice_describes_price_and_relative_cost(registry, config):
    reg = registry.with_overrides("mid", description="Good at writing.")
    q = model_choice(RouteRequest.from_prompt("hello"), reg.candidates(), config.jev.choice_instructions["auto"], 500)
    assert "cheapest model" in q.instructions
    assert "the cheapest option for this request" in q.criteria["cheap"]
    assert q.criteria["mid"].startswith("Good at writing. Price: $0.75 per million input tokens and $4 per million")
    assert "x the cost of the cheapest option" in q.criteria["frontier"]


def test_choice_instructions_follow_mode(registry, config):
    cands = registry.candidates()
    best = model_choice(RouteRequest.from_prompt("x", mode="best"), cands, config.jev.choice_instructions["best"], 500)
    assert "regardless of price" in best.instructions


def test_low_confidence_stays_within_jevs_plausible_models(config):
    """Replays a real Jev decision for 'Prove there are infinitely many primes' (confidence 0.55)."""
    from app.config import CONFIG_DIR
    from app.models.registry import ModelRegistry
    from app.models.schemas import CandidateScore
    from app.router.policies import apply_confidence

    reg = ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
    probs = {
        "google/gemini-3.1-flash-lite": 0.61, "google/gemini-3.8-flash": 0.17, "openai/gpt-5.4-mini": 0.10,
        "anthropic/claude-haiku-4.5": 0.10, "anthropic/claude-sonnet-5.5": 0.02,
        "anthropic/claude-opus-5.5": 0.0, "anthropic/claude-fable-5.1": 0.0,
    }
    ranked = [CandidateScore(model_id=m, p_success=p, est_cost=0, est_latency_ms=0, utility=p)
              for m, p in sorted(probs.items(), key=lambda kv: -kv[1])]
    chosen, note = apply_confidence("google/gemini-3.1-flash-lite", 0.55, ranked, reg.candidates(),
                                    config.confidence, probs)
    assert chosen in {"google/gemini-3.8-flash", "openai/gpt-5.4-mini", "anthropic/claude-haiku-4.5"}
    assert "plausible" in note

    literal = config.confidence.model_copy(update={"respect_router_distribution": False})
    chosen, _ = apply_confidence("google/gemini-3.1-flash-lite", 0.55, ranked, reg.candidates(), literal, probs)
    assert chosen == "anthropic/claude-fable-5.1"  # the old behaviour


async def test_raw_variant_keeps_jevs_pick(registry, config):
    from app.service import build_router
    probs = {"cheap": 0.6, "mid": 0.3, "frontier": 0.1}
    body = response(answers(0, model="cheap", model_probs=probs, model_confidence=0.3))
    raw = JevRouter(client(body=body), registry.get("selector"), config, RulesRouter(config.rules),
                    decision="choice", escalate=False)
    d = await raw.route(RouteRequest.from_prompt("x"), registry.candidates())
    assert raw.name == "jev-choice-raw" and d.model_id == "cheap" and not d.escalated
    # A Jev failure still goes through the safety policy.
    failing = JevRouter(client(status=500, body={}), registry.get("selector"), config, RulesRouter(config.rules),
                        decision="choice", escalate=False)
    d = await failing.route(RouteRequest.from_prompt("x"), registry.candidates())
    assert d.model_id == "frontier"
    from app.config import CONFIG_DIR
    from app.models.registry import ModelRegistry
    shipped = ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
    for name in ("jev-choice-raw", "jev-choice", "jev-profile"):
        built = build_router(name, shipped, config)
        assert built.name == name
        await built.aclose()
