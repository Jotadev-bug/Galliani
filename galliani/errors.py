"""Structured errors shared by the runtime. Every error carries a stable code and a safe summary."""

from __future__ import annotations


class GallianiError(Exception):
    code = "galliani_error"
    retryable = False

    def __init__(self, safe_summary: str, *, code: str | None = None, retryable: bool | None = None):
        super().__init__(safe_summary)
        self.safe_summary = safe_summary
        if code is not None:
            self.code = code
        if retryable is not None:
            self.retryable = retryable


class ContractError(GallianiError):
    """A component broke a data contract (spec 002 error handling)."""

    code = "contract_error"


class InvalidTransition(ContractError):
    code = "invalid_transition"


class TaskNotFound(GallianiError):
    code = "not_found"


class ConcurrencyConflict(GallianiError):
    """The state was patched by someone else since it was read (optimistic concurrency)."""

    code = "conflict"
    retryable = True
