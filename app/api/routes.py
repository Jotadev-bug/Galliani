"""Galliani HTTP API and web UI.

    python -m app.api            # http://127.0.0.1:8000

Bring-your-own-key: a caller may send `X-OpenRouter-Key` (required: Jev runs on OpenRouter) and,
optionally, `X-OpenAI-Key` / `X-Anthropic-Key` to call those vendors' models on their own APIs.
Keys are used for that request only and never stored or logged; missing ones fall back to the
server environment.

Desktop mode (ROUTER_DESKTOP=1, set by app/desktop.py): the user's key lives in the OS credential
store (/api/key), and every /api/* call must carry the per-launch ROUTER_APP_TOKEN so other local
programs cannot use the saved key.

Not production-hardened yet: no authentication or rate limiting. It binds to localhost by default;
add both before exposing it to the internet (PROJECT.md section 27).
"""

from __future__ import annotations

import os
import secrets

import httpx
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app import keys as keystore
from app.config import CONFIG_DIR, load_dotenv, load_routing_config, settings
from app.executor import Executor
from app.models.registry import ModelRegistry
from app.models.schemas import ExecutionResult, Message, RouteDecision, RouteRequest
from app.providers.base import estimate_tokens
from app.providers.factory import ProviderPool, resolve_key
from app.router.policies import most_capable
from app.service import build_router
from app.telemetry.costs import JsonlSink, build_record
from galliani.web.agent_api import agent_router

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
KEY_HEADERS = {  # env-var name -> request header
    "OPENROUTER_API_KEY": "x-openrouter-key",
    "OPENAI_API_KEY": "x-openai-key",
    "ANTHROPIC_API_KEY": "x-anthropic-key",
}
CREDITS_URL = "https://openrouter.ai/api/v1/credits"
DEFAULT_MAX_OUTPUT_TOKENS = 4096  # caps what OpenRouter reserves from the caller's credits per call

load_dotenv()
REGISTRY = ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
CONFIG = load_routing_config()
SINK = JsonlSink(settings()["log_path"])

app = FastAPI(title="Galliani", version="0.1.0")


def desktop_mode() -> bool:
    return os.environ.get("ROUTER_DESKTOP") == "1"


@app.middleware("http")
async def require_app_token(request: Request, call_next):
    token = os.environ.get("ROUTER_APP_TOKEN")
    if token and request.url.path.startswith("/api/"):
        if not secrets.compare_digest(request.headers.get("x-app-token", ""), token):
            return JSONResponse({"detail": "Invalid app token."}, status_code=403)
    return await call_next(request)


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
    provider: str | None  # "openrouter", "anthropic" or "openai": who actually served the answer


# --------------------------------------------------------------------------- helpers


def caller_keys(request: Request) -> dict[str, str]:
    """Per provider: header (web testers) > OS credential store (desktop) > server environment (resolved later)."""
    keys = {}
    for env, header in KEY_HEADERS.items():
        key = request.headers.get(header, "").strip() or (keystore.get(env) if desktop_mode() else None)
        if key:
            keys[env] = key
    return keys


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
        "desktop": desktop_mode(),
        # Per provider: saved in the OS credential store (desktop) and/or set in the server environment.
        "keys": {
            provider: {"saved": desktop_mode() and keystore.get(env) is not None, "env": bool(os.environ.get(env))}
            for provider, env in keystore.PROVIDERS.items()
        },
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
        provider=r.provider,
    )


@app.get("/api/credits")
async def get_credits(request: Request) -> dict:
    """The caller's OpenRouter balance, for the sidebar card. Null fields if unavailable."""
    key = resolve_key(REGISTRY.providers["openrouter"], caller_keys(request))
    if not key:
        return {"balance": None}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(CREDITS_URL, headers={"Authorization": f"Bearer {key}"}, timeout=10)
        data = resp.json().get("data") or {}
        total, used = float(data["total_credits"]), float(data["total_usage"])
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {"balance": None}
    return {"balance": total - used, "total_credits": total, "total_usage": used}


class KeyBody(BaseModel):
    provider: Literal["openrouter", "openai", "anthropic"] = "openrouter"
    key: str = Field(min_length=8, max_length=500)


def _desktop_only() -> None:
    if not desktop_mode():
        raise HTTPException(404, "Key storage is only available in the desktop app.")


@app.put("/api/key")
def put_key(body: KeyBody) -> dict:
    """Save one provider key in the OS credential store (desktop only)."""
    _desktop_only()
    keystore.save(body.key.strip(), keystore.PROVIDERS[body.provider])
    return {"provider": body.provider, "saved": True}


@app.delete("/api/key/{provider}")
def delete_key(provider: Literal["openrouter", "openai", "anthropic"]) -> dict:
    _desktop_only()
    keystore.delete(keystore.PROVIDERS[provider])
    return {"provider": provider, "saved": False}


# The supervisor's agent API (spec 012, Decision 0018). Same app token, same caller keys.
app.include_router(agent_router(keys_for=caller_keys))


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})
