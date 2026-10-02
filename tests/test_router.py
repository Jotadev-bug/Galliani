from app.models.schemas import Message, RouteRequest, TaskProfile, TaskType
from app.router import scoring
from app.router.baselines import FixedRouter, RandomRouter, RulesRouter, classify
from app.router.base import decide_from_profile
from app.router.policies import apply_confidence


def profile(level: float, task_type=TaskType.reasoning, out_tokens=300) -> TaskProfile:
    """A reasoning-heavy task: `level` on reasoning and precision, half of it elsewhere."""
    return TaskProfile(
        task_type=task_type, reasoning=level, coding=level / 2, writing=level / 2, knowledge=level / 2,
        precision=level, expected_output_tokens=out_tokens,
    )


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
