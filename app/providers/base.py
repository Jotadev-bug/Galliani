"""Common provider interface and the failure taxonomy used for fallbacks."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.schemas import GenerationResult, Message, ModelSpec


class ProviderError(Exception):
    """Base provider failure. `try_other_model` tells the executor whether a fallback can help."""

    kind = "provider_error"
    try_other_model = True

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


class ProviderTimeout(ProviderError):
    kind = "timeout"


class RateLimited(ProviderError):
    kind = "rate_limit"


class ProviderOutage(ProviderError):
    kind = "provider_outage"


class ModelUnavailable(ProviderError):
    kind = "model_unavailable"


class ContextOverflow(ProviderError):
    kind = "context_overflow"


class InvalidRequest(ProviderError):
    """The request itself is malformed; another model will not fix it."""

    kind = "invalid_request"
    try_other_model = False


class AuthError(ProviderError):
    """Missing or rejected credentials for this provider; another provider may still work."""

    kind = "auth_error"


def classify_http_error(status: int, body: str) -> ProviderError:
    text = body[:500]
    lowered = text.lower()
    if status == 429:
        return RateLimited(text, status=status)
    if status in (401, 403):
        return AuthError(text, status=status)
    if status == 404:
        return ModelUnavailable(text, status=status)
    if status in (400, 413, 422):
        if "context" in lowered or "too long" in lowered or ("maximum" in lowered and "token" in lowered):
            return ContextOverflow(text, status=status)
        return InvalidRequest(text, status=status)
    if status >= 500:
        return ProviderOutage(text, status=status)
    return ProviderError(text, status=status)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) used only for pre-flight checks."""
    return max(1, len(text) // 4)


class ModelProvider(ABC):
    name: str

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        model: ModelSpec,
        *,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        json_mode: bool = False,
        timeout_s: float = 120,
    ) -> GenerationResult:
        """Run one completion. Raises ProviderError subclasses on failure."""

    async def aclose(self) -> None:  # noqa: B027 - optional hook
        pass
