"""Refresh registry prices from OpenRouter's public model list (no API key needed).

    python -m scripts.sync_pricing           # show differences
    python -m scripts.sync_pricing --write   # update config/models.yaml in place

Only models whose provider is `openrouter` are updated; the line-level edit keeps comments intact.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date

import httpx

from app.config import CONFIG_DIR
from app.models.registry import ModelRegistry

MODELS_URL = "https://openrouter.ai/api/v1/models"


def fetch_prices() -> dict[str, tuple[float, float, int]]:
    data = httpx.get(MODELS_URL, timeout=30).json()["data"]
    return {
        m["id"]: (
            round(float(m["pricing"]["prompt"]) * 1_000_000, 6),
            round(float(m["pricing"]["completion"]) * 1_000_000, 6),
            int(m.get("context_length") or 0),
        )
        for m in data
    }


def fetch_endpoint_price(model_id: str) -> tuple[float, float, int] | None:
    """Models outside the main list (e.g. decision models such as Jev) via the endpoints API."""
    resp = httpx.get(f"https://openrouter.ai/api/v1/models/{model_id}/endpoints", timeout=30)
    if resp.status_code != 200:
        return None
    endpoints = resp.json()["data"].get("endpoints") or []
    if not endpoints:
        return None
    e = endpoints[0]
    return (
        round(float(e["pricing"]["prompt"]) * 1_000_000, 6),
        round(float(e["pricing"]["completion"]) * 1_000_000, 6),
        int(e.get("context_length") or 0),
    )


def fmt(x: float) -> str:
    return f"{x:g}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    args = p.parse_args()

    path = CONFIG_DIR / "models.yaml"
    registry = ModelRegistry.from_yaml(path)
    live = fetch_prices()
    text = path.read_text(encoding="utf-8")
    today = date.today().isoformat()
    changed = 0

    for m in registry.all():
        if not (registry.providers[m.provider].base_url or "").startswith("https://openrouter.ai/api"):
            continue
        price = live.get(m.api_model) or fetch_endpoint_price(m.api_model)
        if price is None:
            print(f"!! {m.id}: not found on OpenRouter (renamed or retired?)", file=sys.stderr)
            continue
        inp, out, _ctx = price
        old = (m.pricing.input_per_million, m.pricing.output_per_million)
        status = "ok" if old == (inp, out) else f"CHANGED {old} -> {(inp, out)}"
        print(f"{m.id:<40} in ${fmt(inp)}/M  out ${fmt(out)}/M  {status}")
        block = re.compile(rf"(- id: {re.escape(m.id)}\n(?:(?!\n  - id:).)*?)"
                           r"pricing: \{[^}]*\}\n(\s*)pricing_checked: [\d-]+", re.DOTALL)
        text, n = block.subn(
            lambda mt: f"{mt.group(1)}pricing: {{input_per_million: {fmt(inp)}, output_per_million: {fmt(out)}}}\n"
                       f"{mt.group(2)}pricing_checked: {today}",
            text, count=1,
        )
        changed += n

    if args.write:
        path.write_text(text, encoding="utf-8")
        ModelRegistry.from_yaml(path)  # validate the result
        print(f"\nUpdated {changed} entries in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
