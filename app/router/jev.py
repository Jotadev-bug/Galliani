"""Jev router: TypeSafe's Jev decision model judges the task; it never answers it.

Jev is not a generative model. It answers typed questions about a `state` with probabilities
(https://docs.typesafe.ai/primitives). One call asks every question at once:

- model                 Choice over the candidate models, each described by its strengths,
                          its $/token price and its cost relative to the cheapest option
- task_type             Choice over TaskType
- reasoning ... precision Score over ordered, descriptive levels -> requirement in [0, 1]
- output_length         Score over length buckets -> token estimate (numbers stay in code)
- sufficient_<tier>     Noul per candidate tier: "would this class of model answer correctly?"

Three decision styles reuse the same answers, so the benchmark compares them at no extra cost:
- choice:      Jev picks the model directly, weighing task against price (the default).
- profile:     the Score answers form a TaskProfile and the utility function picks the model.
- sufficiency: the cheapest tier whose Noul clears min_success wins.

Questions follow Jev's documented failure modes (docs.typesafe.ai/model-jaggedness/jev-1.13):
literal wording, the request named in state, no arithmetic or counting asked of the model.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from app.config import RoutingConfig
from app.models.schemas import (
    CandidateScore,
    ModelSpec,
    RouteDecision,
    RouteRequest,
    TaskProfile,
    TaskType,
    Usage,
)
from app.providers.base import ProviderError, estimate_tokens
from app.providers.decisions import (
    Answer,
    ChoiceQuestion,
    DecisionResult,
    DecisionsClient,
    NoulQuestion,
    Question,
    ScoreQuestion,
)
from app.router import policies, scoring
from app.router.base import NoCandidatesError, Router, decide_from_profile

TASK_TYPES: dict[TaskType, str] = {
    TaskType.conversation: "Chit-chat, greetings, opinions or a simple factual question.",
    TaskType.translation: "Translate text from one language to another.",
    TaskType.summarization: "Shorten or summarize text that is included in the request.",
    TaskType.extraction: "Pull specific fields, values or entities out of text into a list or structure.",
    TaskType.classification: "Assign a label or category (sentiment, topic, language, yes/no) to given text.",
    TaskType.writing: "Write new prose: emails, stories, poems, descriptions, essays.",
    TaskType.reasoning: "Logic puzzles, riddles or multi-step deduction that is not mainly arithmetic.",
    TaskType.math: "Calculate, solve equations, probability, counting or proofs.",
    TaskType.coding: "Write new code or a query in a programming language.",
    TaskType.debugging: "Find or fix a bug in code that is included in the request.",
    TaskType.document_analysis: "Answer questions about a contract, policy, specification or transcript included in the request.",
    TaskType.multimodal_analysis: "Analyse an image, audio or video.",
    TaskType.planning: "Produce a plan, itinerary, schedule or step-by-step strategy.",
    TaskType.tool_use: "Act through external tools, browsing or APIs.",
    TaskType.analysis: "Compare options or interpret data, numbers or tables and draw a conclusion.",
}

# Ordered levels for each requirement. Index i of n maps to requirement i / (n - 1).
LEVELS: dict[str, tuple[str, list[str]]] = {
    "reasoning": (
        "How much step-by-step reasoning does a correct answer to `user_request` require?",
        [
            "None: a lookup, chit-chat or a direct transformation of the given text.",
            "Light: one or two obvious steps.",
            "Moderate: several steps, or some care with edge cases.",
            "Heavy: a long chain of logic, tricky constraints or non-trivial math.",
            "Expert: competition-level math, proofs or subtle multi-constraint problems.",
        ],
    ),
    "coding": (
        "How much programming skill does a correct answer to `user_request` require?",
        [
            "None: no code is involved.",
            "Trivial: a one-line snippet or a very simple query.",
            "Standard: a typical function, query or straightforward bug fix.",
            "Advanced: a complex algorithm, a subtle bug or a multi-part implementation.",
            "Expert: systems-level, concurrency or performance-critical engineering.",
        ],
    ),
    "writing": (
        "How much writing skill does a good answer to `user_request` require?",
        [
            "None: a short factual or structured answer.",
            "Basic: plain, clear sentences.",
            "Polished: a specific tone, format or audience.",
            "Crafted: creative writing or strict stylistic rules such as meter, acrostics or banned letters.",
            "Expert: publication-quality, nuanced writing.",
        ],
    ),
    "knowledge": (
        "How much specialised knowledge does a correct answer to `user_request` require beyond the text it contains?",
        [
            "None: everything needed is in the request or is common knowledge.",
            "General: what an educated adult knows.",
            "Specialised: solid knowledge of one professional field.",
            "Deep: expert knowledge of a field.",
            "Frontier: rare, niche or cutting-edge expertise.",
        ],
    ),
    "precision": (
        "How exact must the answer to `user_request` be to count as correct?",
        [
            "Loose: any reasonable answer is fine.",
            "Tolerant: small mistakes are acceptable.",
            "Correct: the answer should be right and follow the requested format.",
            "Exact: one wrong detail, number or format rule makes the answer wrong.",
            "Critical: legal, medical, financial or safety-critical exactness.",
        ],
    ),
}

OUTPUT_LENGTH = (
    "How long should a complete answer to `user_request` be?",
    [
        "A single word, number or line.",
        "A short paragraph or a short list.",
        "Several paragraphs or a short code file.",
        "A long document or a substantial program.",
    ],
)


def build_state(request: RouteRequest, max_chars: int) -> dict[str, str]:
    text = request.prompt_text
    state = {"user_request": text[:max_chars]}
    if len(text) > max_chars:
        state["note"] = "user_request was cut short; the full request is much longer."
    return state


def _relative_cost(ratio: float) -> str:
    if ratio < 1.15:
        return "the cheapest option for this request"
    if ratio < 1.5:
        return "slightly more expensive than the cheapest option"
    return f"about {ratio:.0f}x the cost of the cheapest option" if ratio < 10 else \
        f"about {round(ratio, -1):.0f}x the cost of the cheapest option"


def _speed(latency_ms: float, fastest: float) -> str:
    ratio = latency_ms / fastest
    return "very fast" if ratio < 1.5 else "fast" if ratio < 2.5 else "moderate speed" if ratio < 5 else "slow"


def model_choice(
    request: RouteRequest, candidates: Sequence[ModelSpec], instructions: str, assumed_output_tokens: int
) -> ChoiceQuestion:
    """One option per candidate: strengths, $/M tokens, and cost/speed relative to the alternatives.

    Jev reads numbers poorly, so code turns prices into a relative-cost phrase for this request
    and keeps the exact $/M figures alongside for reference. Options are listed cheapest first.
    """
    input_tokens = estimate_tokens(request.prompt_text)
    cost = {m.id: sum(m.pricing.cost(input_tokens, assumed_output_tokens)) for m in candidates}
    latency = {m.id: m.latency.estimate_ms(assumed_output_tokens) for m in candidates}
    cheapest, fastest = min(cost.values()), min(latency.values())
    criteria = {}
    for m in sorted(candidates, key=lambda m: cost[m.id]):
        p = m.pricing
        criteria[m.id] = (
            f"{m.description or m.tier + ' tier model.'} "
            f"Price: ${p.input_per_million:g} per million input tokens and ${p.output_per_million:g} per million "
            f"output tokens, {_relative_cost(cost[m.id] / cheapest)}. Speed: {_speed(latency[m.id], fastest)}."
        )
    return ChoiceQuestion(instructions=instructions, criteria=criteria)


def build_questions(
    tiers: Sequence[str], tier_descriptions: dict[str, str], choice: ChoiceQuestion | None = None
) -> dict[str, Question]:
    questions: dict[str, Question] = {"model": choice} if choice else {}
    questions |= {
        "task_type": ChoiceQuestion(
            instructions="What kind of task is `user_request` asking for?",
            criteria={t.value: desc for t, desc in TASK_TYPES.items()},
        ),
        "output_length": ScoreQuestion(instructions=OUTPUT_LENGTH[0], criteria=OUTPUT_LENGTH[1]),
    }
    for name, (instructions, levels) in LEVELS.items():
        questions[name] = ScoreQuestion(instructions=instructions, criteria=levels)
    for tier in tiers:
        questions[f"sufficient_{tier}"] = NoulQuestion(
            instructions=(
                f"Would a {tier_descriptions[tier]} answer `user_request` completely and correctly "
                "on the first try?"
            ),
            criteria={
                "true": "This kind of model reliably gets this task fully right.",
                "false": "This kind of model would likely make a mistake or give an incomplete answer.",
            },
        )
    return questions


class JevAnswerError(ProviderError):
    kind = "jev_answer_error"


def _level(answer: Answer, n_levels: int) -> float:
    if answer.score is None:
        raise JevAnswerError("score answer without a score")
    return min(1.0, max(0.0, answer.score / (n_levels - 1)))


def to_profile(result: DecisionResult, output_tokens_by_level: list[int]) -> TaskProfile:
    a = result.answers
    try:
        task_type = TaskType(a["task_type"].choice)
    except ValueError as e:
        raise JevAnswerError(f"unknown task_type {a['task_type'].choice!r}") from e
    length_idx = round(_level(a["output_length"], len(OUTPUT_LENGTH[1])) * (len(OUTPUT_LENGTH[1]) - 1))
    return TaskProfile(
        task_type=task_type,
        expected_output_tokens=output_tokens_by_level[length_idx],
        **{name: _level(a[name], len(levels)) for name, (_, levels) in LEVELS.items()},
    )


def overall_confidence(result: DecisionResult) -> float:
    """Mean of Jev's per-answer confidence (how concentrated each distribution is). Uncalibrated."""
    values = [a.confidence for a in result.answers.values() if a.confidence is not None]
    return sum(values) / len(values) if values else 0.0


