"""Assembles registry, routers, providers and telemetry from configuration."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from app.config import CONFIG_DIR, RoutingConfig, load_dotenv, load_routing_config, settings
from app.executor import Executor
from app.models.registry import ModelRegistry
from app.models.schemas import ExecutionResult, ModelSpec, Pricing, RouteRequest
from app.providers.base import ModelProvider, estimate_tokens
from app.providers.factory import ProviderPool
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.router.base import Router
from app.router.baselines import FixedRouter, RandomRouter, RulesRouter, cheapest
from app.router.jeb import JEBRouter
from app.router.policies import most_capable
from app.telemetry.costs import JsonlSink, build_record

ROUTER_NAMES = ("jeb", "rules", "random", "frontier", "cheapest")


def jeb_selector(registry: ModelRegistry, config: RoutingConfig, pool: ProviderPool) -> tuple[ModelSpec, ModelProvider]:
    """Resolve the JEB selector model and its provider, honouring JEB_* env overrides."""
    selector = registry.get(config.jeb.selector_model)
    override_model = os.environ.get("JEB_MODEL")
    if override_model:
        if override_model in registry:
            selector = registry.get(override_model)
        else:
            print(
                f"warning: JEB_MODEL={override_model!r} is not in the registry; its cost is recorded as $0",
                file=sys.stderr,
            )
            selector = selector.model_copy(update={
                "id": override_model, "provider_model": override_model,
                "pricing": Pricing(input_per_million=0, output_per_million=0),
            })
    base_url = os.environ.get("JEB_BASE_URL")
    if base_url:
        return selector, pool.wrap(OpenAICompatibleProvider("jeb", base_url, os.environ.get("JEB_API_KEY")))
    return selector, pool.for_model(selector)


def jeb_unavailable_reason(registry: ModelRegistry, config: RoutingConfig, pool: ProviderPool) -> str | None:
    """Why JEB cannot run with the current environment, or None if it can."""
    if os.environ.get("JEB_BASE_URL"):
        return None
    override = os.environ.get("JEB_MODEL")
    selector = registry.get(override if override in registry else config.jeb.selector_model)
    missing = pool.missing_keys([selector])
    return f"missing {', '.join(missing)} for selector {selector.id}" if missing else None


def build_router(name: str, registry: ModelRegistry, config: RoutingConfig, pool: ProviderPool, seed: int = 0) -> Router:
    candidates = registry.candidates()
    if name == "rules":
        return RulesRouter(config.rules)
    if name == "random":
        return RandomRouter(seed)
    if name == "frontier":
        return FixedRouter(most_capable(candidates).id, name="frontier")
    if name == "cheapest":
        return FixedRouter(cheapest(candidates).id, name="cheapest")
    if name == "jeb":
        selector, provider = jeb_selector(registry, config, pool)
        return JEBRouter(provider, selector, config, fallback_router=RulesRouter(config.rules))
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
    def from_config(cls, router_name: str = "jeb") -> RouterService:
        load_dotenv()
        registry = ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
        config = load_routing_config()
        pool = ProviderPool(registry)
        s = settings()
        return cls(
            registry=registry, config=config, pool=pool,
            router=build_router(router_name, registry, config, pool),
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
