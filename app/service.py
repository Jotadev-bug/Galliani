"""Assembles registry, routers, providers and telemetry from configuration."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from app.config import CONFIG_DIR, RoutingConfig, load_dotenv, load_routing_config, settings
from app.executor import Executor
from app.models.registry import ModelRegistry
from app.models.schemas import ExecutionResult, ModelSpec, RouteRequest
from app.providers.base import estimate_tokens
from app.providers.decisions import DecisionsClient
from app.providers.factory import ProviderPool
from app.router.base import Router
from app.router.baselines import FixedRouter, RandomRouter, RulesRouter, cheapest
from app.router.jev import JevRouter
from app.router.policies import most_capable
from app.telemetry.costs import JsonlSink, build_record

ROUTER_NAMES = ("jev", "jev-profile", "jev-sufficiency", "rules", "random", "frontier", "cheapest")


def jev_client(
    registry: ModelRegistry, config: RoutingConfig, cache_dir: Path | None = None
) -> tuple[ModelSpec, DecisionsClient]:
    """Resolve the Jev model and its Decisions API client, honouring JEV_* env overrides."""
    model_id = os.environ.get("JEV_MODEL") or config.jev.selector_model
    if model_id in registry:
        selector = registry.get(model_id)
    else:
        print(f"warning: JEV_MODEL={model_id!r} is not in the registry; using the configured "
              f"selector's pricing for cost estimates", file=sys.stderr)
        selector = registry.get(config.jev.selector_model).model_copy(update={"id": model_id, "provider_model": model_id})
    provider = registry.providers[selector.provider]
    base_url = os.environ.get("JEV_BASE_URL") or provider.base_url or ""
    api_key = os.environ.get("JEV_API_KEY") or (os.environ.get(provider.api_key_env) if provider.api_key_env else None)
    return selector, DecisionsClient(base_url, api_key, cache_dir=cache_dir)


def jev_unavailable_reason(registry: ModelRegistry, config: RoutingConfig) -> str | None:
    """Why Jev cannot run with the current environment, or None if it can."""
    if os.environ.get("JEV_API_KEY"):
        return None
    selector = registry.get(config.jev.selector_model)
    env = registry.providers[selector.provider].api_key_env
    return f"missing {env} for {selector.id}" if env and not os.environ.get(env) else None


def build_router(
    name: str,
    registry: ModelRegistry,
    config: RoutingConfig,
    seed: int = 0,
    cache_dir: Path | None = None,
) -> Router:
    """Router names: jev (configured style), jev-profile, jev-sufficiency, rules, random, frontier, cheapest."""
    candidates = registry.candidates()
    if name == "rules":
        return RulesRouter(config.rules)
    if name == "random":
        return RandomRouter(seed)
    if name == "frontier":
        return FixedRouter(most_capable(candidates).id, name="frontier")
    if name == "cheapest":
        return FixedRouter(cheapest(candidates).id, name="cheapest")
    if name == "jev" or name.startswith("jev-"):
        selector, client = jev_client(registry, config, cache_dir)
        style = name.removeprefix("jev-") if name != "jev" else None
        return JevRouter(client, selector, config, fallback_router=RulesRouter(config.rules), decision=style)
    raise ValueError(f"Unknown router {name!r}; choose from {ROUTER_NAMES}")


@dataclass
class RouterService:
    registry: ModelRegistry
    config: RoutingConfig
    pool: ProviderPool
    router: Router
    sink: JsonlSink | None = None
    store_prompts: bool = False

    @classmethod
    def from_config(cls, router_name: str = "jev") -> RouterService:
        load_dotenv()
        registry = ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
        config = load_routing_config()
        pool = ProviderPool(registry)
        s = settings()
        return cls(
            registry=registry, config=config, pool=pool,
            router=build_router(router_name, registry, config),
            sink=JsonlSink(s["log_path"]),
            store_prompts=s["store_prompts"].lower() == "true",
        )

    async def run(self, request: RouteRequest, user_id: str | None = None) -> ExecutionResult:
        candidates = self.registry.candidates(request, input_tokens=estimate_tokens(request.prompt_text))
        decision = await self.router.route(request, candidates)
        execution = await Executor(self.registry, self.pool, self.config).execute(request, decision)
        if self.sink:
            provider = self.registry.get(execution.result.model_id).provider if execution.result else None
            self.sink.write(build_record(
                request, execution, provider=provider, user_id=user_id, store_prompt=self.store_prompts
            ))
        return execution

    async def aclose(self) -> None:
        await self.router.aclose()
        await self.pool.aclose()
