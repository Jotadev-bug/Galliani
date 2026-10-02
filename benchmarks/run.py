"""Router benchmark (PROJECT.md sections 16-20, 35).

Phase 1 - matrix: every task is run once on every candidate model and scored automatically.
Phase 2 - routing: each router picks a model per task; its outcome is looked up in the matrix.
            Routers therefore compete on identical responses, and a new router or new routing
            weights can be evaluated without re-running generation.

Responses and Jev calls are cached in benchmarks/results/cache, so re-runs are free.

    python benchmark.py                       # real run (needs provider API keys)
    python benchmark.py --simulate            # offline pipeline check, SIMULATED numbers
    python benchmark.py --routers jev,rules --limit 20 --no-exec
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.config import CONFIG_DIR, RoutingConfig, load_dotenv, load_routing_config
from app.models.registry import ModelRegistry
from app.models.schemas import Message, ModelSpec, RouteDecision, RouteRequest
from app.providers.base import ProviderError, estimate_tokens
from app.providers.caching import CachingProvider
from app.providers.factory import ProviderPool
from app.providers.mock import MockProvider
from app.router.base import Router
from app.router.policies import most_capable
from app.service import build_router, jev_unavailable_reason
from benchmarks.evaluate import evaluate, needs_exec

BENCH_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BENCH_DIR / "results"
MAX_OUTPUT_TOKENS = 4096


def load_tasks(path: Path = BENCH_DIR / "tasks.yaml") -> list[dict]:
    tasks = yaml.safe_load(path.read_text(encoding="utf-8"))
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate task ids in benchmark")
    return tasks


# --------------------------------------------------------------------------- matrix


@dataclass
class Cell:
    model_id: str
    ok: bool
    cost: float = 0.0
    latency_ms: float = 0.0
    output_tokens: int = 0
    score: float = 0.0
    success: bool = False
    error: str | None = None
    failed_checks: list[str] = field(default_factory=list)


def simulated_responder(tasks: list[dict]) -> callable:
    """Pass/fail drawn from a fixed seed, weighted by mean model skill vs task difficulty."""
    by_prompt = {t["prompt"]: t for t in tasks}

    def respond(messages: list[Message], model: ModelSpec) -> str:
        task = by_prompt[messages[-1].content]
        skills = model.skills.model_dump().values()
        p = 1 / (1 + math.exp(-(12 * (sum(skills) / len(skills) - task["difficulty"]) - 1.0)))
        seed = int(hashlib.sha256(f"{task['id']}|{model.id}".encode()).hexdigest()[:8], 16)
        return task["reference"] if random.Random(seed).random() < p else "I'm not sure."

    return respond


async def build_matrix(
    tasks: list[dict], models: list[ModelSpec], pool: ProviderPool, concurrency: int
) -> dict[tuple[str, str], Cell]:
    sem = asyncio.Semaphore(concurrency)
    done = 0

    async def one(task: dict, model: ModelSpec) -> tuple[tuple[str, str], Cell]:
        nonlocal done
        async with sem:
            try:
                r = await pool.for_model(model).generate(
                    [Message(role="user", content=task["prompt"])], model, max_output_tokens=MAX_OUTPUT_TOKENS
                )
                ev = await asyncio.to_thread(evaluate, task, r.text)
                cell = Cell(
                    model.id, True, r.usage.total_cost, r.latency_ms, r.usage.output_tokens, ev.score, ev.success,
                    failed_checks=[f"{c.type}: {c.detail}" for c in ev.checks if not c.passed],
                )
            except ProviderError as e:
                cell = Cell(model.id, False, error=f"{e.kind}: {str(e)[:200]}")
        done += 1
        total = len(tasks) * len(models)
        if done == total or done % max(1, total // 10) == 0:
            print(f"  generated {done}/{total}", file=sys.stderr, flush=True)
        return (task["id"], model.id), cell

    return dict(await asyncio.gather(*(one(t, m) for t in tasks for m in models)))


# --------------------------------------------------------------------------- routing


@dataclass
class Outcome:
    task_id: str
    category: str
    chosen: str
    served_by: str | None
    confidence: float
    escalated: bool
    router_error: str | None
    routing_cost: float
    routing_latency_ms: float
    gen_cost: float
    gen_latency_ms: float
    score: float
    success: bool
    fallback_used: bool

    @property
    def total_cost(self) -> float:
        return self.routing_cost + self.gen_cost


def serve(decision: RouteDecision, task_id: str, matrix: dict[tuple[str, str], Cell]) -> tuple[Cell | None, bool]:
    """Walk the decision's fallback chain over precomputed results, like the live executor."""
    for i, model_id in enumerate([decision.model_id, *decision.fallbacks]):
        cell = matrix.get((task_id, model_id))
        if cell and cell.ok:
            return cell, i > 0
    return None, False


