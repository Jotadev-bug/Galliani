"""Shared redaction: drops hidden reasoning and masks secrets before anything is stored or shown.

Used by Task State (002 security), observability (011 R4-R5) and provider adapters (000 privacy boundary).
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

REDACTED = "[redacted]"

# Field names whose values are hidden reasoning. They are dropped, never shown or persisted.
HIDDEN_REASONING_KEYS = frozenset({
    "reasoning",
    "reasoning_content",
    "reasoning_details",
    "chain_of_thought",
    "thinking",
    "thoughts",
    "scratchpad",
    "hidden_reasoning",
    "redacted_thinking",
})


class RedactionPolicy(BaseModel):
    """Spec 011 `RedactionPolicy`: field_patterns, sensitivity_labels, action."""

    # Matched against whole key names, so ordinary keys such as `input_tokens` are left alone.
    field_patterns: list[str] = Field(default_factory=lambda: [
        r"^(x[_-])?api[_-]?key$", r".*secret.*", r".*passw(or)?d.*", r"^((access|refresh|auth|bearer|session|id)[_-]?)?token$",
        r"^authorization$", r"^credentials?$", r".*private[_-]?key.*", r"^(set[_-])?cookie$",
    ])
    value_patterns: list[str] = Field(default_factory=lambda: [
        r"sk-[A-Za-z0-9_\-]{16,}",
        r"(?i:bearer)\s+[A-Za-z0-9._\-]{16,}",
        r"AKIA[0-9A-Z]{16}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    ])
    sensitivity_labels: list[str] = Field(default_factory=lambda: ["sensitive"])
    action: str = "redact"

    def _field_re(self) -> re.Pattern[str]:
        return re.compile("|".join(f"(?:{p})" for p in self.field_patterns), re.IGNORECASE)
    def _value_re(self) -> re.Pattern[str]:
        return re.compile("|".join(f"(?:{p})" for p in self.value_patterns))


DEFAULT_POLICY = RedactionPolicy()


def redact_text(text: str, policy: RedactionPolicy = DEFAULT_POLICY) -> str:
    return policy._value_re().sub(REDACTED, text)


def contains_secret(value: Any, policy: RedactionPolicy = DEFAULT_POLICY) -> bool:
    return redact(value, policy) != _plain(value)


def redact(value: Any, policy: RedactionPolicy = DEFAULT_POLICY, diagnostics: list[str] | None = None) -> Any:
    """Return a JSON-safe copy with hidden reasoning dropped and secrets masked.

    A field that cannot be processed is dropped and a safe diagnostic is appended (011 error handling).
    """
    field_re, value_re = policy._field_re(), policy._value_re()

    def walk(v: Any, path: str) -> Any:
        if isinstance(v, BaseModel):
            v = v.model_dump(mode="json")
        if isinstance(v, dict):
            out: dict[str, Any] = {}
            for k, item in v.items():
                key = str(k)
                if key.lower() in HIDDEN_REASONING_KEYS:
                    continue
                if field_re.fullmatch(key):
                    out[key] = REDACTED
                    continue
                try:
                    out[key] = walk(item, f"{path}.{key}")
                except Exception:  # noqa: BLE001 - redaction failure drops the field
                    if diagnostics is not None:
                        diagnostics.append(f"dropped unredactable field {path}.{key}")
            return out
        if isinstance(v, (list, tuple, set, frozenset)):
            return [walk(item, f"{path}[]") for item in v]
        if isinstance(v, str):
            return value_re.sub(REDACTED, v)
        if v is None or isinstance(v, (bool, int, float)):
            return v
        return value_re.sub(REDACTED, str(v))

    return walk(value, "$")


def _plain(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)
