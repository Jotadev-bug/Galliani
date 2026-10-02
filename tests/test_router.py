import json

from app.models.schemas import Message, RouteRequest, TaskProfile, TaskType
from app.providers.base import RateLimited
from app.providers.mock import MockProvider
from app.router import scoring
from app.router.baselines import FixedRouter, RandomRouter, RulesRouter, classify
from app.router.base import decide_from_profile
from app.router.jeb import JEBRouter, parse_output
from app.router.policies import apply_confidence


def profile(level: float, task_type=TaskType.reasoning, out_tokens=300) -> TaskProfile:
    """A reasoning-heavy task: `level` on reasoning and precision, half of it elsewhere."""
    return TaskProfile(
        task_type=task_type, reasoning=level, coding=level / 2, writing=level / 2, knowledge=level / 2,
        precision=level, expected_output_tokens=out_tokens,
    )


def jeb_reply(level: float, confidence: float, **extra) -> str:
    return json.dumps({
        "task_type": "reasoning", "reasoning": level, "coding": level, "writing": level, "knowledge": level,
        "precision": level, "expected_output_tokens": 300, "confidence": confidence, "rationale": "test", **extra,
    })


# --------------------------------------------------------------------------- scoring


def test_easy_task_routes_to_cheapest(registry, config):
    d = decide_from_profile("t", profile(0.1), RouteRequest.from_prompt("hi"), registry.candidates(), config,
                            confidence=1, reason="")
    assert d.model_id == "cheap"


def test_hard_task_routes_to_frontier(registry, config):
    d = decide_from_profile("t", profile(0.9), RouteRequest.from_prompt("x"), registry.candidates(), config,
                            confidence=1, reason="")
    assert d.model_id == "frontier"


def test_medium_task_routes_to_mid(registry, config):
    d = decide_from_profile("t", profile(0.6), RouteRequest.from_prompt("x"), registry.candidates(), config,
                            confidence=1, reason="")
    assert d.model_id == "mid"
    assert set(d.fallbacks) == {"cheap", "frontier"}


def test_best_mode_prefers_quality(registry, config):
    req = RouteRequest.from_prompt("x", mode="best")
    d = decide_from_profile("t", profile(0.5), req, registry.candidates(), config, confidence=1, reason="")
    assert d.model_id == "frontier"


def test_p_success_monotonic_in_skill_and_requirement(registry, config):
    sm = config.success_model
    cheap, frontier = registry.get("cheap"), registry.get("frontier")
    assert scoring.p_success(frontier, profile(0.7), sm) > scoring.p_success(cheap, profile(0.7), sm)
    assert scoring.p_success(cheap, profile(0.2), sm) > scoring.p_success(cheap, profile(0.7), sm)


def test_rank_falls_back_to_most_likely_when_none_capable(registry, config):
    weights = config.modes["auto"].model_copy(update={"min_success": 1.0})
    scores = scoring.score_candidates(registry.candidates(), profile(0.5), 100, weights, config.success_model)
    assert scoring.rank(scores, 1.0)[0].model_id == "frontier"


# --------------------------------------------------------------------------- confidence policy


def _ranked(registry, config, level):
    return decide_from_profile("t", profile(level), RouteRequest.from_prompt("x"), registry.candidates(), config,
                               confidence=1, reason="").scores


def test_confidence_bands(registry, config):
    ranked, cands, pol = _ranked(registry, config, 0.1), registry.candidates(), config.confidence
    assert apply_confidence("cheap", 0.95, ranked, cands, pol) == ("cheap", None)
    assert apply_confidence("cheap", 0.80, ranked, cands, pol)[0] == "mid"
    assert apply_confidence("cheap", 0.50, ranked, cands, pol)[0] == "frontier"
    assert apply_confidence("frontier", 0.80, ranked, cands, pol) == ("frontier", None)


# --------------------------------------------------------------------------- JEB


def make_jeb(registry, config, reply, failures=None):
    selector = MockProvider(responder=lambda msgs, model: reply, failures=failures)
    return JEBRouter(selector, registry.get("selector"), config, RulesRouter(config.rules)), selector


