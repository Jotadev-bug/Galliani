# AI Model Router

Write any prompt; the router picks the cheapest model that is *sufficiently capable* of solving it.
See [PROJECT.md](PROJECT.md) for the product thesis. This repository is at **Phase 1–3** of the plan:
offline router + execution + metrics, validated by a benchmark. No API or UI yet, by design.

## Quick start

```bash
python -m venv .venv && .venv/Scripts/activate   # Windows; on macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                  # add OPENROUTER_API_KEY (one key covers Google, OpenAI and Anthropic models)
python -m app.api                     # web UI at http://127.0.0.1:8000
python -m pytest                      # tests, no network
python benchmark.py --simulate        # offline pipeline check; numbers are SIMULATED
python benchmark.py                   # the real experiment (~335 generations + 67 Jev decisions)
python -m app.main --route-only "Prove there are infinitely many primes"   # see which model Jev picks and why
python -m app.main "Translate 'good morning' into French"                  # route and answer
```

## Layout

| Path | What |
|---|---|
| `config/models.yaml` | Model Registry: providers, models, prices, capability priors. No model facts live in code. |
| `config/routing.yaml` | Utility weights per mode, success model, confidence thresholds, Jev and fallback settings. |
| `app/router/` | `Router` interface; `JevRouter` (TypeSafe Jev via the Decisions API); baselines (`rules`, `random`, `fixed`); scoring and policies. |
| `app/providers/` | `ModelProvider` interface; OpenAI-compatible (OpenAI, OpenRouter, vLLM, Ollama), Anthropic, mock, cache; `DecisionsClient` for Jev. |
| `app/api/`, `app/web/` | FastAPI endpoints (`/api/route`, `/api/chat`, `/api/config`) and the single-page UI. Bring-your-own-key via `X-OpenRouter-Key`. |
| `app/executor.py` | Runs a decision, walking the fallback chain under a cost cap. |
| `app/telemetry/costs.py` | Per-request cost/latency records (JSONL; prompts not stored by default). |
| `benchmarks/` | 80 auto-graded tasks (13 of them hard), evaluator, runner; `routing_eval.py` judges Jev's picks without generating answers. |
| `scripts/sync_pricing.py` | Refresh prices from OpenRouter's live model list. |

## Docs

- [docs/architecture.md](docs/architecture.md) — components and data flow
- [docs/routing.md](docs/routing.md) — how a model is chosen, and what still needs calibrating
- [docs/benchmark.md](docs/benchmark.md) — methodology, metrics, how to read the report

## Web UI

`python -m app.api` serves the UI on localhost. Testers paste their own OpenRouter key in
Settings; it stays in their browser and is sent only with their own requests (never stored or
logged by the server). "Preview route" shows Jev's pick and reasoning without generating an answer.

Before hosting it for others: add authentication, rate limiting and HTTPS (PROJECT.md §27).
The server binds to 127.0.0.1 by default for that reason.

## Desktop app

The same UI in a native window (pywebview on Edge WebView2 / WebKit), packaged as one file.

```bash
pip install -e ".[desktop,build]"
python -m app.desktop                 # run from source
python -m scripts.build_desktop       # -> dist/Router.exe, then runs its --smoke-test
```

- The OpenRouter key is saved in the OS credential store (Windows Credential Manager / macOS
  Keychain), not in a file or browser storage.
- Each launch serves the UI on a random localhost port with a random token; `/api` calls without
  the token are rejected, so other local programs can't spend the saved key.
- Logs (no prompts, no keys) go to `%LOCALAPPDATA%\AI Model Router\` (Windows).
- Build on each target OS: a Windows build makes `Router.exe`; build on a Mac for macOS.
