"""Client for the OpenRouter Decisions API (System One models such as TypeSafe's Jev).

Unlike chat models, a decision model does not generate text: it answers typed questions
(Choice, Score, Noul) about a `state` and returns probabilities.
https://openrouter.ai/docs/guides/community/jev-tutorial
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.providers.base import ProviderError, ProviderOutage, ProviderTimeout, classify_http_error


class NoulQuestion(BaseModel):
    type: Literal["noul"] = "noul"
    instructions: str
    criteria: dict[str, str] | None = None  # {"true": ..., "false": ...}


class ChoiceQuestion(BaseModel):
    type: Literal["choice"] = "choice"
    instructions: str
    criteria: dict[str, str]


class ScoreQuestion(BaseModel):
    type: Literal["score"] = "score"
    instructions: str
    criteria: list[str] = Field(min_length=1)  # ordered levels, index 0 first


Question = NoulQuestion | ChoiceQuestion | ScoreQuestion


class Answer(BaseModel):
    type: Literal["noul", "choice", "score"]
    noul: float | None = None
    choice: str | None = None
    score: float | None = None
    confidence: float | None = None
    probabilities: dict[str, float] | None = None


class DecisionUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float | None = None


class DecisionResult(BaseModel):
    model: str
    answers: dict[str, Answer]
    usage: DecisionUsage
    latency_ms: float = 0.0


class DecisionsClient:
    name = "decisions"

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        client: httpx.AsyncClient | None = None,
        cache_dir: str | Path | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = client or httpx.AsyncClient()
        self.cache_dir = Path(cache_dir) if cache_dir else None

    async def decide(
        self, model: str, state: Any, questions: dict[str, Question], timeout_s: float = 20
    ) -> DecisionResult:
        payload = {
            "model": model,
            "state": state,
            "questions": {k: q.model_dump(exclude_none=True) for k, q in questions.items()},
        }
        cache_path = self._cache_path(payload)
        if cache_path and cache_path.exists():
            return DecisionResult.model_validate_json(cache_path.read_text(encoding="utf-8"))

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        start = time.perf_counter()
        try:
            resp = await self._client.post(f"{self.base_url}/decisions", json=payload, headers=headers, timeout=timeout_s)
        except httpx.TimeoutException as e:
            raise ProviderTimeout(f"decisions: timeout after {timeout_s}s") from e
        except httpx.HTTPError as e:
            raise ProviderOutage(f"decisions: {e!r}") from e
        latency_ms = (time.perf_counter() - start) * 1000
        if resp.status_code != 200:
            raise classify_http_error(resp.status_code, resp.text)

        data = resp.json()
        try:
            result = DecisionResult.model_validate({**data, "latency_ms": latency_ms})
        except ValueError as e:
            raise ProviderError(f"decisions: malformed response: {str(data)[:300]}") from e
        missing = set(questions) - set(result.answers)
        if missing:
            raise ProviderError(f"decisions: response is missing answers for {sorted(missing)}")
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(result.model_dump_json(), encoding="utf-8")
        return result

    def _cache_path(self, payload: dict) -> Path | None:
        if not self.cache_dir:
            return None
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
        return self.cache_dir / "decisions" / f"{digest}.json"

    async def aclose(self) -> None:
        await self._client.aclose()