async def run_router(
    router: Router, tasks: list[dict], registry: ModelRegistry, matrix: dict, concurrency: int
) -> list[Outcome]:
    sem = asyncio.Semaphore(concurrency)

    async def one(task: dict) -> Outcome:
        request = RouteRequest.from_prompt(task["prompt"])
        candidates = registry.candidates(request, input_tokens=estimate_tokens(task["prompt"]))
        async with sem:
            d = await router.route(request, candidates)
        cell, fb = serve(d, task["id"], matrix)
        return Outcome(
            task_id=task["id"], category=task["category"], chosen=d.model_id,
            served_by=cell.model_id if cell else None, confidence=d.confidence, escalated=d.escalated,
            router_error=d.router_error, routing_cost=d.router_usage.total_cost,
            routing_latency_ms=d.router_latency_ms, gen_cost=cell.cost if cell else 0.0,
            gen_latency_ms=cell.latency_ms if cell else 0.0, score=cell.score if cell else 0.0,
            success=cell.success if cell else False, fallback_used=fb,
        )

    return list(await asyncio.gather(*(one(t) for t in tasks)))


def oracle(tasks: list[dict], models: list[ModelSpec], matrix: dict, frontier_id: str) -> list[Outcome]:
    """Upper bound: the cheapest model that actually succeeded on each task (frontier if none did)."""
    out = []
    for t in tasks:
        cells = [matrix[(t["id"], m.id)] for m in models if matrix[(t["id"], m.id)].ok]
        winners = [c for c in cells if c.success]
        cell = min(winners, key=lambda c: c.cost) if winners else matrix.get((t["id"], frontier_id))
        out.append(Outcome(
            t["id"], t["category"], cell.model_id if cell else "-", cell.model_id if cell and cell.ok else None,
            1.0, False, None, 0.0, 0.0, cell.cost if cell else 0.0, cell.latency_ms if cell else 0.0,
            cell.score if cell else 0.0, cell.success if cell else False, False,
        ))
    return out


# --------------------------------------------------------------------------- report