def describe(profile: TaskProfile) -> str:
    dims = ("reasoning", "coding", "writing", "knowledge", "precision")
    top = sorted(dims, key=lambda d: -getattr(profile, d))[:2]
    return f"{profile.task_type.value}; " + ", ".join(f"{d} {getattr(profile, d):.2f}" for d in top)


class JevRouter(Router):
    def __init__(
        self,
        client: DecisionsClient,
        selector: ModelSpec,
        config: RoutingConfig,
        fallback_router: Router,
        decision: str | None = None,
    ):
        self.client = client
        self.selector = selector
        self.config = config
        self.fallback_router = fallback_router
        self.decision = decision or config.jev.decision
        if self.decision not in ("choice", "profile", "sufficiency"):
            raise ValueError(f"Unknown Jev decision style {self.decision!r}")
        self.name = f"jev-{self.decision}"

    async def aclose(self) -> None:
        await self.client.aclose()

    async def route(self, request: RouteRequest, candidates: Sequence[ModelSpec]) -> RouteDecision:
        if not candidates:
            raise NoCandidatesError("No candidate model satisfies the request constraints")
        cfg = self.config.jev
        tiers = sorted({m.tier for m in candidates}, key=lambda t: list(cfg.tier_descriptions).index(t))
        choice = model_choice(
            request, candidates, cfg.choice_instructions[request.mode], cfg.choice_assumed_output_tokens
        )
        start = time.perf_counter()
        try:
            result = await self.client.decide(
                self.selector.api_model,
                build_state(request, cfg.max_state_chars),
                build_questions(tiers, cfg.tier_descriptions, choice),
                timeout_s=cfg.timeout_s,
            )
            profile = to_profile(result, cfg.output_tokens_by_level)
            if result.answers["model"].choice not in {m.id for m in candidates}:
                raise JevAnswerError(f"Jev chose an unknown model {result.answers['model'].choice!r}")
        except (ProviderError, KeyError) as e:
            # Jev failed: let the fallback router decide, with zero confidence so the confidence
            # policy sends the request to the most capable model.
            decision = await self.fallback_router.route(request, candidates)
            return self._finish(decision, candidates, 0.0, start, Usage(), error=f"{type(e).__name__}: {e}")

        confidence = overall_confidence(result)
        if self.decision == "choice":
            decision = self._by_choice(result, profile, request, candidates)
            confidence = decision.confidence
        elif self.decision == "profile":
            decision = decide_from_profile(
                self.name, profile, request, candidates, self.config, confidence=confidence, reason=describe(profile)
            )
        else:
            decision = self._by_sufficiency(result, profile, request, candidates, confidence)

        u = result.usage
        in_cost, out_cost = self.selector.pricing.cost(u.input_tokens, u.output_tokens)
        if u.cost is not None:  # the API reports the billed cost; prefer it over our estimate
            in_cost, out_cost = u.cost, 0.0
        usage = Usage(input_tokens=u.input_tokens, output_tokens=u.output_tokens, input_cost=in_cost, output_cost=out_cost)
        return self._finish(decision, candidates, confidence, start, usage)

    def _by_choice(
        self, result: DecisionResult, profile: TaskProfile, request: RouteRequest, candidates: Sequence[ModelSpec]
    ) -> RouteDecision:
        """Jev's own pick. Fallbacks follow Jev's probability for each model; confidence is the Choice's."""
        answer = result.answers["model"]
        probs = answer.probabilities or {answer.choice: 1.0}
        input_tokens = estimate_tokens(request.prompt_text)
        out_tokens = profile.expected_output_tokens
        scores = sorted(
            (
                CandidateScore(
                    # For this style p_success holds Jev's choice probability, not a success estimate.
                    model_id=m.id, p_success=probs.get(m.id, 0.0),
                    est_cost=sum(m.pricing.cost(input_tokens, out_tokens)),
                    est_latency_ms=m.latency.estimate_ms(out_tokens), utility=probs.get(m.id, 0.0),
                )
                for m in candidates
            ),
            key=lambda s: (s.model_id != answer.choice, -s.utility, s.est_cost),
        )
        top = ", ".join(f"{s.model_id.split('/')[-1]} {s.p_success:.2f}" for s in scores[:3])
        return RouteDecision(
            router=self.name, model_id=answer.choice,
            confidence=answer.confidence if answer.confidence is not None else max(probs.values()),
            profile=profile, reason=f"Jev chose {answer.choice} ({top}); {describe(profile)}",
            fallbacks=[s.model_id for s in scores[1:]], scores=scores,
        )

    def _by_sufficiency(
        self,
        result: DecisionResult,
        profile: TaskProfile,
        request: RouteRequest,
        candidates: Sequence[ModelSpec],
        confidence: float,
    ) -> RouteDecision:
        """Cheapest candidate whose tier Jev judges sufficient (P >= min_success), else the most likely tier."""
        input_tokens = estimate_tokens(request.prompt_text)
        out_tokens = profile.expected_output_tokens
        scores = []
        for m in candidates:
            p = result.answers[f"sufficient_{m.tier}"].noul or 0.0
            cost = sum(m.pricing.cost(input_tokens, out_tokens))
            scores.append(CandidateScore(
                model_id=m.id, p_success=p, est_cost=cost,
                est_latency_ms=m.latency.estimate_ms(out_tokens), utility=-cost,
            ))
        ranked = scoring.rank(scores, self.config.modes[request.mode].min_success)
        p_by_tier = {m.tier: result.answers[f"sufficient_{m.tier}"].noul for m in candidates}
        reason = describe(profile) + "; P(sufficient) " + ", ".join(f"{t} {p:.2f}" for t, p in p_by_tier.items())
        return RouteDecision(
            router=self.name, model_id=ranked[0].model_id, confidence=confidence, profile=profile,
            reason=reason, fallbacks=[s.model_id for s in ranked[1:]], scores=ranked,
        )

    def _finish(
        self,
        decision: RouteDecision,
        candidates: Sequence[ModelSpec],
        confidence: float,
        start: float,
        usage: Usage,
        error: str | None = None,
    ) -> RouteDecision:
        probabilities = {s.model_id: s.p_success for s in decision.scores} if self.decision == "choice" else None
        new_id, note = policies.apply_confidence(
            decision.model_id, confidence, decision.scores, candidates, self.config.confidence, probabilities
        )
        fallbacks = decision.fallbacks
        if new_id != decision.model_id:
            fallbacks = [decision.model_id] + [f for f in fallbacks if f != new_id]
        return decision.model_copy(update={
            "router": self.name,
            "model_id": new_id,
            "fallbacks": fallbacks,
            "confidence": confidence,
            "escalated": note is not None,
            "reason": decision.reason + (f" [{note}]" if note else ""),
            "router_model": self.selector.id,
            "router_usage": usage,
            "router_latency_ms": (time.perf_counter() - start) * 1000,
            "router_error": error,
        })
