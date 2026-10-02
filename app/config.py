"""Loads configuration from config/*.yaml and environment variables (.env supported)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(os.environ.get("ROUTER_CONFIG_DIR", ROOT / "config"))


class ModeWeights(BaseModel):
    quality_weight: float = Field(ge=0)
    cost_weight: float = Field(ge=0)
    latency_weight: float = Field(ge=0)
    risk_weight: float = Field(ge=0)
    min_success: float = Field(ge=0, le=1)


class SuccessModel(BaseModel):
    steepness: float = Field(gt=0)
    bias: float


class ConfidencePolicy(BaseModel):
    execute_threshold: float = Field(ge=0, le=1)
    safer_threshold: float = Field(ge=0, le=1)


class JevConfig(BaseModel):
    decision: str = Field(pattern="^(profile|sufficiency)$")
    selector_model: str
    timeout_s: float = 20
    max_state_chars: int = Field(default=6000, gt=0)
    # Token estimate for each output-length level Jev can return (shortest first).
    output_tokens_by_level: list[int] = Field(min_length=4, max_length=4)
    # Plain-language description of each tier, used in Jev's "is this model sufficient?" questions.
    # Order is from least to most capable.
    tier_descriptions: dict[str, str]


class RulesConfig(BaseModel):
    default_tier: str
    task_type_tiers: dict[str, str]


class FallbackConfig(BaseModel):
    max_attempts: int = Field(ge=1)
    request_timeout_s: float = Field(gt=0)
    max_cost_per_request: float = Field(gt=0)


class RoutingConfig(BaseModel):
    modes: dict[str, ModeWeights]
    success_model: SuccessModel
    confidence: ConfidencePolicy
    jev: JevConfig
    rules: RulesConfig
    fallback: FallbackConfig


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env loader; real environment variables take precedence."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_routing_config(path: Path | None = None) -> RoutingConfig:
    path = path or CONFIG_DIR / "routing.yaml"
    return RoutingConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@lru_cache
def settings() -> dict[str, str]:
    load_dotenv()
    return {
        "log_path": os.environ.get("ROUTER_LOG_PATH", str(ROOT / "data" / "requests.jsonl")),
        "store_prompts": os.environ.get("ROUTER_STORE_PROMPTS", "false"),
    }
