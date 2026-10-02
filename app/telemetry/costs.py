"""Per-request cost/latency records (PROJECT.md section 14). Prompts are not stored by default."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from app.models.schemas import ExecutionResult, RouteRequest


class RequestRecord(BaseModel):
    request_id: str
    user_id: str | None
    timestamp: str
    mode: str
    router: str
    router_model: str | None
    router_cost: float
    routing_latency_ms: float
    confidence: float
    selected_model: str | None
    selected_provider: str | None
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    generation_latency_ms: float
    status: str
    fallback_used: bool
    attempts: list[str]
    errors: list[str]
    prompt_sha256: str
    prompt: str | None = None


def build_record(
    request: RouteRequest,
    execution: ExecutionResult,
    *,
    provider: str | None,
    user_id: str | None = None,
    store_prompt: bool = False,
) -> RequestRecord:
    d, r = execution.decision, execution.result
    text = request.prompt_text
    return RequestRecord(
        request_id=str(uuid.uuid4()),
        user_id=user_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        mode=request.mode,
        router=d.router,
        router_model=d.router_model,
        router_cost=d.router_usage.total_cost,
        routing_latency_ms=d.router_latency_ms,
        confidence=d.confidence,
        selected_model=r.model_id if r else None,
        selected_provider=provider if r else None,
        input_tokens=r.usage.input_tokens if r else 0,
        output_tokens=r.usage.output_tokens if r else 0,
        input_cost=r.usage.input_cost if r else 0.0,
        output_cost=r.usage.output_cost if r else 0.0,
        total_cost=(r.usage.total_cost if r else 0.0) + d.router_usage.total_cost,
        generation_latency_ms=r.latency_ms if r else 0.0,
        status="ok" if r else "failed",
        fallback_used=execution.fallback_used,
        attempts=execution.attempts,
        errors=execution.errors,
        prompt_sha256=hashlib.sha256(text.encode()).hexdigest(),
        prompt=text if store_prompt else None,
    )


class JsonlSink:
    """Append-only JSONL log. A PostgreSQL sink can implement the same `write` method later."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: RequestRecord) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")
