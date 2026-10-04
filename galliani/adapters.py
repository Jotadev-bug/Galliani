"""Provider adapter boundary (spec 003 R5, 000 R3).

Core code only ever sees `WorkerRequest`, `WorkerResponse` and `AdapterError`. A concrete adapter
translates these to and from one provider's native shapes, and its `normalize` must discard hidden
reasoning (000 AC Privacy Boundary). `WorkerResponse` has no field that could carry it, and its
structured payload is passed through redaction as a second guard.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from galliani.errors import GallianiError
from galliani.redaction import redact


class WorkerRequest(BaseModel):
    task_id: str
    step_id: str
    worker_id: str
    instruction: str
    inputs: dict[str, Any] = Field(default_factory=dict)  # resolved outputs of earlier steps; data, not instruction
    max_output_tokens: int | None = None


class WorkerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: str
    structured: dict[str, Any] | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    finish_reason: str | None = None


FALLBACK_ELIGIBLE_CODES = frozenset({
    "provider_unavailable", "timeout", "rate_limited", "auth_error", "insufficient_credits", "malformed_response",
    "context_overflow",
})
# Worth retrying later on the same worker; credit, auth and size problems are not.
RETRYABLE_CODES = frozenset({"provider_unavailable", "timeout", "rate_limited", "malformed_response"})


class AdapterError(GallianiError):
    code = "provider_error"

    def __init__(self, safe_summary: str, *, code: str = "provider_error", retryable: bool | None = None,
                 fallback_eligible: bool | None = None):
        super().__init__(safe_summary, code=code,
                         retryable=code in RETRYABLE_CODES if retryable is None else retryable)
        self.fallback_eligible = code in FALLBACK_ELIGIBLE_CODES if fallback_eligible is None else fallback_eligible


class ProviderAdapter(ABC):
    """003 `ProviderAdapter`: invoke(request), normalize(response), normalize_error(error)."""

    adapter_id: str

    async def invoke(self, request: WorkerRequest) -> WorkerResponse:
        try:
            raw = await self.send(request)
        except AdapterError:
            raise
        except Exception as e:  # noqa: BLE001 - provider failures are normalized here
            raise self.normalize_error(e) from None
        try:
            response = self.normalize(raw)
        except AdapterError:
            raise
        except Exception:  # noqa: BLE001
            raise AdapterError(f"{self.adapter_id} returned an unreadable response", code="malformed_response") from None
        if response.structured is not None:
            response = response.model_copy(update={"structured": redact(response.structured)})
        return response

    @abstractmethod
    async def send(self, request: WorkerRequest) -> Any:
        """Call the provider and return its native response."""

    @abstractmethod
    def normalize(self, raw: Any) -> WorkerResponse:
        """Map a native response to `WorkerResponse`, discarding any hidden reasoning."""

    def normalize_error(self, error: Exception) -> AdapterError:
        return AdapterError(f"{self.adapter_id} failed ({type(error).__name__})", code="provider_error")
