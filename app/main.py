"""CLI entry point: route and run a single prompt.

    python -m app.main "Translate 'good morning' into French"
    python -m app.main --router rules --mode cheapest "..."
    python -m app.main --route-only "..."      # show Jev's decision without generating (costs ~$0.00004)
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.models.schemas import RouteRequest
from app.providers.base import estimate_tokens
from app.service import ROUTER_NAMES, RouterService


async def _main(args: argparse.Namespace) -> int:
    service = RouterService.from_config(args.router)
    request = RouteRequest.from_prompt(args.prompt, mode=args.mode)
    try:
        if args.route_only:
            candidates = service.registry.candidates(request, input_tokens=estimate_tokens(args.prompt))
            d = await service.router.route(request, candidates)
            if args.json:
                print(d.model_dump_json(indent=2))
                return 0
            print(f"Selected:    {d.model_id}")
            print(f"Confidence:  {d.confidence:.0%}" + ("  (escalated)" if d.escalated else ""))
            print(f"Why:         {d.reason}")
            if d.router_error:
                print(f"Router error: {d.router_error}")
            print(f"Routing:     ${d.router_usage.total_cost:.6f}, {d.router_latency_ms:.0f} ms")
            if d.scores:
                print("\nOptions (router score, estimated cost of this request):")
                for s in d.scores:
                    mark = "->" if s.model_id == d.model_id else "  "
                    print(f"  {mark} {s.model_id:<32} {s.p_success:>5.2f}   ${s.est_cost:.5f}")
            return 0
        ex = await service.run(request)
    finally:
        await service.aclose()

    d = ex.decision
    if ex.result:
        print(ex.result.text)
        print("\n" + "-" * 50, file=sys.stderr)
        print(f"Auto-selected:      {ex.result.model_id}", file=sys.stderr)
        print(f"Cost:               ${ex.result.usage.total_cost + d.router_usage.total_cost:.6f}"
              f" (routing ${d.router_usage.total_cost:.6f})", file=sys.stderr)
        print(f"Routing confidence: {d.confidence:.0%}", file=sys.stderr)
        print(f"Why:                {d.reason}", file=sys.stderr)
        if ex.fallback_used:
            print(f"Fallbacks:          {' -> '.join(ex.attempts)}", file=sys.stderr)
        return 0
    print("All models failed:\n  " + "\n  ".join(ex.errors), file=sys.stderr)
    return 1


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt")
    p.add_argument("--router", default="jev", choices=ROUTER_NAMES)
    p.add_argument("--mode", default="auto", choices=["auto", "cheapest", "fastest", "best"])
    p.add_argument("--route-only", action="store_true", help="show the routing decision without generating")
    p.add_argument("--json", action="store_true", help="with --route-only, print the raw decision as JSON")
    sys.exit(asyncio.run(_main(p.parse_args())))


if __name__ == "__main__":
    main()
