"""Typed data contracts shared by the registry, routers, providers and telemetry."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Score = float  # 0.0 - 1.0

SKILL_DIMENSIONS = ("reasoning", "coding", "writing", "knowledge", "instruction_following")


class TaskType(str, Enum):
    conversation = "conversation"
    translation = "translation"
    summarization = "summarization"
    extraction = "extraction"
    classification = "classification"
    writing = "writing"
    reasoning = "reasoning"
    math = "math"
    coding = "coding"
    debugging = "debugging"
    document_analysis = "document_analysis"
    multimodal_analysis = "multimodal_analysis"
    planning = "planning"
    tool_use = "tool_use"
    analysis = "analysis"


Tier = Literal["cheap", "mid", "strong", "frontier"]
TIER_ORDER: dict[str, int] = {"cheap": 0, "mid": 1, "strong": 2, "frontier": 3}


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


class Skills(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: Score = Field(ge=0, le=1)
    coding: Score = Field(ge=0, le=1)
    writing: Score = Field(ge=0, le=1)
    knowledge: Score = Field(ge=0, le=1)
    instruction_following: Score = Field(ge=0, le=1)


class Features(BaseModel):
    vision: bool = False
    tools: bool = False


class Pricing(BaseModel):
    input_per_million: float = Field(ge=0)
    output_per_million: float = Field(ge=0)

    def cost(self, input_tokens: int, output_tokens: int) -> tuple[float, float]:
        return (
            input_tokens * self.input_per_million / 1_000_000,
            output_tokens * self.output_per_million / 1_000_000,
        )


class Latency(BaseModel):
    ttft_ms: float = Field(ge=0)
    tokens_per_second: float = Field(gt=0)

    def estimate_ms(self, output_tokens: int) -> float:
        return self.ttft_ms + output_tokens / self.tokens_per_second * 1000


class Limits(BaseModel):
    context_window: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    vendor: str
    tier: Tier
    # Plain-language strengths and weaknesses; Jev reads this when choosing a model.
    description: str | None = None
    # Capability priors; required for candidates, unused for router-only models such as Jev.
    skills: Skills | None = None
    features: Features = Features()
    pricing: Pricing
    pricing_checked: date | None = None
    latency: Latency
    limits: Limits
    status: Literal["active", "disabled"] = "active"
    candidate: bool = True
    # Model id to send to the provider when it differs from the registry id.
    provider_model: str | None = None

    @model_validator(mode="after")
    def _candidates_need_skills(self) -> ModelSpec:
        if self.candidate and self.skills is None:
            raise ValueError(f"candidate model {self.id} needs skills")
        return self

    @property
    def api_model(self) -> str:
        return self.provider_model or self.id


class ProviderConfig(BaseModel):
    adapter: Literal["openai_compatible", "anthropic", "decisions", "mock"]
    base_url: str | None = None
    api_key_env: str | None = None


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #

Mode = Literal["auto", "cheapest", "fastest", "best"]


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class RouteRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    mode: Mode = "auto"
    needs_vision: bool = False
    needs_tools: bool = False
    allow_vendors: list[str] | None = None
    block_vendors: list[str] = Field(default_factory=list)
    max_output_tokens: int | None = None

    @classmethod
    def from_prompt(cls, prompt: str, **kwargs: object) -> RouteRequest:
        return cls(messages=[Message(role="user", content=prompt)], **kwargs)

    @property
    def prompt_text(self) -> str:
        return "\n\n".join(m.content for m in self.messages)


class TaskProfile(BaseModel):
    """What the task demands. Produced by a router (Jev, rules...), consumed by scoring."""

    task_type: TaskType
    reasoning: Score = Field(ge=0, le=1)
    coding: Score = Field(ge=0, le=1)
    writing: Score = Field(ge=0, le=1)
    knowledge: Score = Field(ge=0, le=1)
    precision: Score = Field(ge=0, le=1)
    expected_output_tokens: int = Field(default=400, ge=1, le=200_000)


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost


class CandidateScore(BaseModel):
    model_id: str
    p_success: float
    est_cost: float
    est_latency_ms: float
    utility: float


class RouteDecision(BaseModel):
    router: str
    model_id: str
    confidence: float = Field(ge=0, le=1)
    profile: TaskProfile | None = None
    reason: str
    # Ordered models to try if the chosen one fails (excludes model_id).
    fallbacks: list[str] = Field(default_factory=list)
    scores: list[CandidateScore] = Field(default_factory=list)
    escalated: bool = False
    # Cost and latency of making the decision itself.
    router_model: str | None = None
    router_usage: Usage = Usage()
    router_latency_ms: float = 0.0
    router_error: str | None = None


# --------------------------------------------------------------------------- #
# Execution
# --------------------------------------------------------------------------- #


class GenerationResult(BaseModel):
    model_id: str
    text: str
    usage: Usage
    latency_ms: float
    finish_reason: str | None = None


class ExecutionResult(BaseModel):
    decision: RouteDecision
    result: GenerationResult | None
    attempts: list[str]
    errors: list[str] = Field(default_factory=list)

    @property
    def fallback_used(self) -> bool:
        return len(self.attempts) > 1

    @property
    def ok(self) -> bool:
        return self.result is not None