def summarize(outcomes: list[Outcome]) -> dict:
    n = len(outcomes)
    lat = sorted(o.routing_latency_ms + o.gen_latency_ms for o in outcomes)
    return {
        "tasks": n,
        "quality": sum(o.score for o in outcomes) / n,
        "success_rate": sum(o.success for o in outcomes) / n,
        "total_cost": sum(o.total_cost for o in outcomes),
        "generation_cost": sum(o.gen_cost for o in outcomes),
        "routing_cost": sum(o.routing_cost for o in outcomes),
        "mean_latency_ms": sum(lat) / n,
        "p50_latency_ms": lat[n // 2],
        "mean_routing_latency_ms": sum(o.routing_latency_ms for o in outcomes) / n,
        "fallback_rate": sum(o.fallback_used for o in outcomes) / n,
        "failed": sum(o.served_by is None for o in outcomes),
        "escalation_rate": sum(o.escalated for o in outcomes) / n,
        "router_errors": sum(o.router_error is not None for o in outcomes),
        "mean_confidence": sum(o.confidence for o in outcomes) / n,
        "selection": dict(Counter(o.served_by or "FAILED" for o in outcomes).most_common()),
    }


def compare(s: dict, base: dict) -> dict:
    savings_abs = base["total_cost"] - s["generation_cost"]
    return {
        "savings": 1 - s["total_cost"] / base["total_cost"] if base["total_cost"] else 0.0,
        "quality_delta_pts": (s["quality"] - base["quality"]) * 100,
        "success_delta_pts": (s["success_rate"] - base["success_rate"]) * 100,
        "routing_overhead_share_of_savings": s["routing_cost"] / savings_abs if savings_abs > 0 else None,
    }


def calibration(outcomes: list[Outcome]) -> list[dict]:
    buckets = [(0.0, 0.7), (0.7, 0.9), (0.9, 1.01)]
    out = []
    for lo, hi in buckets:
        group = [o for o in outcomes if lo <= o.confidence < hi]
        if group:
            out.append({
                "confidence": f"[{lo:.1f}, {min(hi, 1.0):.1f}]", "n": len(group),
                "success_rate": sum(o.success for o in group) / len(group),
            })
    return out


def by_category(outcomes: list[Outcome]) -> dict[str, dict]:
    groups: dict[str, list[Outcome]] = defaultdict(list)
    for o in outcomes:
        groups[o.category].append(o)
    return {
        c: {"n": len(g), "quality": sum(o.score for o in g) / len(g), "cost": sum(o.total_cost for o in g)}
        for c, g in sorted(groups.items())
    }


def print_report(report: dict, focus: list[str]) -> None:
    line = "=" * 78
    s, b = report["routers"], report["baseline"]
    print(line)
    print("AI MODEL ROUTER BENCHMARK" + ("   [SIMULATED - NOT REAL RESULTS]" if report["simulated"] else ""))
    print(line)
    print(f"\nTasks: {report['tasks']}    Candidates: {len(report['candidates'])}    Baseline: {b}")

    def block(title: str, m: dict) -> None:
        print(f"\n{title}:")
        print(f"  Cost:       ${m['total_cost']:.4f}")
        print(f"  Quality:    {m['quality'] * 100:.1f}%   (success rate {m['success_rate'] * 100:.1f}%)")
        print(f"  Latency:    {m['mean_latency_ms']:.0f} ms mean, {m['p50_latency_ms']:.0f} ms p50")

    block(f"Baseline ({b})", s["frontier"]["summary"])
    for name in focus:
        if name not in s:
            print(f"\n{name} router: not run (see warnings above)")
            continue
        f = s[name]
        block(f"{name} router", f["summary"])
        c = f["vs_baseline"]
        share = c["routing_overhead_share_of_savings"]
        print(f"  Savings:    {c['savings'] * 100:.1f}%")
        print(f"  Quality delta: {c['quality_delta_pts']:+.1f} pts   (success {c['success_delta_pts']:+.1f} pts)")
        print(f"  Routing overhead: {f['summary']['mean_routing_latency_ms']:.0f} ms/request, "
              f"${f['summary']['routing_cost']:.5f} total"
              + (f" ({share * 100:.2f}% of gross savings)" if share is not None else ""))

    print(f"\n{line}\n{'router':<17}{'quality':>9}{'success':>9}{'cost $':>10}{'savings':>9}"
          f"{'d.qual':>9}{'lat ms':>8}{'route ms':>9}")
    for name, r in s.items():
        m, c = r["summary"], r["vs_baseline"]
        print(f"{name:<17}{m['quality'] * 100:>8.1f}%{m['success_rate'] * 100:>8.1f}%{m['total_cost']:>10.4f}"
              f"{c['savings'] * 100:>8.1f}%{c['quality_delta_pts']:>+8.1f}p{m['mean_latency_ms']:>8.0f}"
              f"{m['mean_routing_latency_ms']:>9.0f}")

    print(f"\n{line}\nModel selection (tasks served by each model):")
    for name, r in s.items():
        sel = ", ".join(f"{k.split('/')[-1]} {v}" for k, v in r["summary"]["selection"].items())
        print(f"  {name:<16} {sel}")

    for name in focus:
        if name in s and s[name].get("calibration"):
            f = s[name]["summary"]
            print(f"\n{name} confidence calibration (Jev's stated confidence vs actual success):")
            for row in s[name]["calibration"]:
                print(f"  {row['confidence']:<12} n={row['n']:<4} success={row['success_rate'] * 100:.0f}%")
            print(f"  escalations: {f['escalation_rate'] * 100:.0f}%   Jev errors: {f['router_errors']}")
    print(line)


# --------------------------------------------------------------------------- main


async def main(args: argparse.Namespace) -> int:
    load_dotenv()
    registry = ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
    config: RoutingConfig = load_routing_config()
    tasks = load_tasks()
    if args.no_exec:
        tasks = [t for t in tasks if not needs_exec(t)]
    if args.categories:
        tasks = [t for t in tasks if t["category"] in args.categories.split(",")]
    if args.limit:
        tasks = tasks[: args.limit]
    models = registry.candidates()
    cache = RESULTS_DIR / "cache"

    frontier_id = most_capable(models).id
    cache_wrapper = lambda p: CachingProvider(p, cache)  # noqa: E731
    if args.simulate:
        sim = MockProvider("simulated", responder=simulated_responder(tasks))
        pool = ProviderPool(registry, overrides={p: sim for p in {m.provider for m in models}})
    else:
        pool = ProviderPool(registry, wrapper=cache_wrapper)
        missing = pool.missing_keys(models)
        if missing:
            print(f"Missing API keys for candidate models: {', '.join(missing)}. Set them in .env "
                  f"or run with --simulate.", file=sys.stderr)
            return 2

    print(f"Matrix: {len(tasks)} tasks x {len(models)} models", file=sys.stderr)
    matrix = await build_matrix(tasks, models, pool, args.concurrency)

    router_names = args.routers.split(",")
    if "frontier" not in router_names:
        router_names.insert(0, "frontier")
    outcomes: dict[str, list[Outcome]] = {}
    # Jev always makes real (cached) calls, even when generation is simulated.
    jev_reason = jev_unavailable_reason(registry, config)
    for name in router_names:
        if name.startswith("jev") and jev_reason:
            print(f"Skipping {name}: {jev_reason}", file=sys.stderr)
            continue
        router = build_router(name, registry, config, seed=args.seed, cache_dir=cache)
        print(f"Routing with {name}...", file=sys.stderr)
        outcomes[name] = await run_router(router, tasks, registry, matrix, args.concurrency)
        await router.aclose()
    outcomes["oracle"] = oracle(tasks, models, matrix, frontier_id)
    await pool.aclose()

    base = summarize(outcomes["frontier"])
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "simulated": args.simulate,
        "tasks": len(tasks),
        "candidates": [m.id for m in models],
        "baseline": frontier_id,
        "routing_config": config.model_dump(),
        "routers": {},
        "matrix": {f"{t}|{m}": asdict(c) for (t, m), c in matrix.items()},
        "per_model": {
            m.id: {
                "quality": sum(matrix[(t["id"], m.id)].score for t in tasks) / len(tasks),
                "success_rate": sum(matrix[(t["id"], m.id)].success for t in tasks) / len(tasks),
                "cost": sum(matrix[(t["id"], m.id)].cost for t in tasks),
                "errors": sum(not matrix[(t["id"], m.id)].ok for t in tasks),
            }
            for m in models
        },
    }
    for name, outs in outcomes.items():
        summary = summarize(outs)
        report["routers"][name] = {
            "summary": summary,
            "vs_baseline": compare(summary, base),
            "by_category": by_category(outs),
            "calibration": calibration(outs) if name.startswith("jev") else None,
            "outcomes": [asdict(o) for o in outs],
        }

    print_report(report, focus=[n for n in router_names if n.startswith("jev")])
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = RESULTS_DIR / f"report-{stamp}{'-simulated' if args.simulate else ''}.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nFull report: {out}", file=sys.stderr)
    return 0


def cli() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--routers", default="frontier,jev-choice,jev-profile,jev-sufficiency,rules,random,cheapest")
    p.add_argument("--simulate", action="store_true", help="offline mock models; numbers are NOT real")
    p.add_argument("--no-exec", action="store_true", help="skip tasks that execute model-generated code")
    p.add_argument("--categories", help="comma-separated category filter")
    p.add_argument("--limit", type=int)
    p.add_argument("--concurrency", type=int, default=6)
    p.add_argument("--seed", type=int, default=0)
    sys.exit(asyncio.run(main(p.parse_args())))


if __name__ == "__main__":
    cli()
