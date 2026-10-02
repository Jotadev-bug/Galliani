"""Routing-only evaluation: does Jev pick a sensible model? No answers are generated.

Every case carries `min_tier`, the cheapest tier expected to handle it reliably (an author label).
A router's pick is judged by its tier:

    correct       min_tier or one tier above
    underpowered  below min_tier: the answer is likely to be wrong
    overspend     two or more tiers above min_tier: paying for capability the task does not need

Only the Jev decision model is called (about $0.0001 per prompt). All Jev styles share one cached
call per prompt, so re-runs are free.

    python -m benchmarks.routing_eval
    python -m benchmarks.routing_eval --cases benchmarks/routing_cases.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml

from app.config import CONFIG_DIR, load_dotenv, load_routing_config
from app.models.registry import ModelRegistry
from app.models.schemas import TIER_ORDER, ModelSpec, RouteDecision, RouteRequest
from app.providers.base import estimate_tokens
from app.router.policies import most_capable
from app.service import build_router, jev_unavailable_reason

BENCH_DIR = Path(__file__).resolve().parent
DEFAULT_CASES = [BENCH_DIR / "tasks.yaml", BENCH_DIR / "routing_cases.yaml"]
ROUTERS = ["jev-choice", "jev-choice-raw", "jev-profile", "jev-sufficiency", "rules"]
DEFAULT_OUTPUT_TOKENS = 500


def load_cases(paths: list[Path]) -> list[dict]:
    cases = []
    for path in paths:
        for c in yaml.safe_load(path.read_text(encoding="utf-8")):
            if "min_tier" in c:
                cases.append({"id": c["id"], "min_tier": c["min_tier"], "prompt": c["prompt"],
                              "source": path.name})
    return cases


def verdict(model: ModelSpec, min_tier: str) -> str:
    gap = TIER_ORDER[model.tier] - TIER_ORDER[min_tier]
    return "underpowered" if gap < 0 else "overspend" if gap >= 2 else "correct"


def est_cost(model: ModelSpec, prompt: str, output_tokens: int) -> float:
    return sum(model.pricing.cost(estimate_tokens(prompt), output_tokens))


def label_ideal(candidates: list[ModelSpec], min_tier: str) -> ModelSpec:
    """Cheapest model at the labelled tier (or the nearest tier above)."""
    eligible = [m for m in candidates if TIER_ORDER[m.tier] >= TIER_ORDER[min_tier]]
    lowest = min(TIER_ORDER[m.tier] for m in eligible)
    return min((m for m in eligible if TIER_ORDER[m.tier] == lowest),
               key=lambda m: m.pricing.input_per_million + m.pricing.output_per_million)


async def evaluate(cases: list[dict], routers: list[str], concurrency: int) -> dict:
    registry = ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
    config = load_routing_config()
    cache = BENCH_DIR / "results" / "cache"
    built = {name: build_router(name, registry, config, cache_dir=cache) for name in routers}
    sem = asyncio.Semaphore(concurrency)

    async def one(case: dict) -> dict:
        request = RouteRequest.from_prompt(case["prompt"])
        candidates = registry.candidates(request, input_tokens=estimate_tokens(case["prompt"]))
        decisions: dict[str, RouteDecision] = {}
        for name, router in built.items():  # sequential per case: Jev styles reuse the cached call
            async with sem:
                decisions[name] = await router.route(request, candidates)
        jev = next((d for d in decisions.values() if d.profile), None)
        out_tokens = jev.profile.expected_output_tokens if jev else DEFAULT_OUTPUT_TOKENS
        ideal, top = label_ideal(candidates, case["min_tier"]), most_capable(candidates)
        row = {
            **case,
            "output_tokens": out_tokens,
            "task_type": jev.profile.task_type.value if jev else None,
            "ideal_model": ideal.id, "ideal_cost": est_cost(ideal, case["prompt"], out_tokens),
            "frontier_model": top.id, "frontier_cost": est_cost(top, case["prompt"], out_tokens),
            "routers": {},
        }
        for name, d in decisions.items():
            m = registry.get(d.model_id)
            row["routers"][name] = {
                "model": m.id, "tier": m.tier, "verdict": verdict(m, case["min_tier"]),
                "est_cost": est_cost(m, case["prompt"], out_tokens), "confidence": d.confidence,
                "escalated": d.escalated, "reason": d.reason, "error": d.router_error,
                "routing_cost": d.router_usage.total_cost, "routing_ms": d.router_latency_ms,
            }
        return row

    rows = await asyncio.gather(*(one(c) for c in cases))
    for r in built.values():
        await r.aclose()
    return {"timestamp": datetime.now().isoformat(), "routers": routers, "cases": rows}


def summarize(report: dict) -> dict:
    rows, out = report["cases"], {}
    frontier = sum(r["frontier_cost"] for r in rows)
    ideal = sum(r["ideal_cost"] for r in rows)
    for name in report["routers"]:
        picks = [r["routers"][name] for r in rows]
        v = Counter(p["verdict"] for p in picks)
        cost = sum(p["est_cost"] for p in picks)
        routing = sum(p["routing_cost"] for p in picks)
        out[name] = {
            "n": len(picks),
            "correct": v["correct"] / len(picks),
            "underpowered": v["underpowered"] / len(picks),
            "overspend": v["overspend"] / len(picks),
            "est_cost": cost, "routing_cost": routing,
            "savings_vs_frontier": 1 - (cost + routing) / frontier if frontier else 0.0,
            "cost_vs_label_ideal": (cost + routing) / ideal if ideal else 0.0,
            "errors": sum(p["error"] is not None for p in picks),
            "escalated": sum(p["escalated"] for p in picks) / len(picks),
            "mean_routing_ms": sum(p["routing_ms"] for p in picks) / len(picks),
            "models": dict(Counter(p["model"].split("/")[-1] for p in picks).most_common()),
        }
    out["_baselines"] = {"frontier_cost": frontier, "label_ideal_cost": ideal}
    return out


def print_report(report: dict, summary: dict, detail: list[str]) -> None:
    line = "=" * 92
    rows = report["cases"]
    b = summary["_baselines"]
    print(line)
    print(f"JEV ROUTING EVALUATION  -  {len(rows)} prompts, no answers generated (estimated costs)")
    print(line)
    print(f"Always-{rows[0]['frontier_model'].split('/')[-1]}: ${b['frontier_cost']:.4f}    "
          f"Label-ideal (cheapest model at each labelled tier): ${b['label_ideal_cost']:.4f}\n")
    print(f"{'router':<17}{'correct':>9}{'under':>8}{'over':>8}{'est. cost':>11}{'vs ideal':>10}"
          f"{'savings':>9}{'escal.':>8}{'errors':>8}")
    for name in report["routers"]:
        s = summary[name]
        print(f"{name:<17}{s['correct'] * 100:>8.0f}%{s['underpowered'] * 100:>7.0f}%{s['overspend'] * 100:>7.0f}%"
              f"{s['est_cost'] + s['routing_cost']:>11.4f}{s['cost_vs_label_ideal']:>9.1f}x"
              f"{s['savings_vs_frontier'] * 100:>8.0f}%{s['escalated'] * 100:>7.0f}%{s['errors']:>8}")
    jev = next((summary[n] for n in report["routers"] if n.startswith("jev")), None)
    if jev:
        print(f"\nJev cost: ${jev['routing_cost']:.5f} total, {jev['mean_routing_ms']:.0f} ms mean per call "
              f"(0 ms means served from cache)")

    for name in detail:
        print(f"\n{line}\n{name}: per-prompt picks\n{line}")
        print(f"{'case':<9}{'label':<9}{'picked':<24}{'tier':<9}{'verdict':<13}{'conf':>5}  prompt")
        for r in sorted(rows, key=lambda r: (r["routers"][name]["verdict"] == "correct", r["id"])):
            p = r["routers"][name]
            mark = "" if p["verdict"] == "correct" else " <-"
            prompt = r["prompt"].strip().replace("\n", " ")[:38]
            print(f"{r['id']:<9}{r['min_tier']:<9}{p['model'].split('/')[-1]:<24}{p['tier']:<9}"
                  f"{p['verdict'] + mark:<13}{p['confidence']:>5.2f}  {prompt}")
    print(line)


async def main(args: argparse.Namespace) -> int:
    load_dotenv()
    registry = ModelRegistry.from_yaml(CONFIG_DIR / "models.yaml")
    routers = args.routers.split(",")
    if any(r.startswith("jev") for r in routers) and (reason := jev_unavailable_reason(registry, load_routing_config())):
        print(f"Jev unavailable: {reason}", file=sys.stderr)
        return 2
    cases = load_cases([Path(p) for p in args.cases] if args.cases else DEFAULT_CASES)
    if args.limit:
        cases = cases[: args.limit]
    report = await evaluate(cases, routers, args.concurrency)
    summary = summarize(report)

    errors = max(summary[n]["errors"] for n in routers if n.startswith("jev")) if any(
        n.startswith("jev") for n in routers) else 0
    if errors > len(cases) * 0.05:
        sample = next(p["error"] for r in report["cases"] for p in r["routers"].values() if p["error"])
        print(f"\nABORTED: Jev failed on {errors}/{len(cases)} prompts, so its routers fell back to rules.\n"
              f"First error: {sample}", file=sys.stderr)
        return 3

    print_report(report, summary, args.detail.split(",") if args.detail else [])
    out = BENCH_DIR / "results" / f"routing-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**report, "summary": summary}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFull report: {out}", file=sys.stderr)
    return 0


def cli() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cases", nargs="*", help="YAML files with id, prompt, min_tier (default: tasks + routing_cases)")
    p.add_argument("--routers", default=",".join(ROUTERS))
    p.add_argument("--detail", default="jev-choice-raw", help="routers to list per prompt (comma-separated)")
    p.add_argument("--limit", type=int)
    p.add_argument("--concurrency", type=int, default=6)
    sys.exit(asyncio.run(main(p.parse_args())))


if __name__ == "__main__":
    cli()
