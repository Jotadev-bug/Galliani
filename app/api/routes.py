"""HTTP API and web UI.

    python -m app.api            # http://127.0.0.1:8000

Bring-your-own-key: a caller may send `X-OpenRouter-Key`; it is used for that request only (Jev
and generation) and is never stored or logged. Without it, the server's OPENROUTER_API_KEY is used.

Not production-hardened yet: no authentication or rate limiting. It binds to localhost by default;
add both before exposing it to the internet (PROJECT.md section 27).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import CONFIG_DIR, load_dotenv, load_routing_config, settings
from app.executor import Executor
from app.models.registry import ModelRegistry
from app.models.schemas import ExecutionResult, Message, RouteDecision, RouteRequest
from app.providers.base import estimate_tokens
from app.providers.factory import ProviderPool, resolve_key
from app.router.policies import most_capable
from app.service import build_router
from app.telemetry.costs import JsonlSink, build_record

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
KEY_HEADER = "x-openrouter-key"
DEFAULT_MAX_OUTPUT_TOKENS = 4096  # caps what OpenRouter reserves from the caller's credits per call

load_dotenv()
REGISTRY = ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
CONFIG = load_routing_config()
SINK = JsonlSink(settings()["log_path"])

app = FastAPI(title="AI Model Router", version="0.1.0")


# --------------------------------------------------------------------------- schemas


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=200_000)


class RouteBody(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=200)
    mode: Literal["auto", "cheapest", "fastest", "best"] = "auto"


class PlannedRoute(BaseModel):
    """A decision previously returned by /api/route, sent back to run it without routing again."""

    model_id: str
    fallbacks: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)
    reason: str = ""


class ChatBody(RouteBody):
    route: PlannedRoute | None = None
    max_output_tokens: int = Field(default=DEFAULT_MAX_OUTPUT_TOKENS, ge=16, le=32_000)


class OptionView(BaseModel):
    model_id: str
    score: float
    est_cost: float


class RouteView(BaseModel):
    model_id: str
    first_choice: str  # the router's own pick, before any confidence escalation
    confidence: float
    escalated: bool
    reason: str
    task_type: str | None
    signals: dict[str, float]  # requirement levels 0-1 judged by Jev (reasoning, coding, ...)
    options: list[OptionView]
    fallbacks: list[str]
    router_cost: float
    router_ms: float
    router_error: str | None


class ChatView(BaseModel):
    route: RouteView | None
    answer: str
    model_id: str
    input_tokens: int
    output_tokens: int
    generation_cost: float
    total_cost: float
    latency_ms: float
    attempts: list[str]
    errors: list[str]
    frontier_model: str
    frontier_cost: float


# --------------------------------------------------------------------------- helpers


def caller_keys(request: Request) -> dict[str, str]:
    key = request.headers.get(KEY_HEADER, "").strip()
    return {"OPENROUTER_API_KEY": key} if key else {}


def require_key(keys: dict[str, str]) -> None:
    cfg = REGISTRY.providers["openrouter"]
    if not resolve_key(cfg, keys):
        raise HTTPException(401, "No OpenRouter API key. Add yours in Settings.")


def to_request(body: RouteBody, max_output_tokens: int | None = None) -> RouteRequest:
    return RouteRequest(
        messages=[Message(role=m.role, content=m.content) for m in body.messages],
        mode=body.mode,
        max_output_tokens=max_output_tokens,
    )


SIGNALS = ("reasoning", "coding", "writing", "knowledge", "precision")


def view(d: RouteDecision) -> RouteView:
    # Escalation puts the router's own pick first among the fallbacks.
    first = d.fallbacks[0] if d.escalated and d.fallbacks else d.model_id
    return RouteView(
        model_id=d.model_id, first_choice=first, confidence=d.confidence, escalated=d.escalated, reason=d.reason,
        task_type=d.profile.task_type.value if d.profile else None,
        signals={k: getattr(d.profile, k) for k in SIGNALS} if d.profile else {},
        options=[OptionView(model_id=s.model_id, score=s.p_success, est_cost=s.est_cost) for s in d.scores],
        fallbacks=d.fallbacks, router_cost=d.router_usage.total_cost, router_ms=d.router_latency_ms,
        router_error=d.router_error,
    )


async def route(request: RouteRequest, keys: dict[str, str]) -> RouteDecision:
    candidates = REGISTRY.candidates(request, input_tokens=estimate_tokens(request.prompt_text))
    if not candidates:
        raise HTTPException(422, "No model can handle this request (too long for every model's context).")
    router = build_router("jev", REGISTRY, CONFIG, keys=keys)
    try:
        return await router.route(request, candidates)
    finally:
        await router.aclose()


def planned_decision(plan: PlannedRoute, request: RouteRequest) -> RouteDecision:
    allowed = {m.id for m in REGISTRY.candidates(request, input_tokens=estimate_tokens(request.prompt_text))}
    if plan.model_id not in allowed:
        raise HTTPException(422, f"Model {plan.model_id!r} is not an available candidate.")
    return RouteDecision(
        router="jev", model_id=plan.model_id, confidence=plan.confidence, reason=plan.reason,
        fallbacks=[f for f in plan.fallbacks if f in allowed and f != plan.model_id],
    )


# --------------------------------------------------------------------------- endpoints


@app.get("/api/config")
def get_config() -> dict:
    return {
        "modes": list(CONFIG.modes),
        "server_key": bool(os.environ.get("OPENROUTER_API_KEY")),
        "router_model": CONFIG.jev.selector_model,
        "frontier_model": most_capable(REGISTRY.candidates()).id,
        "models": [
            {
                "id": m.id, "vendor": m.vendor, "tier": m.tier, "description": m.description,
                "input_per_million": m.pricing.input_per_million, "output_per_million": m.pricing.output_per_million,
            }
            for m in REGISTRY.candidates()
        ],
    }


@app.post("/api/route")
async def post_route(body: RouteBody, request: Request) -> RouteView:
    """Jev's routing decision only: no answer is generated (costs about $0.0001)."""
    keys = caller_keys(request)
    require_key(keys)
    return view(await route(to_request(body), keys))


@app.post("/api/chat")
async def post_chat(body: ChatBody, request: Request) -> ChatView:
    """Route (unless `route` is given) and generate the answer, with fallbacks."""
    keys = caller_keys(request)
    require_key(keys)
    req = to_request(body, body.max_output_tokens)
    decision = planned_decision(body.route, req) if body.route else await route(req, keys)

    pool = ProviderPool(REGISTRY, keys=keys)
    try:
        ex: ExecutionResult = await Executor(REGISTRY, pool, CONFIG).execute(req, decision)
    finally:
        await pool.aclose()

    provider = REGISTRY.get(ex.result.model_id).provider if ex.result else None
    SINK.write(build_record(req, ex, provider=provider))  # no prompt text, no key
    if not ex.result:
        raise HTTPException(502, {"message": "Every model failed.", "attempts": ex.attempts, "errors": ex.errors})

    r = ex.result
    frontier = most_capable(REGISTRY.candidates())
    router_cost = decision.router_usage.total_cost
    return ChatView(
        route=None if body.route else view(decision),
        answer=r.text, model_id=r.model_id,
        input_tokens=r.usage.input_tokens, output_tokens=r.usage.output_tokens,
        generation_cost=r.usage.total_cost, total_cost=r.usage.total_cost + router_cost,
        latency_ms=r.latency_ms, attempts=ex.attempts, errors=ex.errors,
        frontier_model=frontier.id,
        frontier_cost=sum(frontier.pricing.cost(r.usage.input_tokens, r.usage.output_tokens)),
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})
