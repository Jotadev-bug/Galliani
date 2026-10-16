"""Shared redaction: drops hidden reasoning and masks secrets before anything is stored or shown.

Used by Task State (002 security), observability (011 R4-R5) and provider adapters (000 privacy boundary).
"""

from __future__ import annotations

import functools
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

# Left boundary for `sk-` and Stripe keys (spec 012 Security, Decision 0032). Not after an ASCII letter or
# digit, so words ending in "sk"/"rk" ("task-runner-...", "network_test_...") are not keys, except directly
# after an escape, where a real key still starts: a URL escape `%XX` or double-encoded `%25XX`, a string
# escape `\n \r \t \f \v \b \0`, a hex escape `\xNN`, a Unicode escape `\uXXXX`, or an ANSI colour code (SGR,
# `ESC[...m`, parameters separated by `;` or `:`) whose ESC is the raw character or is written `\x1b`,
# `\033`, `\u001b` or `\e` (hex digits in either case). Python's lookbehinds are fixed-width, so the SGR one
# is listed per parameter length, up to 24 characters (`1;38;2;255;255;255` is 18); a longer one is not a
# boundary. Accepted trade-off: a key glued to a letter or digit is not masked.
_SGR_ESCAPES = (r"\x1b", r"\\(?:x1[bB]|033)", r"\\u001[bB]", r"\\e")  # each alternative group has one width
_LEFT_BOUNDARY = "(?:" + "|".join([
    r"(?<![A-Za-z0-9])", r"(?<=%[0-9A-Fa-f]{2})", r"(?<=%25[0-9A-Fa-f]{2})", r"(?<=\\[nrtfvb0])",
    r"(?<=\\x[0-9A-Fa-f]{2})", r"(?<=\\u[0-9A-Fa-f]{4})",
    *(rf"(?<={esc}\[[0-9;:]{{{n}}}m)" for esc in _SGR_ESCAPES for n in range(25)),
]) + ")"


class RedactionPolicy(BaseModel):
    """Spec 011 `RedactionPolicy`: field_patterns, sensitivity_labels, action."""

    # Matched against whole key names, so ordinary keys such as `input_tokens` are left alone.
    field_patterns: list[str] = Field(default_factory=lambda: [
        r"^(x[_-])?api[_-]?key$", r".*secret.*", r".*passw(or)?d.*", r"^((access|refresh|auth|bearer|session|id)[_-]?)?token$",
        r"^authorization$", r"^credentials?$", r".*private[_-]?key.*", r"^(set[_-])?cookie$",
    ])
    value_patterns: list[str] = Field(default_factory=lambda: [
        # The lookahead comes first, so the left boundary's lookbehinds run only where a key could start.
        rf"(?=sk-){_LEFT_BOUNDARY}sk-[A-Za-z0-9_\-]{{16,}}",
        r"(?i:bearer)\s+[A-Za-z0-9._\-]{16,}",
        r"AKIA[0-9A-Z]{16}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        # SEC-11: common service token formats (GitHub, Google, Slack, GitLab, Stripe live and test keys).
        r"gh[pousr]_[A-Za-z0-9]{36,}",
        r"github_pat_[A-Za-z0-9_]{22,}",
        r"AIza[0-9A-Za-z_\-]{35}",
        r"xox[abprs]-[A-Za-z0-9-]{10,}",
        r"glpat-[A-Za-z0-9_\-]{20,}",
        rf"(?=[sr]k_){_LEFT_BOUNDARY}[sr]k_(?:live|test)_[A-Za-z0-9]{{16,}}",  # same left boundary as sk-
    ])
    sensitivity_labels: list[str] = Field(default_factory=lambda: ["sensitive"])
    action: str = "redact"

    def _field_re(self) -> re.Pattern[str]:
        return _joined(tuple(self.field_patterns), re.IGNORECASE)

    def _value_re(self) -> re.Pattern[str]:
        return _joined(tuple(self.value_patterns), 0)


@functools.lru_cache(maxsize=64)
def _joined(patterns: tuple[str, ...], flags: int) -> re.Pattern[str]:
    """One compiled alternation per pattern list, cached: keyed by the patterns, so editing a policy's
    lists takes effect on the next call."""
    return re.compile("|".join(f"(?:{p})" for p in patterns), flags)


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
