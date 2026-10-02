# AI Model Router

Write any prompt; the router picks the cheapest model that is *sufficiently capable* of solving it.
See [PROJECT.md](PROJECT.md) for the product thesis. This repository is at **Phase 1–3** of the plan:
offline router + execution + metrics, validated by a benchmark. No API or UI yet, by design.

## Quick start

```bash
pip install -e ".[dev]"
cp .env.example .env                  # add OPENROUTER_API_KEY (one key covers Google, OpenAI and Anthropic models)
python -m pytest                      # 178 tests, no network
python benchmark.py --simulate        # offline pipeline check; numbers are SIMULATED
python benchmark.py                   # the real experiment (~335 generations + 67 Jev calls)
python -m app.main "Translate 'good morning' into French"
```

## Layout

| Path | What |
|---|---|
| `config/models.yaml` | Model Registry: providers, models, prices, capability priors. No model facts live in code. |
| `config/routing.yaml` | Utility weights per mode, success model, confidence thresholds, Jev and fallback settings. |
| `app/router/` | `Router` interface; `JevRouter`; baselines (`rules`, `random`, `fixed`); scoring and policies. |
| `app/providers/` | `ModelProvider` interface; OpenAI-compatible (OpenAI, OpenRouter, vLLM, Ollama), Anthropic, mock, cache. |
| `app/executor.py` | Runs a decision, walking the fallback chain under a cost cap. |
| `app/telemetry/costs.py` | Per-request cost/latency records (JSONL; prompts not stored by default). |
| `benchmarks/` | 67 auto-graded tasks across 13 categories, evaluator, runner. |
| `scripts/sync_pricing.py` | Refresh prices from OpenRouter's live model list. |

## Docs

- [docs/architecture.md](docs/architecture.md) — components and data flow
- [docs/routing.md](docs/routing.md) — how a model is chosen, and what still needs calibrating
- [docs/benchmark.md](docs/benchmark.md) — methodology, metrics, how to read the report