async def test_jeb_profile_mode_easy_task(registry, config):
    jeb, selector = make_jeb(registry, config, jeb_reply(0.1, 0.95))
    d = await jeb.route(RouteRequest.from_prompt("translate hola"), registry.candidates())
    assert d.model_id == "cheap" and not d.escalated
    assert d.router == "jeb" and d.router_model == "selector"
    assert d.router_usage.total_cost > 0
    assert selector.calls == ["selector"]


async def test_jeb_low_confidence_escalates(registry, config):
    jeb, _ = make_jeb(registry, config, jeb_reply(0.1, 0.5))
    d = await jeb.route(RouteRequest.from_prompt("x"), registry.candidates())
    assert d.model_id == "frontier" and d.escalated
    assert d.fallbacks[0] == "cheap"


async def test_jeb_direct_mode_uses_recommendation(registry, config):
    config.jeb.decision = "direct"
    jeb, _ = make_jeb(registry, config, jeb_reply(0.1, 0.95, recommended_model="mid"))
    d = await jeb.route(RouteRequest.from_prompt("x"), registry.candidates())
    assert d.model_id == "mid"


async def test_jeb_direct_mode_ignores_unknown_model(registry, config):
    config.jeb.decision = "direct"
    jeb, _ = make_jeb(registry, config, jeb_reply(0.1, 0.95, recommended_model="gpt-99"))
    d = await jeb.route(RouteRequest.from_prompt("x"), registry.candidates())
    assert d.model_id == "cheap" and "unknown model" in d.reason


async def test_jeb_garbage_output_falls_back_safely(registry, config):
    jeb, _ = make_jeb(registry, config, "Sure! I think you should use a big model.")
    d = await jeb.route(RouteRequest.from_prompt("hello"), registry.candidates())
    assert d.router_error and "JEBParseError" in d.router_error
    assert d.confidence == 0.0 and d.model_id == "frontier"


async def test_jeb_provider_failure_falls_back_safely(registry, config):
    jeb, _ = make_jeb(registry, config, "", failures={"selector": RateLimited("slow down")})
    d = await jeb.route(RouteRequest.from_prompt("hello"), registry.candidates())
    assert "RateLimited" in d.router_error and d.model_id == "frontier"


def test_parse_output_accepts_fenced_json():
    out = parse_output("```json\n" + jeb_reply(0.3, 0.8) + "\n```")
    assert out.confidence == 0.8 and out.profile().reasoning == 0.3


def test_jeb_prompt_wraps_and_truncates_task(registry):
    from app.router.jeb import MAX_TASK_CHARS, build_messages
    msgs = build_messages(RouteRequest.from_prompt("a" * (MAX_TASK_CHARS + 100)), registry.candidates(), False)
    assert msgs[0].role == "system" and "NOT to solve" in msgs[0].content
    assert msgs[1].content.startswith("<task>") and "truncated" in msgs[1].content
    direct = build_messages(RouteRequest.from_prompt("x"), registry.candidates(), True)
    assert "recommended_model" in direct[0].content and "frontier" in direct[0].content


# --------------------------------------------------------------------------- baselines


def test_classify_keywords():
    assert classify("Fix this bug: IndexError traceback") == TaskType.debugging
    assert classify("Write a Python function that sorts") == TaskType.coding
    assert classify("Traduce al inglés: hola") == TaskType.translation
    assert classify("Resume este texto") == TaskType.summarization
    assert classify("hello there") == TaskType.conversation


async def test_rules_router_tiers(registry, config):
    r = RulesRouter(config.rules)
    cands = registry.candidates()
    assert (await r.route(RouteRequest.from_prompt("hello"), cands)).model_id == "cheap"
    # coding -> strong tier; no strong model exists, so the nearest higher tier (frontier) is used
    assert (await r.route(RouteRequest.from_prompt("write a python function"), cands)).model_id == "frontier"
    assert (await r.route(RouteRequest.from_prompt("write an email to my boss"), cands)).model_id == "mid"


async def test_fixed_and_random(registry):
    cands = registry.candidates()
    assert (await FixedRouter("frontier").route(RouteRequest.from_prompt("x"), cands)).model_id == "frontier"
    rnd = RandomRouter(1)
    picks = {(await rnd.route(RouteRequest.from_prompt("x"), cands)).model_id for _ in range(30)}
    assert picks == {"cheap", "mid", "frontier"}


def test_message_roles_validated():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Message(role="robot", content="x")
    with pytest.raises(ValidationError):
        RouteRequest(messages=[])
