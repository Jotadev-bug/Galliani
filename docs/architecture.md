# Architecture

```text
RouteRequest ──► ModelRegistry.candidates()      hard constraints: status, vendor allow/block,
                       │                         vision/tools, context window
                       ▼
                 Router.route()                  JEBRouter | RulesRouter | RandomRouter | FixedRouter
                       │                         -> RouteDecision (model, fallbacks, confidence, profile)
                       ▼
                 Executor.execute()              model, then fallbacks; skips models over the cost cap
                       │                         and models too small after a context overflow
                       ▼
                 ProviderPool → ModelProvider    OpenAICompatibleProvider | AnthropicProvider | MockProvider
                       │
                       ▼
                 JsonlSink(RequestRecord)        cost, latency, selection, fallbacks; prompt hash only
```

## Decisions

- **Registry is data.** Models, prices, limits and capability priors live in `config/models.yaml`.
  Adding a model is a YAML edit; adding a provider is one adapter class plus one branch in
  `providers/factory.py`. Prices are synced from OpenRouter (`scripts/sync_pricing.py`), never typed in code.
- **JEB is one `Router` among several.** The product depends on the `Router` interface, so JEB
  can be swapped for a learned or rules router without touching the executor, providers or telemetry.
- **JEB classifies, scoring decides (by default).** In `profile` mode JEB returns a structured task
  profile and the utility function picks the model, which keeps prices and capabilities out of the
  LLM's hands and makes the choice auditable. `direct` mode (JEB names the model) exists so the two
  can be compared in the benchmark.
- **Failures are typed.** Providers raise `ProviderError` subclasses (timeout, rate limit, outage,
  context overflow, model unavailable, auth, invalid request). The executor uses `try_other_model`
  to decide whether a fallback can help.
- **A JEB failure never blocks a request.** If the selector errors or returns unparseable output,
  the rules router decides and the confidence is set to 0, which sends the request to the most
  capable model. The error is recorded in `router_error`.
- **Minimal dependencies:** pydantic, httpx, pyyaml. FastAPI and PostgreSQL are deferred to Phase 4,
  and `JsonlSink` has the interface a Postgres sink would implement.
- **Privacy:** prompts are not logged unless `ROUTER_STORE_PROMPTS=true`; records hold a SHA-256 of
  the prompt. Vendor allow/block lists are request-level hard filters.

## Not built yet (on purpose)

The public API (`POST /v1/chat/completions`), UI, authentication, rate limiting, encrypted key
storage, PostgreSQL, the response evaluator and the browser extension. PROJECT.md §33–34 puts them after
the benchmark shows that routing pays off.
