"""Baseline routers used as experimental controls (PROJECT.md experiments #1-#3)."""

from __future__ import annotations

import random
import re
from collections.abc import Sequence

from app.config import RulesConfig
from app.models.schemas import TIER_ORDER, ModelSpec, RouteDecision, RouteRequest, TaskType
from app.router.base import NoCandidatesError, Router


def _require(candidates: Sequence[ModelSpec]) -> None:
    if not candidates:
        raise NoCandidatesError("No candidate model satisfies the request constraints")


def cheapest(models: Sequence[ModelSpec]) -> ModelSpec:
    return min(models, key=lambda m: m.pricing.input_per_million + m.pricing.output_per_million)


class FixedRouter(Router):
    """Always picks one model (e.g. the frontier baseline). Falls back to the cheapest candidate."""

    def __init__(self, model_id: str, name: str | None = None):
        self.model_id = model_id
        self.name = name or f"fixed:{model_id}"

    async def route(self, request: RouteRequest, candidates: Sequence[ModelSpec]) -> RouteDecision:
        _require(candidates)
        ids = [m.id for m in candidates]
        chosen = self.model_id if self.model_id in ids else cheapest(candidates).id
        return RouteDecision(
            router=self.name, model_id=chosen, confidence=1.0, reason="fixed model",
            fallbacks=[i for i in ids if i != chosen],
        )


class RandomRouter(Router):
    name = "random"

    def __init__(self, seed: int = 0):
        self._rng = random.Random(seed)

    async def route(self, request: RouteRequest, candidates: Sequence[ModelSpec]) -> RouteDecision:
        _require(candidates)
        chosen = self._rng.choice(list(candidates))
        return RouteDecision(
            router=self.name, model_id=chosen.id, confidence=0.0, reason="uniform random",
            fallbacks=[m.id for m in candidates if m.id != chosen.id],
        )


# Keyword heuristics (English + Spanish). Order matters: first match wins.
_KEYWORDS: list[tuple[TaskType, str]] = [
    (TaskType.debugging, r"\b(bug|error|exception|traceback|stack ?trace|fix (this|the)|falla|depura|no funciona)\b"),
    (TaskType.coding, r"\b(code|function|python|javascript|typescript|sql|regex|implement|class|api|código|función|programa)\b|```"),
    (TaskType.math, r"\b(solve|equation|integral|derivative|probability|prove|calcula|ecuación|probabilidad|demuestra)\b|\d+\s*[\+\-\*/\^]\s*\d+"),
    (TaskType.reasoning, r"\b(puzzle|riddle|logic|step by step|deduce|razona|acertijo|lógica)\b"),
    (TaskType.planning, r"\b(plan|roadmap|architecture|design a system|strategy|arquitectura|estrategia|planifica)\b"),
    (TaskType.translation, r"\b(translate|translation|traduce|traducción|into (english|spanish|french|german))\b"),
    (TaskType.summarization, r"\b(summari[sz]e|summary|tl;?dr|resume|resumen|resúmelo)\b"),
    (TaskType.extraction, r"\b(extract|json|list all|pull out|extrae|extraer)\b"),
    (TaskType.classification, r"\b(classify|categori[sz]e|sentiment|label|clasifica|sentimiento)\b"),
    (TaskType.writing, r"\b(write|draft|email|essay|story|poem|escribe|redacta|correo|ensayo)\b"),
    (TaskType.analysis, r"\b(analy[sz]e|compare|evaluate|pros and cons|analiza|compara|evalúa)\b"),
]


def classify(prompt: str) -> TaskType:
    text = prompt.lower()
    for task_type, pattern in _KEYWORDS:
        if re.search(pattern, text):
            return task_type
    return TaskType.conversation


class RulesRouter(Router):
    """if coding -> strong; if reasoning -> frontier; else cheap (tiers configurable)."""

    name = "rules"

    def __init__(self, config: RulesConfig):
        self.config = config

    async def route(self, request: RouteRequest, candidates: Sequence[ModelSpec]) -> RouteDecision:
        _require(candidates)
        task_type = classify(request.prompt_text)
        target = TIER_ORDER[self.config.task_type_tiers.get(task_type.value, self.config.default_tier)]
        # Cheapest model at the target tier; if the tier is empty, the nearest tier above, then below.
        by_tier = sorted({TIER_ORDER[m.tier] for m in candidates})
        above = [t for t in by_tier if t >= target]
        tier = above[0] if above else by_tier[-1]
        chosen = cheapest([m for m in candidates if TIER_ORDER[m.tier] == tier])
        fallbacks = sorted(
            (m for m in candidates if m.id != chosen.id),
            key=lambda m: (TIER_ORDER[m.tier] < tier, abs(TIER_ORDER[m.tier] - tier)),
        )
        return RouteDecision(
            router=self.name, model_id=chosen.id, confidence=1.0,
            reason=f"rule: {task_type.value} -> {chosen.tier}",
            fallbacks=[m.id for m in fallbacks],
        )
